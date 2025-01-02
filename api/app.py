from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from api.gradescopeClient import GradescopeClient
from api.utils import *
import gspread
from google.oauth2.service_account import Credentials
from backoff_utils import strategies
from backoff_utils import backoff
import requests

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials_json = os.getenv("SERVICE_ACCOUNT_CREDENTIALS")
credentials_dict = json.loads(credentials_json)
credentials = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
client = gspread.authorize(credentials)
app = FastAPI()
GRADESCOPE_CLIENT = GradescopeClient()
# Load JSON variables
config_path = os.path.join(os.path.dirname(__file__), "config/cs10_fall_2024.json")
with open(config_path, "r") as config_file:
    config = json.load(config_file)

# Hardcoded (for now) GradeScope CS10 Fall 2024 COURSE ID
CS_10_GS_COURSE_ID = str(config.get("CS_10_GS_COURSE_ID"))
# Hardcoded (for now) PL CS10 Summer 2024 COURSE ID
CS_10_PL_COURSE_ID = str(config.get("CS_10_PL_COURSE_ID"))
PL_API_TOKEN = os.getenv("PL_API_TOKEN")
PL_SERVER = "https://us.prairielearn.com/pl/api/v1"


@app.get("/")
def read_root():
    return {"message": "Welcome to the GradeSync API"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "query": q}


@app.get("/getGrades")
@handle_errors
@gradescope_session(GRADESCOPE_CLIENT)
def fetchGrades(class_id: str, assignment_id: str, file_type: str = "json"):
    """
    Fetches student grades from Gradescope as JSON. 

    Parameters:
        class_id (str): The ID of the class/course. If not provided, a default ID (CS_10_COURSE_ID) is used.
        assignment_id (str): The ID of the assignment for which grades are to be fetched.
        file_type (str): JSON or CSV format. The default type is JSON.
    Returns:
        dict or list: A list of dictionaries containing student grades if the request is successful.
                      If an error occurs, a dictionary with an error message is returned.
    Raises:
        HTTPException: If there is an issue with the request to Gradescope (e.g., network issues).
        Exception: Catches any unexpected errors and includes a descriptive message.
    """
    # supported filetypes
    assert file_type in ["csv", "json"], "File type must be either CSV or JSON."
    # If the class_id is not passed in, use the default (CS10) class id
    class_id = class_id or CS_10_GS_COURSE_ID
    filetype = "csv" # json is not supported
    GRADESCOPE_CLIENT.last_res = result = GRADESCOPE_CLIENT.session.get(f"https://www.gradescope.com/courses/{class_id}/assignments/{assignment_id}/scores.{filetype}")
    if result.ok:
        csv_content = result.content.decode("utf-8")
        json_content = csv_to_json(csv_content)
        return json_content
    else:
        return JSONResponse(
            content={"message": f"Failed to fetch grades."},
            status_code=int(result.status_code)
        )


@app.get("/getAssignmentJSON")
@handle_errors
@gradescope_session(GRADESCOPE_CLIENT)
def get_assignment_info(class_id: str = None):
    """
    Fetches and returns assignment information in a JSON format for a specified class from Gradescope.

    This endpoint retrieves all assignments for the given `class_id` from Gradescope, using the 
    Gradescope client session.

    Parameters:
    - class_id (str, optional): The ID of the class for which assignments are being retrieved. 
      Defaults to `None`.

    Returns:
    - JSON

    Example Output:
    {
        "lecture_quizzes": {
            "1": {"title": "Lecture Quiz 1: Intro", "assignment_id": "5211613"},
            ...
        },
        "labs": {
            "2": {
                "conceptual": {"title": "Lab 2: Basics (Conceptual)", "assignment_id": "5211616"},
                "code": {"title": "Lab 2: Basics (Code)", "assignment_id": "5211617"}
            },
            ...
        },
        "discussions": {
            "1": {"title": "Discussion 1: Overview", "assignment_id": "5211618"},
            ...
        }
    }
    """
    # if class_id is None, use CS10's CS_10_COURSE_ID
    class_id = class_id or CS_10_GS_COURSE_ID

    if str(class_id) == "902165": #CS10_FALL_2024_DUMMY class
        # Load assignment data from local JSON file
        # This JSON is for the CS10_FALL_2024 dummy Gradescope test class
        local_json_path = os.path.join(os.path.dirname(__file__), "cs10_assignments.json")
        with open(local_json_path, "r") as f:
            assignments = json.load(f)
        return assignments
    if not GRADESCOPE_CLIENT.logged_in:
        return JSONResponse(
            content={"error": "Unauthorized access", "message": "User is not logged into Gradescope"},
            status_code=401
        )
    GRADESCOPE_CLIENT.last_res = res = GRADESCOPE_CLIENT.session.get(f"https://www.gradescope.com/courses/{class_id}/assignments")
    if not res:
        return JSONResponse(
        content={"error": "Connection Error", "message": "Failed to connect to Gradescope"},
        status_code=503
    )
    if not res.ok:
        return JSONResponse(
        content={"error": "Gradescope Error", "message": f"Gradescope returned a {res.status_code} status code"},
        status_code=res.status_code
    )
    # We return the JSON without JSONResponse so we can reuse this in other APIs easily.
    # We let FastAPI reformat this for us.
    json_format_content = convert_course_info_to_json(str(res.content).replace("\\", "").replace("\\u0026", "&"))
    return json_format_content


