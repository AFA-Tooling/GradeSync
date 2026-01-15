#!/usr/local/bin/python
# Author: Naveen Nathan

import json
from fullGSapi.api import client as GradescopeClient
import os.path
import re
import io
import time
import warnings
import functools
from googleapiclient.errors import HttpError
import gspread
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import backoff
import csv
import pandas as pd
import backoff_utils
import requests
from datetime import datetime
from difflib import SequenceMatcher
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from api.config_loader import load_config, DEFAULT_SCOPES

load_dotenv()
GRADESCOPE_EMAIL = os.getenv("GRADESCOPE_EMAIL")
GRADESCOPE_PASSWORD = os.getenv("GRADESCOPE_PASSWORD")
USE_DB_AS_PRIMARY = os.getenv("USE_DB_AS_PRIMARY", "true").lower() in ("1", "true", "yes")

import logging

# Configure logging to output to both file and console
logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more detail
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Logs to console (stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info("Starting the gradescope_to_spreadsheet script.")

# Load JSON variables
class_json_name = 'courses.json'
config_path = os.path.join(os.path.dirname(__file__), '..', 'config', class_json_name)
config = load_config(config_path)

# IDs to link files
GRADESCOPE_COURSE_ID = config["gradescope_course_id"]
SCOPES = config.get("scopes", DEFAULT_SCOPES)
SPREADSHEET_ID = config["spreadsheet_id"]


def get_number_of_students():
    """Get dynamic student count from database."""
    try:
        from api import summary_from_db
        summary_data = summary_from_db.get_summary_data_from_db(str(GRADESCOPE_COURSE_ID))
        return len(summary_data.get('students', []))
    except Exception as e:
        logger.warning(f"Failed to get student count from DB: {e}, using default 200")
        return 200  # Fallback default


# These constants are deprecated. 
# The following explanation is for what their purpose was: 
# ASSIGNMENT_ID is for users who wish to generate a sub-sheet (not update the dashboard) for one assignment. 
# ASSIGNMENT_NAME specifies the name of the subsheet where grades for the assignment are to be stored. 
# They are populated using the first and second command-line args respectively.

ASSIGNMENT_ID = (len(sys.argv) > 1) and sys.argv[1]
ASSIGNMENT_NAME = (len(sys.argv) > 2) and sys.argv[2]
"""
Explanation of GRADE_RETRIEVAL_SPREADSHEET_FORMULA:
[Grade data for assignment] =XLOOKUP([Search key (student id)], [Range of sid in assignment subsheet], [Range of grades in assignment subsheet])
[Range of sid in assignment subsheet as a string] =INDIRECT( [Name of assignment subsheet] & [Column range of sids in assignment subsheet])
[Name of assignment subsheet, as retrieved from first cell in column] =INDIRECT(ADDRESS(1, COLUMN(), 4))

DISCUSSION_COMPLETION_INDICATOR_FORMULA uses similar logic, but includes a condition that checks whether a discussion has been submitted or is missing. 
A submitted discussion is awarded full credit; discussions are not manually graded.
"""
# Updated these two lines, given the updated CSV return format of GradeScope

# # Formula for Fall 2025 GradeScope Instance
GRADE_RETRIEVAL_SPREADSHEET_FORMULA = '=XLOOKUP(C:C, INDIRECT( INDIRECT(ADDRESS(1, COLUMN(), 4)) & "!B:B"), INDIRECT(INDIRECT(ADDRESS(1, COLUMN(), 4)) & "!E:E"))'
DISCUSSION_COMPLETION_INDICATOR_FORMULA = '=IF(XLOOKUP($C:$C, INDIRECT(INDIRECT(ADDRESS(1,COLUMN(),4)) & "!B:B"), INDIRECT(INDIRECT(ADDRESS(1,COLUMN(),4)) & "!G:G")) = "Missing", 0, 1)'
# #For autoreminder test
# GRADE_RETRIEVAL_SPREADSHEET_FORMULA = '=XLOOKUP(C:C, INDIRECT( INDIRECT(ADDRESS(1, COLUMN(), 4)) & "!C:C"), INDIRECT(INDIRECT(ADDRESS(1, COLUMN(), 4)) & "!E:E"))'
# DISCUSSION_COMPLETION_INDICATOR_FORMULA = '=IF(XLOOKUP($C:$C, INDIRECT(INDIRECT(ADDRESS(1,COLUMN(),4)) & "!C:C"), INDIRECT(INDIRECT(ADDRESS(1,COLUMN(),4)) & "!G:G")) = "Missing", 0, 1)'
# This is not a constant; it is a variable that needs global scope. It should not be modified by the user
subsheet_titles_to_ids = None
# Tracking the number of_attempts to_update a sheet.
number_of_retries_needed_to_update_sheet = 0

request_list = []

# Global list to track all created/updated assignment sub-sheets for the index
assignment_sheets_created = []

# Define a depracated decorator to warn users about deprecated functions.
def deprecated(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"'{func.__name__}' is deprecated and will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2
        )
        return func(*args, **kwargs)
    return wrapper

# Connect the script to the Google Sheets API through authorizing the google cloud service account
# The service account is created in order to automatically run the script in a Google Cloud Run Service through the docker containerization of a cron job.
credentials_json = os.getenv("SERVICE_ACCOUNT_CREDENTIALS")
credentials_dict = json.loads(credentials_json)
credentials = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
client = gspread.authorize(credentials)

def create_sheet_and_request_to_populate_it(sheet_api_instance, assignment_scores, assignment_name = ASSIGNMENT_NAME):
    """
    Creates a sheet and adds the request that will populate the sheet to request_list.
    When USE_DB_AS_PRIMARY is True, skips sheet creation (data is in DB instead).

    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
        assignment_scores (String): The csv containing assignment scores
        assignment_name (String): The name of the assignment as listed on Gradescope

    Returns:
        None: This function does not return a value.
    """
    global number_of_retries_needed_to_update_sheet, assignment_sheets_created, subsheet_titles_to_ids
    
    # Skip per-assignment sheet creation when using DB as primary storage
    if USE_DB_AS_PRIMARY:
        logger.info(f"Skipping sheet creation for '{assignment_name}' (USE_DB_AS_PRIMARY=true)")
        return
    
    try:
        # Keep assignment name exactly as provided (do not strip whitespace)
        sub_sheet_titles_to_ids = get_sub_sheet_titles_to_ids(sheet_api_instance)
        
        if assignment_name not in sub_sheet_titles_to_ids:
            logger.info(f"Sheet '{assignment_name}' does not exist, creating new sheet")
            create_sheet_rest_request = {
                "requests": {
                    "addSheet": {
                        "properties": {
                            "title": assignment_name
                        }
                    }
                }
            }
            request = sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=create_sheet_rest_request)
            response = make_request(request)
            sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
            # Update the global cache with the newly created sheet
            subsheet_titles_to_ids[assignment_name] = sheet_id
            assignment_sheets_created.append(assignment_name)
            logger.info(f"Created new sheet '{assignment_name}' with ID {sheet_id}")
        else:
            sheet_id = sub_sheet_titles_to_ids[assignment_name]
            assignment_sheets_created.append(assignment_name)
        assemble_rest_request_for_assignment(assignment_scores, sheet_id)
        logger.info(f"Created sheets request for {assignment_name}")
        number_of_retries_needed_to_update_sheet = 0
    except HttpError as err:
        logger.error(f"An HttpError has occurred while creating sheet for {assignment_name}: {err}")
    except Exception as err:
        logger.error(f"An unknown error has occurred while creating sheet for {assignment_name}: {err}")

