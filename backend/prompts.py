"""Loads system instructions and fallback text from prompts/. Step 1.6.

Fallback variants are separated by a line containing only `---` and one is
picked at random per call. The system prompt is reassembled per call so a
fresh fallback variant is substituted each time.
"""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=1)
def _fallback_variants() -> list[str]:
    text = (_PROMPTS_DIR / "fallback.txt").read_text(encoding="utf-8")
    text = text.split("(Placeholder")[0]
    variants = [v.strip() for v in text.split("---") if v.strip()]
    return variants


def fallback() -> str:
    return random.choice(_fallback_variants())


@lru_cache(maxsize=1)
def _instructions_template() -> str:
    return (_PROMPTS_DIR / "instructions.txt").read_text(encoding="utf-8").strip()


def system_prompt() -> str:
    return _instructions_template().replace("{FALLBACK}", fallback())
