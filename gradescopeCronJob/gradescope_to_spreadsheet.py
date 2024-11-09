# Author: Naveen Nathan

import json

from fullGSapi.api import client as GradescopeClient
import os.path
import sys
import re
import pandas as pd
import io
import time
import warnings
import functools
from googleapiclient.errors import HttpError
import gspread
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv


load_dotenv()
GRADESCOPE_EMAIL = os.getenv("EMAIL")
GRADESCOPE_PASSWORD = os.getenv("PASSWORD")

# CS10 Fa24 course id
# NOTE: Change this `COURSE_ID` variable to change the semester
COURSE_ID = "831412" #"782967"
# This scope allows for write access.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1bqXOiAOYnEUD1FHoK1f_uX4PP3gplRR8maQr3S1zmTQ"
NUMBER_OF_STUDENTS = 180
# Lab number of labs that are not graded.
UNGRADED_LABS = [0]
# Used only for Final grade calculation; not for display in the middle of the semester
TOTAL_LAB_POINTS = 80
NUM_LECTURES = 24

# Used for labs with 4 parts (very uncommon)
SPECIAL_CASE_LABS = [16]
NUM_LECTURE_DROPS = 3

# The ASSIGNMENT_ID constant is for users who wish to generate a sub-sheet (not update the dashboard) for one assignment, passing it as a parameter.
ASSIGNMENT_ID = (len(sys.argv) > 1) and sys.argv[1]
ASSIGNMENT_NAME = (len(sys.argv) > 2) and sys.argv[2]

# This is not a constant; it is a variable that needs global scope. It should not be modified by the user
subsheet_titles_to_ids = None

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

credentials_json = os.getenv("SERVICE_ACCOUNT_CREDENTIALS")
credentials_dict = json.loads(credentials_json)
credentials = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
client = gspread.authorize(credentials)

@deprecated
def writeToSheet(sheet_api_instance, assignment_scores, assignment_name = ASSIGNMENT_NAME):
    try:
        sub_sheet_titles_to_ids = get_sub_sheet_titles_to_ids(sheet_api_instance)

        sheet_id = None

        if assignment_name not in sub_sheet_titles_to_ids:
            create_sheet_request = {
                "requests": {
                    "addSheet": {
                        "properties": {
                            "title": assignment_name
                        }
                    }
                }
            }
            response = sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=create_sheet_request).execute()
            sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
        else:
            sheet_id = sub_sheet_titles_to_ids[assignment_name]
        time.sleep(5)
        update_sheet_with_csv(assignment_scores, sheet_api_instance, sheet_id)
        print("Successfully updated spreadsheet with new score data")
    except HttpError as err:
        print(err)

@deprecated
def create_sheet_api_instance():
    service = build("sheets", "v4", credentials=credentials)
    sheet_api_instance = service.spreadsheets()
    return sheet_api_instance

@deprecated
def get_sub_sheet_titles_to_ids(sheet_api_instance):
    global subsheet_titles_to_ids
    if subsheet_titles_to_ids:
        return subsheet_titles_to_ids
    sheets = sheet_api_instance.get(spreadsheetId=SPREADSHEET_ID, fields='sheets/properties').execute()
    sub_sheet_titles_to_ids = {sheet['properties']['title']: sheet['properties']['sheetId'] for sheet in
                               sheets['sheets']}
    return sub_sheet_titles_to_ids

@deprecated
def update_sheet_with_csv(assignment_scores, sheet_api_instance, sheet_id, rowIndex = 0, columnIndex=0):
    push_grade_data_request = {
        'requests': [
            {
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
        ]
    }
    sheet_api_instance.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=push_grade_data_request).execute()

@deprecated
def retrieve_grades_from_gradescope(gradescope_client, assignment_id = ASSIGNMENT_ID):
    assignment_scores = str(gradescope_client.download_scores(COURSE_ID, assignment_id)).replace("\\n", "\n")
    return assignment_scores

@deprecated
def initialize_gs_client():
    gradescope_client = GradescopeClient.GradescopeClient()
    gradescope_client.log_in(GRADESCOPE_EMAIL, GRADESCOPE_PASSWORD)
    return gradescope_client

