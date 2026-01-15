"""
iClicker Sync Wrapper

Provides a clean interface for syncing iClicker grades.
"""
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


def sync_iclicker_course(
    course_names: List[str],
    spreadsheet_id: str,
    use_db: bool = True
) -> Dict[str, Any]:
    """
    Sync iClicker grades for course sections.
    
    Args:
        course_names: List of iClicker course names (e.g., ["[CS10 | Fa25] Lab", ...])
        spreadsheet_id: Google Sheets spreadsheet ID
        use_db: Whether to save to database
    
    Returns:
        Dict with sync results
    """
    logger.info(f"Starting iClicker sync for {len(course_names)} course sections")
    
    try:
        # Import the main iClicker module
        from iclicker_to_spreadsheet import main as iclicker_sync_main
        
        # Set configuration
        os.environ['SPREADSHEET_ID'] = spreadsheet_id
        os.environ['USE_DB_AS_PRIMARY'] = 'true' if use_db else 'false'
        
        synced_sections = []
        
        # Sync each course section
        for course_name in course_names:
            try:
                os.environ['ICLICKER_COURSE_NAME'] = course_name
                result = iclicker_sync_main()
                synced_sections.append({
                    "course_name": course_name,
                    "success": True,
                    "sessions_synced": result.get("sessions_synced", 0)
                })
            except Exception as e:
                logger.error(f"Failed to sync iClicker section {course_name}: {e}")
                synced_sections.append({
                    "course_name": course_name,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "success": all(s["success"] for s in synced_sections),
            "sections": synced_sections,
            "total_sections": len(course_names)
        }
        
    except Exception as e:
        logger.exception(f"iClicker sync failed")
        raise


if __name__ == "__main__":
    # Test sync
    result = sync_iclicker_course(
        course_names=[
            "[CS10 | Fa25] Discussion",
            "[CS10 | Fa25] Lab",
            "[CS10 | Fa25] Lecture"
        ],
        spreadsheet_id="130Vsasjjy8cc8MWqpyVy32mS9lqhvy0mhJyOhfTAmOo",
        use_db=True
    )
    print(result)
