from openai import OpenAI

from .config import get_settings
from .models import ChatMessage, ChatResponse, SourceChunk, SourceReference
from .vector_store import VectorStore

NOT_FOUND_RESPONSE = (
    "I couldn't find sufficiently reliable information in the WQU Help Center to answer this "
    "question. Please check https://help.wqu.edu/en/ or provide a more specific question."
)

SYSTEM_PROMPT = f"""You are the WQU student-support assistant. Answer in the user's language.
Use only the supplied retrieved sources for factual claims about WQU. If the sources do not
answer the question, reply exactly in English with this sentence: {NOT_FOUND_RESPONSE}
Cite factual claims inline with source labels such as [S1]. Do not invent procedures, deadlines,
links, course names, or chapters. Format answers as concise CommonMark Markdown; use headings or
lists only when they make the answer easier to read."""


def group_chunks_by_url(chunks: list[tuple[SourceChunk, float]]) -> list[list[SourceChunk]]:
    """Keep all relevant chunks in context while assigning one citation per source article."""
    grouped: dict[str, list[SourceChunk]] = {}
    for chunk, _ in chunks:
        grouped.setdefault(chunk.url, []).append(chunk)
    return list(grouped.values())


class RAGService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.store = VectorStore()
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self.llm = OpenAI(api_key=self.settings.openai_api_key)

    def answer(self, question: str, history: list[ChatMessage]) -> ChatResponse:
        history_text = " ".join(
            message.content for message in history[-4:] if message.role == "user"
        )
        retrieved = self.store.search(f"{history_text} {question}".strip())
        usable = [
            (chunk, score)
            for chunk, score in retrieved
            if score >= self.settings.min_retrieval_score
        ]
        if not usable:
            return ChatResponse(
                answer=NOT_FOUND_RESPONSE,
                sources=[],
            )

        context_blocks = []
        references = []
        for index, chunks in enumerate(group_chunks_by_url(usable), start=1):
            chunk = chunks[0]
            label = f"S{index}"
            context_blocks.append(
                f"[{label}]\nTitle: {chunk.title}\nURL: {chunk.url}\nContent:\n"
                + "\n\n---\n\n".join(part.text for part in chunks)
            )
            references.append(
                SourceReference(
                    label=label,
                    title=chunk.title,
                    course=chunk.course,
                    chapter=chunk.chapter,
                    url=chunk.url,
                )
            )

        context = "\n\n".join(context_blocks)
        messages = [message.model_dump() for message in history]
        messages.append(
            {
                "role": "user",
                "content": f"Retrieved sources:\n\n{context}\n\nQuestion: {question}",
            }
        )
        completion = self.llm.responses.create(
            model=self.settings.openai_model,
            instructions=SYSTEM_PROMPT,
            input=messages,
            reasoning={"effort": self.settings.openai_reasoning_effort},
            text={"verbosity": "low"},
        )
        answer = completion.output_text or "I am unable to generate a response right now."
        return ChatResponse(answer=answer, sources=references)
