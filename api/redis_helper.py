import json
import redis
import os
# TODO: Create a database schema to cache student grades in Redis
# TODO: Cache assignmentID configurations into Redis

# Load configuration from config.json
config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(config_path, "r") as config_file:
    config = json.load(config_file)

# Use the loaded configuration to set Redis connection details
redis_host = config.get("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
database_index = config.get("REDIS_DB_INDEX", 0)


def get_redis_client(db:int= None):
    """Create and return a Redis client based on environment variables."""
    redis_host = os.getenv("REDIS_HOST", "localhost")  # Default to localhost
    redis_port = int(os.getenv("REDIS_PORT", 6379))    # Default to 6379
    database_index = db if db is not None else int(os.getenv("REDIS_DB_INDEX", 0))
    
    return redis.Redis(host=redis_host, port=redis_port, db=database_index, decode_responses=True)

def set_value(key, value, db_index=database_index):
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
    client = get_redis_client(db_index)
    return client.set(key, value)

def get_value(key, db_index=database_index):
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
    client = get_redis_client(db_index)
    return client.get(key)
