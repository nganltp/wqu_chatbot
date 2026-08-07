import json

from wqu_chatbot.help_crawler import HelpCenterCrawler


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
