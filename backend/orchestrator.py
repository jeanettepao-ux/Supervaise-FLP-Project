"""Backend orchestration - retrieve, ground, generate. Day-15 convergence."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from backend.llm import chat
from backend.prompts import fallback, system_prompt
from backend.retrieval import RetrievedChunk, retrieve


@dataclass
class Response:
    text: str
    citations: list = field(default_factory=list)
    latency_ms: float = 0.0
    fallback: bool = False
    fallback_reason: str | None = None


def _format_sources_message(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f'[{i}] "{c.title}" ({c.date})\n    {c.text}')
    return (
        "Provided sources (CJ Panganiban's published columns). "
        "Answer ONLY from these passages.\n\n" + "\n\n".join(parts)
    )


def _trim_to_word_limit(text: str, limit: int = 150) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(",.;: ") + "..."


def _citations_from(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "title": c.title,
            "date": c.date,
            "url": c.url,
            "bucket": c.bucket,
            "distance": round(c.distance, 3),
            "citation_safe": c.citation_safe,
        }
        for c in chunks
    ]


def answer_question(text: str, history: list[dict] | None = None) -> Response:
    start = time.perf_counter()

    chunks = retrieve(text)

    if not chunks:
        latency_ms = (time.perf_counter() - start) * 1000
        return Response(
            text=fallback(),
            latency_ms=latency_ms,
            fallback=True,
            fallback_reason="no chunks above retrieval threshold",
        )

    messages = [
        {"role": "system", "content": system_prompt()},
        {"role": "system", "content": _format_sources_message(chunks)},
        *(history or []),
        {"role": "user", "content": text},
    ]
    answer = chat(messages)
    answer = _trim_to_word_limit(answer, limit=150)

    latency_ms = (time.perf_counter() - start) * 1000
    return Response(
        text=answer,
        citations=_citations_from(chunks),
        latency_ms=latency_ms,
    )
