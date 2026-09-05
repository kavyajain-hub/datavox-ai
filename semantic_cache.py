import json
from typing import Optional
import numpy as np
from openai import OpenAI
from config.settings import get_settings

settings = get_settings()


from config.llm import get_embeddings_client


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two 1D vectors."""
    va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def embed(text: str) -> list[float]:
    """Call embeddings API and return the embedding vector."""
    client, model = get_embeddings_client()
    response = client.embeddings.create(
        input=text, model=model
    )
    return response.data[0].embedding


def get(query: str, redis_client) -> Optional[str]:
    """Check Redis semantic cache for a similar query with similarity > 0.9."""
    if not redis_client:
        return None

    try:
        embedded_query = embed(query)
        redis_data = redis_client.lrange("datavox:cache", 0, -1)
        for i in redis_data:
            entry = json.loads(i)
            stored_embedding = entry.get("embeddings") or entry.get("embedded_query")
            if stored_embedding:
                similarity = cosine_similarity(stored_embedding, embedded_query)
                if similarity > 0.9:
                    return entry.get("response")
    except Exception:
        return None
    return None


def set(query: str, response: str, redis_client) -> None:
    """Store query, embedding, and response in Redis semantic cache."""
    if not redis_client:
        return

    try:
        embedded_query = embed(query)
        entry = json.dumps({
            "query": query,
            "embeddings": embedded_query,
            "response": response
        })
        redis_client.rpush("datavox:cache", entry)
    except Exception:
        pass
