"""Polite crawler for WQU's public Intercom Help Center."""

import time
from collections import deque
from collections.abc import Callable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .chunking import make_chunks
from .models import SourceChunk

ROOT_URL = "https://help.wqu.edu/en/"
ALLOWED_PREFIXES = ("/en/collections/", "/en/articles/")


def _canonical(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", "", ""))


def _is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == "help.wqu.edu" and (
        parsed.path == "/en/" or parsed.path.startswith(ALLOWED_PREFIXES)
    )


def _text(element) -> str:
    return element.get_text("\n", strip=True) if element else ""


class HelpCenterCrawler:
    def __init__(self, *, delay_seconds: float = 0.35, timeout_seconds: float = 12.0):
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.max_redirects = 5
        self.session.headers["User-Agent"] = "WQU-Support-RAG/0.1 (public help-center indexer)"

    def crawl(
        self,
        max_pages: int = 1_000,
        on_page: Callable[[int, str], None] | None = None,
    ) -> list[SourceChunk]:
        queue: deque[str] = deque([ROOT_URL])
        visited: set[str] = set()
        chunks: list[SourceChunk] = []

        while queue and len(visited) < max_pages:
            url = _canonical(queue.popleft())
            if url in visited:
                continue
            visited.add(url)
            if on_page:
                on_page(len(visited), url)
            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
            except requests.RequestException:
                time.sleep(self.delay_seconds)
                continue
            soup = BeautifulSoup(response.text, "html.parser")

            for link in soup.select("a[href]"):
                target = _canonical(urljoin(url, link["href"]))
                if _is_allowed(target) and target not in visited:
                    queue.append(target)

            if "/en/articles/" in url:
                title = _text(soup.find("h1")) or "WQU Help Center"
                main = soup.find("article") or soup.find("main")
                for noisy in main.select("nav, header, footer, script, style") if main else []:
                    noisy.decompose()
                body = _text(main)
                category_link = soup.select_one('a[href*="/en/collections/"]')
                category = _text(category_link) or None
                chunks.extend(make_chunks(text=body, title=title, url=url, category=category))

            time.sleep(self.delay_seconds)
        return chunks
