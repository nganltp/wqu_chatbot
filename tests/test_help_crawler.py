import json

from bs4 import BeautifulSoup

from wqu_chatbot.help_crawler import HelpCenterCrawler, _text


def test_save_raw_document_writes_complete_pre_chunk_article(tmp_path):
    crawler = HelpCenterCrawler(raw_output=tmp_path)
    crawler._prepare_raw_output()

    crawler._save_raw_document(
        url="https://help.wqu.edu/en/articles/example/",
        title="Example article",
        category="Getting started",
        content="Complete article body before chunking.",
    )

    metadata_files = list((tmp_path / "metadata").glob("*.json"))
    assert len(metadata_files) == 1
    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["source"]["canonical_url"] == "https://help.wqu.edu/en/articles/example/"
    assert metadata["title"] == "Example article"
    content_path = tmp_path / "content" / f"{metadata['content_id']}.md"
    assert content_path.read_text(encoding="utf-8") == "Complete article body before chunking.\n"
    assert crawler.raw_documents_saved == 1


def test_text_decodes_cloudflare_protected_email():
    # The first byte is the XOR key (0x2A); the remaining bytes encode admissions@wqu.edu.
    soup = BeautifulSoup(
        '<article>Email <span class="__cf_email__" '
        'data-cfemail="2a4b4e47435959434544596a5d5b5f044f4e5f">[email protected]</span></article>',
        "html.parser",
    )

    assert _text(soup.article) == "Email\nadmissions@wqu.edu"


def test_clear_raw_documents_removes_only_generated_document_folders(tmp_path):
    (tmp_path / "metadata").mkdir()
    (tmp_path / "content").mkdir()
    (tmp_path / "metadata" / "old.json").write_text("old", encoding="utf-8")
    (tmp_path / "content" / "old.md").write_text("old", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("keep", encoding="utf-8")

    HelpCenterCrawler(raw_output=tmp_path).clear_raw_documents()

    assert not (tmp_path / "metadata").exists()
    assert not (tmp_path / "content").exists()
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "keep"
