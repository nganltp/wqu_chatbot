import pytest
from fastapi.testclient import TestClient

from wqu_chatbot.api import app


def test_cors_allows_configured_local_origin() -> None:
    response = TestClient(app).options(
        "/chat",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"


def test_chat_quota_blocks_before_generation_and_ignores_invalid_body(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from wqu_chatbot import api
    from wqu_chatbot.models import ChatResponse
    from wqu_chatbot.rate_limit import DailyQuota

    service = Mock()
    service.answer.return_value = ChatResponse(answer="Answer", sources=[])
    quota = DailyQuota(str(tmp_path / "usage.sqlite3"), 10, "Asia/Singapore")
    monkeypatch.setattr(api, "get_quota", lambda: quota)
    monkeypatch.setattr(api, "get_service", lambda: service)
    client = TestClient(app)
    assert client.post("/chat", json={"question": ""}).status_code == 422
    for _ in range(10):
        assert client.post("/chat", json={"question": "Hello"}).status_code == 200
    response = client.post("/chat", json={"question": "Hello"})
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    assert "10 questions" in response.json()["detail"]
    import sqlite3

    with sqlite3.connect(tmp_path / "usage.sqlite3") as db:
        rows = db.execute("SELECT status, question, answer FROM chat_requests").fetchall()
    assert len(rows) == 11
    assert rows[:10] == [("success", "Hello", "Answer")] * 10
    assert rows[10] == ("rate_limited", "Hello", None)
    assert service.answer.call_count == 10
    assert client.get("/health").status_code == 200


def test_failed_generation_counts_toward_quota(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from wqu_chatbot import api
    from wqu_chatbot.rate_limit import DailyQuota

    service = Mock()
    service.answer.side_effect = RuntimeError("unavailable")
    quota = DailyQuota(str(tmp_path / "usage.sqlite3"), 1, "Asia/Singapore")
    monkeypatch.setattr(api, "get_quota", lambda: quota)
    monkeypatch.setattr(api, "get_service", lambda: service)
    client = TestClient(app)
    assert client.post("/chat", json={"question": "Hello"}).status_code == 503
    assert client.post("/chat", json={"question": "Hello"}).status_code == 429
    import sqlite3

    with sqlite3.connect(tmp_path / "usage.sqlite3") as db:
        row = db.execute("SELECT status, error_code FROM chat_requests LIMIT 1").fetchone()
    assert row == ("error", "RuntimeError")
    assert service.answer.call_count == 1


@pytest.fixture(autouse=True)
def isolated_history(tmp_path, monkeypatch):
    from wqu_chatbot import api
    from wqu_chatbot.chat_history import ChatHistory

    monkeypatch.setattr(api, "get_history", lambda: ChatHistory(str(tmp_path / "usage.sqlite3")))


def test_history_persists_unicode_sources_and_session(tmp_path):
    import json
    import sqlite3
    from uuid import uuid4

    from wqu_chatbot.chat_history import ChatHistory
    from wqu_chatbot.models import ChatResponse, SourceReference

    path = str(tmp_path / "history.sqlite3")
    session = str(uuid4())
    request_id = ChatHistory(path).start("Đăng ký thế nào?", session, "test-model")
    response = ChatResponse(
        answer="Đây là hướng dẫn [S1]",
        sources=[SourceReference(label="S1", title="Help", url="https://help.wqu.edu/")],
    )
    ChatHistory(path).finish(request_id, "success", 123, response)
    with sqlite3.connect(path) as db:
        row = db.execute(
            "SELECT question, answer, sources, conversation_id, latency_ms FROM chat_requests"
        ).fetchone()
    assert row[0] == "Đăng ký thế nào?"
    assert row[1] == response.answer
    assert json.loads(row[2])[0]["url"] == "https://help.wqu.edu/"
    assert row[3:] == (session, 123)
