from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "wqu_help"
    qdrant_local_path: str | None = None
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    # Omit only when using a locally saved `hf auth login` token during development.
    hf_token: str | None = None
    hf_model: str = "Qwen/Qwen3-8B:fastest"
    hf_provider: str = "auto"
    cors_origins: str = "http://localhost:8000,http://localhost:5500,http://127.0.0.1:5500"
    top_k: int = 5
    min_retrieval_score: float = 0.35


@lru_cache
def get_settings() -> Settings:
    return Settings()