def create_sheet_api_instance():
    """
    Creates a sheet api instance through the googleapiclient library.
    The build function references "from googleapiclient.discovery import build" in the imports.

    Returns:
        googleapiclient.discovery.Resource: The sheet api instance.
    """
    service = build("sheets", "v4", credentials=credentials)
    sheet_api_instance = service.spreadsheets()
    return sheet_api_instance


def create_or_get_index_sheet(sheet_api_instance):
    """
    Creates an index sheet (if it doesn't exist) that lists all assignment sub-sheets.
    
    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
    
    Returns:
        str: The sheet ID of the index sheet
    """
    global subsheet_titles_to_ids
    index_sheet_name = "Index"
    
    # Check if index sheet already exists
    if index_sheet_name in subsheet_titles_to_ids:
        return subsheet_titles_to_ids[index_sheet_name]
    
    # Create index sheet if it doesn't exist
    create_sheet_rest_request = {
        "requests": {
            "addSheet": {
                "properties": {
                    "title": index_sheet_name
                }
            }
        }
    }
    request = sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=create_sheet_rest_request)
    response = make_request(request)
    index_sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
    
    # Update the global mapping
    subsheet_titles_to_ids[index_sheet_name] = index_sheet_id
    
    logger.info(f"Created index sheet with ID: {index_sheet_id}")
    return index_sheet_id


def categorize_assignment(assignment_name):
    """
    Categorize an assignment based on its name.
    
    Args:
        assignment_name (str): Name of the assignment
    
    Returns:
        str: Category name
    """
    name_lower = assignment_name.lower()
    
    # Check for different assignment types
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


def get_max_points_for_assignment(sheet_api_instance, assignment_name):
    """
    Get the maximum points for an assignment from its sub-sheet.
    
    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
        assignment_name (str): Name of the assignment sheet
    
    Returns:
        float: Maximum points for the assignment, or 0 if not found
    """
    try:
        # Escape single quotes in sheet name by doubling them
        # Google Sheets requires single quotes to be escaped as ''
        escaped_name = assignment_name.replace("'", "''")
        
        # Get the assignment sheet data
        range_name = f"'{escaped_name}'!1:2"  # Get first two rows
        result = sheet_api_instance.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        if len(values) >= 2:
            headers = values[0]
            # Look for "Max Points" or "Total Points" column
            if 'Max Points' in headers:
                max_points_idx = headers.index('Max Points')
                if len(values[1]) > max_points_idx:
                    try:
                        return float(values[1][max_points_idx])
                    except (ValueError, TypeError):
                        pass
            # Try to find it in "Total Points"
            if 'Total Points' in headers:
                total_points_idx = headers.index('Total Points')
                if len(values[1]) > total_points_idx:
                    try:
                        return float(values[1][total_points_idx])
                    except (ValueError, TypeError):
                        pass
        
        # If not found, return a default value (could be improved with better heuristics)
        return 0.0
    except Exception as e:
        logger.warning(f"Could not get max points for {assignment_name}: {e}")
        return 0.0


def populate_summary_sheet_from_db(sheet_api_instance, assignment_id_to_names):
    """
    Creates and populates the Summary sheet from DB data (no formulas).
    
    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
        assignment_id_to_names (dict): Dictionary mapping assignment IDs to assignment names
    """
    global subsheet_titles_to_ids
    from api import summary_from_db
    
    summary_sheet_name = "Summary"
    
    # Get or create Summary sheet
    if summary_sheet_name not in subsheet_titles_to_ids:
        logger.info(f"Creating {summary_sheet_name} sheet...")
        create_sheet_rest_request = {
            "requests": [{
                "addSheet": {
                    "properties": {
                        "title": summary_sheet_name,
                        "index": 0,
                        "gridProperties": {
                            "frozenRowCount": 3,
                            "frozenColumnCount": 2
                        }
                    }
                }
            }]
        }
        request = sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=create_sheet_rest_request)
        response = make_request(request)
        summary_sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
        subsheet_titles_to_ids[summary_sheet_name] = summary_sheet_id
    else:
        summary_sheet_id = subsheet_titles_to_ids[summary_sheet_name]
    
    # Get data from DB
    summary_data = summary_from_db.get_summary_data_from_db(str(GRADESCOPE_COURSE_ID))
    assignment_names = summary_data["assignments"]
    students = summary_data["students"]
    
    logger.info(f"Building Summary from DB: {len(assignment_names)} assignments, {len(students)} students")
    
    # Build header rows
    rows = []
    
    # Row 1: Assignment names
    row1_cells = [
        {"userEnteredValue": {"stringValue": "Legal Name"}},
        {"userEnteredValue": {"stringValue": "Email"}}
    ]
    for assignment_name in assignment_names:
        row1_cells.append({"userEnteredValue": {"stringValue": assignment_name}})
    rows.append({"values": row1_cells})
    
    # Row 2: Category labels
    row2_cells = [
        {"userEnteredValue": {"stringValue": "CATEGORY"}},
        {"userEnteredValue": {"stringValue": "CATEGORY"}}
    ]
    for assignment_name in assignment_names:
        category = summary_from_db.categorize_assignment_for_summary(assignment_name)
        row2_cells.append({"userEnteredValue": {"stringValue": category}})
    rows.append({"values": row2_cells})
    
    # Row 3: Max points
    row3_cells = [
        {"userEnteredValue": {"stringValue": "MAX POINTS"}},
        {"userEnteredValue": {"stringValue": "MAX POINTS"}}
    ]
    for assignment_name in assignment_names:
        max_points = summary_from_db.get_max_points_from_db(str(GRADESCOPE_COURSE_ID), assignment_name)
        row3_cells.append({"userEnteredValue": {"numberValue": max_points}})
    rows.append({"values": row3_cells})
    
    # Student rows with actual values from DB
    for student in students:
        student_cells = [
            {"userEnteredValue": {"stringValue": student["legal_name"]}},
            {"userEnteredValue": {"stringValue": student["email"]}}
        ]
        for assignment_name in assignment_names:
            score = student["scores"].get(assignment_name, "")
            if isinstance(score, (int, float)):
                student_cells.append({"userEnteredValue": {"numberValue": float(score)}})
            else:
                student_cells.append({"userEnteredValue": {"stringValue": str(score)}})
        rows.append({"values": student_cells})
    
    # Ensure sheet has enough rows/columns
    required_columns = 2 + len(assignment_names)
    required_rows = 3 + len(students)
    
    resize_request = {
        "updateSheetProperties": {
            "properties": {
                "sheetId": summary_sheet_id,
                "gridProperties": {
                    "rowCount": required_rows,
                    "columnCount": required_columns
                }
            },
            "fields": "gridProperties.rowCount,gridProperties.columnCount"
        }
    }
    store_request(resize_request)
    
    # Create update request
    update_request = {
        "updateCells": {
            "range": {
                "sheetId": summary_sheet_id,
                "startRowIndex": 0,
                "startColumnIndex": 0,
                "endRowIndex": len(rows),
                "endColumnIndex": required_columns
            },
            "rows": rows,
            "fields": "userEnteredValue"
        }
    }
    store_request(update_request)
    logger.info(f"Created DB-backed Summary with {len(assignment_names)} assignments and {len(students)} students")


