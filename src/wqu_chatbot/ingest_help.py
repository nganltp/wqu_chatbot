import argparse

from .help_crawler import HelpCenterCrawler
from .vector_store import VectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Index the public WQU Help Center into Qdrant.")
    parser.add_argument("--max-pages", type=int, default=1_000)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    progress = (lambda page, url: print(f"Crawling page {page}: {url}", flush=True)) if args.verbose else None
    chunks = HelpCenterCrawler(
        delay_seconds=args.delay, timeout_seconds=args.timeout
    ).crawl(max_pages=args.max_pages, on_page=progress)
    if not chunks:
        raise RuntimeError("No WQU Help Center article chunks were found.")
    VectorStore().upsert(chunks)
    print(f"Indexed {len(chunks)} chunks from WQU Help Center.")


if __name__ == "__main__":
    main()
