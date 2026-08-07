import uuid

from .models import SourceChunk


def chunk_text(text: str, chunk_size: int = 1_000, overlap: int = 180) -> list[str]:
    """Split readable text on paragraph/sentence boundaries where possible."""
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if len(normalized) <= chunk_size:
        return [normalized] if normalized else []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n", start, end), normalized.rfind(". ", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def make_chunks(
    *, text: str, title: str, url: str, category: str | None, source_type: str = "procedure"
) -> list[SourceChunk]:
    result: list[SourceChunk] = []
    for index, part in enumerate(chunk_text(text)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{url}#{index}"))
        result.append(
            SourceChunk(
                id=point_id,
                text=part,
                title=title,
                url=url,
                category=category,
                source_type=source_type,  # type: ignore[arg-type]
            )
        )
    return result
