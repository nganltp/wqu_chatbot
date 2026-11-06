import logging
import sqlite3
from functools import lru_cache
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .chat_history import ChatHistory
from .config import get_settings
from .models import ChatRequest, ChatResponse
from .rag import RAGService
from .rate_limit import DailyQuota, client_ip

app = FastAPI(title="WQU Support Chatbot", version="0.1.0")
settings = get_settings()
allowed_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


@lru_cache
def get_service() -> RAGService:
    """Delay model loading until the first chat request."""
    return RAGService()


@lru_cache
def get_quota() -> DailyQuota:
    return DailyQuota(
        settings.rate_limit_db_path, settings.daily_question_limit, settings.rate_limit_timezone
    )


@lru_cache
def get_history() -> ChatHistory:
    return ChatHistory(settings.rate_limit_db_path)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    started = monotonic()
    request_id = None
    response = None
    status = "error"
    error_code = None
    try:
        ip = client_ip(http_request, settings.trust_cloudflare_tunnel)
        request_id = get_history().start(
            request.question,
            str(request.conversation_id) if request.conversation_id else None,
            settings.openai_model,
        )
        get_quota().consume(ip)
        response = get_service().answer(request.question, request.history)
        status = "success"
        return response
    except HTTPException as error:
        status = "rate_limited" if error.status_code == 429 else "error"
        error_code = f"http_{error.status_code}"
        raise
    except Exception as error:
        error_code = type(error).__name__
        raise HTTPException(
            status_code=503, detail="Chat service is temporarily unavailable"
        ) from error
    finally:
        if request_id:
            try:
                get_history().finish(
                    request_id,
                    status,
                    round((monotonic() - started) * 1000),
                    response,
                    error_code,
                )
            except (sqlite3.Error, OSError):
                # Keep the saved question in processing state; do not discard an answer
                # or replace a quota error if finalizing the audit row fails.
                logging.getLogger(__name__).error("Could not finalize chat history %s", request_id)
