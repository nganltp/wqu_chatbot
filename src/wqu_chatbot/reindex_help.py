"""Replace the Qdrant collection with one local WQU Help Center snapshot."""

import argparse
from pathlib import Path

from .chunking import make_chunks
from .local_documents import load_documents
from .vector_store import VectorStore

HELP_ARTICLE_PREFIX = "https://help.wqu.edu/en/articles/"


def reindex_help(input_dir: Path, store: VectorStore | None = None) -> tuple[int, int]:
    """Reset Qdrant, then index only WQU Help Center article documents."""
    documents = load_documents(input_dir)
    if not documents:
        raise RuntimeError(f"No local WQU Help Center documents found in {input_dir}.")
    if any(
        document.source_type != "procedure" or not document.url.startswith(HELP_ARTICLE_PREFIX)
        for document in documents
    ):
        raise ValueError(f"{input_dir} contains documents outside the WQU Help Center.")

    chunks = [
        chunk
        for document in documents
        for chunk in make_chunks(
            text=document.content,
            title=document.title,
            url=document.url,
            category=document.category,
            source_type=document.source_type,
        )
    ]
    if not chunks:
        raise RuntimeError(f"The local documents in {input_dir} did not contain chunkable content.")

    store = store or VectorStore()
    store.reset()
    store.upsert(chunks)
    return len(documents), len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace Qdrant with local WQU Help Center articles.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/wqu_help_raw/documents/help"),
        help="Folder containing a WQU Help Center metadata/ and content/ snapshot.",
    )
    args = parser.parse_args()

    document_count, chunk_count = reindex_help(args.input_dir)
    print(f"Reset Qdrant and indexed {chunk_count} chunks from {document_count} Help Center articles.")


if __name__ == "__main__":
    main()
