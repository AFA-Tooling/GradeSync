"""
Generate Summary sheet data from DB instead of using XLOOKUP formulas.
"""
import logging
from sqlalchemy.orm import joinedload
from api.core.db import SessionLocal
from api.core.models import Course, Assignment, Student, Submission, SummarySheet

logger = logging.getLogger(__name__)


def get_summary_data_from_db(course_gradescope_id: str):
    """
    Query DB and return summary data structured as:
    {
        "assignments": [list of assignment names in order],
        "students": [
            {
                "legal_name": str,
                "email": str,
                "scores": {assignment_name: score, ...}
            },
            ...
        ]
    }
    
    Args:
        course_gradescope_id: Gradescope course ID
        
    Returns:
        dict: Summary data structure
    """
    session = SessionLocal()
    try:
        # Get course
        course = session.query(Course).filter(Course.gradescope_course_id == course_gradescope_id).first()
        if not course:
            logger.warning(f"Course {course_gradescope_id} not found in DB")
            return {"assignments": [], "students": []}
        
        # Get all assignments for this course, ordered by category and number
        assignments = session.query(Assignment).filter(
            Assignment.course_id == course.id
        ).all()
        
        # Sort assignments by category priority and extracted number
        def extract_number(title):
            import re
            numbers = re.findall(r"\d+", title or "")
            return int(numbers[0]) if numbers else 0
        
        category_order = {
            'lecture': 1, 'quiz': 1,
            'midterm': 2,
            'postterm': 3, 'posterm': 3,
            'project': 4,
            'lab': 5,
            'discussion': 6
        }
        
        def get_category_priority(assignment):
            title_lower = (assignment.title or "").lower()
            for key, priority in category_order.items():
                if key in title_lower:
                    return priority
            return 99
        
        sorted_assignments = sorted(assignments, key=lambda a: (get_category_priority(a), extract_number(a.title)))
        assignment_names = [a.title for a in sorted_assignments]
        assignment_id_to_name = {a.id: a.title for a in sorted_assignments}
        
        # Get all students
        students = session.query(Student).all()
        
        # Get all submissions for this course
        submissions = session.query(Submission).join(Assignment).filter(
            Assignment.course_id == course.id
        ).all()
        
        # Build submission lookup: (assignment_id, student_id) -> submission
        submission_lookup = {}
        for sub in submissions:
            submission_lookup[(sub.assignment_id, sub.student_id)] = sub
        
        # Build student data
        student_data = []
        for student in students:
            scores = {}
            for assignment in sorted_assignments:
                sub = submission_lookup.get((assignment.id, student.id))
                if sub and sub.total_score is not None:
                    scores[assignment.title] = float(sub.total_score)
                else:
                    scores[assignment.title] = ""
            
            student_data.append({
                "legal_name": student.legal_name or "",
                "email": student.email or "",
                "scores": scores
            })
        
        # Sort students by name
        student_data.sort(key=lambda s: s.get("legal_name", "").lower())
        
        return {
            "assignments": assignment_names,
            "students": student_data
        }
    finally:
        session.close()


def categorize_assignment_for_summary(assignment_name):
    """
    Categorize an assignment based on its name for Summary sheet.
    
    Args:
        assignment_name (str): Name of the assignment
    
    Returns:
        str: Category name
    """
    name_lower = assignment_name.lower()
    
    if 'lecture' in name_lower or 'quiz' in name_lower:
        return 'Quest (pre-clobber)'
    elif 'midterm' in name_lower:
        return 'Midterm (pre-clobber)'
    elif 'postterm' in name_lower or 'posterm' in name_lower:
        return 'Postterm'
    elif 'project' in name_lower:
        return 'Projects'
    elif 'lab' in name_lower:
        return 'Labs (before dropping lowest two)'
    elif 'discussion' in name_lower:
        return 'Discussions'
    else:
        return 'Other'


