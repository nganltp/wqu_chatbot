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
    quota = DailyQuota(str(tmp_path / "usage.sqlite3"), 10, "Asia/Ho_Chi_Minh")
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
    assert service.answer.call_count == 10
    assert client.get("/health").status_code == 200


def test_failed_generation_counts_toward_quota(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from wqu_chatbot import api
    from wqu_chatbot.rate_limit import DailyQuota

    service = Mock()
    service.answer.side_effect = RuntimeError("unavailable")
    quota = DailyQuota(str(tmp_path / "usage.sqlite3"), 1, "Asia/Ho_Chi_Minh")
    monkeypatch.setattr(api, "get_quota", lambda: quota)
    monkeypatch.setattr(api, "get_service", lambda: service)
    client = TestClient(app)
    assert client.post("/chat", json={"question": "Hello"}).status_code == 503
    assert client.post("/chat", json={"question": "Hello"}).status_code == 429
    assert service.answer.call_count == 1