@app.get("/getGradeScopeAssignmentID/{category_type}/{assignment_number}")
@handle_errors
def get_assignment_id(category_type: str, assignment_number: int, lab_type: int = None, class_id: str = CS_10_GS_COURSE_ID):
    """
    Retrieve the assignment ID based on category, number, and optional lab type (1 for conceptual, 0 for code).
    
    Parameters:
    - data (dict): The assignments data structure.
    - category (str): The assignment category, e.g., 'labs', 'midterms', 'discussions'.
    - number (str or int): The numeric identifier for the assignment.
    - lab_type (int): Required for labs, but should not be inputted for other assignment types; 1 for 'conceptual' and 0 for 'code'.
    
    Returns:
    - str: Assignment ID or error message if not found.

    Example Invocations:
    >>> get_assignment_id("lecture_quizzes", 3)
    "5211634"
    >>> # Get the assignment ID for Lab 2, conceptual part:
    >>> get_assignment_id("labs", 2, lab_type=1)
    "6311636"
    >>> #Get the assignment ID for Lab 2, code part:
    >>> get_assignment_id("labs", 2, lab_type=0)
    "6311637"
    """
    # currently no way to specify class_id.
    assignments = get_assignment_info(class_id)
    category_data = assignments.get(category_type)
    if not category_data:
        raise HTTPException(
            status_code=404,
            detail={"error": "Not Found", "message": f"Category '{category_type}' not found."}
        )

    assignment_data = category_data.get(str(assignment_number))
    if not assignment_data:
        raise HTTPException(
            status_code=404,
            detail={"error": "Not Found", "message": f"'{category_type.capitalize()} {assignment_number}' not found."}
        )

    if category_type == "labs":
        if lab_type == 1:
            if "conceptual" in assignment_data:
                return {"assignment_id": assignment_data["conceptual"]["assignment_id"]}
            else:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "Not Found", "message": f"'Lab {assignment_number}' does not have a 'conceptual' section."}
                )
        elif lab_type == 0:
            if "code" in assignment_data:
                return {"assignment_id": assignment_data["code"]["assignment_id"]}
            else:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "Not Found", "message": f"'Lab {assignment_number}' does not have a 'code' section."}
                )
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": "Bad Request", "message": "For labs, 'lab_type' must be 1 (conceptual) or 0 (code)."}
            )

    # Return assignment ID if found for categories other than "labs"
    return {"assignment_id": assignment_data.get("assignment_id", "Assignment ID not found.")}


@app.get("/fetchAllGrades")
@handle_errors
def fetchAllGrades(class_id: str = None):
    """
    Fetch Grades for all assignments for all students

    Parameters:
    - class_id (str, optional): The ID of the class for which assignments are being retrieved. 
      Defaults to `None`.

    Returns:
    - JSON
    
    # TODO: In the database design, consider if the assignmentID should be the primary key.
    # TODO: In this function, consider if we need both the assignmentID and title in this JSON
    # TODO: Create a database table mapping assignmentIDs to titles?
    Example Output:
    {
        "Lecture Quiz 1: Welcome to CS10 u0026 Abstraction": [
            {
            "Name": "test2",
            "SID": "",
            "Email": "test2@test.com",
            "Total Score": "",
            "Max Points": "4.0",
            "Status": "Missing",
            "Submission ID": null,
            "Submission Time": null,
            "Lateness (H:M:S)": null,
            "View Count": null,
            "Submission Count": null,
            "1: Lists (1.0 pts)": null,
            "2: Map, Keep, and Combine (1.0 pts)": null,
            "3: Using HOFs (1.0 pts)": null,
            "4: Loops (1.0 pts)": null
            },
            ...,
        ], 
        .....
    }
    """
    class_id = class_id or CS_10_GS_COURSE_ID
    assignment_info = get_assignment_info(class_id)
    all_ids = get_ids_for_all_assignments(assignment_info)

    all_grades = {}
    for title, one_id in all_ids:
        all_grades[title] = fetchGrades(class_id, one_id)
    return all_grades


@handle_errors
@app.post("/testWriteToSheet")
async def write_to_sheet(request: WriteRequest):
    """
    Writes a value to a specified cell in a Google Sheet.
    # NOTE: This function is only used for testing that Google Authentication works 
    # NOTE: Remove this test function in a future version once more Sheets API endpoints are written.
    """
    try:
        sheet = client.open_by_key(request.spreadsheet_id).worksheet(request.sheet_name)
        sheet.update_acell(request.cell, request.value)
        return JSONResponse(content={"message": f"Successfully wrote '{request.value}' to {request.cell}"}, status_code=200)
    except Exception as e:
        return JSONResponse(
            content={"error": "Failed to write to cell", "message": str(e)},
            status_code=500
        )
    

@handle_errors
@app.get("/getPLGrades")
def retrieve_gradebook():
    """
    Fetches student grades from PrairieLearn as JSON. 

    Note: You will need to generate a personal token in PrairieLearn found under the settings, and
        add it the .env file.
    Parameters: None
    Returns:
        dict: A dictionary containing student grades for every assessment in PL 
                if the request is successful. If an error occurs, a dictionary
                with an error message is returned.
    Raises:
        Exception: Catches any unexpected errors and includes a descriptive message.
    """
    headers = {'Private-Token': PL_API_TOKEN}
    url = PL_SERVER + f"/course_instances/{CS_10_PL_COURSE_ID}/gradebook"
    r = backoff(requests.get, args = [url], kwargs = {'headers': headers}, max_tries = 3,  max_delay = 30, strategy = strategies.Exponential)
    data = r.json()
    return data
