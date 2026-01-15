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

# Load category configuration
CATEGORY_CONFIG = None
def _load_category_config():
    global CATEGORY_CONFIG
    if CATEGORY_CONFIG is None:
        config_path = os.path.join(os.path.dirname(__file__), 'assignment_categories.json')
        try:
            with open(config_path, 'r') as f:
                CATEGORY_CONFIG = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load category config: {e}")
            CATEGORY_CONFIG = {"categories": []}
    return CATEGORY_CONFIG

def _categorize_assignment(assignment_name: str) -> str:
    """Determine category based on assignment name.
    
    Excludes assignments starting with 'Practice'.
    Uses fuzzy matching - normalizes underscores, case, and whitespace.
    """
    # Exclude Practice assignments
    normalized = assignment_name.replace('_', ' ').strip()
    if normalized.lower().startswith('practice'):
        return None
    
    config = _load_category_config()
    for cat in config.get('categories', []):
        for pattern in cat.get('patterns', []):
            # Fuzzy match: both sides lowercase, ignore extra spaces
            if pattern.lower() in normalized.lower():
                return cat['name']
    return None


def write_assignment_scores_to_db(course_gradescope_id: str, assignment_id: str, assignment_name: str, csv_filepath: str, 
                                  spreadsheet_id: str = None, course_name: str = None, 
                                  department: str = None, course_number: str = None, 
                                  semester: str = None, year: str = None, instructor: str = None):
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
        if not assignment:
            category = _categorize_assignment(assignment_name)
            assignment = Assignment(assignment_id=str(assignment_id), course_id=course.id, title=assignment_name, category=category)
            session.add(assignment)
            session.flush()
        else:
            # Update category if not set
            if not assignment.category:
                assignment.category = _categorize_assignment(assignment_name)

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
                if assignment.max_points is None:
                    max_pts_str = row.get('Max Points', '')
                    try:
                        if max_pts_str:
                            assignment.max_points = float(max_pts_str)
                    except ValueError:
                        pass
            
            # Use first column position for Name (to avoid encoding issue with column name)
            name = list(row.values())[0] if row else None
            
            # Use normal field access for other columns
            sid = row.get("SID")
            
            # Skip rows without SID - these are not valid student records
            if not sid or not sid.strip():
                continue
            
            email = row.get("Email")
            total_score_str = row.get("Total Score", "0")
            max_points_str = row.get("Max Points", "0")
            status = row.get("Status", "Missing")
            submission_id = row.get("Submission ID")
            submission_time_str = row.get("Submission Time")
            lateness = row.get("Lateness (H:M:S)")
            view_count_str = row.get("View Count")
            submission_count_str = row.get("Submission Count")

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
            
            submission_time = None
            if submission_time_str:
                try:
                    submission_time = datetime.fromisoformat(submission_time_str)
                except Exception:
                    submission_time = None

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
