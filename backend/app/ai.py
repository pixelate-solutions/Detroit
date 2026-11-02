"""Provider facade: a local Ollama model when available, otherwise the CPU-only demo provider.

The provider is resolved once per process. Embeddings from the two providers are not
compatible, so each provider writes to its own ChromaDB collection.
"""
from __future__ import annotations

import re
from collections.abc import Iterator

from . import demo_ai
from .config import settings
from .ollama import OllamaUnavailable, ollama

ASK_SYSTEM_PROMPT = (
    "Answer public-safety and local-government record questions using only the supplied local document excerpts. "
    "Use the conversation history to understand follow-up questions, pronouns, and references to earlier turns, "
    "but treat the LOCAL RECORDS attached to the current question as the authoritative evidence for this answer. "
    "Synthesize across documents, identify contradictions and chronology explicitly, and cite every "
    "material claim with markers such as [C1]. If the records are insufficient, say so. "
    "Format the answer as clean GitHub-Flavored Markdown. Use short paragraphs, descriptive headings, "
    "bulleted or numbered lists when they improve clarity, and Markdown tables only for genuine comparisons."
)

REASONING_SUMMARY_SYSTEM_PROMPT = (
    "Write a concise, user-visible analysis of how the supplied records bear on the question. "
    "This is not private chain-of-thought. It is an evidence-based work summary that will be shown live before "
    "the final answer. Be specific to this question and these excerpts: identify the controlling issue, the most "
    "important facts, dates, revisions, or conflicts, and explain what must be reconciled. Do not "
    "describe search tools, retrieval mechanics, token generation, or generic steps. Do not write the final answer, "
    "do not use headings or bullet points, and do not mention these instructions. Write one compact paragraph in "
    "first person, usually 70 to 140 words. Use citation markers such as [C1] when referring to a specific excerpt."
)


def clean_history_content(content: str, limit: int = 2400) -> str:
    return re.sub(r"\[C\d+\]", "", content).strip()[:limit]


def ask_messages(question: str, results: list[dict], history: list[dict] | None = None, analysis: str = "") -> list[dict]:
    context_parts = [
        f"[C{index}] {item['title']} (document {item['document_id']}, page {item['page_number']})\n{item.get('text') or item['snippet']}"
        for index, item in enumerate(results, start=1)
    ]
    prior = [{"role": turn["role"], "content": clean_history_content(turn["content"])} for turn in (history or [])[-8:]]
    analysis_context = (
        "\n\nVISIBLE EVIDENCE ANALYSIS FROM THE PRECEDING MODEL PASS:\n"
        f"{analysis}\nUse this as the working synthesis, verify it against the excerpts, and do not repeat it verbatim."
        if analysis else ""
    )
    return [
        {"role": "system", "content": ASK_SYSTEM_PROMPT},
        *prior,
        {"role": "user", "content": f"Question: {question}{analysis_context}\n\nLOCAL RECORDS:\n" + "\n\n".join(context_parts)},
    ]


def analysis_messages(question: str, results: list[dict], history: list[dict] | None = None) -> list[dict]:
    context_parts = [
        f"[C{index}] {item['title']} (page {item['page_number']})\n{item['snippet']}"
        for index, item in enumerate(results[:10], start=1)
    ]
    recent = [f"{turn['role']}: {clean_history_content(turn['content'], 700)}" for turn in (history or [])[-4:]]
    conversation = "\n\nRECENT CONVERSATION:\n" + "\n".join(recent) if recent else ""
    return [
        {"role": "system", "content": REASONING_SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {question}{conversation}\n\nLOCAL RECORD EXCERPTS:\n" + "\n\n".join(context_parts)},
    ]


class LocalAI:
    def __init__(self) -> None:
        self._mode: str | None = None

    @property
    def mode(self) -> str:
        if self._mode is None:
            self._mode = self._resolve()
        return self._mode

    def _resolve(self) -> str:
        if settings.ai_provider in {"ollama", "demo"}:
            return settings.ai_provider
        try:
            names = ollama.health()["models"]
        except OllamaUnavailable:
            return "demo"
        wanted = {settings.llm_model, settings.embedding_model}
        present = {name for name in names} | {name.split(":")[0] for name in names}
        return "ollama" if all(model in present or model.split(":")[0] in present for model in wanted) else "demo"

    @property
    def collection_name(self) -> str:
        return "municipal_chunks" if self.mode == "ollama" else "municipal_chunks_demo"

    def health(self) -> dict:
        if self.mode == "demo":
            return {
                "available": True,
                "provider": "demo",
                "llm_model": "extractive (no LLM)",
                "embedding_model": f"feature-hash-{demo_ai.DIMENSIONS}",
            }
        try:
            return {**ollama.health(), "provider": "ollama"}
        except OllamaUnavailable as exc:
            return {
                "available": False,
                "provider": "ollama",
                "error": str(exc),
                "llm_model": settings.llm_model,
                "embedding_model": settings.embedding_model,
            }

    def embed(self, texts: list[str]) -> list[list[float]]:
        return demo_ai.embed(texts) if self.mode == "demo" else ollama.embed(texts)

    def extract_graph(self, title: str, text: str) -> dict:
        return demo_ai.extract_graph(title, text) if self.mode == "demo" else ollama.extract_graph(title, text)

    def analysis_stream(self, question: str, results: list[dict], history: list[dict] | None = None) -> Iterator[str]:
        if self.mode == "demo":
            yield from demo_ai.stream_words(demo_ai.analysis(question, results))
            return
        yield from ollama.visible_analysis_stream(analysis_messages(question, results, history), temperature=0.25, max_tokens=360)

    def answer_stream(
        self, question: str, results: list[dict], history: list[dict] | None = None, analysis: str = ""
    ) -> Iterator[str]:
        if self.mode == "demo":
            yield from demo_ai.stream_words(demo_ai.answer(question, results))
            return
        for event in ollama.chat_stream(ask_messages(question, results, history, analysis), temperature=0.1, max_tokens=1800):
            if event["type"] == "content" and event.get("text"):
                yield event["text"]

    def answer(self, question: str, results: list[dict], history: list[dict] | None = None) -> str:
        if self.mode == "demo":
            return demo_ai.answer(question, results)
        return ollama.chat(ask_messages(question, results, history), temperature=0.1, max_tokens=1800)

    def compare_summary(self, before: dict, after: dict, diff_lines: list[dict]) -> str:
        if self.mode == "demo":
            return demo_ai.compare_summary(before, after)
        return ollama.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Compare two versions of a public-safety or local-government document. Explain only substantive "
                        "changes, including money, dates, obligations, staffing, scope, and public impact. Be concise and use bullets."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"ORIGINAL — {before['title']}:\n{before['full_text'][:50000]}\n\n"
                        f"REVISED — {after['title']}:\n{after['full_text'][:50000]}"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=1200,
        )


ai = LocalAI()