def get_max_points_from_db(course_gradescope_id: str, assignment_name: str):
    """
    Get max points for an assignment from DB.
    
    Args:
        course_gradescope_id: Gradescope course ID
        assignment_name: Assignment title
        
    Returns:
        float: Max points or 0.0 if not found
    """
    session = SessionLocal()
    try:
        course = session.query(Course).filter(Course.gradescope_course_id == course_gradescope_id).first()
        if not course:
            return 0.0
        
        assignment = session.query(Assignment).filter(
            Assignment.course_id == course.id,
            Assignment.title == assignment_name
        ).first()
        
        if assignment and assignment.max_points:
            return float(assignment.max_points)
        
        # Fallback: get from any submission for this assignment
        submission = session.query(Submission).join(Assignment).filter(
            Assignment.course_id == course.id,
            Assignment.title == assignment_name,
            Submission.max_points.isnot(None)
        ).first()
        
        if submission and submission.max_points:
            return float(submission.max_points)
        
        return 0.0
    finally:
        session.close()


def get_summary_sheet_from_db(course_gradescope_id: str):
    """
    Get pre-computed summary sheet data directly from the summary_sheets table.
    
    This is more efficient than get_summary_data_from_db() as it reads from 
    a pre-computed table instead of joining multiple tables.
    
    Args:
        course_gradescope_id: Gradescope course ID
        
    Returns:
        dict: Summary data structure with assignments, students, and scores
    """
    session = SessionLocal()
    try:
        # Get course
        course = session.query(Course).filter(
            Course.gradescope_course_id == course_gradescope_id
        ).first()
        
        if not course:
            logger.warning(f"Course {course_gradescope_id} not found in DB")
            return {"assignments": [], "students": [], "categories": {}, "max_points": {}}
        
        # Get all assignments for this course, ordered
        assignments = session.query(Assignment).filter(
            Assignment.course_id == course.id
        ).all()
        
        # Sort assignments
        def extract_number(title):
            import re
            numbers = re.findall(r"\d+", title or "")
            return int(numbers[0]) if numbers else 0
        
        category_order = {
            'lecture': 1, 'quiz': 1,
            'midterm': 2,
            'postterm': 3, 'posterm': 3,
            'project': 4,
            'lab': 5,
            'discussion': 6
        }
        
        def get_category_priority(assignment):
            title_lower = (assignment.title or "").lower()
            for key, priority in category_order.items():
                if key in title_lower:
                    return priority
            return 99
        
        sorted_assignments = sorted(
            assignments, 
            key=lambda a: (get_category_priority(a), extract_number(a.title))
        )
        
        assignment_names = [a.title for a in sorted_assignments]
        assignment_id_map = {a.id: a.title for a in sorted_assignments}
        
        # Build categories and max_points maps using persisted assignment.category
        categories = {}
        max_points = {}
        for assignment in sorted_assignments:
            categories[assignment.title] = assignment.category or "Uncategorized"
            max_points[assignment.title] = float(assignment.max_points or 0)
        
        # Get all students
        students = session.query(Student).order_by(Student.legal_name).all()
        
        # Get summary sheet data for this course
        summary_records = session.query(SummarySheet).filter(
            SummarySheet.course_id == course.id
        ).all()
        
        # Build lookup: (student_id, assignment_id) -> score
        score_lookup = {
            (record.student_id, record.assignment_id): float(record.score) if record.score is not None else None
            for record in summary_records
        }
        
        # Build student data
        student_data = []
        for student in students:
            scores = {}
            for assignment in sorted_assignments:
                score = score_lookup.get((student.id, assignment.id))
                scores[assignment.title] = score if score is not None else ""
            
            student_data.append({
                "legal_name": student.legal_name or "",
                "email": student.email or "",
                "scores": scores
            })
        
        logger.info(f"Retrieved summary sheet from DB: {len(student_data)} students, {len(assignment_names)} assignments")
        
        return {
            "assignments": assignment_names,
            "students": student_data,
            "categories": categories,
            "max_points": max_points
        }
        
    except Exception as e:
        logger.exception(f"Error retrieving summary sheet from DB: {e}")
        return {"assignments": [], "students": [], "categories": {}, "max_points": {}}
    finally:
        session.close()

