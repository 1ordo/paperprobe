from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://cosmin:cosmin_secret@postgres:5432/cosmin_checker"
    database_url_sync: str = "postgresql://cosmin:cosmin_secret@postgres:5432/cosmin_checker"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "document_chunks"
    embedding_dimension: int = 768

    # AI API
    ai_api_base_url: str = "http://your-ai-server:1234/v1"
    ai_api_key: Optional[str] = ""
    ai_model_primary: str = "openai/gpt-oss-120b"
    ai_model_fast: str = "openai/gpt-oss-120b"
    ai_model_embedding: str = "text-embedding-nomic-embed-text-v1.5"

    # Upload
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 100

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
