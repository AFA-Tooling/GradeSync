import io
import csv
import os
import json
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from .db import SessionLocal, init_db
from .models import Course, Assignment, Student, Submission
import logging

logger = logging.getLogger(__name__)


def _parse_submission_time(val: str):
    """Best-effort parser for Gradescope submission timestamps."""
    if not val:
        return None

    cleaned = val.strip()

    # Handle common ISO-ish shapes and a few Gradescope exports
    candidates = [
        cleaned,
        cleaned.replace("Z", "+00:00"),
    ]
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            pass

    # Try with timezone offset (e.g., "2025-09-17 23:29:50 -0700")
    for fmt in (
        "%Y-%m-%d %H:%M:%S %z",  # Gradescope format with timezone
        "%Y-%m-%dT%H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%m/%d/%y %I:%M %p",
        "%m/%d/%Y %I:%M %p",
    ):
        try:
            dt = datetime.strptime(cleaned, fmt)
            # If timezone-aware, return as-is; otherwise return naive
            return dt
        except Exception:
            continue

    return None

# Legacy fallback: Load category configuration from assignment_categories.json
CATEGORY_CONFIG = None
def _load_category_config():
    """Load legacy category config as fallback."""
    global CATEGORY_CONFIG
    if CATEGORY_CONFIG is None:
        config_path = os.path.join(os.path.dirname(__file__), 'assignment_categories.json')
        try:
            with open(config_path, 'r') as f:
                CATEGORY_CONFIG = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load legacy category config: {e}")
            CATEGORY_CONFIG = {"categories": []}
    return CATEGORY_CONFIG

def _categorize_assignment(assignment_name: str, course_categories: list = None) -> str:
    """Determine category based on assignment name.
    
    Excludes assignments starting with 'Practice'.
    Uses fuzzy matching - normalizes underscores, case, and whitespace.
    
    Args:
        assignment_name: Name of the assignment
        course_categories: List of category configs from course config (preferred)
                          If None, falls back to assignment_categories.json
    """
    # Exclude Practice assignments
    normalized = assignment_name.replace('_', ' ').strip()
    if normalized.lower().startswith('practice'):
        return None
    
    # Use course-specific categories if provided, otherwise fallback to legacy
    if course_categories:
        categories = course_categories
    else:
        config = _load_category_config()
        categories = config.get('categories', [])
    
    for cat in categories:
        for pattern in cat.get('patterns', []):
            # Fuzzy match: both sides lowercase, ignore extra spaces
            if pattern.lower() in normalized.lower():
                return cat['name']
    return None


