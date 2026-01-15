"""
Gradescope Sync Wrapper

Provides a clean interface for syncing Gradescope grades.
"""
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


def sync_gradescope_course(
    course_id: str,
    spreadsheet_id: str,
    course_name: str,
    department: str,
    course_number: str,
    semester: str,
    year: int,
    instructor: str,
    use_db: bool = True
) -> Dict[str, Any]:
    """
    Sync Gradescope grades for a course.
    
    Args:
        course_id: Gradescope course ID
        spreadsheet_id: Google Sheets spreadsheet ID
        course_name: Course name
        department: Department code
        course_number: Course number
        semester: Semester (Fall, Spring, etc.)
        year: Year
        instructor: Instructor name
        use_db: Whether to save to database
    
    Returns:
        Dict with sync results
    """
    logger.info(f"Starting Gradescope sync for course {course_id}")
    
    try:
        # Set environment variable for DB usage
        os.environ['USE_DB_AS_PRIMARY'] = 'true' if use_db else 'false'
        
        # Import the main gradescope module
        # Note: This assumes gradescope_to_spreadsheet.py has been refactored
        # to expose a function we can call instead of running as a script
        
        from gradescope_to_spreadsheet import push_all_grade_data_to_sheets
        
        # Set temporary config (this should ideally be passed as parameters)
        os.environ['GRADESCOPE_COURSE_ID'] = course_id
        os.environ['SPREADSHEET_ID'] = spreadsheet_id
        
        # Run the sync
        result = push_all_grade_data_to_sheets()
        
        return {
            "success": True,
            "course_id": course_id,
            "assignments_synced": result.get("assignments_synced", 0),
            "students_updated": result.get("students_updated", 0)
        }
        
    except Exception as e:
        logger.exception(f"Gradescope sync failed for course {course_id}")
        raise


if __name__ == "__main__":
    # Test sync
    result = sync_gradescope_course(
        course_id="1098053",
        spreadsheet_id="130Vsasjjy8cc8MWqpyVy32mS9lqhvy0mhJyOhfTAmOo",
        course_name="CS10",
        department="COMPSCI",
        course_number="10",
        semester="Fall",
        year=2025,
        instructor="Dan Garcia",
        use_db=True
    )
    print(result)
