"""Backend orchestration - retrieve, ground, generate. Day-15 convergence."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from backend.llm import chat
from backend.prompts import fallback, system_prompt
from backend.retrieval import RetrievedChunk, retrieve


# Strip markdown heading lines (#, ##, ###...) from text. Streamlit renders
# them as oversized H1/H2/H3 in the chat UI, which is jarring inside an
# answer that should be plain prose. Used both for chunks (before they go
# to the LLM, so the LLM doesn't see/copy the column title twice) and for
# the LLM's response (defense in depth — if the LLM still emits headings,
# we strip them before display).
_MD_HEADING_RE = re.compile(r"(?m)^\s*#+\s+")
_MD_LEADING_TITLE_RE = re.compile(r"^\s*#+\s+[^\n]+\n+")


@dataclass
class Response:
    text: str
    citations: list = field(default_factory=list)
    latency_ms: float = 0.0
    fallback: bool = False
    fallback_reason: str | None = None


def _strip_chunk_title_heading(text: str) -> str:
    """Remove the leading '# Title' line from a chunk's body — the column's
    title is already passed to the LLM via the citation label, no need for
    it to appear twice in the prompt (causes the LLM to echo it back as
    a heading in its answer)."""
    return _MD_LEADING_TITLE_RE.sub("", text).strip()


def _strip_response_headings(text: str) -> str:
    """Defense in depth: strip any markdown heading prefixes the LLM still
    emits in its answer, so the chat UI doesn't render them as H1."""
    return _MD_HEADING_RE.sub("", text)


def _format_sources_message(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        body = _strip_chunk_title_heading(c.text)
        parts.append(f'[{i}] "{c.title}" ({c.date})\n    {body}')
    return (
        "Provided sources (CJ Panganiban's published columns). "
        "Answer ONLY from these passages. Reply in plain prose — do NOT "
        "use markdown headings (#, ##) or repeat source titles as headings.\n\n"
        + "\n\n".join(parts)
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
    answer = _strip_response_headings(answer)
    answer = _trim_to_word_limit(answer, limit=150)

    latency_ms = (time.perf_counter() - start) * 1000
    return Response(
        text=answer,
        citations=_citations_from(chunks),
        latency_ms=latency_ms,
    )