@deprecated
def get_assignment_info(gs_instance, class_id: str) -> bytes:
    if not gs_instance.logged_in:
        print("You must be logged in to download grades!")
        return False
    gs_instance.last_res = res = gs_instance.session.get(f"https://www.gradescope.com/courses/{class_id}/assignments")
    if not res or not res.ok:
        print(f"Failed to get a response from gradescope! Got: {res}")
        return False
    return res.content

@deprecated
def make_score_sheet_for_one_assignment(sheet_api_instance, gradescope_client, assignment_name = ASSIGNMENT_NAME,
                                        assignment_id=ASSIGNMENT_ID):
    assignment_scores = retrieve_grades_from_gradescope(gradescope_client = gradescope_client, assignment_id = assignment_id)
    writeToSheet(sheet_api_instance, assignment_scores, assignment_name)
    return assignment_scores

"""
This method returns a dictionary mapping assignment IDs to the names (titles) of the assignments
"""
@deprecated
def get_assignment_id_to_names(gradescope_client):
    # The response cannot be parsed as a json as is.
    course_info_response = str(get_assignment_info(gradescope_client, COURSE_ID)).replace("\\", "").replace("\\u0026", "&")
    pattern = '{"id":[0-9]+,"title":"[^}"]+?"}'
    info_for_all_assignments = re.findall(pattern, course_info_response)
    assignment_to_names = {}
    #  = { json.loads(assignment)['id'] : json.loads(assignment)['title'] for assignment in info_for_all_assignments }
    for assignment in info_for_all_assignments:
        assignment_as_json = json.loads(assignment)
        assignment_to_names[str(assignment_as_json["id"])] = assignment_as_json["title"]
    return assignment_to_names

def main():
    if len(sys.argv) > 1:
        gradescope_client = initialize_gs_client()
        make_score_sheet_for_one_assignment(credentials, gradescope_client=gradescope_client,
                                            assignment_name=ASSIGNMENT_NAME, assignment_id=ASSIGNMENT_ID)
    else:
        push_all_grade_data_to_sheets()

@deprecated
def push_all_grade_data_to_sheets():
    gradescope_client = initialize_gs_client()
    assignment_id_to_names = get_assignment_id_to_names(gradescope_client)
    """
    labs = filter(lambda assignment: "lab" in assignment.lower(),
                  assignment_id_to_names.values())
    extract_number_from_lab_title = lambda lab: int(re.findall("\d+", lab)[0])
    sorted_labs = sorted(labs, key=extract_number_from_lab_title)

    assignment_names_to_ids = {v: k for k, v in assignment_id_to_names.items()}
    projects = set(filter(lambda assignment: "project" in assignment.lower(),
                  assignment_id_to_names.values()))
    sorted_projects = sorted(projects, key=lambda project: assignment_names_to_ids[project])

    lecture_quizzes = list(filter(lambda assignment: "lecture" in assignment.lower(),
                  assignment_id_to_names.values()))

    discussions = filter(lambda assignment: "discussion" in assignment.lower(),
                  assignment_id_to_names.values())
    """
    sheet_api_instance = create_sheet_api_instance()
    sub_sheet_titles_to_ids = get_sub_sheet_titles_to_ids(sheet_api_instance)
    dashboard_sheet_id = sub_sheet_titles_to_ids['Instructor_Dashboard']
    dashboard_dict = {}

    all_lab_ids = set()
    paired_lab_ids = set()

    # An assignment is marked as current if there are >3 submissions and if the commented code in the for loop below is removed
    assignment_id_to_currency_status = {}
    for id in assignment_id_to_names:
        assignment_scores = make_score_sheet_for_one_assignment(sheet_api_instance, gradescope_client=gradescope_client,
                                                                assignment_name=assignment_id_to_names[id], assignment_id=id)
        #if assignment_scores.count("Graded") >= 3:
        #    assignment_id_to_currency_status[id] = assignment_scores



