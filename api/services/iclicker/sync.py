"""
iClicker Sync Module

High-level sync operations for iClicker attendance data.
"""
from typing import Dict, Any, List, Optional
import logging
from .client import IClickerClient
from ..sheets.client import SheetsClient

logger = logging.getLogger(__name__)


class IClickerSync:
    """
    Sync iClicker attendance to database and Google Sheets.
    
    Orchestrates:
    - iClicker web scraping
    - Data parsing
    - Database persistence
    - Google Sheets export
    """
    
    def __init__(
        self,
        username: str,
        password: str,
        download_dir: Optional[str] = None,
        sheets_client: Optional[SheetsClient] = None
    ):
        """
        Initialize iClicker sync.
        
        Args:
            username: Campus login username
            password: Campus login password
            download_dir: Directory for CSV downloads
            sheets_client: Optional SheetsClient
        """
        self.ic_client = IClickerClient(
            username=username,
            password=password,
            download_dir=download_dir
        )
        self.sheets_client = sheets_client or SheetsClient()
    
    def sync_courses(
        self,
        course_names: List[str],
        spreadsheet_id: Optional[str] = None,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Sync multiple iClicker courses.
        
        Args:
            course_names: List of course names (e.g., ["[CS10 | Fa25] Lab"])
            spreadsheet_id: Optional Google Sheets ID
            save_to_db: Whether to save to database
            
        Returns:
            Dictionary with sync results
        """
        logger.info(f"Starting iClicker sync for {len(course_names)} courses")
        
        try:
            # Login
            self.ic_client.login()
            
            # Download all courses
            files = self.ic_client.download_all_courses(course_names)
            
            synced_courses = []
            for course_name, file_path in files.items():
                try:
                    # Read CSV
                    df = self.ic_client.read_attendance_csv(file_path)
                    
                    # Export to Sheets if requested
                    if spreadsheet_id:
                        self.sheets_client.dataframe_to_sheet(
                            df=df,
                            spreadsheet_id=spreadsheet_id,
                            worksheet_title=f"iClicker - {course_name}"
                        )
                    
                    # TODO: Save to database if save_to_db
                    
                    synced_courses.append({
                        "course": course_name,
                        "records": len(df),
                        "file": file_path
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to process {course_name}: {e}")
                    continue
            
            results = {
                "success": True,
                "courses_synced": len(synced_courses),
                "courses": synced_courses
            }
            
            logger.info(f"Sync completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise
        finally:
            self.ic_client.close()
    
    def close(self):
        """Close clients."""
        self.ic_client.close()
        if self.sheets_client:
            self.sheets_client.close()
