import csv
import io
from fastapi import HTTPException
from functools import wraps
from requests.exceptions import RequestException
from dotenv import load_dotenv
import os
import re
import json
from pydantic import BaseModel
import logging
import traceback

logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")
load_dotenv()
GRADESCOPE_EMAIL = os.getenv("GRADESCOPE_EMAIL")
GRADESCOPE_PASSWORD = os.getenv("GRADESCOPE_PASSWORD")

def csv_to_json(csv_content: str):
    """
    Converts CSV content to a JSON-like list of dictionaries.
    
    Parameters:
        csv_content (str): The raw CSV content as a string.

    Returns:
        list: A list of dictionaries representing the CSV data.
    """
    csv_reader = csv.DictReader(io.StringIO(csv_content))
    return [row for row in csv_reader]

def handle_errors(func):
    """
    Decorator to handle common exceptions in API endpoints.

    This decorator wraps an API endpoint function to provide standardized error handling. 
    It catches specific exceptions, such as client-side errors (e.g., `ValueError`, `TypeError`, `AttributeError`) 
    and network-related errors (`RequestException`), and returns appropriate HTTP responses with 
    meaningful error messages. If an unexpected error occurs, it returns a 500 Internal Server Error.

    Parameters:
        func (function): The API endpoint function to be wrapped by the decorator.

    Returns:
        function: A wrapper function that executes the original function with error handling applied.

    Raises:
        HTTPException: If a known error occurs, an appropriate `HTTPException` is raised with
                       status codes:
                       - 400 for client-side errors
                       - 503 for network-related errors
                       - 500 for unexpected errors

    Example:
        >>> @app.get("/example")
        >>> @handle_errors
        >>> async def example_endpoint():
        >>>     # Your endpoint logic here

    Usage:
        Apply this decorator to any FastAPI endpoint to handle errors consistently, without needing
        to duplicate error-handling logic across multiple endpoints.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Execute the wrapped function
            return func(*args, **kwargs)
        
        except (ValueError, TypeError, AttributeError) as e:
            # Handle client-side errors (400-level)
            tb = traceback.format_exc()
            logging.error(f"Client-side error: {e}\nTraceback:\n{tb}")
            raise HTTPException(status_code=400, detail="Invalid request: missing or incorrect parameters.")
        
        except RequestException as e:
            # Handle network-related errors (503-level)
            tb = traceback.format_exc()
            logging.error(f"Network error: {e}\nTraceback:\n{tb}")
            raise HTTPException(status_code=503, detail="Service unavailable: network error while connecting to Gradescope.")
        
        except Exception as e:
            # Handle all other unexpected server-side errors (500-level)
            tb = traceback.format_exc()
            logging.error(f"Unexpected server error: {e}\nTraceback:\n{tb}")
            raise HTTPException(status_code=500, detail="An unexpected server error occurred.")
    return wrapper

def gradescope_session(client):
    """
    A decorator to log in and log out to GradeScope.
    After `GRADESCOPE_TIMEOUT` seconds of inactivity, the client automatically logs out.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Log in again if we are logged out
                client.log_in(GRADESCOPE_EMAIL, GRADESCOPE_PASSWORD)
                # Execute the decorated function
                return func(*args, **kwargs)
            except Exception as e:
                return {"message": "Unknown error: " + str(e)}

        return wrapper
    return decorator


