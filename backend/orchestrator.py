"""Backend orchestration — single entry point answer_question(). Hard-coded for Step 1.2."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Response:
    text: str
    citations: list = field(default_factory=list)
    latency_ms: float = 0.0
    fallback: bool = False
    fallback_reason: str | None = None


PLACEHOLDER_ANSWER = (
    "(placeholder) Orchestration is wired but no LLM, persona, or retrieval is "
    "connected yet — see Steps 1.3, 1.6, and the Day-15 RAG convergence."
)


def answer_question(text: str, history: list[dict] | None = None) -> Response:
    start = time.perf_counter()
    answer = PLACEHOLDER_ANSWER
    latency_ms = (time.perf_counter() - start) * 1000
    return Response(text=answer, latency_ms=latency_ms)
