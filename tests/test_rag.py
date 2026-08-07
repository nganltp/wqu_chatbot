from wqu_chatbot.models import SourceChunk
from wqu_chatbot.rag import group_chunks_by_url


def make_chunk(identifier: str, url: str) -> SourceChunk:
    return SourceChunk(
        id=identifier,
        text=f"Text {identifier}",
        title="Article",
        url=url,
        source_type="procedure",
    )


def test_group_chunks_by_url_assigns_one_source_per_article() -> None:
    first = make_chunk("first", "https://help.wqu.edu/en/articles/1")
    second = make_chunk("second", "https://help.wqu.edu/en/articles/1")
    third = make_chunk("third", "https://help.wqu.edu/en/articles/2")

    grouped = group_chunks_by_url([(first, 0.9), (second, 0.8), (third, 0.7)])

    assert grouped == [[first, second], [third]]