def convert_course_info_to_json(course_info_response: str):
    """
    Parses course assignment information from a JSON-formatted string and categorizes assignments into
    structured dictionaries based on assignment types such as lecture quizzes, labs, discussions, etc.

    # TODO: Create an assignment mapping structure that maps one assignment to another assignment for each semester
    # TODO: Example: Lab 4 for Fall 2023 can correspond to Lab 5 in Fall 2024. 
    # TODO: Create a function to input (OldSemester, OldAssignmentID, NewSemester) -> Output new assignmentID. 
    # TODO: The above suggested function is for processing incomplete students.
    # TODO: In Redis, do we want an ID {UNIVERSAL_ID_FOR_ASSIGNMENT: {Fall2023: FALL2023_ID_FOR_ASSIGNMENT, Fall2024: FALL2024_ID_FOR_ASSIGNMENT}}?

    # TODO: Statically configure this assignmentID configuration for Fall 2024 and cache this in Redis
    # TODO: Or statically cache this in a config file to avoid constant API calls to GradeScope
    # TODO: This JSON will be needed to periodically update grades (CRON job) for 1 particular assignment by inputting the assignmentID.

    Each assignment is identified by its "id" and "title" and is categorized accordingly:
    - "lecture_quizzes": Contains lecture quizzes organized by numeric keys.
    - "labs": Contains labs, which may have "conceptual" and "code" subcategories.
    - "discussions": Contains discussions organized by numeric keys.
    - Other categories can be added to the structure as needed.

    Parameters:
    - course_info_response (str): A JSON-formatted string containing assignment details, including 
      unique "id" and "title" fields for each assignment.

    Returns:
    - dict: A dictionary with categorized assignments. Each category is structured as a dictionary
      where keys are assignment identifiers (or subcategories), and values are dictionaries 
      containing "title" and "assignment_id".

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
    pattern = '{"id":[0-9]+,"title":"[^}"]+?"}'
    info_for_all_assignments = re.findall(pattern, course_info_response)
    assignment_to_categories = {
        "lecture_quizzes": {},
        "labs": {},
        "discussions": {},
        "midterms": {},
        "projects": {},
        "other": {}
    }

    for assignment in info_for_all_assignments:
        assignment_as_json = json.loads(assignment)
        assignment_id = str(assignment_as_json["id"])
        title = assignment_as_json["title"]

        # Categorize based on assignment title
        if "Lecture Quiz" in title:
            quiz_number = re.search(r'\d+', title)
            if quiz_number:
                key = quiz_number.group()
                assignment_to_categories["lecture_quizzes"][key] = {
                    "title": title,
                    "assignment_id": assignment_id
                }
        elif "Discussion" in title:
            discussion_number = re.search(r'\d+', title)
            if discussion_number:
                key = discussion_number.group()
                assignment_to_categories["discussions"][key] = {
                    "title": title,
                    "assignment_id": assignment_id
                }
        elif "Midterm" in title or "Practice Midterm" in title:
            midterm_key = len(assignment_to_categories["midterms"]) + 1
            assignment_to_categories["midterms"][str(midterm_key)] = {
                "title": title,
                "assignment_id": assignment_id
            }
        elif "Project" in title:
            project_number = re.search(r'\d+', title)
            if project_number:
                key = project_number.group()
                assignment_to_categories["projects"][key] = {
                    "title": title,
                    "assignment_id": assignment_id
                }
        elif "Lab" in title:
            lab_number = re.search(r'\d+', title)
            if lab_number:
                key = lab_number.group()
                if key not in assignment_to_categories["labs"]:
                    assignment_to_categories["labs"][key] = {}
                if "Conceptual" in title:
                    assignment_to_categories["labs"][key]["conceptual"] = {
                        "title": title,
                        "assignment_id": assignment_id
                    }
                elif "Code" in title:
                    assignment_to_categories["labs"][key]["code"] = {
                        "title": title,
                        "assignment_id": assignment_id
                    }
                else:
                    assignment_to_categories["labs"][key] = {
                        "title": title,
                        "assignment_id": assignment_id
                    }
        else:
            assignment_to_categories["other"][assignment_id] = title

    # Sort categories with numbers by extracting numbers
    for category in ["lecture_quizzes", "labs", "projects", "discussions", "midterms"]:
        sorted_items = dict(sorted(assignment_to_categories[category].items(), key=lambda item: int(item[0])))
        assignment_to_categories[category] = sorted_items

    return assignment_to_categories

def extract_assignment_ids(sub_dict: dict):
    """
    Extracts all assignment IDs from a nested dictionary.

    Parameters:
        - sub_dict (dict): A dictionary that may contain nested dictionaries with one or more "assignment_id" keys.
            - Example structure: {"hw": {"score": 4, "assignment_id": 12345, ...}}
    
    Output:
        - A list of assignment id's as strings: ["######", "######", ...., "######"]
    """

    assignment_ids = []
    for _, value in sub_dict.items():
        if isinstance(value, dict):
            if 'assignment_id' in value:
                assignment_ids.append([value["title"], value['assignment_id']])
            else:
                assignment_ids.extend(extract_assignment_ids(value))  # Recursively handle nested dictionaries
    return assignment_ids

def get_assignment_ids_for_category(data_dict: dict, category: str) -> list:
    """
    Get all the assignment IDs for one category

    Parameters:
        - data_dict: a dictionary
        - category: a key value in data_dict 

    Output:
        - A list of assignment id's as strings: ["######", "######", ...., "######"]
    """

    if category not in data_dict:
        logging.info(f"Category: {category} not found")
        return
    
    category_data = data_dict[category]
    return extract_assignment_ids(category_data)


def get_ids_for_all_assignments(data_dict: dict) -> list:
    """
    Extract the assignment id's and titles for all assignments (lecture, labs, projects, etc)

    Input: 
        - Output of the function get_assignment_info()

    Return: 
        - A list of assignment titles and ids

    Example output:
        [["Lecture 1: Quiz", "#######"], ["Lab 4: Conceptual", "########"], ..... , ["Midterm Fractal", "#######"]]
    """
    all_assignment_ids = []

    for category in data_dict.keys():
        ids_for_category = get_assignment_ids_for_category(data_dict, category)
        if isinstance(ids_for_category, list):  # Make sure it's a list of IDs
            all_assignment_ids.extend(ids_for_category)
    return all_assignment_ids

class WriteRequest(BaseModel):
    """
    This is used in the `testWriteToSheet` API to ensure Google Authentication works.
    """
    spreadsheet_id: str
    sheet_name: str
    cell: str
    value: str
