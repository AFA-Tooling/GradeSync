import pytest
from fastapi.testclient import TestClient
from api.app import app

@pytest.fixture
def client():
    return TestClient(app)

class TestGradescopeEndpoints:
    """Test suite for Gradescope-related endpoints."""
    def test_fetch_grades(self, client):
        response = client.get("/getGrades", params={"class_id": "902165", "assignment_id": "5211665"})
        assert response.status_code == 200
        assert "message" not in response.json()  # Assuming success response does not include an error message
    
    
    def test_lab_conceptual(self, client):
        response = client.get("/getGradeScopeAssignmentID/labs/2", params={"lab_type": 1})
        assert response.status_code == 200
        assert "assignment_id" in response.json()


    def test_lab_code(self, client):
        response = client.get("/getGradeScopeAssignmentID/labs/2", params={"lab_type": 0})
        assert response.status_code == 200
        assert "assignment_id" in response.json()


class TestPrairieLearnEndpoints:
    """Test suite for PrairieLearn-related endpoints."""
    pass
