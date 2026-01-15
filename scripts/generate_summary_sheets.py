#!/usr/bin/env python3
"""
Generate summary sheets from database.

This script reads grade data from PostgreSQL and generates Google Sheets with:
1. Summary sheet: All students and assignments organized by category
2. Category sheets: Separate sheets for each category (Labs, Projects, etc.)
3. Assignment sheets: Individual sheets for each assignment with detailed scores

Usage:
    python scripts/generate_summary_sheets.py --config config/courses.json [--course-id cs10_fa25]
"""
import sys
import os
import argparse
import logging
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import json

from api.config_loader import load_config, list_courses, DEFAULT_SCOPES
from api.core.db import SessionLocal
from api.core.models import Course, Assignment, Student, Submission
from api.core.ingest import save_summary_sheet_to_db
from sqlalchemy import func

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def column_letter(n):
    """Convert column number (1-indexed) to Excel-style column letter (A, B, ..., Z, AA, AB, ...)."""
    result = ""
    while n > 0:
        n -= 1
        result = chr(65 + (n % 26)) + result
        n //= 26
    return result


def create_sheets_service():
    """Create Google Sheets API service."""
    credentials_json = os.getenv("SERVICE_ACCOUNT_CREDENTIALS")
    if not credentials_json:
        raise ValueError("SERVICE_ACCOUNT_CREDENTIALS not set in environment")
    
    # Parse JSON and handle escaped newlines in private_key
    credentials_dict = json.loads(credentials_json)
    
    # Fix private_key if it has literal \n instead of actual newlines
    if 'private_key' in credentials_dict:
        private_key = credentials_dict['private_key']
        # Replace literal \n with actual newlines if needed
        if '\\n' in private_key:
            credentials_dict['private_key'] = private_key.replace('\\n', '\n')
    
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=DEFAULT_SCOPES)
    return build('sheets', 'v4', credentials=credentials)


def get_course_data(course_gradescope_id):
    """
    Fetch all course data from database.
    
    Returns:
        dict: {
            "course": Course object,
            "assignments": [Assignment objects ordered by category],
            "students": [Student objects],
            "submissions": {(assignment_id, student_id): Submission}
        }
    """
    session = SessionLocal()
    try:
        # Get course
        course = session.query(Course).filter(
            Course.gradescope_course_id == course_gradescope_id
        ).first()
        
        if not course:
            raise ValueError(f"Course {course_gradescope_id} not found in database")
        
        # Get assignments
        assignments = session.query(Assignment).filter(
            Assignment.course_id == course.id
        ).all()
        
        # Sort by category and number
        assignments = sort_assignments_by_category(assignments)
        
        # Get students
        students = session.query(Student).order_by(Student.legal_name).all()
        
        # Get all submissions
        submissions = session.query(Submission).join(Assignment).filter(
            Assignment.course_id == course.id
        ).all()
        
        # Build lookup
        submission_lookup = {
            (sub.assignment_id, sub.student_id): sub 
            for sub in submissions
        }
        
        return {
            "course": course,
            "assignments": assignments,
            "students": students,
            "submissions": submission_lookup
        }
    finally:
        session.close()


def categorize_assignment(assignment_name):
    """Categorize assignment by name."""
    name_lower = assignment_name.lower()
    
    if 'lecture' in name_lower or 'quiz' in name_lower:
        return 'Quest'
    elif 'midterm' in name_lower:
        return 'Midterm'
    elif 'postterm' in name_lower or 'posterm' in name_lower:
        return 'Postterm'
    elif 'project' in name_lower:
        return 'Projects'
    elif 'lab' in name_lower:
        return 'Labs'
    elif 'discussion' in name_lower:
        return 'Discussions'
    else:
        return 'Other'


def sort_assignments_by_category(assignments):
    """Sort assignments by category priority and number."""
    import re
    
    def extract_number(title):
        numbers = re.findall(r"\d+", title or "")
        return int(numbers[0]) if numbers else 0
    
    category_order = {
        'Quest': 1,
        'Midterm': 2,
        'Postterm': 3,
        'Projects': 4,
        'Labs': 5,
        'Discussions': 6,
        'Other': 99
    }
    
    def get_sort_key(assignment):
        category = categorize_assignment(assignment.title)
        priority = category_order.get(category, 99)
        number = extract_number(assignment.title)
        return (priority, number, assignment.title)
    
    return sorted(assignments, key=get_sort_key)