def write_assignment_scores_to_db(course_gradescope_id: str, assignment_id: str, assignment_name: str, csv_filepath: str, 
                                  spreadsheet_id: str = None, course_name: str = None, 
                                  department: str = None, course_number: str = None, 
                                  semester: str = None, year: str = None, instructor: str = None,
                                  course_categories: list = None):
    """Parse the given CSV file and upsert Course, Assignment, Student and Submission rows.

    Args:
        course_gradescope_id: Gradescope course id from config
        assignment_id: Gradescope assignment id
        assignment_name: Assignment title
        csv_filepath: Path to saved CSV file (text/csv)
        spreadsheet_id: Optional Google Sheets ID to store in course
        course_name: Optional course name
        department: Optional department code
        course_number: Optional course number
        semester: Optional semester
        year: Optional year
        instructor: Optional instructor name
    """
    init_db()
    session = SessionLocal()
    try:
        # Ensure course exists
        course = session.query(Course).filter(Course.gradescope_course_id == course_gradescope_id).first()
        if not course:
            course = Course(
                gradescope_course_id=course_gradescope_id,
                spreadsheet_id=spreadsheet_id,
                name=course_name,
                department=department,
                course_number=course_number,
                semester=semester,
                year=year,
                instructor=instructor
            )
            session.add(course)
            session.flush()
        else:
            # Update course info if provided
            updated = False
            if spreadsheet_id and course.spreadsheet_id != spreadsheet_id:
                course.spreadsheet_id = spreadsheet_id
                updated = True
            if course_name and course.name != course_name:
                course.name = course_name
                updated = True
            if department and course.department != department:
                course.department = department
                updated = True
            if course_number and course.course_number != course_number:
                course.course_number = course_number
                updated = True
            if semester and course.semester != semester:
                course.semester = semester
                updated = True
            if year and course.year != year:
                course.year = year
                updated = True
            if instructor and course.instructor != instructor:
                course.instructor = instructor
                updated = True
            if updated:
                session.flush()

        # Ensure assignment exists
        assignment = session.query(Assignment).filter(Assignment.assignment_id == str(assignment_id), Assignment.course_id == course.id).first()
        category = _categorize_assignment(assignment_name, course_categories)
        
        if not assignment:
            assignment = Assignment(assignment_id=str(assignment_id), course_id=course.id, title=assignment_name, category=category)
            session.add(assignment)
            session.flush()
        else:
            # Always update category (in case config changed)
            assignment.category = category

        # Parse CSV and upsert records
        with open(csv_filepath, "rb") as fh:
            content = fh.read().decode('utf-8')
        
        # Use DictReader but access first column by position to avoid encoding issues with "Name" column
        fh = io.StringIO(content)
        reader = csv.DictReader(fh)
        
        # Extract max_points from first row if not set
        first_row_processed = False
        
        # Known columns to exclude from scores_by_question
        known_cols = {"SID", "Email", "Sections", "Total Score", "Max Points", "Status", 
                      "Submission ID", "Submission Time", "Lateness (H:M:S)", 
                      "View Count", "Submission Count"}
        # Add first column name (Name or b'Name) to known columns
        if reader.fieldnames and len(reader.fieldnames) > 0:
            known_cols.add(reader.fieldnames[0])

        for row in reader:
            # Update assignment max_points from first row if not set
            if not first_row_processed:
                first_row_processed = True
                if assignment.max_points is None or assignment.max_points == 0:
                    max_pts_str = row.get('Max Points', '')
                    try:
                        if max_pts_str:
                            max_val = float(max_pts_str)
                            if max_val > 0:
                                assignment.max_points = max_val
                    except ValueError:
                        pass
            
            # Use first column position for Name (to avoid encoding issue with column name)
            name = list(row.values())[0] if row else None
            
            # Use normal field access for other columns
            sid = row.get("SID")
            status = row.get("Status", "Missing")
            
            # Skip rows without SID - these are not valid student records
            if not sid or not sid.strip():
                continue
            
            # Skip Missing submissions
            if status == "Missing":
                continue
            
            email = row.get("Email")
            total_score_str = row.get("Total Score", "0")
            max_points_str = row.get("Max Points", "0")
            submission_id = row.get("Submission ID")
            submission_time_str = row.get("Submission Time")
            lateness = row.get("Lateness (H:M:S)")
            view_count_str = row.get("View Count")
            submission_count_str = row.get("Submission Count")
            
            # Debug: 记录前几条的 submission_time_str
            if not first_row_processed:
                logger.info(f"CSV has Submission Time column: {submission_time_str is not None}")
                logger.info(f"Sample Submission Time value: '{submission_time_str}'")

            # Upsert student - 直接用 SID 匹配
            student = None
            if sid and sid.strip():  # Only process if SID is not empty
                student = session.query(Student).filter(Student.sid == sid).first()
            
            if not student and sid and sid.strip():
                # 学生不存在，创建新记录
                student = Student(sid=sid, email=email, legal_name=name)
                session.add(student)
                session.flush()
            elif student:
                # 学生已存在，更新 email 和 legal_name（以防有变化）
                if email and student.email != email:
                    student.email = email
                if name and student.legal_name != name:
                    student.legal_name = name
            else:
                # SID为空，跳过此学生
                continue

            # Build submission object
            def _num(v):
                try:
                    if v is None or v == "":
                        return None
                    return float(v)
                except Exception:
                    return None
            
            def _int(v):
                try:
                    if v is None or v == "":
                        return None
                    return int(v)
                except Exception:
                    return None

            total_score = _num(total_score_str)
            max_points = _num(max_points_str)
            view_count = _int(view_count_str)
            submission_count = _int(submission_count_str)
            
            submission_time = _parse_submission_time(submission_time_str)
            
            # Debug: 总是记录第一条有 submission_time_str 的记录
            if submission_time_str and sid:
                logger.info(f"[SUBMISSION_TIME] SID={sid}, Raw='{submission_time_str}', Parsed={submission_time}")

            # per-question scores - exclude known columns
            scores_by_question = {}
            for k, v in row.items():
                if k not in known_cols and v:
                    scores_by_question[k] = v

            # Upsert submission (unique per assignment_id + student_id)
            existing = session.query(Submission).filter(Submission.assignment_id == assignment.id, Submission.student_id == student.id).first()
            if existing:
                existing.total_score = total_score
                existing.max_points = max_points
                existing.status = status
                existing.submission_id = submission_id
                existing.submission_time = submission_time
                existing.lateness = lateness
                existing.view_count = view_count
                existing.submission_count = submission_count
                existing.scores_by_question = scores_by_question
            else:
                new_sub = Submission(
                    assignment_id=assignment.id, 
                    student_id=student.id, 
                    total_score=total_score, 
                    max_points=max_points, 
                    status=status, 
                    submission_id=submission_id, 
                    submission_time=submission_time,
                    lateness=lateness,
                    view_count=view_count,
                    submission_count=submission_count,
                    scores_by_question=scores_by_question
                )
                session.add(new_sub)

        # Update course student count dynamically based on actual students in DB
        student_count = session.query(Student).count()
        if course.number_of_students != student_count:
            course.number_of_students = student_count

        session.commit()
        logger.info(f"Ingested CSV {csv_filepath} into DB for assignment {assignment_name} ({assignment_id})")
    except Exception as e:
        session.rollback()
        logger.exception("Failed ingesting CSV to DB: %s", e)
        raise
    finally:
        session.close()


