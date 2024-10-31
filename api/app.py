from fastapi import FastAPI
from fastapi.responses import JSONResponse
from gradescopeClient import GradescopeClient
import os
import json 
from utils import *

app = FastAPI()
GRADESCOPE_CLIENT = GradescopeClient()
# Load JSON variables
config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(config_path, "r") as config_file:
    config = json.load(config_file)

# Hardcoded (for now) GradeScope CS10 Fall 2024 COURSE ID
COURSE_ID = str(config.get("COURSE_ID"))

@app.get("/")
def read_root():
    return {"message": "Welcome to the GradeSync API"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "query": q}

@app.get("/getGrades")
@handle_errors
@gradescope_session(GRADESCOPE_CLIENT)
def fetchGrades(class_id: str, assignment_id: str):
    """
    Fetches student grades from Gradescope as JSON. 

    Parameters:
        class_id (str): The ID of the class/course. If not provided, a default ID (COURSE_ID) is used.
        assignment_id (str): The ID of the assignment for which grades are to be fetched.
    Returns:
        dict or list: A list of dictionaries containing student grades if the request is successful.
                      If an error occurs, a dictionary with an error message is returned.
    Raises:
        HTTPException: If there is an issue with the request to Gradescope (e.g., network issues).
        Exception: Catches any unexpected errors and includes a descriptive message.
    """
    # If the class_id is not passed in, use the default (CS10) class id
    class_id = class_id or COURSE_ID
    try:
        filetype = "csv" # json is not supported
        GRADESCOPE_CLIENT.last_res = result = GRADESCOPE_CLIENT.session.get(f"https://www.gradescope.com/courses/{class_id}/assignments/{assignment_id}/scores.{filetype}")
        if result.ok:
            csv_content = result.content.decode("utf-8")
            json_content = csv_to_json(csv_content)
            return json_content
        else:
            return JSONResponse(
                content={"message": f"Failed to fetch grades. "},
                status_code=int(result.status_code)
            )
    except Exception as e:
        return JSONResponse(
            content={"error": "Unknown error ", "message": str(e)},
            status_code=500
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
    # if class_id is None, use CS10's COURSE_ID
    class_id = class_id or COURSE_ID
    if not GRADESCOPE_CLIENT.logged_in:
        return JSONResponse(
            content={"error": "Unauthorized access", "message": "User is not logged into Gradescope"},
            status_code=401
        )
    try: 
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
    except Exception as e:
        return JSONResponse(
            content={"error": "Data Processing Error", "message": str(e)},
            status_code=500
        )


@app.get("/getGradeScopeAssignmentID/{category_type}/{assignment_number}")
@handle_errors
def get_assignment_id(category_type: str, assignment_number: int, lab_type: int = None):
    """
    Retrieve the assignment ID based on category, number, and optional lab type (1 for conceptual, 0 for code).
    
    Parameters:
    - data (dict): The assignments data structure.
    - category (str): The assignment category, e.g., 'labs', 'midterms', 'discussions'.
    - number (str or int): The numeric identifier for the assignment.
    - lab_type (int): Optional for labs; 1 for 'conceptual' and 0 for 'code'.
    
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
    assignments = get_assignment_info(COURSE_ID)
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
    class_id = class_id or COURSE_ID
    assignment_info = get_assignment_info()
    all_ids = get_ids_for_all_assignments(assignment_info)

    all_grades = {}
    for title, one_id in all_ids:
        all_grades[title] = fetchGrades(class_id, one_id)
    return all_grades
