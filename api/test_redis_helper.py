# test_redis_helper.py
from redis_helper import set_value, get_value, redis_client

def test_set_and_get_value():
    # Test data
    test_key = "test_key"
    test_value = "Hello, Redis!"

    # Test setting a value
    set_success = set_value(test_key, test_value)
    assert set_success is True, "Failed to set value in Redis."

    # Test retrieving the value
    retrieved_value = get_value(test_key)
    assert retrieved_value == test_value, "Retrieved value does not match expected result."

    # Clean up the test data
    redis_client.delete(test_key)
