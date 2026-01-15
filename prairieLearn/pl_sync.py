"""
PrairieLearn Sync Wrapper

Provides a clean interface for syncing PrairieLearn grades.
"""
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


def sync_prairielearn_course(
    course_id: str,
    spreadsheet_id: str,
    use_db: bool = True
) -> Dict[str, Any]:
    """
    Sync PrairieLearn grades for a course.
    
    Args:
        course_id: PrairieLearn course ID
        spreadsheet_id: Google Sheets spreadsheet ID
        use_db: Whether to save to database
    
    Returns:
        Dict with sync results
    """
    logger.info(f"Starting PrairieLearn sync for course {course_id}")
    
    try:
        # Import the main PrairieLearn module
        from pl_to_spreadsheet import main as pl_sync_main
        
        # Set configuration
        os.environ['PL_COURSE_ID'] = course_id
        os.environ['SPREADSHEET_ID'] = spreadsheet_id
        os.environ['USE_DB_AS_PRIMARY'] = 'true' if use_db else 'false'
        
        # Run the sync
        result = pl_sync_main()
        
        return {
            "success": True,
            "course_id": course_id,
            "assessments_synced": result.get("assessments_synced", 0)
        }
        
    except Exception as e:
        logger.exception(f"PrairieLearn sync failed for course {course_id}")
        raise


if __name__ == "__main__":
    # Test sync
    result = sync_prairielearn_course(
        course_id="192475",
        spreadsheet_id="130Vsasjjy8cc8MWqpyVy32mS9lqhvy0mhJyOhfTAmOo",
        use_db=True
    )
    print(result)
