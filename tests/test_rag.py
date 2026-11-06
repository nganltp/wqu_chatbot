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
    service.llm.with_options = lambda **kwargs: service.llm

    result = service.answer("A question", [])

    assert result.answer == "Official answer [S1]."
    assert result.sources[0].label == "S1"
    assert response_calls[0]["model"] == "gpt-5.6-luna"
    assert response_calls[0]["reasoning"] == {"effort": "low"}


def test_answer_logs_retrieved_chunks_when_debug_enabled(caplog):
    chunk = make_chunk("first", "https://help.wqu.edu/en/articles/1")

    class Store:
        def search_hybrid(self, query):
            return [(chunk, 0.9)]

    class Responses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text="Official answer [S1].")

    service = RAGService.__new__(RAGService)
    service.settings = SimpleNamespace(
        debug_retrieval=True,
        openai_model="gpt-5.6-luna",
        openai_reasoning_effort="low",
    )
    service.store = Store()
    service.llm = SimpleNamespace(responses=Responses())
    service.llm.with_options = lambda **kwargs: service.llm

    with caplog.at_level("INFO"):
        service.answer("A question", [])

    assert "Retrieved chunks for question='A question'" in caplog.text
    assert "hybrid_score=0.900000" in caplog.text
    assert "content:\nText first" in caplog.text


def test_translation_used_only_for_retrieval_preserves_original_question():
    from wqu_chatbot.models import ChatMessage

    chunk = make_chunk("first", "https://help.wqu.edu/en/articles/1")
    calls, queries = [], []
    question = "khi nào tôi có thể đăng kí khoá học mới"
    translated = "When can I register for my next course?"

    class Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text=translated if len(calls) == 1 else "Trả lời [S1].")

    service = RAGService.__new__(RAGService)
    service.settings = SimpleNamespace(openai_model="test", openai_reasoning_effort="low")
    service.llm = SimpleNamespace(responses=Responses())
    service.llm.with_options = lambda **kwargs: service.llm
    service.store = SimpleNamespace(
        search_hybrid=lambda query: queries.append(query) or [(chunk, 0.9)]
    )
    history = [ChatMessage(role="user", content="Tôi đang học WQU.")]

    result = service.answer(question, history)

    assert queries == [translated]
    assert calls[0]["input"] == f"Tôi đang học WQU. {question}"
    assert calls[1]["input"][0]["content"] == history[0].content
    assert calls[1]["input"][-1]["content"].endswith(f"Question: {question}")
    assert result.answer == "Trả lời [S1]."
    assert result.sources[0].label == "S1"


def test_translation_falls_back_on_empty_response_or_api_error():
    from openai import OpenAIError

    service = RAGService.__new__(RAGService)
    service.settings = SimpleNamespace(openai_model="test", openai_reasoning_effort="low")

    class Responses:
        def create(self, **kwargs):
            if self.fail:
                raise OpenAIError("translation unavailable")
            return SimpleNamespace(output_text="   ")

    responses = Responses()
    service.llm = SimpleNamespace(responses=responses)
    service.llm.with_options = lambda **kwargs: service.llm
    for fail in (False, True):
        responses.fail = fail
        assert service.translate_retrieval_query("câu hỏi gốc") == "câu hỏi gốc"
