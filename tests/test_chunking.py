from wqu_chatbot.chunking import chunk_text, make_chunks


def test_chunk_text_preserves_content_and_overlap() -> None:
    text = "A" * 700 + "\n" + "B" * 700
    chunks = chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) == 2
    assert chunks[0].startswith("A")
    assert chunks[1].endswith("B")


def test_chunk_ids_are_stable() -> None:
    first = make_chunks(text="Useful content", title="Title", url="https://example.test/a", category=None)
    second = make_chunks(text="Useful content", title="Title", url="https://example.test/a", category=None)
    assert first[0].id == second[0].id
    assert first[0].source_type == "procedure"

