"""Backend orchestration — single entry point answer_question(). Wired to Groq in Step 1.3."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from backend.llm import chat


@dataclass
class Response:
    text: str
    citations: list = field(default_factory=list)
    latency_ms: float = 0.0
    fallback: bool = False
    fallback_reason: str | None = None


def answer_question(text: str, history: list[dict] | None = None) -> Response:
    start = time.perf_counter()
    messages = (history or []) + [{"role": "user", "content": text}]
    answer = chat(messages)
    latency_ms = (time.perf_counter() - start) * 1000
    return Response(text=answer, latency_ms=latency_ms)
