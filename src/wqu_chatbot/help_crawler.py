"""Polite crawler for WQU's public Intercom Help Center."""

import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from shutil import rmtree
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .local_documents import document_id_for_url, write_document
from .models import SourceDocument

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
    if element:
        for protected_email in element.select("[data-cfemail]"):
            decoded = _decode_cloudflare_email(protected_email.get("data-cfemail", ""))
            if decoded:
                protected_email.replace_with(decoded)
    return element.get_text("\n", strip=True) if element else ""


def _decode_cloudflare_email(value: str) -> str | None:
    """Decode Cloudflare's `data-cfemail` attribute without executing page JavaScript."""
    try:
        encoded = bytes.fromhex(value)
    except ValueError:
        return None
    if len(encoded) < 2:
        return None
    try:
        return bytes(byte ^ encoded[0] for byte in encoded[1:]).decode("utf-8")
    except UnicodeDecodeError:
        return None


class HelpCenterCrawler:
    def __init__(
        self,
        *,
        delay_seconds: float = 0.35,
        timeout_seconds: float = 12.0,
        raw_output: Path | None = Path("data/wqu_help_raw/documents/help"),
    ):
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.raw_output = raw_output
        self.raw_documents_saved = 0
        self.session = requests.Session()
        self.session.max_redirects = 5
        self.session.headers["User-Agent"] = "WQU-Support-RAG/0.1 (public help-center indexer)"

    def crawl(
        self,
        max_pages: int = 1_000,
        on_page: Callable[[int, str], None] | None = None,
    ) -> list[SourceDocument]:
        queue: deque[str] = deque([ROOT_URL])
        visited: set[str] = set()
        documents: list[SourceDocument] = []
        self._prepare_raw_output()

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
                documents.append(
                    self._save_raw_document(url=url, title=title, category=category, content=body)
                )

            time.sleep(self.delay_seconds)
        return documents

    def _prepare_raw_output(self) -> None:
        if self.raw_output is None:
            return
        self.raw_output.mkdir(parents=True, exist_ok=True)

    def clear_raw_documents(self) -> None:
        """Remove only generated document files from the configured local source store."""
        if self.raw_output is None:
            return
        for directory_name in ("metadata", "content"):
            directory = self.raw_output / directory_name
            if directory.is_dir():
                rmtree(directory)

    def _save_raw_document(
        self, *, url: str, title: str, category: str | None, content: str
    ) -> SourceDocument:
        document = SourceDocument(
            id=document_id_for_url(url),
            url=url,
            title=title,
            category=category,
            fetched_at=datetime.now(UTC).isoformat(),
            content=content,
        )
        if self.raw_output is None:
            return document
        write_document(self.raw_output, document)
        self.raw_documents_saved += 1
        return document
