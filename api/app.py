from fastapi import FastAPI, HTTPException
from redis_helper import set_value, get_value

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the GradeSync API"}

@app.post("/set-value")
async def set_value_endpoint(key: str, value: str):
    """
    Sets a key-value pair in Redis via a FastAPI endpoint.

    Parameters:
    - key (str): The key under which the value will be stored in Redis. 
      - Must be a unique string identifier, as Redis keys are unique within each database.
    - value (str): The value to be stored in Redis, associated with the specified `key`.
    Returns:
    - dict: A JSON response with a confirmation message if the value was successfully stored.
    Raises:
    - HTTPException (500): If the Redis operation fails (e.g., due to connectivity issues).
    Example:
    ```
    # Request
    POST /set-value?key=username&value=Alice

    # Response
    {
        "message": "Value set successfully"
    }
    ```
    """
    success = set_value(key, value)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to set value in Redis.")
    return {"message": "Value set successfully"}

@app.get("/get-value/{key}")
async def get_value_endpoint(key: str):
    """
    Retrieves a value from Redis by its key via a FastAPI endpoint.

    Parameters:
    - key (str): The key used to retrieve the corresponding value from Redis.
      - Should match a previously set key in Redis; otherwise, a 404 response is returned.
    Returns:
    - dict: A JSON response containing the `key` and its associated `value` if found.
    Raises:
    - HTTPException (404): If the specified `key` does not exist in Redis.
    Example:
    ```
    # Request
    GET /get-value/username

    # Response (if key exists)
    {
        "key": "username",
        "value": "Alice"
    }

    # Response (if key does not exist)
    {
        "detail": "Key not found in Redis."
    }
    ```
    """
    value = get_value(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Key not found in Redis.")
    return {"key": key, "value": value}
