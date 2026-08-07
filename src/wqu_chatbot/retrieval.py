"""Keyword retrieval and rank fusion helpers for the RAG pipeline."""

import math
import re
from collections import Counter
from dataclasses import dataclass

from .models import SourceChunk

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


@dataclass(frozen=True)
class KeywordResult:
    chunk: SourceChunk
    score: float


class BM25Index:
    """Small in-process BM25 index over the current Qdrant collection."""

    def __init__(self, documents: list[tuple[SourceChunk, str]], k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.term_counts = [Counter(tokenize(text)) for _, text in documents]
        self.document_lengths = [sum(counts.values()) for counts in self.term_counts]
        self.average_document_length = (
            sum(self.document_lengths) / len(self.document_lengths)
            if self.document_lengths
            else 0.0
        )
        self.document_frequencies = Counter(
            token for counts in self.term_counts for token in counts
        )

    def search(self, query: str, limit: int) -> list[KeywordResult]:
        query_terms = set(tokenize(query))
        if not query_terms or not self.documents:
            return []

        document_count = len(self.documents)
        scored: list[KeywordResult] = []
        for (chunk, _), counts, length in zip(
            self.documents, self.term_counts, self.document_lengths, strict=True
        ):
            score = 0.0
            for term in query_terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                document_frequency = self.document_frequencies[term]
                idf = math.log(
                    1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length / self.average_document_length
                )
                score += idf * frequency * (self.k1 + 1) / denominator
            if score > 0:
                scored.append(KeywordResult(chunk=chunk, score=score))
        return sorted(scored, key=lambda result: result.score, reverse=True)[:limit]


def reciprocal_rank_fusion(
    dense: list[SourceChunk], keyword: list[SourceChunk], rank_constant: int
) -> list[tuple[SourceChunk, float]]:
    """Combine rankings while avoiding incomparable dense and BM25 score scales."""
    scores: dict[str, float] = {}
    chunks: dict[str, SourceChunk] = {}
    for ranking in (dense, keyword):
        for rank, chunk in enumerate(ranking, start=1):
            chunks[chunk.id] = chunk
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1 / (rank_constant + rank)
    return sorted(
        ((chunks[chunk_id], score) for chunk_id, score in scores.items()),
        key=lambda result: result[1],
        reverse=True,
    )