def clear_sheet(service, spreadsheet_id, sheet_id):
    """Clear all content in a sheet."""
    request = {
        "requests": [{
            "updateCells": {
                "range": {"sheetId": sheet_id},
                "fields": "userEnteredValue"
            }
        }]
    }
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request
    ).execute()


def get_or_create_sheet(service, spreadsheet_id, sheet_name, index=None):
    """Get existing sheet ID or create new sheet."""
    # Get existing sheets
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = spreadsheet.get('sheets', [])
    
    for sheet in sheets:
        if sheet['properties']['title'] == sheet_name:
            sheet_id = sheet['properties']['sheetId']
            logger.info(f"Using existing sheet: {sheet_name} (ID: {sheet_id})")
            return sheet_id
    
    # Create new sheet
    request = {
        "requests": [{
            "addSheet": {
                "properties": {
                    "title": sheet_name,
                    "gridProperties": {
                        "frozenRowCount": 3,
                        "frozenColumnCount": 2
                    }
                }
            }
        }]
    }
    
    if index is not None:
        request["requests"][0]["addSheet"]["properties"]["index"] = index
    
    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request
    ).execute()
    
    sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
    logger.info(f"Created new sheet: {sheet_name} (ID: {sheet_id})")
    return sheet_id


def generate_summary_sheet(service, spreadsheet_id, course_data):
    """
    Generate main summary sheet with all assignments.
    
    Format:
    Row 1: Legal Name | Email | Assignment1 | Assignment2 | ...
    Row 2: CATEGORY | CATEGORY | Category1 | Category2 | ...
    Row 3: MAX POINTS | MAX POINTS | MaxPoints1 | MaxPoints2 | ...
    Row 4+: Student data
    """
    logger.info("Generating Summary sheet...")
    
    sheet_id = get_or_create_sheet(service, spreadsheet_id, "Summary", index=0)
    
    assignments = course_data["assignments"]
    students = course_data["students"]
    submissions = course_data["submissions"]
    
    # Build rows
    rows = []
    
    # Row 1: Headers
    row1 = ["Legal Name", "Email"] + [a.title for a in assignments]
    
    # Row 2: Categories
    row2 = ["CATEGORY", "CATEGORY"] + [categorize_assignment(a.title) for a in assignments]
    
    # Row 3: Max points
    row3 = ["MAX POINTS", "MAX POINTS"] + [float(a.max_points or 0) for a in assignments]
    
    rows.append(row1)
    rows.append(row2)
    rows.append(row3)
    
    # Student rows
    for student in students:
        row = [student.legal_name or "", student.email or ""]
        for assignment in assignments:
            sub = submissions.get((assignment.id, student.id))
            if sub and sub.total_score is not None:
                row.append(float(sub.total_score))
            else:
                row.append("")
        rows.append(row)
    
    # Calculate column range dynamically
    num_columns = 2 + len(assignments)  # Legal Name, Email + assignments
    end_column = column_letter(num_columns)
    
    # Update sheet
    range_name = f"Summary!A1:{end_column}{len(rows)}"
    body = {"values": rows}
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    
    logger.info(f"Summary sheet updated: {len(students)} students, {len(assignments)} assignments")


def generate_category_sheet(service, spreadsheet_id, category_name, category_assignments, course_data):
    """
    Generate sheet for a specific category.
    
    Format:
    Row 1: Legal Name | Email | Assignment1 | Assignment2 | ... | Average | Total
    Row 2: MAX POINTS | MAX POINTS | MaxPoints1 | MaxPoints2 | ... | - | -
    Row 3+: Student data with calculated averages
    """
    logger.info(f"Generating {category_name} sheet...")
    
    sheet_id = get_or_create_sheet(service, spreadsheet_id, category_name)
    
    students = course_data["students"]
    submissions = course_data["submissions"]
    
    # Build rows
    rows = []
    
    # Row 1: Headers
    row1 = ["Legal Name", "Email"] + [a.title for a in category_assignments] + ["Average", "Total"]
    
    # Row 2: Max points
    row2 = ["MAX POINTS", "MAX POINTS"] + [float(a.max_points or 0) for a in category_assignments] + ["-", "-"]
    
    rows.append(row1)
    rows.append(row2)
    
    # Student rows
    for student in students:
        row = [student.legal_name or "", student.email or ""]
        scores = []
        
        for assignment in category_assignments:
            sub = submissions.get((assignment.id, student.id))
            if sub and sub.total_score is not None:
                score = float(sub.total_score)
                row.append(score)
                scores.append(score)
            else:
                row.append("")
        
        # Calculate average and total
        if scores:
            average = sum(scores) / len(scores)
            total = sum(scores)
            row.append(round(average, 2))
            row.append(round(total, 2))
        else:
            row.append("")
            row.append("")
        
        rows.append(row)
    
    # Calculate column range dynamically
    num_columns = 2 + len(category_assignments) + 2  # Name, Email + assignments + Average, Total
    end_column = column_letter(num_columns)
    
    # Update sheet
    range_name = f"{category_name}!A1:{end_column}{len(rows)}"
    body = {"values": rows}
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    
    logger.info(f"{category_name} sheet updated: {len(students)} students, {len(category_assignments)} assignments")


