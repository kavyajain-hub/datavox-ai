import os
import pytest

# Ensure environment variables exist for test suite imports
os.environ.setdefault("OPENAI_API_KEY", "sk-mock-key-for-tests-only")
os.environ.setdefault("CHECKPOINT_DB_URL", "postgresql://localhost:5432/test_datavox_checkpoints")
os.environ["DATABASE_URL"] = "sqlite:///./datavox_sample.db"
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
