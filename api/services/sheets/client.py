"""
Google Sheets Client

Unified client for Google Sheets operations with retry logic and error handling.
"""
import os
import json
import math
import numpy as np
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import backoff
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SheetsClient:
    """
    Google Sheets client with built-in retry logic and error handling.
    
    Features:
    - Automatic authentication with service account
    - Exponential backoff for rate limiting
    - Batch operations support
    - Standardized error handling
    """
    
    # Google Sheets API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Google Sheets client.
        
        Args:
            credentials_path: Path to service account JSON. 
                            If None, uses GOOGLE_APPLICATION_CREDENTIALS env var
        """
        self.credentials_path = credentials_path
        self._gspread_client = None
        self._sheets_service = None
        self._drive_service = None
        
    @property
    def gspread_client(self) -> gspread.Client:
        """Lazy-load gspread client."""
        if self._gspread_client is None:
            creds = self._get_credentials()
            self._gspread_client = gspread.authorize(creds)
        return self._gspread_client
    
    @property
    def sheets_service(self):
        """Lazy-load Google Sheets API service."""
        if self._sheets_service is None:
            creds = self._get_credentials()
            self._sheets_service = build('sheets', 'v4', credentials=creds)
        return self._sheets_service
    
    @property
    def drive_service(self):
        """Lazy-load Google Drive API service."""
        if self._drive_service is None:
            creds = self._get_credentials()
            self._drive_service = build('drive', 'v3', credentials=creds)
        return self._drive_service
    
    def _get_credentials(self) -> Credentials:
        """Get Google API credentials."""
        # 1) Explicit path override
        if self.credentials_path:
            return Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )

        # 2) JSON string in env (preferred)
        json_env = os.getenv("SERVICE_ACCOUNT_CREDENTIALS")
        if json_env:
            try:
                data = json.loads(json_env)
                return Credentials.from_service_account_info(data, scopes=self.SCOPES)
            except Exception:
                logger.exception("Failed to load service account from SERVICE_ACCOUNT_CREDENTIALS env var")

        # 3) Path from GOOGLE_APPLICATION_CREDENTIALS
        gac_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if gac_path and Path(gac_path).exists():
            return Credentials.from_service_account_file(
                gac_path,
                scopes=self.SCOPES
            )

        # 4) Legacy gspread default location
        return Credentials.from_service_account_file(
            Path.home() / '.config' / 'gspread' / 'service_account.json',
            scopes=self.SCOPES
        )
    
    @backoff.on_exception(
        backoff.expo,
        (gspread.exceptions.APIError, HttpError),
        max_tries=5,
        giveup=lambda e: isinstance(e, HttpError) and e.resp.status not in [429, 500, 503]
    )
    def open_spreadsheet(self, spreadsheet_id: str) -> gspread.Spreadsheet:
        """
        Open a spreadsheet by ID with retry logic.
        
        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            
        Returns:
            gspread.Spreadsheet object
        """
        logger.info(f"Opening spreadsheet: {spreadsheet_id}")
        return self.gspread_client.open_by_key(spreadsheet_id)
    
    @backoff.on_exception(
        backoff.expo,
        (gspread.exceptions.APIError, HttpError),
        max_tries=5
    )
    def get_or_create_worksheet(
        self, 
        spreadsheet: gspread.Spreadsheet, 
        title: str,
        rows: int = 1000,
        cols: int = 26
    ) -> gspread.Worksheet:
        """
        Get existing worksheet or create new one.
        
        Args:
            spreadsheet: Parent spreadsheet
            title: Worksheet title
            rows: Initial row count (default 1000)
            cols: Initial column count (default 26)
            
        Returns:
            gspread.Worksheet object
        """
        try:
            worksheet = spreadsheet.worksheet(title)
            logger.info(f"Found existing worksheet: {title}")
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Creating new worksheet: {title}")
            return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
    
    @backoff.on_exception(
        backoff.expo,
        (gspread.exceptions.APIError, HttpError),
        max_tries=5
    )
    def update_worksheet(
        self,
        worksheet: gspread.Worksheet,
        data: List[List[Any]],
        start_cell: str = 'A1'
    ) -> None:
        """
        Update worksheet with data using batch update.
        
        Args:
            worksheet: Target worksheet
            data: 2D list of values [[row1], [row2], ...]
            start_cell: Starting cell (default 'A1')
        """
        logger.info(f"Updating {len(data)} rows to worksheet '{worksheet.title}'")
        worksheet.update(start_cell, data)
    
    @backoff.on_exception(
        backoff.expo,
        (gspread.exceptions.APIError, HttpError),
        max_tries=5
    )
    def append_rows(
        self,
        worksheet: gspread.Worksheet,
        rows: List[List[Any]]
    ) -> None:
        """
        Append rows to worksheet.
        
        Args:
            worksheet: Target worksheet
            rows: List of rows to append
        """
        logger.info(f"Appending {len(rows)} rows to worksheet '{worksheet.title}'")
        worksheet.append_rows(rows)
    
    def dataframe_to_sheet(
        self,
        df: pd.DataFrame,
        spreadsheet_id: str,
        worksheet_title: str,
        include_index: bool = False
    ) -> None:
        """
        Write pandas DataFrame to Google Sheets.
        
        Args:
            df: DataFrame to write
            spreadsheet_id: Target spreadsheet ID
            worksheet_title: Target worksheet title
            include_index: Whether to include DataFrame index
        """
        spreadsheet = self.open_spreadsheet(spreadsheet_id)
        worksheet = self.get_or_create_worksheet(spreadsheet, worksheet_title)
        
        # Clear existing content
        worksheet.clear()
        
        # Prepare data
        if include_index:
            df = df.reset_index()

        # Replace NaN/inf with None for JSON compliance
        df_cleaned = df.replace([np.inf, -np.inf], None)
        df_cleaned = df_cleaned.where(pd.notna(df_cleaned), None)
        
        # Convert to list of lists (header + data)
        data = [df_cleaned.columns.tolist()] + df_cleaned.values.tolist()
        
        # Final safety pass to catch any remaining non-JSON values
        def _sanitize(val):
            if val is None or isinstance(val, (str, bool)):
                return val
            try:
                if isinstance(val, (float, np.floating)):
                    if not np.isfinite(val):
                        return None
                return val
            except:
                return str(val)
        
        data = [[_sanitize(cell) for cell in row] for row in data]
        
        # Update worksheet
        self.update_worksheet(worksheet, data)
        logger.info(f"Successfully wrote {len(df)} rows to '{worksheet_title}'")
    
    def sheet_to_dataframe(
        self,
        spreadsheet_id: str,
        worksheet_title: str
    ) -> pd.DataFrame:
        """
        Read Google Sheets worksheet into pandas DataFrame.
        
        Args:
            spreadsheet_id: Source spreadsheet ID
            worksheet_title: Source worksheet title
            
        Returns:
            pandas DataFrame
        """
        spreadsheet = self.open_spreadsheet(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_title)
        
        # Get all records as list of dicts
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        
        logger.info(f"Read {len(df)} rows from '{worksheet_title}'")
        return df
    
    @backoff.on_exception(
        backoff.expo,
        (gspread.exceptions.APIError, HttpError),
        max_tries=5
    )
    def batch_update(
        self,
        spreadsheet_id: str,
        requests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute batch update requests on spreadsheet.
        
        Args:
            spreadsheet_id: Target spreadsheet ID
            requests: List of update request objects
            
        Returns:
            API response dictionary
        """
        body = {'requests': requests}
        logger.info(f"Executing {len(requests)} batch update requests")
        response = self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()
        return response
    
    def format_header_row(
        self,
        spreadsheet_id: str,
        worksheet_id: int,
        bold: bool = True,
        background_color: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Format the first row as header.
        
        Args:
            spreadsheet_id: Target spreadsheet ID
            worksheet_id: Worksheet ID (not title)
            bold: Make header text bold
            background_color: RGB dict like {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            
        Returns:
            API response
        """
        if background_color is None:
            background_color = {'red': 0.9, 'green': 0.9, 'blue': 0.9}
        
        requests = [{
            'repeatCell': {
                'range': {
                    'sheetId': worksheet_id,
                    'startRowIndex': 0,
                    'endRowIndex': 1
                },
                'cell': {
                    'userEnteredFormat': {
                        'textFormat': {'bold': bold},
                        'backgroundColor': background_color
                    }
                },
                'fields': 'userEnteredFormat(textFormat,backgroundColor)'
            }
        }]
        
        return self.batch_update(spreadsheet_id, requests)
