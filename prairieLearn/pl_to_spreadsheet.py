#!/usr/local/bin/python
# Author: Manan Bhargava and Nawoda Wijesooriya

import json

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
import pandas as pd
import requests
import logging
import sys
from pprint import pprint

# ------------------------------------------------------------------------------------
# SECTION 1: Importing credentials, configurations, setting up logging
# ------------------------------------------------------------------------------------

load_dotenv()
PL_API_TOKEN = os.getenv("PL_API_TOKEN")
PL_SERVER = "https://us.prairielearn.com/pl/api/v1"

# Configure logging to output to both file and console
logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more detail
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Logs to console (stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info("Starting the prairielearn_to_sheets script.")

# Load JSON variables
# Note: this class JSON name can be made customizable, inputted through a front end user interface for example
# But the default is cs10_fall2024.json
class_json_name = 'cs10_sp25.json'
config_path = os.path.join(os.path.dirname(__file__), 'config/', class_json_name)
with open(config_path, "r") as config_file:
    config = json.load(config_file)

# IDs to link files
PL_COURSE_ID = str(config["PL_COURSE_ID"])
SCOPES = config["SCOPES"]
SPREADSHEET_ID = config["SPREADSHEET_ID"]

# These constants are deprecated. 
# The following explanation is for what their purpose was: 
# ASSIGNMENT_ID is for users who wish to generate a sub-sheet (not update the dashboard) for one assignment. 
# ASSIGNMENT_NAME specifies the name of the subsheet where grades for the assignment are to be stored. 
# They are populated using the first and second command-line args respectively.

ASSIGNMENT_ID = (len(sys.argv) > 1) and sys.argv[1]
ASSIGNMENT_NAME = (len(sys.argv) > 2) and sys.argv[2]


# ------------------------------------------------------------------------------------
# SECTION 2: Sheets Request and Population
# ------------------------------------------------------------------------------------

# This is not a constant; it is a variable that needs global scope. It should not be modified by the user
subsheet_titles_to_ids = None
# Tracking the number of_attempts to_update a sheet.
number_of_retries_needed_to_update_sheet = 0

request_list = []

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

    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
        assignment_scores (String): The csv containing assignment scores
        assignment_name (String): The name of the assignment as listed on Gradescope

    Returns:
        None: This function does not return a value.
    """
    global number_of_retries_needed_to_update_sheet
    try:
        sub_sheet_titles_to_ids = get_sub_sheet_titles_to_ids(sheet_api_instance)

        if assignment_name not in sub_sheet_titles_to_ids:
            create_sheet_rest_request = {
                "requests": [
                    {
                    "addSheet": {
                        "properties": {
                            "title": assignment_name
                        }
                    }
                    }
                ]
            }
            request = sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=create_sheet_rest_request)
            response = make_request(request)
            sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
        else:
            sheet_id = sub_sheet_titles_to_ids[assignment_name]
        assemble_rest_request_for_assignment(assignment_scores, sheet_id)
        logger.info(f"Created sheets request for {assignment_name}")
        number_of_retries_needed_to_update_sheet = 0
    except HttpError as err:
        logger.error(f"An HttpError has occurred: {err}")
    except Exception as err:
        logger.error(f"An unknown error has occurred: {err}")


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


def get_sub_sheet_titles_to_ids(sheet_api_instance):
    """
    If subsheet_titles_to_ids, a dict mapping subsheet titles to sheet ids, has already been created,
    return it. If not, retrieve that info from Google sheets.

    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance

    Returns:
        dict: A dict mapping subsheet names (titles) to sheet ids.
    """
    global subsheet_titles_to_ids
    if subsheet_titles_to_ids:
        return subsheet_titles_to_ids
    logger.info("Retrieving subsheet titles to ids")
    request = sheet_api_instance.get(spreadsheetId=SPREADSHEET_ID, fields='sheets/properties')
    sheets = make_request(request)
    subsheet_titles_to_ids = {sheet['properties']['title']: sheet['properties']['sheetId'] for sheet in
                               sheets['sheets']}
    return subsheet_titles_to_ids


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
    return request.execute()


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
        assignment_type (String): One of the following assignment types: ["Labs", "Discussions", "Projects", "Midterms", "Postterms", "Pyturis"]
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
    Returns:
        None
    """
    range = f'{assignment_type}!1:1'
    result = sheet_api_instance.values().get(spreadsheetId=SPREADSHEET_ID, range=range).execute()
    first_row = result.get('values', [])
    return first_row[0][3:]


def make_batch_request(sheet_api_instance):
    """
    Executes a batch request including all requests in our running list: request_list

    Args:
        sheet_api_instance (googleapiclient.discovery.Resource): The sheet api instance
    Returns:
        None
    """
    global request_list
    rest_batch_request = {
        "requests": request_list
    }
    batch_request = sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=rest_batch_request)
    logger.info(f"Issuing batch request")
    make_request(batch_request)
    logger.info(f"Completing batch request")
    