def populate_summary_sheet(sheet_api_instance, assignment_id_to_names):
    """
    Creates and populates the Summary sheet with all assignments.
    When USE_DB_AS_PRIMARY is True, reads data from DB instead of using XLOOKUP formulas.
    Format matches the H Dynamic CM Test Sheet with:
    - Row 1: Legal Name, Email, Assignment names
    - Row 2: CATEGORY, CATEGORY, Category labels
    - Row 3: MAX POINTS, MAX POINTS, Max points for each assignment
    - Following rows: Student data (formulas if Sheets-only, values if DB-backed)
    
    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
        assignment_id_to_names (dict): Dictionary mapping assignment IDs to assignment names
    
    Returns:
        None
    """
    global subsheet_titles_to_ids
    
    # If using DB, delegate to DB-backed summary generation
    if USE_DB_AS_PRIMARY:
        populate_summary_sheet_from_db(sheet_api_instance, assignment_id_to_names)
        return
    
    summary_sheet_name = "Summary"
    
    # Create or get Summary sheet
    if summary_sheet_name not in subsheet_titles_to_ids:
        logger.info(f"Creating {summary_sheet_name} sheet...")
        create_sheet_rest_request = {
            "requests": [{
                "addSheet": {
                    "properties": {
                        "title": summary_sheet_name,
                        "index": 0,  # Place at the beginning
                        "gridProperties": {
                            "frozenRowCount": 3,  # Freeze header rows
                            "frozenColumnCount": 2  # Freeze Name and Email columns
                        }
                    }
                }
            }]
        }
        request = sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=create_sheet_rest_request)
        response = make_request(request)
        summary_sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
        subsheet_titles_to_ids[summary_sheet_name] = summary_sheet_id
        logger.info(f"Created {summary_sheet_name} sheet with ID: {summary_sheet_id}")
    else:
        summary_sheet_id = subsheet_titles_to_ids[summary_sheet_name]
        logger.info(f"Using existing {summary_sheet_name} sheet with ID: {summary_sheet_id}")
        # Move to index 0 if it already exists
        move_request = {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": summary_sheet_id,
                    "index": 0
                },
                "fields": "index"
            }
        }
        store_request(move_request)
    
    # Filter non-optional assignments
    is_not_optional = lambda assignment: not "optional" in assignment.lower()
    assignment_names = [name for name in assignment_id_to_names.values() if is_not_optional(name)]
    
    # Categorize and sort assignments by category
    def extract_number_from_assignment_title(assignment):
        numbers_present = re.findall(r"\d+", assignment)
        return int(numbers_present[0]) if numbers_present else 0
    
    # Group assignments by category
    assignments_by_category = {
        'Quest (pre-clobber)': [],
        'Midterm (pre-clobber)': [],
        'Postterm': [],
        'Projects': [],
        'Labs (before dropping lowest two)': [],
        'Discussions': []
    }
    
    for assignment_name in assignment_names:
        category = categorize_assignment(assignment_name)
        if category in assignments_by_category:
            assignments_by_category[category].append(assignment_name)
    
    # Sort each category
    for category in assignments_by_category:
        assignments_by_category[category].sort(key=extract_number_from_assignment_title)
    
    # Build ordered assignment list (Quest -> Midterm -> Postterm -> Projects -> Labs)
    ordered_assignments = []
    for category in ['Quest (pre-clobber)', 'Midterm (pre-clobber)', 'Postterm', 'Projects', 'Labs (before dropping lowest two)']:
        ordered_assignments.extend(assignments_by_category[category])
    
    logger.info(f"Summary sheet will contain {len(ordered_assignments)} assignments")
    
    # Calculate required columns: 2 fixed columns (Name, Email) + assignments
    required_columns = 2 + len(ordered_assignments)
    number_of_students = get_number_of_students()
    required_rows = 3 + number_of_students  # 3 header rows + student rows
    
    # Ensure the sheet has enough columns and rows
    logger.info(f"Ensuring Summary sheet has {required_columns} columns and {required_rows} rows")
    resize_request = {
        "updateSheetProperties": {
            "properties": {
                "sheetId": summary_sheet_id,
                "gridProperties": {
                    "rowCount": required_rows,
                    "columnCount": required_columns
                }
            },
            "fields": "gridProperties.rowCount,gridProperties.columnCount"
        }
    }
    store_request(resize_request)
    
    # Build the three header rows
    rows = []
    
    # Row 1: Assignment names
    row1_cells = [
        {"userEnteredValue": {"stringValue": "Legal Name"}},
        {"userEnteredValue": {"stringValue": "Email"}}
    ]
    for assignment_name in ordered_assignments:
        row1_cells.append({"userEnteredValue": {"stringValue": assignment_name}})
    rows.append({"values": row1_cells})
    
    # Row 2: Category labels
    row2_cells = [
        {"userEnteredValue": {"stringValue": "CATEGORY"}},
        {"userEnteredValue": {"stringValue": "CATEGORY"}}
    ]
    for assignment_name in ordered_assignments:
        category = categorize_assignment(assignment_name)
        row2_cells.append({"userEnteredValue": {"stringValue": category}})
    rows.append({"values": row2_cells})
    
    # Row 3: Max points
    row3_cells = [
        {"userEnteredValue": {"stringValue": "MAX POINTS"}},
        {"userEnteredValue": {"stringValue": "MAX POINTS"}}
    ]
    for assignment_name in ordered_assignments:
        max_points = get_max_points_for_assignment(sheet_api_instance, assignment_name)
        row3_cells.append({"userEnteredValue": {"numberValue": max_points}})
    rows.append({"values": row3_cells})
    
    # Verify all header rows have the same column count
    expected_cols = 2 + len(ordered_assignments)
    logger.info(f"Header rows: Row1={len(row1_cells)} cols, Row2={len(row2_cells)} cols, Row3={len(row3_cells)} cols, Expected={expected_cols}")
    
    # Row 4+: Student data with formulas
    # Use XLOOKUP formulas to pull data from individual assignment sheets
    for student_row_idx in range(number_of_students):
        student_cells = [
            # Legal Name from Labs sheet
            {"userEnteredValue": {"formulaValue": f"=IFERROR(Labs!A{student_row_idx+2},\"\")"}},
            # Email from Labs sheet  
            {"userEnteredValue": {"formulaValue": f"=IFERROR(Labs!B{student_row_idx+2},\"\")"}}  
        ]
        
        # For each assignment, create XLOOKUP formula
        for assignment_name in ordered_assignments:
            # Escape single quotes in sheet name for formula
            escaped_name = assignment_name.replace("'", "''")
            # Formula: =XLOOKUP($B5, '{SheetName}'!$C:$C, '{SheetName}'!$E:$E, "")
            # This looks up the email in column B of Summary, finds it in column C (Email) of the assignment sheet,
            # and returns the corresponding grade from column E (Score column)
            # Use row number starting from 4 (after 3 header rows)
            formula = f"=IFERROR(XLOOKUP($B{student_row_idx+4},'{escaped_name}'!$C:$C,'{escaped_name}'!$E:$E),\"\")"
            student_cells.append({"userEnteredValue": {"formulaValue": formula}})
        
        rows.append({"values": student_cells})
        
        # Verify first student row column count (for debugging)
        if student_row_idx == 0:
            logger.info(f"First student row has {len(student_cells)} columns, expected {expected_cols}")
    
    # Verify all rows have consistent column counts before creating the request
    all_cols_consistent = True
    for idx, row in enumerate(rows):
        if len(row["values"]) != expected_cols:
            logger.error(f"Row {idx} has {len(row['values'])} columns, expected {expected_cols}")
            all_cols_consistent = False
    
    if not all_cols_consistent:
        logger.error("Column count mismatch detected! Aborting Summary sheet update.")
        return
    
    # Create the update request
    update_request = {
        "updateCells": {
            "range": {
                "sheetId": summary_sheet_id,
                "startRowIndex": 0,
                "startColumnIndex": 0,
                "endRowIndex": len(rows),
                "endColumnIndex": expected_cols
            },
            "rows": rows,
            "fields": "userEnteredValue"
        }
    }
    
    store_request(update_request)
    logger.info(f"Created summary sheet with {len(ordered_assignments)} assignment columns and {number_of_students} student rows")


