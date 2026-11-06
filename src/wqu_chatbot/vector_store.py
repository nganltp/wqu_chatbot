from functools import lru_cache

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from .config import get_settings
from .models import SourceChunk
from .retrieval import BM25Index, reciprocal_rank_fusion


@lru_cache
def get_embedder() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(
        settings.embedding_model,
        device=settings.embedding_device,
        token=settings.hf_token,
    )


class VectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = (
            QdrantClient(path=self.settings.qdrant_local_path)
            if self.settings.qdrant_local_path
            else QdrantClient(url=self.settings.qdrant_url)
        )
        self.embedder = get_embedder()
        self.keyword_index: BM25Index | None = None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.settings.qdrant_collection):
            return
        dimension = len(self._embed(["dimension probe"])[0])
        self.client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
        )

    def upsert(self, chunks: list[SourceChunk], batch_size: int = 64) -> None:
        self.ensure_collection()
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = self._embed([self._document_for_embedding(chunk) for chunk in batch])
            points = [
                models.PointStruct(id=chunk.id, vector=vector, payload=chunk.model_dump())
                for chunk, vector in zip(batch, vectors, strict=True)
            ]
            self.client.upsert(self.settings.qdrant_collection, points=points, wait=True)
        self.keyword_index = None

    def reset(self) -> None:
        """Delete the configured collection so the next upsert is a complete replacement."""
        if self.client.collection_exists(self.settings.qdrant_collection):
            self.client.delete_collection(self.settings.qdrant_collection)
        self.keyword_index = None

    def search(self, query: str, limit: int | None = None) -> list[tuple[SourceChunk, float]]:
        self.ensure_collection()
        results = self.client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=self._embed([query])[0],
            limit=limit or self.settings.top_k,
            with_payload=True,
        ).points
        return [(SourceChunk.model_validate(hit.payload), hit.score) for hit in results]

    def search_hybrid(
        self, query: str, limit: int | None = None
    ) -> list[tuple[SourceChunk, float]]:
        """Fuse eligible dense and BM25 rankings with reciprocal rank fusion."""
        dense = self.search(query, limit=self.settings.hybrid_dense_candidates)
        keyword = self.keyword_search(query, limit=self.settings.hybrid_keyword_candidates)
        eligible_dense = [
            chunk for chunk, score in dense if score >= self.settings.min_retrieval_score
        ]
        eligible_keyword = [
            result.chunk
            for result in keyword
            if result.score >= self.settings.hybrid_min_keyword_score
        ]
        fused = reciprocal_rank_fusion(
            eligible_dense,
            eligible_keyword,
            self.settings.hybrid_rrf_rank_constant,
        )
        return fused[: limit or self.settings.top_k]

    def keyword_search(self, query: str, limit: int) -> list:
        if self.keyword_index is None:
            self.keyword_index = BM25Index(
                [(chunk, self._document_for_embedding(chunk)) for chunk in self._all_chunks()]
            )
        return self.keyword_index.search(query, limit)

    def _all_chunks(self) -> list[SourceChunk]:
        self.ensure_collection()
        chunks: list[SourceChunk] = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.settings.qdrant_collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(SourceChunk.model_validate(point.payload) for point in points)
            if offset is None:
                return chunks

    @staticmethod
    def _document_for_embedding(chunk: SourceChunk) -> str:
        parts = [f"Title: {chunk.title}"]
        if chunk.category:
            parts.append(f"Category: {chunk.category}")
        if chunk.course:
            parts.append(f"Course: {chunk.course}")
        if chunk.chapter:
            parts.append(f"Chapter: {chunk.chapter}")
        parts.append(chunk.text)
        return "\n".join(parts)
