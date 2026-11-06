"""Application history, separate from the RAG collection and quota lifecycle."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import ChatResponse


class ChatHistory:
    def __init__(self, path: str):
        self.path = Path(path)

    def start(self, question: str, conversation_id: str | None, model: str) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        request_id = str(uuid4())
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS chat_requests ("
                "id TEXT PRIMARY KEY, conversation_id TEXT, created_at TEXT NOT NULL, "
                "question TEXT NOT NULL, answer TEXT, sources TEXT NOT NULL DEFAULT '[]', "
                "status TEXT NOT NULL, latency_ms INTEGER, model TEXT NOT NULL, "
                "error_code TEXT)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS chat_requests_created_at ON chat_requests(created_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS chat_requests_conversation "
                "ON chat_requests(conversation_id)"
            )
            db.execute(
                "INSERT INTO chat_requests "
                "(id, conversation_id, created_at, question, status, model) "
                "VALUES (?, ?, ?, ?, 'processing', ?)",
                (request_id, conversation_id, datetime.now(UTC).isoformat(), question, model),
            )
        return request_id

    def finish(
        self,
        request_id: str,
        status: str,
        latency_ms: int,
        response: ChatResponse | None = None,
        error_code: str | None = None,
    ) -> None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute(
                "UPDATE chat_requests SET status=?, latency_ms=?, answer=?, sources=?, "
                "error_code=? WHERE id=?",
                (
                    status,
                    latency_ms,
                    response.answer if response else None,
                    json.dumps(
                        [source.model_dump(mode="json") for source in response.sources]
                        if response
                        else [],
                        ensure_ascii=False,
                    ),
                    error_code,
                    request_id,
                ),
            )