def populate_index_sheet(sheet_api_instance, assignment_id_to_names):
    """
    Populates the index sheet with a list of all assignment sub-sheets.
    Each assignment name is a clickable hyperlink that jumps to the corresponding sub-sheet.
    
    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
        assignment_id_to_names (dict): Dictionary mapping assignment IDs to assignment names
    
    Returns:
        None
    """
    global subsheet_titles_to_ids, assignment_sheets_created
    
    # Get or create the index sheet
    index_sheet_id = create_or_get_index_sheet(sheet_api_instance)
    
    # Get all current sheets to filter assignments
    is_not_optional = lambda assignment: not "optional" in assignment.lower()
    assignment_names = sorted([name for name in assignment_id_to_names.values() if is_not_optional(name)])
    
    logger.info(f"Total assignments from Gradescope: {len(assignment_id_to_names)}")
    logger.info(f"Non-optional assignments: {len(assignment_names)}")
    logger.info(f"Sheets created in Google Sheets: {len(subsheet_titles_to_ids) if subsheet_titles_to_ids else 0}")
    
    # Build update request using updateCells API instead of CSV to handle formulas correctly
    # This allows us to set formulas and values without CSV quoting issues
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    rows = []
    
    # Header row
    header_cells = [
        {"userEnteredValue": {"stringValue": "Assignment Name"}},
        {"userEnteredValue": {"stringValue": "Link to Sheet"}},
        {"userEnteredValue": {"stringValue": "Status"}}
    ]
    rows.append({"values": header_cells})
    
    # Data rows
    actual_row_idx = 1  # Track actual row index for formula references
    for assignment_name in assignment_names:
        if assignment_name in subsheet_titles_to_ids:
            sheet_id = subsheet_titles_to_ids[assignment_name]
            status = current_time if assignment_name in assignment_sheets_created else "Existing"
            
            # Create cells for this row
            cells = [
                {"userEnteredValue": {"stringValue": assignment_name}},
                # Use formula that references the assignment name in column A
                {"userEnteredValue": {"formulaValue": f'=HYPERLINK("#gid={sheet_id}",A{actual_row_idx+1})'}},
                {"userEnteredValue": {"stringValue": status}}
            ]
            rows.append({"values": cells})
            actual_row_idx += 1
        else:
            logger.warning(f"Assignment '{assignment_name}' from Gradescope not found in Google Sheets")
    
    # Create the update request
    update_request = {
        "updateCells": {
            "range": {
                "sheetId": index_sheet_id,
                "startRowIndex": 0,
                "startColumnIndex": 0,
                "endRowIndex": len(rows),
                "endColumnIndex": 3  # We have 3 columns: Assignment Name, Link to Sheet, Status
            },
            "rows": rows,
            "fields": "userEnteredValue"
        }
    }
    
    store_request(update_request)
    logger.info(f"Created index with {len(rows)-1} clickable links to assignment sheets")

def get_sub_sheet_titles_to_ids(sheet_api_instance, force_refresh=False):
    """
    If subsheet_titles_to_ids, a dict mapping subsheet titles to sheet ids, has already been created,
    return it. If not, retrieve that info from Google sheets.

    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
        force_refresh (bool): If True, force refresh the cache from Google Sheets

    Returns:
        dict: A dict mapping subsheet names (titles) to sheet ids.
    """
    global subsheet_titles_to_ids
    if subsheet_titles_to_ids and not force_refresh:
        return subsheet_titles_to_ids
    logger.info("Retrieving subsheet titles to ids")
    request = sheet_api_instance.get(spreadsheetId=SPREADSHEET_ID, fields='sheets/properties')
    sheets = make_request(request)
    # Strip whitespace from sheet titles to ensure consistent naming
    subsheet_titles_to_ids = {sheet['properties']['title'].strip(): sheet['properties']['sheetId'] for sheet in
                               sheets['sheets']}
    return subsheet_titles_to_ids


def get_sheets_to_delete(assignment_id_to_names, sheet_titles_to_ids):
    """
    Identifies sheets in Google Sheets that are not in the Gradescope assignment list.
    These should be deleted to maintain consistency.
    
    Args:
        assignment_id_to_names (dict): Dictionary of assignment IDs to names from Gradescope
        sheet_titles_to_ids (dict): Dictionary of sheet titles to IDs from Google Sheets
        
    Returns:
        list: List of (sheet_id, sheet_title) tuples to delete
    """
    gradescope_names = set(assignment_id_to_names.values())
    
    # Reserved sheets that should never be deleted
    # Includes category sheets, index, and other summary/utility sheets
    reserved_sheets = {
        "Dashboard",
        "Labs",
        "Discussions",
        "Projects",
        "Lecture Quizzes",
        "Midterms",
        "Postterms",
        "Index",
        "Roster",
        "Pyturis",
        "PrarieLearn Gradebook"
    }
    
    sheets_to_delete = []
    for sheet_title, sheet_id in sheet_titles_to_ids.items():
        # Skip reserved sheets
        if sheet_title in reserved_sheets:
            continue
        
        # Check if this sheet exists in Gradescope
        if sheet_title not in gradescope_names:
            sheets_to_delete.append((sheet_id, sheet_title))
            logger.info(f"Marked for deletion: '{sheet_title}' (not in Gradescope)")
    
    return sheets_to_delete


def delete_sheets(sheet_api_instance, sheets_to_delete):
    """
    Deletes the specified sheets from Google Sheets.
    
    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
        sheets_to_delete (list): List of (sheet_id, sheet_title) tuples to delete
        
    Returns:
        None
    """
    if not sheets_to_delete:
        logger.info("No sheets to delete")
        return
    
    logger.info(f"Deleting {len(sheets_to_delete)} inconsistent sheets...")
    delete_requests = []
    for sheet_id, sheet_title in sheets_to_delete:
        logger.info(f"Deleting sheet: {sheet_title}")
        delete_request = {
            "deleteSheet": {
                "sheetId": sheet_id
            }
        }
        delete_requests.append(delete_request)
    
    batch_delete_request = {
        "requests": delete_requests
    }
    
    try:
        batch_delete = sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=batch_delete_request)
        make_request(batch_delete)
        logger.info(f"Successfully deleted {len(sheets_to_delete)} sheets")
    except HttpError as err:
        logger.error(f"Error deleting sheets: {err}")


