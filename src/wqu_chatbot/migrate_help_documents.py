"""Migrate flat Help Center JSON documents into the local document-store layout."""

import argparse
import json
from pathlib import Path

from .local_documents import document_id_for_url, write_document
from .models import SourceDocument


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate flat Help Center JSON documents.")
    parser.add_argument("source_dir", type=Path, help="Directory containing the old flat JSON files.")
    parser.add_argument("output_dir", type=Path, help="Destination document-store directory.")
    args = parser.parse_args()

    source_paths = sorted(args.source_dir.glob("*.json"))
    if not source_paths:
        raise RuntimeError(f"No flat JSON documents found in {args.source_dir}.")
    for source_path in source_paths:
        document = SourceDocument.model_validate(
            json.loads(source_path.read_text(encoding="utf-8"))
        )
        document.id = document_id_for_url(document.url)
        write_document(args.output_dir, document)
    print(f"Migrated {len(source_paths)} documents to {args.output_dir}.")


if __name__ == "__main__":
    main()