# ------------------------------------------------------------------------------------
# SECTION 3: PrairieLearn API Calls
# ------------------------------------------------------------------------------------

def create_pivot_table(instance_question_df):

    logger.info("Creating pivot table")

    score_pivot = instance_question_df.pivot_table(
        index='UIN',
        columns=['Assessment', 'Zone number', 'Zone title'],
        values='Question points',
        aggfunc='first'
    )

    max_points_row = instance_question_df.pivot_table(
        index=None,  
        columns=['Assessment', 'Zone number', 'Zone title'],
        values='Max points',
        aggfunc='first'
    )

    
    score_pivot = score_pivot.sort_index(axis=1, level=['Assessment', 'Zone number', 'Zone title'])
    max_points_row = max_points_row.sort_index(axis=1, level=['Assessment', 'Zone number', 'Zone title'])

    
    score_pivot.columns = score_pivot.columns.droplevel('Zone number')
    max_points_row.columns = max_points_row.columns.droplevel('Zone number')

    max_points_row.index = ['Max Points']
    final_df = pd.concat([max_points_row, score_pivot])

    # Get the an ascending column number for easier indexing of columns 
    column_numbers = pd.DataFrame(
        [range(final_df.shape[1])],  
        columns=final_df.columns,
        index=['Column #']
    )
    final_df_with_column_nums = pd.concat([column_numbers, final_df])

    return final_df_with_column_nums

def assessment_name_mapping(instance_question_df):
    '''

    - Rename the columns in the instance_question_df to the assessment title
    - Use the assessment endpoint to create a mapping of the assessment name to the assessment title
    - Rename the columns in the instance_question_df to the assessment title

    '''

    course_instance_path = f"/course_instances/{PL_COURSE_ID}"

    assessments = call_pl_api(f"{course_instance_path}/assessments")

    assessment_name_mapping = {assessments[i]["assessment_name"]: assessments[i]["title"] for i in range(len(assessments))}

    for assessment_name, assessment_title in assessment_name_mapping.items():
        instance_question_df['Assessment'] = instance_question_df['Assessment'].replace(assessment_name, assessment_title)

    return instance_question_df
    

def instance_question_endpoint(gradebook_df):
    """
    For each student (row) in gradebook_df and for each assessment (dynamic column),
    call the PrairieLearn instance questions endpoint, and build a record for each
    returned question. The resulting DataFrame will contain one row per question
    with columns:
    UID, UIN, Username, Name, Role, Assessment, Assessment instance,
    Zone number, Zone title, Question, Question instance, Question points,
    Max points, Question % score, Auto points, Max auto points, Manual points,
    Max manual points, Date, Highest submission score, Last submission score,
    Number attempts, Duration seconds, Assigned manual grader, Last manual grader.
    """
    records = []
    # Columns in original gradebook DataFrame.
    fixed_cols = ['user_id', 'user_uid', 'user_uin', 'user_name', 'user_role', 'assessments']
    # Assessment Columns
    assessment_columns = [col for col in gradebook_df.columns if col not in fixed_cols]

    for idx, row in gradebook_df.iterrows():
        for assessment in assessment_columns:
            instance_id = row[assessment]

            # Skip if this student doesn't have an instance for that assessment.
            if pd.isnull(instance_id):
                continue

            # Instance Question endpoint
            endpoint = f"/course_instances/{PL_COURSE_ID}/assessment_instances/{int(instance_id)}/instance_questions"
            
            instance_questions = call_pl_api(endpoint)
            
            # Process each instance question.
            for question in instance_questions:
                record = {
                    "UID": row.get('user_uid'),
                    "UIN": row.get('user_uin'), 
                    "Username": None, # Leave Empty
                    "Name": row.get('user_name'),  
                    "Role": row.get('user_role'),
                    "Assessment": assessment,
                    "Assessment instance": instance_id,
                    "Zone number": question.get('zone_number'),       
                    "Zone title": question.get('zone_title'),       
                    "Question": question.get("question_name"),
                    "Question instance": question.get("instance_question_id"),
                    "Question points": question.get("instance_question_points"),
                    "Max points": question.get("assessment_question_max_points"),
                    "Question % score": question.get("instance_question_score_perc"),
                    "Auto points": question.get("instance_question_auto_points"),
                    "Max auto points": question.get("assessment_question_max_auto_points"),
                    "Manual points": question.get("instance_question_manual_points"),
                    "Max manual points": question.get("assessment_question_max_manual_points"),
                    "Date": None,  #
                    "Highest submission score": question.get("highest_submission_score"),
                    "Last submission score": question.get("last_submission_score"),
                    "Number attempts": question.get("number_attempts"),
                    "Duration seconds": question.get("duration_seconds"),
                    "Assigned manual grader": None,  # 
                    "Last manual grader": None         # 
                }
                records.append(record)
    
    # Convert list of records to a DataFrame.
    return pd.DataFrame(records)


    

