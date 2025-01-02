"""
These integration tests interact with the CS10 Fall 2024 dummy course, which has class_id = 902165.
This interacts with the Gradescope and PraireLearn APIs. The tests should not be mocked.
"""
import os
import pytest
from fastapi.testclient import TestClient
from api.app import app, GRADESCOPE_CLIENT
from dotenv import load_dotenv
from api.gradescopeClient import GradescopeClient
load_dotenv()

@pytest.fixture
def client():
    return TestClient(app)


class TestGradescopeEndpoints:
    email = os.getenv("GRADESCOPE_EMAIL")
    password = os.getenv("GRADESCOPE_PASSWORD")
    """Integration tests for Gradescope-related endpoints."""
    def test_log_in_log_out_success(self):
        """
        Test successful login with valid credentials.
        """

        assert self.email is not None, "GRADESCOPE_EMAIL not set in .env file"
        assert self.password is not None, "GRADESCOPE_PASSWORD not set in .env file"
        gradescope_client = GradescopeClient()
        success = gradescope_client.log_in(self.email, self.password)
        assert success == True, "Failed to log in with valid credentials"
        assert gradescope_client.logged_in is True, "gradescope_client.logged_in should be True after successful login"
        logout_success = gradescope_client.logout()
        assert logout_success == True, "Failed to log out"
        assert gradescope_client.logged_in == False, "gradescope_client.logged_in should be False after logout"


    def test_fetch_grades(self, client):
        GRADESCOPE_CLIENT.log_in(self.email, self.password)
        GRADESCOPE_CLIENT.logged_in = True
        response = client.get("/getGrades", params={"class_id": "902165", "assignment_id": "5211665"})
        assert response.status_code == 200
        assert "message" not in response.json()  # Assuming success response does not include an error message
    

    def test_lab_conceptual(self, client):
        response = client.get("/getGradeScopeAssignmentID/labs/2", params={"lab_type": 1, "class_id": 902165})
        assert response.status_code == 200
        assert "assignment_id" in response.json()


    def test_lab_code(self, client):
        response = client.get("/getGradeScopeAssignmentID/labs/2", params={"lab_type": 0, "class_id": 902165})
        assert response.status_code == 200
        assert "assignment_id" in response.json()
    

class TestPrairieLearnEndpoints:
    """Test suite for PrairieLearn-related endpoints."""
    pass