def generate_assignment_sheet(service, spreadsheet_id, assignment, course_data):
    """
    Generate detailed sheet for a single assignment.
    
    Format:
    Row 1: Legal Name | Email | Total Score | Max Points | Status | Submission Time | Lateness | View Count
    Row 2+: Student data with detailed submission info
    """
    sheet_name = assignment.title[:100]  # Google Sheets limits sheet names to 100 chars
    logger.info(f"Generating assignment sheet: {sheet_name}...")
    
    try:
        sheet_id = get_or_create_sheet(service, spreadsheet_id, sheet_name)
    except Exception as e:
        logger.warning(f"Could not create sheet for {sheet_name}: {e}")
        return
    
    students = course_data["students"]
    submissions = course_data["submissions"]
    
    # Build rows
    rows = []
    
    # Row 1: Headers
    row1 = ["Legal Name", "Email", "Total Score", "Max Points", "Status", 
            "Submission Time", "Lateness (hours)", "View Count"]
    rows.append(row1)
    
    # Student rows
    for student in students:
        sub = submissions.get((assignment.id, student.id))
        
        if sub:
            lateness_hours = ""
            if sub.lateness:
                try:
                    # Parse lateness format "HH:MM:SS"
                    parts = str(sub.lateness).split(':')
                    if len(parts) >= 2:
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        lateness_hours = round(hours + minutes / 60, 2)
                except:
                    lateness_hours = str(sub.lateness)
            
            row = [
                student.legal_name or "",
                student.email or "",
                float(sub.total_score) if sub.total_score is not None else "",
                float(sub.max_points) if sub.max_points is not None else "",
                sub.status or "",
                str(sub.submission_time) if sub.submission_time else "",
                lateness_hours,
                int(sub.view_count) if sub.view_count is not None else ""
            ]
        else:
            row = [student.legal_name or "", student.email or "", "", "", "Not Submitted", "", "", ""]
        
        rows.append(row)
    
    # Update sheet
    range_name = f"'{sheet_name}'!A1:H{len(rows)}"
    body = {"values": rows}
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    
    logger.info(f"Assignment sheet '{sheet_name}' updated: {len(students)} students")


def generate_all_sheets_with_config(config):
    """Generate all summary sheets from database using config dict."""
    logger.info(f"Generating summary sheets for course: {config.get('id', 'unknown')}")
    logger.info(f"  Course: {config.get('course_name')}")
    logger.info(f"  Semester: {config.get('semester')} {config.get('year')}")
    
    # Get data from database
    course_gradescope_id = config["gradescope_course_id"]
    spreadsheet_id = config["spreadsheet_id"]
    
    course_data = get_course_data(course_gradescope_id)
    
    logger.info(f"Loaded from database:")
    logger.info(f"  Students: {len(course_data['students'])}")
    logger.info(f"  Assignments: {len(course_data['assignments'])}")
    logger.info(f"  Submissions: {len(course_data['submissions'])}")
    
    # Create Google Sheets service
    service = create_sheets_service()
    
    # 1. Generate main summary sheet
    generate_summary_sheet(service, spreadsheet_id, course_data)
    
    # 2. Save summary sheet data to database
    logger.info("Saving summary sheet to database...")
    try:
        save_summary_sheet_to_db(course_gradescope_id, course_data)
        logger.info("✅ Summary sheet saved to database")
    except Exception as e:
        logger.error(f"❌ Failed to save summary sheet to database: {e}")
    
    # 3. Group assignments by category
    assignments_by_category = defaultdict(list)
    for assignment in course_data["assignments"]:
        category = categorize_assignment(assignment.title)
        assignments_by_category[category].append(assignment)
    
    # 4. Generate category sheets
    for category, category_assignments in assignments_by_category.items():
        if category_assignments:
            generate_category_sheet(service, spreadsheet_id, category, 
                                   category_assignments, course_data)
    
    logger.info("✅ All sheets generated successfully!")


