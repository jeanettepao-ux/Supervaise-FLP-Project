"""Loads system instructions and fallback text from prompts/. Step 1.6."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=1)
def fallback() -> str:
    text = (_PROMPTS_DIR / "fallback.txt").read_text(encoding="utf-8")
    return text.split("(Placeholder")[0].strip()


@lru_cache(maxsize=1)
def system_prompt() -> str:
    template = (_PROMPTS_DIR / "instructions.txt").read_text(encoding="utf-8")
    return template.replace("{FALLBACK}", fallback()).strip()
