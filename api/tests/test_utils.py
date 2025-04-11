"""
These are unit tests for utils.py
"""

import csv
import pytest
from api.utils import csv_to_json, handle_errors
from fastapi import HTTPException
from requests.exceptions import RequestException

def test_csv_to_json_success():
    """
    Test csv_to_json for successful conversion of CSV content to JSON-like list of dictionaries.
    """
    # Mock CSV content
    csv_content = """Name,Age,Grade
John,25,A
Doe,22,B
"""

    # Expected JSON output
    expected_output = [
        {"Name": "John", "Age": "25", "Grade": "A"},
        {"Name": "Doe", "Age": "22", "Grade": "B"},
    ]

    # Call the function
    output = csv_to_json(csv_content)

    # Assert the output matches the expected result
    assert output == expected_output


def test_csv_to_json_empty():
    """
    Test csv_to_json with empty CSV content.
    """
    # Mock empty CSV content
    csv_content = ""

    # Expected JSON output for empty content
    expected_output = []

    # Call the function
    output = csv_to_json(csv_content)

    # Assert the output matches the expected result
    assert output == expected_output


def test_csv_to_json_malformed_csv():
    """
    Test csv_to_json with malformed CSV content.
    """
    # Mock malformed CSV content
    csv_content = """Name,Age,Grade
John,25
Doe,22,B
"""

    # Expected output: Missing fields are `None` or empty in the parsed dictionary
    expected_output = [
        {"Name": "John", "Age": "25", "Grade": None},
        {"Name": "Doe", "Age": "22", "Grade": "B"},
    ]

    # Call the function
    output = csv_to_json(csv_content)

    # Assert the function handles the malformed rows gracefully
    assert output == expected_output

@handle_errors
def sample_function(trigger_error=None):
    """
    This is used to test the handle_errors decorator function.
    """
    if trigger_error == "value_error":
        raise ValueError("Invalid value")
    elif trigger_error == "type_error":
        raise TypeError("Wrong type")
    elif trigger_error == "attribute_error":
        raise AttributeError("Missing attribute")
    elif trigger_error == "request_exception":
        raise RequestException("Network error")
    elif trigger_error == "unexpected_error":
        raise RuntimeError("Unexpected error")
    return {"message": "Success"}


def test_handle_errors_no_error():
    """
    Test the decorator when no error is raised.
    """
    result = sample_function()
    assert result == {"message": "Success"}

def test_handle_errors_value_error():
    """
    Test the decorator handling a ValueError.
    """
    with pytest.raises(HTTPException) as excinfo:
        sample_function(trigger_error="value_error")
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid request: missing or incorrect parameters."

def test_handle_errors_type_error():
    """
    Test the decorator handling a TypeError.
    """
    with pytest.raises(HTTPException) as excinfo:
        sample_function(trigger_error="type_error")
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid request: missing or incorrect parameters."

def test_handle_errors_attribute_error():
    """
    Test the decorator handling an AttributeError.
    """
    with pytest.raises(HTTPException) as excinfo:
        sample_function(trigger_error="attribute_error")
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid request: missing or incorrect parameters."

def test_handle_errors_request_exception():
    """
    Test the decorator handling a RequestException.
    """
    with pytest.raises(HTTPException) as excinfo:
        sample_function(trigger_error="request_exception")
    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == "Service unavailable: network error while connecting to Gradescope."

def test_handle_errors_unexpected_error():
    """
    Test the decorator handling an unexpected error.
    """
    with pytest.raises(HTTPException) as excinfo:
        sample_function(trigger_error="unexpected_error")
    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "An unexpected server error occurred."
