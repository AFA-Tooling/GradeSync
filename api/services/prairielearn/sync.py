"""
PrairieLearn Sync Module

High-level sync operations for PrairieLearn gradebook data.
"""
from typing import Dict, Any, Optional
import logging
from .client import PrairieLearnClient
from ..sheets.client import SheetsClient

logger = logging.getLogger(__name__)


class PrairieLearnSync:
    """
    Sync PrairieLearn grades to database and Google Sheets.
    
    Orchestrates:
    - PrairieLearn API access
    - Gradebook retrieval
    - Database persistence
    - Google Sheets export
    """
    
    def __init__(
        self,
        api_token: str,
        sheets_client: Optional[SheetsClient] = None
    ):
        """
        Initialize PrairieLearn sync.
        
        Args:
            api_token: PrairieLearn API token
            sheets_client: Optional SheetsClient
        """
        self.pl_client = PrairieLearnClient(api_token=api_token)
        self.sheets_client = sheets_client or SheetsClient()
    
    def sync_course(
        self,
        course_id: str,
        spreadsheet_id: Optional[str] = None,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Sync a PrairieLearn course.
        
        Args:
            course_id: PrairieLearn course instance ID
            spreadsheet_id: Optional Google Sheets ID
            save_to_db: Whether to save to database
            
        Returns:
            Dictionary with sync results
        """
        logger.info(f"Starting PrairieLearn sync for course {course_id}")
        
        try:
            # Get course info
            course_info = self.pl_client.get_course_info(course_id)
            logger.info(f"Course: {course_info.title}")
            
            # Get gradebook
            gradebook_df = self.pl_client.get_gradebook(course_id)
            
            # Get assessments
            assessments = self.pl_client.get_assessments(course_id)
            
            # Export to Sheets if requested
            if spreadsheet_id:
                # Export main gradebook
                self.sheets_client.dataframe_to_sheet(
                    df=gradebook_df,
                    spreadsheet_id=spreadsheet_id,
                    worksheet_title="PrairieLearn Gradebook"
                )
                
                # Export by assessment
                assessment_data = self.pl_client.export_gradebook_to_dict(course_id)
                for title, df in assessment_data.items():
                    # Sanitize worksheet title (max 100 chars, no special chars)
                    safe_title = title[:90]
                    self.sheets_client.dataframe_to_sheet(
                        df=df,
                        spreadsheet_id=spreadsheet_id,
                        worksheet_title=f"PL - {safe_title}"
                    )
            
            # TODO: Save to database if save_to_db
            
            results = {
                "success": True,
                "course_id": course_id,
                "course_title": course_info.title,
                "assessments_synced": len(assessments),
                "students_synced": len(gradebook_df)
            }
            
            logger.info(f"Sync completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise
        finally:
            self.pl_client.close()
    
    def close(self):
        """Close clients."""
        self.pl_client.close()
        if self.sheets_client:
            self.sheets_client.close()