def generate_all_sheets(config_path, course_id=None):
    """Generate all summary sheets from database using config file."""
    # Load config
    config = load_config(config_path, course_id)
    generate_all_sheets_with_config(config)


def get_courses_from_db():
    """Get all courses from database."""
    session = SessionLocal()
    try:
        courses = session.query(Course).all()
        return [
            {
                'id': f"{c.department.lower()}{c.course_number}_{c.semester.lower()[:2]}{str(c.year)[-2:]}",
                'gradescope_course_id': c.gradescope_course_id,
                'spreadsheet_id': c.spreadsheet_id,
                'course_name': c.name,
                'department': c.department,
                'course_number': c.course_number,
                'semester': c.semester,
                'year': c.year,
                'instructor': None  # Not stored in this query
            }
            for c in courses
        ]
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate summary sheets from database",
        epilog="""
Examples:
  # Use config file
  python scripts/generate_summary_sheets.py --config config/courses.json
  
  # Use config file with specific course
  python scripts/generate_summary_sheets.py --config config/courses.json --course-id cs10_fa25
  
  # Use database (process all courses)
  python scripts/generate_summary_sheets.py --from-db
  
  # Use database with specific Gradescope course ID
  python scripts/generate_summary_sheets.py --from-db --gradescope-id 1098053
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", help="Path to config JSON (e.g., config/courses.json)")
    parser.add_argument("--course-id", help="Specific course ID to process (when using --config)")
    parser.add_argument("--from-db", action="store_true", help="Load courses from database instead of config file")
    parser.add_argument("--gradescope-id", help="Specific Gradescope course ID to process (when using --from-db)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.config and not args.from_db:
        # Default: try to find courses.json in config directory
        default_config = Path(__file__).parent.parent / "config" / "courses.json"
        if default_config.exists():
            args.config = str(default_config)
            logger.info(f"Using default config: {args.config}")
        else:
            parser.error("Either --config or --from-db must be specified")
    
    if args.config and args.from_db:
        parser.error("Cannot specify both --config and --from-db")
    
    if args.course_id and args.from_db:
        parser.error("--course-id only works with --config, use --gradescope-id with --from-db")
    
    try:
        if args.from_db:
            # Load courses from database
            logger.info("Loading courses from database...")
            db_courses = get_courses_from_db()
            
            if not db_courses:
                logger.error("No courses found in database")
                sys.exit(1)
            
            logger.info(f"Found {len(db_courses)} courses in database:")
            for course in db_courses:
                logger.info(f"  - {course['id']}: {course['course_name']} ({course['semester']} {course['year']})")
            
            # Process specified course or all courses
            if args.gradescope_id:
                course = next((c for c in db_courses if c['gradescope_course_id'] == args.gradescope_id), None)
                if not course:
                    logger.error(f"Course with Gradescope ID {args.gradescope_id} not found")
                    sys.exit(1)
                courses_to_process = [course]
            else:
                courses_to_process = db_courses
            
            # Generate sheets for each course
            for course in courses_to_process:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing: {course['course_name']}")
                logger.info(f"{'='*60}\n")
                
                # Create temporary config dict
                temp_config = {
                    'id': course['id'],
                    'gradescope_course_id': course['gradescope_course_id'],
                    'spreadsheet_id': course['spreadsheet_id'],
                    'course_name': course['course_name'],
                    'department': course['department'],
                    'course_number': course['course_number'],
                    'semester': course['semester'],
                    'year': course['year']
                }
                
                # Generate sheets directly with config dict
                generate_all_sheets_with_config(temp_config)
        
        else:
            # Load from config file
            config_path = Path(args.config)
            if not config_path.exists():
                logger.error(f"Config file not found: {args.config}")
                sys.exit(1)
            
            # Show available courses
            courses = list_courses(str(config_path))
            logger.info(f"Available courses in config:")
            for course in courses:
                logger.info(f"  - {course['id']}: {course['name']} ({course['semester']} {course['year']})")
            
            generate_all_sheets(str(config_path), args.course_id)
    
    except Exception as e:
        logger.error(f"Failed to generate sheets: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
