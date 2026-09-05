import json
import os
from rag.schema_indexer import index_schema
from db.redis_client import get_redis_client


def seed():
    client = get_redis_client()
    if not client:
        print("Redis is not available. Skipping schema seeding.")
        return

    schema_file = os.path.join(os.path.dirname(__file__), "..", "schema.json")
    with open(schema_file, "r") as f:
        schema_context = json.load(f)

    # Clear old schema entries
    client.delete("datavox:schema")
    index_schema(schema_context, client)
    print(f"Successfully indexed {len(schema_context)} tables into Redis key 'datavox:schema'.")


if __name__ == "__main__":
    seed()
