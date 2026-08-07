from types import SimpleNamespace

from wqu_chatbot.models import SourceChunk
from wqu_chatbot.rag import RAGService, group_chunks_by_url


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


def test_answer_uses_openai_responses_api():
    chunk = make_chunk("first", "https://help.wqu.edu/en/articles/1")
    response_calls = []

    class Store:
        def search_hybrid(self, query):
            return [(chunk, 0.9)]

    class Responses:
        def create(self, **kwargs):
            response_calls.append(kwargs)
            return SimpleNamespace(output_text="Official answer [S1].")

    service = RAGService.__new__(RAGService)
    service.settings = SimpleNamespace(
        min_retrieval_score=0.35,
        openai_model="gpt-5.6-luna",
        openai_reasoning_effort="low",
    )
    service.store = Store()
    service.llm = SimpleNamespace(responses=Responses())

    result = service.answer("A question", [])

    assert result.answer == "Official answer [S1]."
    assert result.sources[0].label == "S1"
    assert response_calls[0]["model"] == "gpt-5.6-luna"
    assert response_calls[0]["reasoning"] == {"effort": "low"}
