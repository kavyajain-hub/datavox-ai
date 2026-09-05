import os
import json
from typing import Optional
import redis
from semantic_cache import embed, cosine_similarity
from db.redis_client import get_schema_cache, get_redis_client


def get_local_schema_fallback() -> str:
    """Read all tables directly from schema.json as a fallback when Redis is offline."""
    try:
        schema_file = os.path.join(os.path.dirname(__file__), "..", "schema.json")
        if os.path.exists(schema_file):
            with open(schema_file, "r") as f:
                tables = json.load(f)
            return "\n\n".join(
                f"table:{t.get('table', '')},description:{t.get('description', '')},columns:{t.get('columns', '')}"
                for t in tables
            )
    except Exception:
        pass
    return ""


def retrieve_schema(query: str, redis_client: Optional[redis.Redis] = None, top_k: int = 3) -> str:
    """Retrieve relevant schema tables using cosine similarity with query embeddings, falling back to schema.json."""
    if redis_client is None:
        redis_client = get_redis_client()

    schema_entries = get_schema_cache(redis_client)
    if not schema_entries:
        return get_local_schema_fallback()

    try:
        embedded_query = embed(query)
    except Exception:
        return get_local_schema_fallback()

    similarity_scores = {}
    for entry in schema_entries:
        if isinstance(entry, str):
            try:
                entry = json.loads(entry)
            except Exception:
                continue

        table_name = entry.get("table", "unknown")
        stored_emb = entry.get("embeddings")
        if stored_emb:
            similarity = cosine_similarity(stored_emb, embedded_query)
            similarity_scores[table_name] = {
                "score": similarity,
                "text": entry.get("text_representation", "")
            }

    if not similarity_scores:
        return get_local_schema_fallback()

    sorted_tables = sorted(
        similarity_scores,
        key=lambda x: similarity_scores[x]["score"],
        reverse=True
    )

    filtered_tables = [
        similarity_scores[t]["text"]
        for t in sorted_tables[:top_k]
        if similarity_scores[t]["score"] > 0.6
    ]

    return "\n\n".join(filtered_tables) if filtered_tables else get_local_schema_fallback()
