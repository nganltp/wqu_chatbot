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
