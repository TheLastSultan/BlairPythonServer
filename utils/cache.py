import os
import time
import signal
import logging
import redis
from typing import Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Redis Connection and Helper Functions ---

max_retries = 3
retry_count = 0

redis_host = os.environ.get("REDIS_HOST", "localhost")
redis_port = int(os.environ.get("REDIS_PORT", 6379))

# Create a global Redis client instance with automatic decoding of responses
redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

def connect_redis():
    """
    Attempts to connect to Redis with retries.
    Sets up a signal handler to gracefully disconnect on termination.
    Returns the connected Redis client or None if connection fails.
    """
    global retry_count, redis_client

    while retry_count < max_retries:
        try:
            # Ping Redis to ensure connection
            redis_client.ping()
            logger.info("Connected to Redis successfully")

            # Setup signal handler for graceful shutdown
            def shutdown_handler(signum, frame):
                redis_client.close()  # Close the connection
                logger.info("Redis client disconnected through app termination")
                exit(0)

            signal.signal(signal.SIGINT, shutdown_handler)
            return redis_client

        except redis.exceptions.RedisError as e:
            retry_count += 1
            logger.error(f"Failed to connect to Redis: {e}")
            logger.info(f"Retrying to connect to Redis... ({retry_count}/{max_retries})")
            time.sleep(2)

    logger.error("Failed to connect to Redis after retries")
    return None

def set_redis_data(key: str, value: Any) -> None:
    """
    Sets the given key to the provided value in Redis.
    """
    try:
        redis_client.set(key, value)
        logger.info("Data set in Redis successfully")
    except Exception as e:
        logger.error("Error setting data in Redis: %s", e)

def get_redis_data(key: str) -> Optional[str]:
    """
    Retrieves the value associated with the given key from Redis.
    Returns None if key does not exist or an error occurs.
    """
    try:
        value = redis_client.get(key)
        return value
    except Exception as e:
        logger.error("Error retrieving data from Redis: %s", e)
        return None

def set_redis_data_with_ex(key: str, value: Any, ttl: int) -> None:
    """
    Sets the key to the given value with an expiration time (ttl in seconds).
    """
    try:
        redis_client.setex(key, ttl, value)
        logger.info("Data set in Redis with an expiration of %s seconds", ttl)
    except Exception as e:
        logger.error("Error setting data with expiration in Redis: %s", e)

def delete_redis_data(key: str) -> None:
    """
    Deletes the key from Redis.
    """
    try:
        redis_client.delete(key)
        logger.info("Data for key %s deleted", key)
    except Exception as e:
        logger.error("Error deleting data in Redis: %s", e)

