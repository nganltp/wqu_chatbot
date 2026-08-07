from huggingface_hub import InferenceClient

from .config import get_settings
from .models import ChatMessage, ChatResponse, SourceReference
from .vector_store import VectorStore

NOT_FOUND_RESPONSE = (
    "I couldn't find sufficiently reliable information in the WQU Help Center to answer this "
    "question. Please check https://help.wqu.edu/en/ or provide a more specific question."
)

SYSTEM_PROMPT = f"""You are the WQU student-support assistant. Answer in the user's language.
Use only the supplied retrieved sources for factual claims about WQU. If the sources do not
answer the question, reply exactly in English with this sentence: {NOT_FOUND_RESPONSE}
Cite factual claims inline with source labels such as [S1]. Do not invent procedures, deadlines,
links, course names, or chapters."""


class RAGService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.store = VectorStore()
        self.llm = InferenceClient(
            model=self.settings.hf_model,
            provider=self.settings.hf_provider,
            api_key=self.settings.hf_token,
        )

    def answer(self, question: str, history: list[ChatMessage]) -> ChatResponse:
        history_text = " ".join(message.content for message in history[-4:] if message.role == "user")
        retrieved = self.store.search(f"{history_text} {question}".strip())
        usable = [(chunk, score) for chunk, score in retrieved if score >= self.settings.min_retrieval_score]
        if not usable:
            return ChatResponse(
                answer=NOT_FOUND_RESPONSE,
                sources=[],
            )

        context_blocks = []
        references = []
        for index, (chunk, _) in enumerate(usable, start=1):
            label = f"S{index}"
            context_blocks.append(
                f"[{label}]\nTitle: {chunk.title}\nURL: {chunk.url}\nContent:\n{chunk.text}"
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
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(message.model_dump() for message in history)
        messages.append(
            {
                "role": "user",
                "content": f"Retrieved sources:\n\n{context}\n\nQuestion: {question}",
            }
        )
        completion = self.llm.chat.completions.create(
            model=self.settings.hf_model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.1,
        )
        answer = completion.choices[0].message.content or "I am unable to generate a response right now."
        return ChatResponse(answer=answer, sources=references)
