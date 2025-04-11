"""
These unit tests do not directly interact with Gradescope and PraireLearn. 
The return values from these services must be mocked.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api.app import app

@pytest.fixture
def client():
    return TestClient(app)



@patch("api.app.GRADESCOPE_CLIENT")  # Mock the GRADESCOPE_CLIENT object
def test_fetch_grades_success(mock_client, client):
    """
    Test the fetchGrades endpoint for a successful response.
    """
    # Mock the session.get method
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.content.decode.return_value = "Name,Total Score\nStudent1,90\nStudent2,85"  # Example CSV
    mock_client.session.get.return_value = mock_response

    response = client.get(
        "/getGrades",
        params={"class_id": "12345", "assignment_id": "67890", "file_type": "csv"},
    )

    # Check the response status code
    assert response.status_code == 200

    # Check the returned JSON matches the expected output
    expected_json = [
        {"Name": "Student1", "Total Score": "90"},
        {"Name": "Student2", "Total Score": "85"},
    ]
    assert response.json() == expected_json


@patch("api.app.GRADESCOPE_CLIENT")  # Mock the GRADESCOPE_CLIENT object
def test_fetch_grades_failure(mock_client, client):
    """
    Test the fetchGrades endpoint for a failure response from Gradescope.
    """
    # Mock the session.get method to simulate a failed API response
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 500
    mock_client.session.get.return_value = mock_response

    response = client.get(
        "/getGrades",
        params={"class_id": "12345", "assignment_id": "67890", "file_type": "csv"},
    )

    # Check the response status code
    assert response.status_code == 500

    # Check the error message in the response
    assert response.json() == {"message": "Failed to fetch grades."}


@patch("api.app.GRADESCOPE_CLIENT")
def test_get_assignment_info_dummy_class(mock_client, client):
    """
    Test the /getAssignmentJSON endpoint for the CS10_FALL_2024_DUMMY class.
    """
    # Mock the local file access
    with patch("api.app.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = '''
        {
            "lecture_quizzes": {"1": {"title": "Lecture Quiz 1: Intro", "assignment_id": "5211613"}},
            "labs": {"2": {"conceptual": {"title": "Lab 2: Basics (Conceptual)", "assignment_id": "5211616"}}}
        }
        '''
        response = client.get("/getAssignmentJSON", params={"class_id": 902165})

        # Check the response status code
        assert response.status_code == 200

        # Verify the returned JSON
        expected_json = {
            "lecture_quizzes": {"1": {"title": "Lecture Quiz 1: Intro", "assignment_id": "5211613"}},
            "labs": {"2": {"conceptual": {"title": "Lab 2: Basics (Conceptual)", "assignment_id": "5211616"}}},
        }
        print(response.json())
        assert response.json() == expected_json

@patch("api.app.client.open_by_key")  # Mock the Google Sheets client
def test_write_to_sheet_success(mock_open_by_key, client):
    """
    Test the /testWriteToSheet endpoint for a successful write to a Google Sheet.
    """
    # Mock the worksheet and update_acell method
    mock_worksheet = MagicMock()
    mock_open_by_key.return_value.worksheet.return_value = mock_worksheet

    # Test data
    request_data = {
        "spreadsheet_id": "test_spreadsheet_id",
        "sheet_name": "Sheet1",
        "cell": "A1",
        "value": "Hello, World!",
    }

    # Simulate a successful cell update
    mock_worksheet.update_acell.return_value = None

    response = client.post("/testWriteToSheet", json=request_data)

    # Assert the response status code and content
    assert response.status_code == 200
    assert response.json() == {
        "message": "Successfully wrote 'Hello, World!' to A1"
    }

    # Verify that the mock methods were called correctly
    mock_open_by_key.assert_called_once_with("test_spreadsheet_id")
    mock_open_by_key.return_value.worksheet.assert_called_once_with("Sheet1")
    mock_worksheet.update_acell.assert_called_once_with("A1", "Hello, World!")


@patch("api.app.client.open_by_key")  # Mock the Google Sheets client
def test_write_to_sheet_failure(mock_open_by_key, client):
    """
    Test the /testWriteToSheet endpoint for a failed write to a Google Sheet.
    """
    # Mock the worksheet and update_acell method
    mock_worksheet = MagicMock()
    mock_open_by_key.return_value.worksheet.return_value = mock_worksheet

    # Test data
    request_data = {
        "spreadsheet_id": "test_spreadsheet_id",
        "sheet_name": "Sheet1",
        "cell": "A1",
        "value": "Hello, World!",
    }

    # Simulate an exception when updating a cell
    mock_worksheet.update_acell.side_effect = Exception("Mocked failure")

    response = client.post("/testWriteToSheet", json=request_data)

    # Assert the response status code and content
    assert response.status_code == 500
    assert response.json() == {
        "error": "Failed to write to cell",
        "message": "Mocked failure",
    }

    # Verify that the mock methods were called correctly
    mock_open_by_key.assert_called_once_with("test_spreadsheet_id")
    mock_open_by_key.return_value.worksheet.assert_called_once_with("Sheet1")
    mock_worksheet.update_acell.assert_called_once_with("A1", "Hello, World!")