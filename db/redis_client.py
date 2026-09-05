import json
import logging
from typing import List, Optional
import redis
from config.settings import get_settings

logger = logging.getLogger(__name__)


def get_redis_client() -> Optional[redis.Redis]:
    """Get a connected Redis client instance based on application settings, or None if unreachable."""
    settings = get_settings()
    try:
        client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,
            protocol=2,
            socket_timeout=1.0
        )
        client.ping()
        return client
    except Exception as e:
        logger.debug(f"Redis is not running or unreachable: {e}")
        return None


def get_schema_cache(client: Optional[redis.Redis] = None) -> List[dict]:
    """Load cached schema entries from Redis or return empty list."""
    if client is None:
        client = get_redis_client()
    if client is None:
        return []

    try:
        schema_entries = client.lrange("datavox:schema", 0, -1)
        return [json.loads(e) if isinstance(e, str) else json.loads(e.decode('utf-8')) for e in schema_entries]
    except Exception as e:
        logger.debug(f"Could not load schema cache from Redis: {e}")
        return []