def is_429_error(exception):
    """
    A 429 error is the error returned when the rate limit is exceeded. 
    This function determines whether we have encountered a rate limit error or 
    an error we should be concerned about.

    Args:
        exception (Exception): An Exception

    Returns:
        bool: A dict mapping subsheet names (titles) to sheet ids.
    """
    return isinstance(exception, HttpError) and exception.resp.status == 429

def backoff_handler(backoff_response=None):
    """
    Count the number of retries needed to execute the request.

    Args:
        backoff_response (Exception): An Exception

    Returns:
        None
    """
    global number_of_retries_needed_to_update_sheet
    number_of_retries_needed_to_update_sheet += 1
    pass


def store_request(request):
    """
    Stores a request in a running list, request_list, to be executed in a batch request.

    Args:
        request (dict): A Google sheets API pasteData request with the schema defined here: 
        https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/request#PasteDataRequest
    Returns:
        None
    """
    request_list.append(request)


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=5,
    on_backoff=backoff_handler,
    giveup=lambda e: not is_429_error(e)
)
def make_request(request):
    """
    Makes one request (with backoff logic)

    Args:
        request (dict): A Google sheets API rest request of any type.
    Returns:
        None
    """
    logger.info(f"Making request: {request}")
    try:
        response = request.execute()
        logger.info(f"Request completed successfully")
        return response
    except HttpError as e:
        logger.error(f"HttpError in make_request: {e.content.decode('utf-8') if hasattr(e, 'content') else str(e)}")
        raise


def assemble_rest_request_for_assignment(assignment_scores, sheet_id, rowIndex = 0, columnIndex=0):
    """
    Assembles a request to populate one sheet with data.

    Args:
        assignment_scores (String):
        sheet_id (int): sheet ID of subsheet where the given assignment's grades are stored.
        rowIndex (int): Index of the row of the cell where grades are to be pasted.
        columnIndex (int): Index of the column of the cell where grades are to be pasted.
    Returns:
        dict: A Google sheets API pasteData request with the schema defined here: 
        https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/request#PasteDataRequest
    """
    push_grade_data_rest_request = {
            'pasteData': {
                    "coordinate": {
                        "sheetId": sheet_id,
                        "rowIndex": rowIndex,
                        "columnIndex": columnIndex,
                    },
                    "data": assignment_scores,
                    "type": 'PASTE_NORMAL',
                    "delimiter": ',',
            }
    }
    store_request(push_grade_data_rest_request)
    return push_grade_data_rest_request

def retrieve_preexisting_columns(assignment_type, sheet_api_instance):
    """
    Retrieves the columns in the subsheet corresponding to a given assignment type.

    Args:
        assignment_type (String): One of the following assignment types: ["Labs", "Discussions", "Projects", "Midterms", "Postterms"]
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
    Returns:
        None
    """
    range = f'{assignment_type}!1:1'
    result = sheet_api_instance.values().get(spreadsheetId=SPREADSHEET_ID, range=range).execute()
    first_row = result.get('values', [])
    return first_row[0][3:]


def normalize_name_for_matching(name):
    """
    Normalizes assignment names for fuzzy matching.
    Removes extra spaces, normalizes special characters, and handles case-insensitive matching.
    Handles variations like:
    - Case differences (With vs with)
    - Extra characters at end (trailing 's')
    - Punctuation differences (colon+dash vs colon+space)
    - Missing/extra text in parentheses
    
    Args:
        name (str): The assignment name to normalize
        
    Returns:
        str: Normalized name for comparison
    """
    if not name:
        return ""
    
    # Convert to lowercase for case-insensitive matching
    normalized = name.lower().strip()
    
    # Remove common trailing artifacts (trailing s, extra spaces)
    normalized = re.sub(r's+$', '', normalized)  # Remove trailing 's' characters
    normalized = re.sub(r'\s+$', '', normalized)  # Remove trailing spaces
    
    # Normalize punctuation: convert various dash/colon patterns to a standard form
    # "Project 4: RESUBMISSION - Artifact" -> "project 4: resubmission artifact"
    # "Project 4 RESUBMISSION: Artifact" -> "project 4 resubmission artifact"
    normalized = re.sub(r':\s*-\s*', ': ', normalized)  # ": -" -> ": "
    normalized = re.sub(r'-\s+', ' ', normalized)  # "- " -> " "
    normalized = re.sub(r'\s*:\s*', ': ', normalized)  # Normalize colons
    
    # Normalize parenthetical content - collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)  # Collapse multiple spaces to one
    
    # Remove extra characterization like "with snap!" or "with python" variations
    # This helps match "Postterm 2: with Snap!" vs "Postterm 2: With Snap! (HOFs)"
    # by removing the parenthetical parts for the base comparison
    base_normalized = re.sub(r'\s*\([^)]*\)\s*', '', normalized)  # Remove all parenthetical content
    base_normalized = re.sub(r'\s+', ' ', base_normalized)  # Clean up spacing after removal
    
    return base_normalized


def find_matching_sheet_name(column_name, available_sheets):
    """
    Finds a matching sheet name for a given column name from the gradebook.
    Handles minor naming differences through multiple matching strategies:
    1. Exact match
    2. Normalized match (case, punctuation, extra characters)
    3. Prefix/substring matching (for cases where column name has extra info)
    4. Similarity matching (for cases with significant textual differences)
    
    Args:
        column_name (str): The column name from the gradebook
        available_sheets (dict): Dictionary of available sheet names to IDs
        
    Returns:
        str: The matching sheet name, or the original column_name if not found
    """
    # First try exact match
    if column_name in available_sheets:
        return column_name
    
    # Try normalized matching
    normalized_column = normalize_name_for_matching(column_name)
    for sheet_name in available_sheets.keys():
        if normalize_name_for_matching(sheet_name) == normalized_column:
            return sheet_name
    
    # Try prefix matching - check if column_name starts with a sheet name
    # This handles cases like "Discussion 13: Concurrency + Postterm Practice" 
    # matching to "Discussion 13: Postterm Practice"
    for sheet_name in available_sheets.keys():
        norm_sheet = normalize_name_for_matching(sheet_name)
        if norm_sheet and normalized_column.startswith(norm_sheet):
            return sheet_name
    
    # Try reverse prefix matching - check if sheet name starts with column name
    # This handles cases where sheet name has more specific info than column
    for sheet_name in available_sheets.keys():
        norm_sheet = normalize_name_for_matching(sheet_name)
        if norm_sheet and norm_sheet.startswith(normalized_column):
            return sheet_name
    
    # Try similarity matching as last resort
    # Find the sheet with highest similarity score to the column name
    best_match = None
    best_score = 0.6  # Minimum threshold for a "good enough" match
    
    for sheet_name in available_sheets.keys():
        # Calculate similarity between normalized versions
        norm_sheet = normalize_name_for_matching(sheet_name)
        # Use SequenceMatcher to calculate similarity ratio
        similarity = SequenceMatcher(None, normalized_column, norm_sheet).ratio()
        
        if similarity > best_score:
            best_score = similarity
            best_match = sheet_name
    
    if best_match:
        logger.info(f"Found similarity match for column '{column_name}' to sheet '{best_match}' (score: {best_score:.2f})")
        return best_match
    
    # If no match found, return original and log warning
    logger.warning(f"No matching sheet found for column '{column_name}'. Available sheets: {list(available_sheets.keys())}")
    return column_name