def save_summary_sheet_to_db(course_gradescope_id: str, summary_data: dict, course_categories: list = None):
    """
    Save summary sheet data to database.
    
    Args:
        course_gradescope_id: Gradescope course ID
        summary_data: Dictionary containing:
            - assignments: list of Assignment objects
            - students: list of Student objects
            - submissions: dict mapping (assignment_id, student_id) to Submission
        course_categories: Optional list of category configurations from course config
    
    This function stores the computed summary in the summary_sheets table,
    making it efficient to retrieve summary data without recomputing.
    """
    from core.models import SummarySheet
    
    session = SessionLocal()
    try:
        # Get course
        course = session.query(Course).filter(
            Course.gradescope_course_id == course_gradescope_id
        ).first()
        
        if not course:
            logger.error(f"Course {course_gradescope_id} not found in database")
            return
        
        assignments = summary_data.get("assignments", [])
        students = summary_data.get("students", [])
        submissions = summary_data.get("submissions", {})
        
        logger.info(f"Saving summary sheet to database for course {course_gradescope_id}")
        logger.info(f"Processing {len(students)} students and {len(assignments)} assignments")
        
        # Store each student-assignment score pair
        for student in students:
            for assignment in assignments:
                sub = submissions.get((assignment.id, student.id))
                score = float(sub.total_score) if sub and sub.total_score is not None else None
                
                # Check if record exists
                existing = session.query(SummarySheet).filter(
                    SummarySheet.course_id == course.id,
                    SummarySheet.student_id == student.id,
                    SummarySheet.assignment_id == assignment.id
                ).first()
                
                if existing:
                    existing.score = score
                else:
                    new_summary = SummarySheet(
                        course_id=course.id,
                        student_id=student.id,
                        assignment_id=assignment.id,
                        score=score
                    )
                    session.add(new_summary)
        
        session.commit()
        logger.info(f"Successfully saved summary sheet to database for course {course_gradescope_id}")
        
    except Exception as e:
        session.rollback()
        logger.exception(f"Failed to save summary sheet to database: {e}")
        raise
    finally:
        session.close()

