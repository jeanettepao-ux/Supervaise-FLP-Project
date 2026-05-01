"""Groq LLM wrapper. Step 1.3 — plumbing only, no persona prompt yet."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


@lru_cache(maxsize=1)
def _client() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def chat(messages: list[dict]) -> str:
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    response = _client().chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content