def transform_gradebook_df(gradebook_df):
    '''
    - Unnest the assessments column in the gradebook df 
    - Create new columns with the assessment name as the title and assessment instance id as the value

    '''
    for idx, row in gradebook_df.iterrows():
        
        for assessment in row['assessments']:
            
            gradebook_df.at[idx, assessment["assessment_name"]] = assessment["assessment_instance_id"]
    return gradebook_df


def gradebook_pl_endpoint():
    '''
    -Create a pandas dataframe, gradebook_df, for the pl gradebook endpoint
    '''
    course_instance_path = f"/course_instances/{PL_COURSE_ID}"

    gradebook_data = call_pl_api(f"{course_instance_path}/gradebook")

    gradebook_df = pd.DataFrame.from_dict(gradebook_data)

    return gradebook_df

def call_pl_api(endpoint):
    url = PL_SERVER + endpoint
    headers = {"Private-Token": PL_API_TOKEN}
    
    logger.info(f"Calling PrairieLearn API: {url}")

    retry_502_max = 30
    retry_502_i = 0
    while True:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            logger.info(f"PrairieLearn API call successful: {url}")
            break
        if r.status_code == 502:
            retry_502_i += 1
            logger.warning(f"502 Bad Gateway Error Encountered at {url} retrying in 10 seconds")
            if retry_502_i >= retry_502_max:
                logger.error(f"Maximum number of retries reached on 502 Bad Gateway Error for {url}")
                raise ValueError(
                    f"Maximum number of retries reached on 502 Bad Gateway Error for {url}"
                )
            #Bad Gateway Error Encountered at {url} retrying in 10 seconds
            time.sleep(10)
            continue
        logger.error(f"Error encountered at {url}: {r.status_code}")
        raise ValueError(f"Invalid status returned for {url}: {r.status_code}")
    
    data = r.json()

    return data

# ------------------------------------------------------------------------------------
# SECTION 4: Dataframe Dictionary --> Dataframe --> CSV --> Sheets
# ------------------------------------------------------------------------------------

# Create a function to convert a dataframe to csv
def df_to_csv(df):
    """
    Converts a pandas dataframe to a csv string.

    Args:
        df (pandas.DataFrame): A pandas dataframe

    Returns:
        str: A csv string
    """
    output = io.StringIO()
    df.to_csv(output, index=True)
    return output.getvalue()

def push_pl_csv_to_sheet(final_df, sheetname):
    """
    Pushes the csv scores for a PL assignment to GradeScope

    Args:
        assignment_id: assignment_id for the PrairieLearn assignment
        assignment_name: Name of subsheet where the PL assignment's grades should be pasted.

    Returns:
        None
    """
    # Make a new subsheet for the assignment and populate it with the scores
    create_sheet_and_request_to_populate_it(create_sheet_api_instance(), final_df, sheetname)


def push_all_grade_data_to_sheets(df):
    """
    Encapsulates the entire process of retrieving grades from GradeScope and Pyturis from PL and pushing to sheets.

    Returns:
        None
    """
    # gradescope_client = initialize_gs_client()
    # assignment_id_to_names = get_assignment_id_to_names(gradescope_client)
    sheet_api_instance = create_sheet_api_instance()
    get_sub_sheet_titles_to_ids(sheet_api_instance)

   
    push_pl_csv_to_sheet(df_to_csv(df), "PrarieLearn Gradebook")

    # populate_spreadsheet_gradebook(assignment_id_to_names, sheet_api_instance)
    make_batch_request(sheet_api_instance)




def main():
    """
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
    # Use the logger to calculate the amount of time for starting and completing the request.
    start_time = time.time()

    gradebook_df = transform_gradebook_df(gradebook_pl_endpoint())

    instance_question_df = instance_question_endpoint(gradebook_df)

    assessment_name_mapping_df = assessment_name_mapping(instance_question_df)

    final_df = create_pivot_table(assessment_name_mapping_df)

    push_all_grade_data_to_sheets(final_df)

    end_time = time.time()
    logger.info(f"Finished in {round(end_time - start_time, 2)} seconds")

if __name__ == "__main__":
    main()
