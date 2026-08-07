"""Read and write complete Help Center documents in the local document store."""

import hashlib
import json
from pathlib import Path

from .models import SourceDocument


def document_id_for_url(url: str) -> str:
    return f"help-{hashlib.sha256(url.encode()).hexdigest()}"


def write_document(root: Path, document: SourceDocument) -> None:
    document_id = document.id
    metadata_directory = root / "metadata"
    content_directory = root / "content"
    metadata_directory.mkdir(parents=True, exist_ok=True)
    content_directory.mkdir(parents=True, exist_ok=True)

    metadata = {
        "schema_version": 1,
        "document_id": document_id,
        "content_id": document_id,
        "source_type": document.source_type,
        "document_type": "help_article",
        "title": document.title,
        "source": {
            "canonical_url": document.url,
            "fetched_at": document.fetched_at,
        },
        "classification": {
            "category": document.category,
            "course": document.course,
            "chapter": document.chapter,
            "language": "en",
        },
        "workflow": {
            "status": "crawled",
            "approved_for_ingest": False,
        },
    }
    (metadata_directory / f"{document_id}.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (content_directory / f"{document_id}.md").write_text(
        document.content.strip() + "\n", encoding="utf-8"
    )


def load_documents(root: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for metadata_path in sorted((root / "metadata").glob("*.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        document_id = metadata["document_id"]
        content_id = metadata.get("content_id", document_id)
        content_path = root / "content" / f"{content_id}.md"
        if not content_path.is_file():
            raise FileNotFoundError(f"Content file for {document_id} is missing: {content_path}")
        source = metadata["source"]
        classification = metadata.get("classification", {})
        documents.append(
            SourceDocument(
                id=document_id,
                content=content_path.read_text(encoding="utf-8").strip(),
                title=metadata["title"],
                url=source["canonical_url"],
                source_type=metadata.get("source_type", "procedure"),
                category=classification.get("category"),
                course=classification.get("course"),
                chapter=classification.get("chapter"),
                fetched_at=source.get("fetched_at"),
            )
        )
    return documents
