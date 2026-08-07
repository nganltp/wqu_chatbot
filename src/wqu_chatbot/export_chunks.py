"""Export indexed RAG chunks into a human-readable plain-text file."""

import argparse
from pathlib import Path

from qdrant_client import QdrantClient

from .config import get_settings
from .models import SourceChunk


def get_client() -> QdrantClient:
    settings = get_settings()
    if settings.qdrant_local_path:
        return QdrantClient(path=settings.qdrant_local_path)
    return QdrantClient(url=settings.qdrant_url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export WQU RAG chunks as readable plain text.")
    parser.add_argument("--output", type=Path, default=Path("data/wqu_help_chunks.txt"))
    args = parser.parse_args()

    settings = get_settings()
    client = get_client()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    offset = None
    chunk_number = 0

    with args.output.open("w", encoding="utf-8") as file:
        while True:
            points, offset = client.scroll(
                collection_name=settings.qdrant_collection,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                chunk_number += 1
                chunk = SourceChunk.model_validate(point.payload)
                file.write(
                    f"{'=' * 80}\n"
                    f"CHUNK {chunk_number}\n"
                    f"TITLE: {chunk.title}\n"
                    f"CATEGORY: {chunk.category or ''}\n"
                    f"COURSE: {chunk.course or ''}\n"
                    f"CHAPTER: {chunk.chapter or ''}\n"
                    f"URL: {chunk.url}\n"
                    f"{'-' * 80}\n"
                    f"{chunk.text}\n\n"
                )
            if offset is None:
                break

    print(f"Exported {chunk_number} chunks to {args.output}")


if __name__ == "__main__":
    main()
