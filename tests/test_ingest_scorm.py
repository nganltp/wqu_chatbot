import base64
import json

from wqu_chatbot.ingest_scorm import extract_course_document, write_scorm_document


def test_extract_course_document_keeps_visible_content_and_skips_quiz_data():
    course = {
        "course": {
            "id": "orientation",
            "title": "Orientation",
            "lessons": [
                {
                    "title": "Welcome",
                    "items": [
                        {"type": "text", "paragraph": "<p>Read this first.</p>"},
                        {
                            "type": "knowledge-check",
                            "title": "Hidden question",
                            "correctAnswer": "Hidden answer",
                        },
                    ],
                }
            ],
        }
    }
    encoded = base64.b64encode(json.dumps(course).encode()).decode()

    document = extract_course_document(f'<script>deserialize("{encoded}")</script>')

    assert document == {
        "course_id": "orientation",
        "title": "Orientation",
        "content": "Welcome\n\nRead this first.",
    }


def test_write_scorm_document_uses_matching_metadata_and_content_ids(tmp_path):
    document = {
        "course_id": "orientation-1",
        "title": "Orientation",
        "content": "Read this first.",
        "source_url": "https://learn.wqu.edu/launch",
        "content_url": "https://learn.wqu.edu/content",
        "fetched_at": "2026-08-07T00:00:00Z",
    }

    content_path = write_scorm_document(document, tmp_path)

    metadata_path = tmp_path / "metadata" / "orientation-orientation-1.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["document_id"] == metadata["content_id"] == "orientation-orientation-1"
    assert content_path == tmp_path / "content" / "orientation-orientation-1.md"
    assert content_path.read_text(encoding="utf-8") == "Read this first.\n"
