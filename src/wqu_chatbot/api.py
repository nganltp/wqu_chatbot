from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models import ChatRequest, ChatResponse
from .rag import RAGService

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        return get_service().answer(request.question, request.history)
    except Exception as error:
        raise HTTPException(
            status_code=503, detail="Chat service is temporarily unavailable"
        ) from error
