from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    try:
        get_quota().consume(client_ip(http_request, settings.trust_cloudflare_tunnel))
        return get_service().answer(request.question, request.history)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=503, detail="Chat service is temporarily unavailable"
        ) from error
