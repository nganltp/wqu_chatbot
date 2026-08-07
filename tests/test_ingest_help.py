from wqu_chatbot.ingest_help import load_documents
from wqu_chatbot.local_documents import write_document
from wqu_chatbot.models import SourceDocument


def test_load_documents_reads_complete_local_documents(tmp_path):
    write_document(
        tmp_path,
        SourceDocument(
            id="help-example",
            title="Example article",
            url="https://help.wqu.edu/en/articles/example/",
            category="Getting started",
            content="Complete article body before chunking.",
        ),
    )

    documents = load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].title == "Example article"
    assert documents[0].content == "Complete article body before chunking."