def populate_instructor_dashboard(all_lab_ids, assignment_id_to_currency_status, assignment_id_to_names,
                                  assignment_names_to_ids, dashboard_dict, dashboard_sheet_id, discussions,
                                  extract_number_from_lab_title, id, lecture_quizzes, paired_lab_ids,
                                  sheet_api_instance, sorted_labs, sorted_projects):
    for i in range(len(sorted_labs) - 1):
        first_element = sorted_labs[i]
        second_element = sorted_labs[i + 1]
        first_element_assignment_id = assignment_names_to_ids[first_element]
        second_element_assignment_id = assignment_names_to_ids[second_element]
        first_element_lab_number = extract_number_from_lab_title(first_element)
        second_element_lab_number = extract_number_from_lab_title(second_element)
        if first_element_lab_number in UNGRADED_LABS:
            continue
        all_lab_ids.add(first_element_assignment_id)
        all_lab_ids.add(second_element_assignment_id)
        if first_element_lab_number == second_element_lab_number:
            paired_lab_ids.add(first_element_assignment_id)
            paired_lab_ids.add(second_element_assignment_id)
            if first_element_lab_number in SPECIAL_CASE_LABS:
                continue
            if assignment_id_to_currency_status[id]:
                spreadsheet_query = f"=DIVIDE(XLOOKUP(C:C, {first_element_assignment_id}!C:C, {first_element_assignment_id}!E:E) + XLOOKUP(C:C, {second_element_assignment_id}!C:C, {second_element_assignment_id}!E:E), XLOOKUP(C:C, {first_element_assignment_id}!C:C, {first_element_assignment_id}!F:F) + XLOOKUP(C:C, {second_element_assignment_id}!C:C, {second_element_assignment_id}!F:F))"
                dashboard_dict["Lab " + str(first_element_lab_number)] = [spreadsheet_query] * NUMBER_OF_STUDENTS
    unpaired_lab_ids = all_lab_ids - paired_lab_ids
    for lab_id in unpaired_lab_ids:
        if assignment_id_to_currency_status[id]:
            spreadsheet_query = f"=DIVIDE(XLOOKUP(C:C, {lab_id}!C:C, {lab_id}!E:E), XLOOKUP(C:C, {lab_id}!C:C, {lab_id}!F:F))"
            lab_number = extract_number_from_lab_title(assignment_id_to_names[lab_id])
            dashboard_dict["Lab " + str(lab_number)] = [spreadsheet_query] * NUMBER_OF_STUDENTS
    for lab_number in SPECIAL_CASE_LABS:
        if assignment_id_to_currency_status[id]:
            special_case_lab_name = "Lab " + str(lab_number)
            special_lab_ids = []
            for lab_name in sorted_labs:
                if special_case_lab_name in lab_name:
                    special_lab_ids.append(assignment_names_to_ids[lab_name])
            spreadsheet_query = f"=DIVIDE(XLOOKUP(C:C, {special_lab_ids[0]}!C:C, {special_lab_ids[0]}!E:E) + XLOOKUP(C:C, {special_lab_ids[1]}!C:C, {special_lab_ids[1]}!E:E) + XLOOKUP(C:C, {special_lab_ids[2]}!C:C, {special_lab_ids[2]}!E:E) + XLOOKUP(C:C, {special_lab_ids[3]}!C:C, {special_lab_ids[3]}!E:E), XLOOKUP(C:C, {special_lab_ids[0]}!C:C, {special_lab_ids[0]}!F:F) + XLOOKUP(C:C, {special_lab_ids[1]}!C:C, {special_lab_ids[1]}!F:F) + XLOOKUP(C:C, {special_lab_ids[2]}!C:C, {special_lab_ids[2]}!F:F) + XLOOKUP(C:C, {special_lab_ids[3]}!C:C, {special_lab_ids[3]}!F:F))"
            dashboard_dict[special_case_lab_name] = [spreadsheet_query] * NUMBER_OF_STUDENTS
    num_graded_labs = len(dashboard_dict) - len(UNGRADED_LABS)
    lab_score_column = [
        f"=ARRAYFORMULA(COUNTIF(FILTER(I{i + 2}:{i + 2}, REGEXMATCH(I1:1, \"Lab\")), 1) / {num_graded_labs} * {TOTAL_LAB_POINTS})"
        for i in range(NUMBER_OF_STUDENTS)]
    lab_score_title = "Su24CS10 Final Lab Score / 100"
    lab_score_dict = {lab_score_title: lab_score_column}
    number_of_full_credit_labs = [f"=ARRAYFORMULA(COUNTIF(FILTER(I{i + 2}:{i + 2}, REGEXMATCH(I1:1, \"Lab\")), 1))" for
                                  i in range(NUMBER_OF_STUDENTS)]
    number_of_full_credit_labs_dict = {"# of full credit labs": number_of_full_credit_labs}
    lab_average_column = [f"=ARRAYFORMULA(AVERAGE(FILTER(I{i + 2}:{i + 2}, REGEXMATCH(I1:1, \"Lab\"))))" for i in
                          range(NUMBER_OF_STUDENTS)]
    lab_average_dict = {"Avg. Lab Score": lab_average_column}
    project_average_column = [f"=ARRAYFORMULA(AVERAGE(FILTER(J{i + 2}:{i + 2}, REGEXMATCH(J1:1, \"Project\"))))" for i
                              in range(NUMBER_OF_STUDENTS)]
    project_average_dict = {"Avg. Project Score": project_average_column}
    lecture_attendance_score = [
        f"=ARRAYFORMULA((COUNTIF(FILTER(I{i + 2}:{i + 2}, REGEXMATCH(I1:1, \"Lecture\")), 1) + {NUM_LECTURE_DROPS}) / {len(lecture_quizzes)})"
        for i in range(NUMBER_OF_STUDENTS)]
    lecture_quiz_count_dict = {"Su24CS10 Final Lecture Attendance Score (Drops Included)": lecture_attendance_score}
    discussion_makeup_count = [f"=ARRAYFORMULA(COUNTIF(FILTER(I{i + 2}:{i + 2}, REGEXMATCH(I1:1, \"Discussion\")), 1))"
                               for i in range(NUMBER_OF_STUDENTS)]
    discussion_makeup_count_dict = {"Su24CS10 Number of Discussion Makeups": discussion_makeup_count}
    for assignment_name in sorted_projects:
        if assignment_id_to_currency_status[id]:
            assignment_id = assignment_names_to_ids[assignment_name]
            spreadsheet_query = f"=DIVIDE(XLOOKUP(C:C, {assignment_id}!C:C, {assignment_id}!E:E), XLOOKUP(C:C, {assignment_id}!C:C, {assignment_id}!F:F))"
            dashboard_dict[assignment_name] = [spreadsheet_query] * NUMBER_OF_STUDENTS
    for assignment_name in lecture_quizzes:
        if assignment_id_to_currency_status[id]:
            assignment_id = assignment_names_to_ids[assignment_name]
            spreadsheet_query = f"=DIVIDE(XLOOKUP(C:C, {assignment_id}!C:C, {assignment_id}!E:E), XLOOKUP(C:C, {assignment_id}!C:C, {assignment_id}!F:F))"
            dashboard_dict[assignment_name] = [spreadsheet_query] * NUMBER_OF_STUDENTS
    for assignment_name in discussions:
        if assignment_id_to_currency_status[id]:
            assignment_id = assignment_names_to_ids[assignment_name]
            spreadsheet_query = f"=IF(XLOOKUP(C:C, {assignment_id}!C:C, {assignment_id}!G:G) <> \"Missing\", 1, 0)"
            dashboard_dict[assignment_name] = [spreadsheet_query] * NUMBER_OF_STUDENTS
    dashboard_dict_with_aggregate_columns = {}
    dashboard_dict_with_aggregate_columns.update(lab_score_dict)
    dashboard_dict_with_aggregate_columns.update(lecture_quiz_count_dict)
    dashboard_dict_with_aggregate_columns.update(discussion_makeup_count_dict)
    dashboard_dict_with_aggregate_columns.update(number_of_full_credit_labs_dict)
    dashboard_dict_with_aggregate_columns.update(lab_average_dict)
    dashboard_dict_with_aggregate_columns.update(project_average_dict)
    dashboard_dict_with_aggregate_columns.update(dashboard_dict)
    first_column_name = lab_score_title
    dashboard_df = pd.DataFrame(dashboard_dict_with_aggregate_columns).set_index(first_column_name)
    output = io.StringIO()
    dashboard_df.to_csv(output)
    update_sheet_with_csv(output.getvalue(), sheet_api_instance, dashboard_sheet_id, 0, 3)
    output.close()


if __name__ == "__main__":
    main()