def retrieve_grades_from_gradescope(gradescope_client, assignment_id = ASSIGNMENT_ID, assignment_name=None):
    """
    Retrieves grades for one GradeScope assignment in csv form and persists raw CSV locally.

    Args:
        gradescope_client (GradescopeClient): Gradescope API client
        assignment_id (str): The Gradescope assignment ID
        assignment_name (str): Optional human-readable assignment title
    Returns:
        str: CSV contents as a string
    """
    assignment_scores_bytes = gradescope_client.download_scores(GRADESCOPE_COURSE_ID, assignment_id)
    logger.debug(f"download_scores returned type: {type(assignment_scores_bytes)}")
    logger.debug(f"First 100 chars: {str(assignment_scores_bytes)[:100]}")
    assignment_scores = assignment_scores_bytes.decode('utf-8') if isinstance(assignment_scores_bytes, bytes) else assignment_scores_bytes
    logger.debug(f"After decode, type: {type(assignment_scores)}")
    logger.debug(f"First 100 chars after decode: {assignment_scores[:100]}")

    # Persist raw CSV to disk for audit/backfill
    try:
        csv_dir = os.path.join(os.path.dirname(__file__), 'data', 'gradescope_csvs', str(GRADESCOPE_COURSE_ID))
        os.makedirs(csv_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%dT%H%M%S')
        safe_name = (assignment_name or str(assignment_id)).replace('/', '_').replace(' ', '_')
        filename = f'assignment_{assignment_id}_{safe_name}_{ts}.csv'
        filepath = os.path.join(csv_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as fh:
            fh.write(assignment_scores)
        logger.info(f"Saved assignment CSV to {filepath}")

        # Ingest into DB (if configured)
        try:
            from api import ingest
            use_db = os.getenv('USE_DB_AS_PRIMARY', 'true').lower() in ('1', 'true', 'yes')
            if use_db:
                ingest.write_assignment_scores_to_db(
                    str(GRADESCOPE_COURSE_ID), 
                    str(assignment_id), 
                    assignment_name or filename, 
                    filepath,
                    spreadsheet_id=SPREADSHEET_ID,
                    course_name=config.get('course_name', f"CS10 {config.get('semester', '')}").strip(),
                    department=config.get('department'),
                    course_number=config.get('course_number'),
                    semester=config.get('semester'),
                    year=config.get('year'),
                    instructor=config.get('staff', {}).get('instructor')
                )
        except Exception as e:
            logger.exception(f"Failed to ingest CSV into DB for assignment {assignment_id}: {e}")
    except Exception as e:
        logger.exception(f"Failed saving CSV for assignment {assignment_id}: {e}")

    return assignment_scores


def initialize_gs_client():
    """
    Initializes GradeScope API client.

    Returns:
        (GradescopeClient): GradeScope API client.
    """
    gradescope_client = GradescopeClient.GradescopeClient()
    gradescope_client.log_in(GRADESCOPE_EMAIL, GRADESCOPE_PASSWORD)
    return gradescope_client


def get_assignment_info(gs_instance, class_id: str) -> bytes:
    """
    Retrieves contents of GradeScope's "assignments" page for a course, which is used to determine the mapping of assignment name to assignment id.

    Args:
        gs_instance (GradescopeClient): Gradescope API client.
        class_id (String): The Gradescope class ID of the course.
    Returns:
        (String): Contents of GradeScope's "assignments" page for a course
    """
    if not gs_instance.logged_in:
        logger.error("You must be logged in to download grades!")
        return False
    gs_instance.last_res = res = gs_instance.session.get(f"https://www.gradescope.com/courses/{class_id}/assignments")
    if not res or not res.ok:
        logger.error(f"Failed to get a response from gradescope! Got: {res}")
        return False
    return res.content


def prepare_request_for_one_assignment(sheet_api_instance, gradescope_client, assignment_name = ASSIGNMENT_NAME,
                                       assignment_id=ASSIGNMENT_ID):
    """
    Encapsulates the entire process of creating a request for one assignment, from data retrieval from GradeScope to the sheets request.

    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
        gradescope_client (GradescopeClient): The Gradescope API instance.
        assignment_name (String): The name of the assignment.
        assignment_id (String): The Gradescope assignment ID of the assignment for which grades are to be retrieved.
    Returns:
        None
    """
    assignment_scores = retrieve_grades_from_gradescope(gradescope_client = gradescope_client, assignment_id = assignment_id, assignment_name=assignment_name)
    create_sheet_and_request_to_populate_it(sheet_api_instance, assignment_scores, assignment_name)


def get_assignment_id_to_names(gradescope_client):
    """
    This method returns a dictionary mapping assignment IDs to the names (titles) of GradeScope assignments

    Args:
        gradescope_client (GradescopeClient): The Gradescope API instance.
    Returns:
        dict: A dictionary mapping assignment IDs to the names (titles) of GradeScope assignments (of type String).
    """
    # The response cannot be parsed as a json as is.
    course_info_response = str(get_assignment_info(gradescope_client, GRADESCOPE_COURSE_ID)).replace("\\", "").replace("\\u0026", "&")
    pattern = '{"id":[0-9]+,"title":"[^}"]+?"}'
    info_for_all_assignments = re.findall(pattern, course_info_response)
    assignment_to_names = {}
    #  = { json.loads(assignment)['id'] : json.loads(assignment)['title'] for assignment in info_for_all_assignments }
    for assignment in info_for_all_assignments:
        assignment_as_json = json.loads(assignment)
        # Keep assignment titles exactly as they appear in Gradescope (including trailing spaces)
        assignment_to_names[str(assignment_as_json["id"])] = assignment_as_json["title"]
    return assignment_to_names


def make_batch_request(sheet_api_instance):
    """
    Executes a batch request including all requests in our running list: request_list

    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
    Returns:
        None
    """
    global request_list
    if not request_list:
        logger.info("No requests to batch process")
        return
    
    # Debug: Log information about updateCells requests
    for idx, req in enumerate(request_list):
        if "updateCells" in req:
            update_cells = req["updateCells"]
            range_info = update_cells.get("range", {})
            rows = update_cells.get("rows", [])
            
            # Check row column counts
            if rows:
                col_counts = [len(row.get("values", [])) for row in rows]
                max_cols = max(col_counts) if col_counts else 0
                end_col = range_info.get("endColumnIndex")
                start_col = range_info.get("startColumnIndex", 0)
                requested_cols = end_col - start_col if end_col is not None else None
                
                if requested_cols is not None and max_cols != requested_cols:
                    logger.warning(f"Request [{idx}] updateCells potential column mismatch:")
                    logger.warning(f"  startColumnIndex: {start_col}, endColumnIndex: {end_col}")
                    logger.warning(f"  Requested columns: {requested_cols}, Max in rows: {max_cols}")
                    if len(set(col_counts)) > 1:
                        logger.warning(f"  Inconsistent row widths: {set(col_counts)}")
    
    rest_batch_request = {
        "requests": request_list
    }
    logger.info(f"Preparing batch request with {len(request_list)} requests")
    batch_request = sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=rest_batch_request)
    logger.info("Issuing batch request")
    try:
        make_request(batch_request)
        logger.info("Completed batch request successfully")
    except HttpError as err:
        logger.error(f"HttpError during batch request: {err}")
        # Don't re-raise, allow the script to continue
    finally:
        request_list = []  # Always clear the request list


def push_all_grade_data_to_sheets():
    """
    Encapsulates the entire process of retrieving grades from GradeScope and pushing to sheets.
    This includes:
    1. Removing inconsistent sheets (sheets in Google Sheets that aren't in Gradescope)
    2. Creating/updating sub-sheets for all assignments
    3. Populating the gradebook with formulas
    4. Updating the index sheet

    Returns:
        None
    """
    gradescope_client = initialize_gs_client()
    assignment_id_to_names = get_assignment_id_to_names(gradescope_client)
    sheet_api_instance = create_sheet_api_instance()
    sheet_titles_to_ids = get_sub_sheet_titles_to_ids(sheet_api_instance)

    # STEP 1: Delete inconsistent sheets that are in Google Sheets but not in Gradescope
    logger.info("Checking for inconsistent sheets to delete...")
    sheets_to_delete = get_sheets_to_delete(assignment_id_to_names, sheet_titles_to_ids)
    if sheets_to_delete:
        delete_sheets(sheet_api_instance, sheets_to_delete)
        # Refresh the sheet mapping after deletion
        sheet_titles_to_ids = get_sub_sheet_titles_to_ids(sheet_api_instance, force_refresh=True)

    # STEP 2: Create/update sub-sheets for all assignments from Gradescope
    logger.info("Creating/updating assignment sub-sheets...")
    for id in assignment_id_to_names:
        prepare_request_for_one_assignment(sheet_api_instance, gradescope_client=gradescope_client,
                                                               assignment_name=assignment_id_to_names[id], assignment_id=id)

    # STEP 3: Populate the gradebook (only in Sheets-only mode)
    if not USE_DB_AS_PRIMARY:
        logger.info("Populating gradebook...")
        populate_spreadsheet_gradebook(assignment_id_to_names, sheet_api_instance)

    # STEP 4: Populate the index sheet with all assignments
    logger.info("Updating index sheet...")
    populate_index_sheet(sheet_api_instance, assignment_id_to_names)

    # STEP 5: Populate the summary sheet
    logger.info("Updating summary sheet...")
    populate_summary_sheet(sheet_api_instance, assignment_id_to_names)

    # STEP 6: Execute all batched requests
    logger.info("Executing batch requests...")
    make_batch_request(sheet_api_instance)
    
    # STEP 7: Update summary_sheets table in database (if using DB)
    if USE_DB_AS_PRIMARY:
        logger.info("Updating summary_sheets table in database...")
        try:
            from api.db import SessionLocal
            from api.models import Course, Assignment, Student, Submission
            from api.ingest import save_summary_sheet_to_db
            
            session = SessionLocal()
            try:
                # Get course data
                course = session.query(Course).filter(
                    Course.gradescope_course_id == str(GRADESCOPE_COURSE_ID)
                ).first()
                
                if course:
                    # Get all data needed for summary sheet
                    assignments = session.query(Assignment).filter(
                        Assignment.course_id == course.id
                    ).all()
                    
                    students = session.query(Student).all()
                    
                    submissions = session.query(Submission).join(Assignment).filter(
                        Assignment.course_id == course.id
                    ).all()
                    
                    submission_lookup = {
                        (sub.assignment_id, sub.student_id): sub 
                        for sub in submissions
                    }
                    
                    course_data = {
                        "course": course,
                        "assignments": assignments,
                        "students": students,
                        "submissions": submission_lookup
                    }
                    
                    # Save to summary_sheets table
                    save_summary_sheet_to_db(str(GRADESCOPE_COURSE_ID), course_data)
                    logger.info("✅ Summary sheet database updated successfully")
                else:
                    logger.warning(f"Course {GRADESCOPE_COURSE_ID} not found in database")
                    
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Failed to update summary_sheets table: {e}")
            # Don't fail the entire process if summary update fails
            logger.exception("Summary sheet update error details:")


def populate_spreadsheet_gradebook(assignment_id_to_names, sheet_api_instance):
    """
    Creates the gradebook, ensuring existing columns remain in order, and encapsulates the process of retrieving grades from GradeScope.

    Args:
        assignment_id_to_names (dict) A dictionary mapping assignment IDs to the names (titles) of GradeScope assignments (of type String).
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance

    Returns:
        None
    """
    is_not_optional =  lambda assignment: not "optional" in assignment.lower()
    assignment_names = set(filter(is_not_optional, assignment_id_to_names.values()))
    
    # The below code is used to filter assignments by category when populating the gradebook.
    filter_by_assignment_category = lambda category: lambda assignment: category in assignment.lower()

    # Labs
    preexisting_lab_columns = retrieve_preexisting_columns("Labs", sheet_api_instance)
    labs = set(filter(filter_by_assignment_category("lab"), assignment_names))
    new_labs = labs - set(preexisting_lab_columns)

    # Discussions
    preexisting_discussion_columns = retrieve_preexisting_columns("Discussions", sheet_api_instance)
    discussions = set(filter(filter_by_assignment_category("discussion"), assignment_names))
    new_discussions = discussions - set(preexisting_discussion_columns)

    # Projects
    preexisting_project_columns = retrieve_preexisting_columns("Projects", sheet_api_instance)
    projects = set(filter(filter_by_assignment_category("project"), assignment_names))
    new_projects = projects - set(preexisting_project_columns)

    # Quizzes
    preexisting_lecture_quiz_columns = retrieve_preexisting_columns("Lecture Quizzes", sheet_api_instance)
    lecture_quizzes = set(filter(filter_by_assignment_category("lecture"), assignment_names))
    new_lecture_quizzes = lecture_quizzes - set(preexisting_lecture_quiz_columns)

    # Midterms
    preexisting_midterm_columns = retrieve_preexisting_columns("Midterms", sheet_api_instance)
    midterms = set(filter(filter_by_assignment_category("midterm"), assignment_names))
    new_midterms = midterms - set(preexisting_midterm_columns)

    filter_postterms = lambda assignment: (("postterm" in assignment.lower()) or ("posterm" in assignment.lower())) and ("discussion" not in assignment.lower())

    preexisting_postterm_columns = retrieve_preexisting_columns("Postterms", sheet_api_instance)
    postterms = set(filter(filter_postterms, assignment_names))
    new_postterms = postterms - set(preexisting_postterm_columns)

    def extract_number_from_assignment_title(assignment):
        """
        Extracts a number from an assignment title

        Args:
            assignment (String) The assignment title

        Returns:
            None
        """
        numbers_present = re.findall("\d+", assignment)
        if numbers_present:
            return int(numbers_present[0])
        return 0


    # Sort all assignments and exams by number
    sorted_new_labs = sorted(new_labs, key=extract_number_from_assignment_title)
    sorted_new_discussions = sorted(new_discussions, key=extract_number_from_assignment_title)
    sorted_new_projects = sorted(new_projects, key=extract_number_from_assignment_title)
    sorted_new_lecture_quizzes = sorted(new_lecture_quizzes, key=extract_number_from_assignment_title)
    sorted_new_midterms = sorted(new_midterms, key=extract_number_from_assignment_title)
    sorted_new_postterms = sorted(new_postterms, key=extract_number_from_assignment_title)

    # The following formulas are used to retrieve grades from the gradebook.
    number_of_students = get_number_of_students()
    formula_list = [GRADE_RETRIEVAL_SPREADSHEET_FORMULA] * number_of_students
    # discussion_formula_list = [DISCUSSION_COMPLETION_INDICATOR_FORMULA]
    discussion_formula_list = [DISCUSSION_COMPLETION_INDICATOR_FORMULA] * number_of_students

    def produce_gradebook_for_category(sorted_assignment_list, category, formula_list):
        """
        Produces a gradebook for a given assignment category by creating (and csv-ifying) a dataframe of column names and spreadsheet formulas.

        Args:
            sorted_assignment_list (list): A numerically sorted list of assignment names for a given category.
            category (String): The assignment category, which can be one of the following ["Labs", "Discussions", "Projects", "Midterms", "Postterms"]
            formula_list (list): This list represents the contents of a given assignment's column. It contains a spreadsheet formula to retrieve grade information. The formulas are explained in comments above the constants GRADE_RETRIEVAL_SPREADSHEET_FORMULA and DISCUSSION_COMPLETION_INDICATOR_FORMULA

        Returns:
            None
        """
        if not sorted_assignment_list:
            return
        global subsheet_titles_to_ids
        
        # Reserved/summary sheets that should not appear as columns in gradebooks
        reserved_sheets = {
            "Dashboard",
            "Labs",
            "Discussions",
            "Projects",
            "Lecture Quizzes",
            "Midterms",
            "Postterms",
            "Index",
            "Roster",
            "Pyturis",
            "PrarieLearn Gradebook"
        }
        
        # Create grade dict with matched sheet names
        # Filter out reserved/summary sheet names - they should not appear in gradebooks
        # This ensures that column names in the gradebook match the actual sheet names
        grade_dict = {}
        for assignment_name in sorted_assignment_list:
            # Skip reserved sheets
            if assignment_name in reserved_sheets:
                continue
            
            # Find the actual sheet name that matches this assignment
            actual_sheet_name = find_matching_sheet_name(assignment_name, subsheet_titles_to_ids)
            
            # Skip if the matched sheet is also a reserved sheet
            if actual_sheet_name in reserved_sheets:
                continue
            
            grade_dict[actual_sheet_name] = formula_list
        
        if not grade_dict:
            logger.warning(f"No valid assignments found for category '{category}' after filtering reserved sheets")
            return
        
        grade_df = pd.DataFrame(grade_dict).set_index(sorted_assignment_list[0])
        output = io.StringIO()
        grade_df.to_csv(output)
        grades_as_csv = output.getvalue()
        output.close()

        assemble_rest_request_for_assignment(grades_as_csv, sheet_id=subsheet_titles_to_ids[category], rowIndex=0, columnIndex=3)

    # Append the preexisting assignments and exams to the new, retrieved assignments and exams
    # and re-sort all of them numerically to ensure consistent ordering
    # This ensures that if an assignment is added later, it will still appear in the correct numerical position
    def merge_and_sort_assignments(preexisting, new_assignments, extract_number_func):
        """
        Merges preexisting and new assignments and sorts them numerically.
        
        Args:
            preexisting (list): List of preexisting assignment names
            new_assignments (list): List of new assignment names
            extract_number_func: Function to extract the number from assignment name
            
        Returns:
            list: Combined and numerically sorted list
        """
        all_assignments = set(preexisting) | set(new_assignments)
        return sorted(list(all_assignments), key=extract_number_func)
    
    sorted_labs = merge_and_sort_assignments(preexisting_lab_columns, sorted_new_labs, extract_number_from_assignment_title)
    sorted_discussions = merge_and_sort_assignments(preexisting_discussion_columns, sorted_new_discussions, extract_number_from_assignment_title)
    sorted_projects = merge_and_sort_assignments(preexisting_project_columns, sorted_new_projects, extract_number_from_assignment_title)
    sorted_lecture_quizzes = merge_and_sort_assignments(preexisting_lecture_quiz_columns, sorted_new_lecture_quizzes, extract_number_from_assignment_title)
    sorted_midterms = merge_and_sort_assignments(preexisting_midterm_columns, sorted_new_midterms, extract_number_from_assignment_title)
    sorted_postterms = merge_and_sort_assignments(preexisting_postterm_columns, sorted_new_postterms, extract_number_from_assignment_title)

    logger.info(f"Sorted assignments - Labs: {len(sorted_labs)}, Discussions: {len(sorted_discussions)}, Projects: {len(sorted_projects)}")
    logger.info(f"Sorted assignments - Quizzes: {len(sorted_lecture_quizzes)}, Midterms: {len(sorted_midterms)}, Postterms: {len(sorted_postterms)}")

    # Create the gradebook for each category
    produce_gradebook_for_category(sorted_labs, "Labs", formula_list)
    produce_gradebook_for_category(sorted_discussions, "Discussions", discussion_formula_list)
    produce_gradebook_for_category(sorted_projects, "Projects", formula_list)
    produce_gradebook_for_category(sorted_lecture_quizzes, "Lecture Quizzes", formula_list)
    produce_gradebook_for_category(sorted_midterms, "Midterms", formula_list)
    produce_gradebook_for_category(sorted_postterms, "Postterms", formula_list)



def main():
    """
    Main function to run the grade synchronization process.
    
    This script retrieves data from a Gradescope course instance and writes the data to Google Sheets. If there are no arguments passed into this script, this script will do the following:
    1. Retrieves a list of assignments from Gradescope
    2. Determines which assignments already have sub sheets in the configured Google spreadsheet
    3. For every assignment:
        Query students' grades from Gradescope
        If there is no corresponding subsheet for the assignment:
            Make a subsheet
        Create a write request for the subsheet, and store the request in a list
    4. Execute all write requests in the list

    The script populates a sheet in the format of this template with grade data: https://docs.google.com/spreadsheets/d/1V77ApZbfwLXGGorUaOMyWrSyydz_X1FCJb7MLIgLCSw/edit?gid=0#gid=0

    The number of api calls the script makes is constant with respect to the number of assignments. The number of calls = [Number of categories of assignments] + 2
    """
    global subsheet_titles_to_ids, request_list, assignment_sheets_created
    try:
        # Reset global variables at the start of each run
        subsheet_titles_to_ids = None
        request_list = []
        assignment_sheets_created = []
        
        logger.info("Starting grade synchronization process")
        start_time = time.time()
        push_all_grade_data_to_sheets()
        end_time = time.time()
        logger.info("Grade synchronization completed successfully")
        logger.info(f"Finished in {round(end_time - start_time, 2)} seconds")
        
    except Exception as e:
        logger.error(f"An error occurred during grade synchronization: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
