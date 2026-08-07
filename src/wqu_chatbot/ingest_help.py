import argparse
from pathlib import Path

from .chunking import make_chunks
from .local_documents import load_documents
from .vector_store import VectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Index local WQU Help Center documents into Qdrant.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/wqu_help_raw/documents/help"),
        help="Directory containing metadata/ and content/ for Help Center documents.",
    )
    args = parser.parse_args()

    documents = load_documents(args.input_dir)
    if not documents:
        raise RuntimeError(f"No WQU Help Center documents found in {args.input_dir}.")
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
        raise RuntimeError("The local WQU Help Center documents did not contain chunkable content.")
    VectorStore().upsert(chunks)
    print(f"Loaded {len(documents)} local documents and indexed {len(chunks)} chunks.")


if __name__ == "__main__":
    main()
