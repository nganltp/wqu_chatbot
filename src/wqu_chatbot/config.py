from functools import lru_cache
from typing import Literal

from pydantic import Field
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
    hybrid_dense_candidates: int = 10
    hybrid_keyword_candidates: int = 10
    hybrid_min_keyword_score: float = 1.0
    hybrid_rrf_rank_constant: int = 60
    debug_retrieval: bool = False
    daily_question_limit: int = Field(default=10, ge=1)
    rate_limit_db_path: str = "data/chat_usage.sqlite3"
    rate_limit_timezone: str = "Asia/Singapore"
    trust_cloudflare_tunnel: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
