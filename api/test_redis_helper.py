# test_redis_helper.py
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from app import app
from redis_helper import get_redis_client

client = TestClient(app)

def test_set_and_get_value():
    # Define test data
    test_key = "johnsmith@example.com"
    test_value = "A+"

    # Test setting a value in Redis
    response = client.post("/set-value", params={"key": test_key, "value": test_value})
    assert response.status_code == 200
    assert response.json() == {"message": "Value set successfully"}

    # Test retrieving the value
    response = client.get(f"/get-value/{test_key}")
    assert response.status_code == 200
    assert response.json() == {"key": test_key, "value": test_value}
    # Clean up the test by deleting the test key
    get_redis_client().delete(test_key)
