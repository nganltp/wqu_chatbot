from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "wqu_help"
    qdrant_local_path: str | None = None
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    # Optional for public embedding models; needed only for gated Hugging Face downloads.
    hf_token: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "low"
    cors_origins: str = "http://localhost:8000,http://localhost:5500,http://127.0.0.1:5500"
    top_k: int = 5
    min_retrieval_score: float = 0.35


@lru_cache
def get_settings() -> Settings:
    return Settings()
