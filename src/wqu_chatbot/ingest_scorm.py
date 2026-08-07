"""Save visible learning content from a WQU SCORM launch as one source document."""

import argparse
import base64
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

COURSE_LOCATION_PATTERN = re.compile(r'strContentLocation\s*=\s*"([^"]+)"')
COURSE_DATA_PATTERN = re.compile(r'deserialize\("([A-Za-z0-9+/=]+)"\)')
ASSESSMENT_MARKERS = ("quiz", "knowledge", "assessment", "question")


def _plain_text(value: str) -> str:
    return BeautifulSoup(value, "html.parser").get_text("\n", strip=True)


def _is_assessment(item: dict) -> bool:
    item_type = " ".join(str(item.get(key, "")) for key in ("type", "family", "variant")).lower()
    return any(marker in item_type for marker in ASSESSMENT_MARKERS) or any(
        key.lower().startswith("correct") for key in item
    )


def _collect_visible_text(items: list[dict]) -> list[str]:
    text: list[str] = []

    def visit(item: dict) -> None:
        if _is_assessment(item):
            return
        for field in ("heading", "title", "paragraph", "description"):
            value = item.get(field)
            if isinstance(value, str):
                value = _plain_text(value)
                if value and (not text or value != text[-1]):
                    text.append(value)
        for child in item.get("items", []):
            if isinstance(child, dict):
                visit(child)

    for item in items:
        visit(item)
    return text


def extract_course_document(content_html: str) -> dict:
    match = COURSE_DATA_PATTERN.search(content_html)
    if match is None:
        raise ValueError("The SCORM page did not contain an embedded course document.")
    course_data = json.loads(base64.b64decode(match.group(1)))
    course = course_data["course"]
    lessons = course.get("lessons", [])
    text = _collect_visible_text([lesson for lesson in lessons if isinstance(lesson, dict)])
    return {
        "course_id": course.get("id"),
        "title": course.get("title") or "WQU SCORM course",
        "content": "\n\n".join(text),
    }


def download_course_document(launch_url: str, session: requests.Session | None = None) -> dict:
    session = session or requests.Session()
    launch_response = session.get(launch_url, timeout=30)
    launch_response.raise_for_status()
    location_match = COURSE_LOCATION_PATTERN.search(launch_response.text)
    if location_match is None:
        raise ValueError("The SCORM launch page did not identify its course content URL.")
    content_url = urljoin(launch_response.url, location_match.group(1))
    content_response = session.get(content_url, timeout=30)
    content_response.raise_for_status()
    document = extract_course_document(content_response.text)
    document.update(
        {
            "source_type": "wqu_scorm",
            "source_url": urlunsplit((*urlsplit(launch_response.url)[:3], "", "")),
            "content_url": content_url,
            "fetched_at": datetime.now(UTC).isoformat(),
        }
    )
    return document


def _filename_stem(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "wqu-scorm-course"


def document_id(document: dict) -> str:
    course_id = document.get("course_id") or _filename_stem(document["title"])
    return f"orientation-{course_id}"


def write_scorm_document(document: dict, output_dir: Path) -> Path:
    identifier = document_id(document)
    metadata_directory = output_dir / "metadata"
    content_directory = output_dir / "content"
    metadata_directory.mkdir(parents=True, exist_ok=True)
    content_directory.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema_version": 1,
        "document_id": identifier,
        "content_id": identifier,
        "source_type": "wqu_scorm",
        "document_type": "orientation_course",
        "title": document["title"],
        "source": {
            "canonical_url": document["content_url"],
            "launch_url": document["source_url"],
            "fetched_at": document["fetched_at"],
        },
        "classification": {
            "category": "Orientation",
            "course": "MScFE",
            "chapter": None,
            "language": "en",
        },
        "workflow": {
            "status": "crawled",
            "approved_for_ingest": False,
        },
    }
    (metadata_directory / f"{identifier}.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    content_path = content_directory / f"{identifier}.md"
    content_path.write_text(document["content"].strip() + "\n", encoding="utf-8")
    return content_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Save a WQU SCORM course as a complete document.")
    parser.add_argument("launch_url", help="SCORM launch URL supplied by the authorised learner.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/wqu_help_raw/documents/100-orientation-course"),
        help="Directory for the complete, pre-chunk course document.",
    )
    args = parser.parse_args()

    document = download_course_document(args.launch_url)
    content_path = write_scorm_document(document, args.output_dir)
    print(f"Saved content document to {content_path}")


if __name__ == "__main__":
    main()
