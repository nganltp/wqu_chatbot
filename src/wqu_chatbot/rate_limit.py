"""Persistent, atomic daily quotas shared by API workers on one host."""

import math
import sqlite3
from contextlib import closing
from datetime import datetime, time, timedelta
from ipaddress import ip_address
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request


def client_ip(request: Request, trust_cloudflare: bool) -> str:
    host = request.client.host if request.client else "unknown"
    try:
        peer = ip_address(host)
    except ValueError:
        return host
    # Only a local cloudflared process may supply this header. Run Uvicorn
    # with --no-proxy-headers so request.client remains the actual socket peer.
    if trust_cloudflare and peer.is_loopback:
        forwarded = request.headers.get("cf-connecting-ip")
        if forwarded:
            try:
                peer = ip_address(forwarded)
            except ValueError as error:
                raise HTTPException(400, "Invalid client IP address") from error
    if peer.version == 6 and peer.ipv4_mapped:
        peer = peer.ipv4_mapped
    return str(peer)


class DailyQuota:
    def __init__(self, path: str, limit: int, timezone: str):
        self.path = Path(path)
        self.limit = limit
        self.timezone = ZoneInfo(timezone)

    def consume(self, ip: str, now: datetime | None = None) -> None:
        now = (now or datetime.now(self.timezone)).astimezone(self.timezone)
        day = now.date().isoformat()
        reset = datetime.combine(now.date() + timedelta(days=1), time(), self.timezone)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS daily_usage ("
                "ip TEXT NOT NULL, day TEXT NOT NULL, used INTEGER NOT NULL, "
                "PRIMARY KEY (ip, day))"
            )
            # Serialize read/modify/write across threads and processes.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM daily_usage WHERE day < ?", (day,))
            row = connection.execute(
                "SELECT used FROM daily_usage WHERE ip = ? AND day = ?", (ip, day)
            ).fetchone()
            if row and row[0] >= self.limit:
                raise HTTPException(
                    429,
                    f"Daily limit of {self.limit} questions reached for this IP. "
                    f"Please try again after midnight ({self.timezone.key}).",
                    headers={
                        "Retry-After": str(max(1, math.ceil(reset.timestamp() - now.timestamp())))
                    },
                )
            connection.execute(
                "INSERT INTO daily_usage (ip, day, used) VALUES (?, ?, 1) "
                "ON CONFLICT(ip, day) DO UPDATE SET used = used + 1",
                (ip, day),
            )
