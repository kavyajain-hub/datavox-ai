import json
from typing import Optional
import redis
from semantic_cache import embed
from db.redis_client import get_redis_client


def index_schema(tables: list, redis_client: Optional[redis.Redis] = None) -> None:
    """Index table definitions and their embeddings into Redis."""
    if redis_client is None:
        redis_client = get_redis_client()

    if not redis_client:
        return

    for t in tables:
        table_text = f"table:{t.get('table', '')},description:{t.get('description', '')},columns:{t.get('columns', '')}"
        embedded_table = embed(table_text)

        entry = json.dumps({
            "table": t.get("table", ""),
            "text_representation": table_text,
            "embeddings": embedded_table
        })

        redis_client.rpush("datavox:schema", entry)
