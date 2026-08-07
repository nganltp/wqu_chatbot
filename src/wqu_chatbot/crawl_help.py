"""Crawl the public WQU Help Center into local, complete source documents."""

import argparse
from pathlib import Path

from .help_crawler import HelpCenterCrawler


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl WQU Help Center documents to local storage.")
    parser.add_argument("--max-pages", type=int, default=1_000)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/wqu_help_raw/documents/help"),
        help="Directory for complete, pre-chunk Help Center documents.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    progress = (
        (lambda page, url: print(f"Crawling page {page}: {url}", flush=True))
        if args.verbose
        else None
    )
    crawler = HelpCenterCrawler(
        delay_seconds=args.delay, timeout_seconds=args.timeout, raw_output=args.output_dir
    )
    documents = crawler.crawl(max_pages=args.max_pages, on_page=progress)
    if not documents:
        raise RuntimeError("No WQU Help Center documents were found.")
    print(f"Saved {len(documents)} source documents to {args.output_dir}.")


if __name__ == "__main__":
    main()
