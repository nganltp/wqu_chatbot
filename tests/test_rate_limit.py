from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from wqu_chatbot.rate_limit import DailyQuota, client_ip


def test_quota_persists_and_resets_at_vietnam_midnight(tmp_path):
    path = str(tmp_path / "usage.sqlite3")
    before = datetime(2026, 11, 6, 16, 59, 59, tzinfo=UTC)
    after = datetime(2026, 11, 6, 17, 0, 0, tzinfo=UTC)
    for _ in range(10):
        DailyQuota(path, 10, "Asia/Ho_Chi_Minh").consume("192.0.2.1", before)
    quota = DailyQuota(path, 10, "Asia/Ho_Chi_Minh")
    with pytest.raises(HTTPException) as caught:
        quota.consume("192.0.2.1", before)
    assert caught.value.status_code == 429
    assert caught.value.headers == {"Retry-After": "1"}
    quota.consume("192.0.2.2", before)
    quota.consume("192.0.2.1", after)


def test_concurrent_requests_cannot_exceed_limit(tmp_path):
    path = str(tmp_path / "usage.sqlite3")

    def attempt(_):
        try:
            DailyQuota(path, 10, "Asia/Ho_Chi_Minh").consume("192.0.2.1")
            return 200
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(30)))
    assert results.count(200) == 10
    assert results.count(429) == 20


@pytest.mark.parametrize(
    ("peer", "trust", "header", "expected"),
    [
        ("127.0.0.1", True, "192.0.2.1", "192.0.2.1"),
        ("::1", True, "2001:db8::1", "2001:db8::1"),
        ("127.0.0.1", False, "192.0.2.1", "127.0.0.1"),
        ("192.0.2.2", True, "192.0.2.1", "192.0.2.2"),
        ("127.0.0.1", True, None, "127.0.0.1"),
        ("::ffff:192.0.2.1", False, None, "192.0.2.1"),
    ],
)
def test_ip_trust(peer, trust, header, expected):
    headers = [(b"x-forwarded-for", b"192.0.2.99")]
    if header:
        headers.append((b"cf-connecting-ip", header.encode()))
    request = Request({"type": "http", "client": (peer, 1234), "headers": headers})
    assert client_ip(request, trust) == expected


def test_invalid_cloudflare_ip_is_rejected():
    request = Request(
        {"type": "http", "client": ("127.0.0.1", 1234), "headers": [(b"cf-connecting-ip", b"fake")]}
    )
    with pytest.raises(HTTPException) as caught:
        client_ip(request, True)
    assert caught.value.status_code == 400
