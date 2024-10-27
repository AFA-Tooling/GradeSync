import json
import redis
# TODO: Create a database schema to cache student grades in Redis
# TODO: Cache assignmentID configurations into Redis

# Load configuration from config.json
with open("config.json") as config_file:
    config = json.load(config_file)

# Use the loaded configuration to set Redis connection details
redis_host = config.get("REDIS_HOST", "localhost")
redis_port = config.get("REDIS_PORT", 6379)
database_index = config.get("REDIS_DB_INDEX", 0)

# Initialize the Redis client with the specified settings
redis_client = redis.Redis(host=redis_host, port=redis_port, db=database_index, decode_responses=True)

def set_value(key, value, db_index=database_index):
    """Set a key-value pair in a specified Redis database."""
    client = redis.Redis(host=redis_host, port=redis_port, db=db_index)
    return client.set(key, value)

def get_value(key, db_index=database_index):
    """Retrieve a value from a specified Redis database by key."""
    client = redis.Redis(host=redis_host, port=redis_port, db=db_index)
    return client.get(key)
