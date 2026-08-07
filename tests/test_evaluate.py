import json

import pytest

from wqu_chatbot.evaluate import EvaluationCase, evaluate_case, load_cases, summarise
from wqu_chatbot.models import ChatResponse, SourceChunk, SourceReference
from wqu_chatbot.rag import NOT_FOUND_RESPONSE

EXPECTED_URL = "https://help.wqu.edu/en/articles/1"


class FakeStore:
    def search(self, question: str):
        return [
            (
                SourceChunk(
                    id="chunk-1",
                    text="Answer text",
                    title="Article",
                    url=EXPECTED_URL,
                    source_type="procedure",
                ),
                0.9,
            )
        ]


class FakeService:
    store = FakeStore()

    def answer(self, question: str, history: list):
        return ChatResponse(
            answer="The answer is here [S1].",
            sources=[SourceReference(label="S1", title="Article", url=EXPECTED_URL)],
        )


def test_load_cases_rejects_answerable_case_without_url(tmp_path):
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "missing-url",
                "question": "A question",
                "answerable": True,
                "expected_urls": [],
                "expected_outcome": "An outcome",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Answerable cases"):
        load_cases(dataset)


def test_evaluate_case_measures_retrieval_and_citation():
    case = EvaluationCase(
        id="case-1",
        question="A question",
        answerable=True,
        expected_urls=(EXPECTED_URL,),
        expected_outcome="An outcome",
    )

    result = evaluate_case(FakeService(), case, generate_answers=True)

    assert result["retrieval_hit"] is True
    assert result["inline_citation_present"] is True
    assert result["error"] is None
    assert summarise([result], generate_answers=True)["recall_at_k_percent"] == 100.0


def test_evaluate_case_checks_unanswerable_fallback():
    class FallbackService:
        store = FakeStore()

        def answer(self, question: str, history: list):
            return ChatResponse(answer=NOT_FOUND_RESPONSE, sources=[])

    case = EvaluationCase(
        id="out-of-scope",
        question="Out of scope",
        answerable=False,
        expected_urls=(),
        expected_outcome="Fallback",
    )

    result = evaluate_case(FallbackService(), case, generate_answers=True)

    assert result["automatic_fallback_correct"] is True
    assert (
        summarise([result], generate_answers=True)["automatic_fallback_correctness_percent"]
        == 100.0
    )
