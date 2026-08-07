from wqu_chatbot.models import SourceChunk
from wqu_chatbot.retrieval import BM25Index, reciprocal_rank_fusion


def make_chunk(identifier: str, text: str) -> SourceChunk:
    return SourceChunk(
        id=identifier,
        text=text,
        title=identifier,
        url=f"https://help.wqu.edu/en/articles/{identifier}",
        source_type="procedure",
    )


def test_bm25_prefers_exact_keyword_match():
    veriff = make_chunk("veriff", "Identity verification with Veriff and a government ID")
    transcript = make_chunk("transcript", "How to request an official transcript")
    index = BM25Index([(veriff, f"{veriff.title} {veriff.text}"), (transcript, transcript.text)])

    results = index.search("Veriff verification", limit=2)

    assert [result.chunk.id for result in results] == ["veriff"]


def test_rrf_rewards_a_chunk_found_by_both_rankers():
    dense_first = make_chunk("dense-first", "Dense first")
    shared = make_chunk("shared", "Shared")
    keyword_first = make_chunk("keyword-first", "Keyword first")

    results = reciprocal_rank_fusion(
        [dense_first, shared], [keyword_first, shared], rank_constant=60
    )

    assert results[0][0].id == "shared"
