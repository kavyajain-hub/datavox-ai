import os
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # Provider & Model selection: "gemini" or "openai"
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")

    # Gemini Configuration
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    gemini_base_url: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    gemini_embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # Database URLs
    checkpoint_db_url: str = os.getenv("CHECKPOINT_DB_URL", "postgresql://postgres:postgres@localhost:5432/datavox_checkpoints")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./datavox_sample.db")

    # Redis Configuration
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD", None)

    @property
    def active_api_key(self) -> str:
        if self.llm_provider.lower() == "gemini":
            return self.gemini_api_key or self.openai_api_key
        return self.openai_api_key

    @property
    def active_model(self) -> str:
        if self.llm_provider.lower() == "gemini":
            return self.gemini_model
        return self.openai_model

    @property
    def active_base_url(self) -> Optional[str]:
        if self.llm_provider.lower() == "gemini":
            return self.gemini_base_url
        return None

    @property
    def active_embedding_model(self) -> str:
        if self.llm_provider.lower() == "gemini":
            return self.gemini_embedding_model
        return "text-embedding-3-small"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
