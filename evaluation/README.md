# RAG evaluation

`wqu_help_eval.jsonl` is the English seed set for evaluating the public WQU Help Center index. Each line is one JSON object with:

- `id`: stable, unique test-case identifier.
- `question`: the exact English question submitted to the chatbot.
- `answerable`: whether the Help Center is expected to answer it.
- `expected_urls`: one or more canonical supporting URLs for answerable questions; an empty list for unanswerable questions.
- `expected_outcome`: a concise statement used by a human reviewer.

The seed set has 18 answerable procedural questions and 6 out-of-scope questions. Grow it deliberately toward 40–60 cases by adding real, anonymised support questions and their verified source URLs. Do not change existing expected URLs merely to make a retrieval experiment look better.

## Run a baseline

From the repository root, with the local Qdrant index available and Hugging Face configured:

```bash
python -m wqu_chatbot.evaluate
```

This writes timestamped JSON and CSV reports to `data/evaluations/` (which remains local and ignored by Git). The command exits non-zero if any case has an infrastructure or model error. To assess retrieval only, without sending questions to the LLM:

```bash
python -m wqu_chatbot.evaluate --skip-generation
```

The JSON report contains complete retrieved chunks, responses, settings, and machine metrics. The CSV is intended for review and has blank `human_answer_score`, `human_citation_score`, and `review_note` columns.

## Metrics

- **Recall@k:** percentage of answerable cases whose expected URL appears in the top `TOP_K` retrieved chunks.
- **Inline citation rate:** percentage of answerable responses containing at least one returned citation label such as `[S1]`.
- **Automatic fallback correctness:** percentage of unanswerable cases that exactly return the safe fallback and no sources.
- **Latency and error rate:** measured per case and summarised for the run.

The runner cannot establish that a source truly supports an answer. That is intentionally a human review task.

## Human review rubric

For every generated answer, score each field from 0 to 2 in the CSV:

| Score | `human_answer_score` | `human_citation_score` |
| --- | --- | --- |
| 2 | Correct, sufficiently complete, and does not invent material facts. | The cited source directly supports the material claims. |
| 1 | Partly correct, incomplete, or ambiguous; no material fabrication. | Source is related but does not fully support the claims. |
| 0 | Incorrect, unsafe, fabricated, or fails to use the fallback for an unanswerable case. | Missing, invalid, or unrelated citation. |

Record a brief cause in `review_note`, such as `wrong article retrieved`, `correct source but incomplete`, `unsupported deadline`, or `fallback should have been used`. Compare these notes across runs before changing retrieval, chunking, or prompts.
