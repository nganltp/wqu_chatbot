"""Run repeatable retrieval and groundedness evaluations for the WQU chatbot."""

import argparse
import csv
import json
import statistics
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from .models import ChatResponse
from .rag import NOT_FOUND_RESPONSE, RAGService

DEFAULT_DATASET = Path("evaluation/wqu_help_eval.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/evaluations")


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    question: str
    answerable: bool
    expected_urls: tuple[str, ...]
    expected_outcome: str


def load_cases(path: Path) -> list[EvaluationCase]:
    """Load and validate JSONL evaluation cases without needing external packages."""
    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            case = EvaluationCase(
                id=item["id"],
                question=item["question"],
                answerable=item["answerable"],
                expected_urls=tuple(item["expected_urls"]),
                expected_outcome=item["expected_outcome"],
            )
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid case at {path}:{line_number}") from error
        if not isinstance(case.id, str) or not case.id.strip() or case.id in seen_ids:
            raise ValueError(f"Case IDs must be unique non-empty strings ({path}:{line_number})")
        if not isinstance(case.question, str) or not case.question.strip():
            raise ValueError(f"Question must be a non-empty string ({path}:{line_number})")
        if not isinstance(case.answerable, bool):
            raise TypeError(f"answerable must be true or false ({path}:{line_number})")
        if not isinstance(case.expected_outcome, str) or not case.expected_outcome.strip():
            raise ValueError(f"expected_outcome must be a non-empty string ({path}:{line_number})")
        if any(
            not isinstance(url, str) or not url.startswith("https://") for url in case.expected_urls
        ):
            raise ValueError(f"expected_urls must contain HTTPS URLs ({path}:{line_number})")
        if case.answerable != bool(case.expected_urls):
            raise ValueError(
                "Answerable cases need one or more expected_urls; unanswerable cases need none "
                f"({path}:{line_number})"
            )
        cases.append(case)
        seen_ids.add(case.id)
    if not cases:
        raise ValueError(f"No cases found in {path}")
    return cases


def urls_from_response(response: ChatResponse) -> list[str]:
    return [str(source.url) for source in response.sources]


def inline_citation_present(response: ChatResponse) -> bool:
    return any(f"[{source.label}]" in response.answer for source in response.sources)


def evaluate_case(service: Any, case: EvaluationCase, generate_answers: bool) -> dict[str, Any]:
    """Run one case and return machine metrics plus blank manual-review fields."""
    result: dict[str, Any] = {
        **asdict(case),
        "retrieval_latency_ms": None,
        "generation_latency_ms": None,
        "total_latency_ms": None,
        "retrieved": [],
        "retrieval_hit": None,
        "answer": None,
        "returned_source_urls": [],
        "inline_citation_present": None,
        "automatic_fallback_correct": None,
        "error": None,
        "human_answer_score": None,
        "human_citation_score": None,
        "review_note": "",
    }
    started_at = perf_counter()
    try:
        retrieval_started_at = perf_counter()
        retrieved = service.store.search(case.question)
        result["retrieval_latency_ms"] = round((perf_counter() - retrieval_started_at) * 1_000, 1)
        result["retrieved"] = [
            {"url": chunk.url, "title": chunk.title, "score": round(score, 5)}
            for chunk, score in retrieved
        ]
        retrieved_urls = {chunk.url for chunk, _ in retrieved}
        result["retrieval_hit"] = (
            bool(set(case.expected_urls) & retrieved_urls) if case.answerable else None
        )

        if generate_answers:
            generation_started_at = perf_counter()
            response = service.answer(case.question, [])
            result["generation_latency_ms"] = round(
                (perf_counter() - generation_started_at) * 1_000, 1
            )
            result["answer"] = response.answer
            result["returned_source_urls"] = urls_from_response(response)
            result["inline_citation_present"] = inline_citation_present(response)
            if not case.answerable:
                result["automatic_fallback_correct"] = (
                    response.answer == NOT_FOUND_RESPONSE and not response.sources
                )
    except Exception as error:  # noqa: BLE001 - A report must capture any service failure per case.
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        result["total_latency_ms"] = round((perf_counter() - started_at) * 1_000, 1)
    return result


def percentage(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100, 1) if denominator else None


def summarise(results: list[dict[str, Any]], generate_answers: bool) -> dict[str, Any]:
    answerable = [result for result in results if result["answerable"]]
    unanswerable = [result for result in results if not result["answerable"]]
    completed = [result for result in results if not result["error"]]
    generated_answerable = [result for result in answerable if result["answer"] is not None]
    generated_unanswerable = [result for result in unanswerable if result["answer"] is not None]
    retrieval_hits = sum(result["retrieval_hit"] is True for result in answerable)
    answerable_with_inline_citation = sum(
        result["inline_citation_present"] is True for result in answerable
    )
    correct_fallbacks = sum(result["automatic_fallback_correct"] is True for result in unanswerable)
    latency_values = [result["total_latency_ms"] for result in completed]
    summary = {
        "case_count": len(results),
        "answerable_case_count": len(answerable),
        "unanswerable_case_count": len(unanswerable),
        "error_count": len(results) - len(completed),
        "error_rate_percent": percentage(len(results) - len(completed), len(results)),
        "recall_at_k_percent": percentage(retrieval_hits, len(answerable)),
        "median_total_latency_ms": round(statistics.median(latency_values), 1)
        if latency_values
        else None,
    }
    if generate_answers:
        summary.update(
            {
                "inline_citation_rate_percent": percentage(
                    answerable_with_inline_citation, len(generated_answerable)
                ),
                "automatic_fallback_correctness_percent": percentage(
                    correct_fallbacks, len(generated_unanswerable)
                ),
                "generated_answerable_case_count": len(generated_answerable),
                "generated_unanswerable_case_count": len(generated_unanswerable),
            }
        )
    return summary


def write_csv(path: Path, results: list[dict[str, Any]]) -> None:
    fieldnames = [
        "id",
        "question",
        "answerable",
        "expected_urls",
        "expected_outcome",
        "retrieval_hit",
        "retrieval_latency_ms",
        "generation_latency_ms",
        "total_latency_ms",
        "inline_citation_present",
        "automatic_fallback_correct",
        "error",
        "human_answer_score",
        "human_citation_score",
        "review_note",
        "answer",
        "returned_source_urls",
        "retrieved",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = result.copy()
            for field in ("expected_urls", "returned_source_urls", "retrieved"):
                row[field] = json.dumps(row[field], ensure_ascii=False)
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate WQU retrieval and groundedness.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--skip-generation",
        action="store_true",
        help="Measure retrieval only; do not call the LLM or produce answer-quality fields.",
    )
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    service = RAGService()
    generate_answers = not args.skip_generation
    results = [evaluate_case(service, case, generate_answers) for case in cases]
    summary = summarise(results, generate_answers)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"evaluation-{timestamp}.json"
    csv_path = args.output_dir / f"evaluation-{timestamp}.csv"
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": str(args.dataset),
        "generation_enabled": generate_answers,
        "settings": {
            "embedding_model": service.settings.embedding_model,
            "openai_model": service.settings.openai_model,
            "openai_reasoning_effort": service.settings.openai_reasoning_effort,
            "top_k": service.settings.top_k,
            "min_retrieval_score": service.settings.min_retrieval_score,
        },
        "summary": summary,
        "results": results,
    }
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(csv_path, results)
    print(
        json.dumps({"summary": summary, "json_report": str(json_path), "review_csv": str(csv_path)})
    )
    if summary["error_count"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
