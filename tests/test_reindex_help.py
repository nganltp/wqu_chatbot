import pytest

from wqu_chatbot.local_documents import write_document
from wqu_chatbot.models import SourceDocument
from wqu_chatbot.reindex_help import reindex_help


def test_reindex_help_resets_store_and_indexes_all_chunks(tmp_path):
    write_document(
        tmp_path,
        SourceDocument(
            id="help-example",
            title="Help article",
            url="https://help.wqu.edu/en/articles/example/",
            category="General",
            content="Complete help article content.",
        ),
    )

    class Store:
        def __init__(self):
            self.reset_called = False
            self.chunks = []

        def reset(self):
            self.reset_called = True

        def upsert(self, chunks):
            self.chunks = chunks

    store = Store()

    document_count, chunk_count = reindex_help(tmp_path, store=store)

    assert (document_count, chunk_count) == (1, 1)
    assert store.reset_called
    assert store.chunks[0].url == "https://help.wqu.edu/en/articles/example/"


def test_reindex_help_rejects_non_help_documents(tmp_path):
    write_document(
        tmp_path,
        SourceDocument(
            id="lecture-example",
            title="Lecture",
            url="https://example.test/lecture/",
            source_type="lecture",
            content="Course material.",
        ),
    )

    with pytest.raises(ValueError, match="outside the WQU Help Center"):
        reindex_help(tmp_path)
