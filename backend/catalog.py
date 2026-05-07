"""Catalog-mode helpers for queries like 'give me 5 sample columns'.

These are different from RAG topical questions: they ask for a LIST of CJ's
writings, not for content on a specific topic. We handle them with explicit
metadata queries against ChromaDB rather than vector retrieval, because
"columns from 2023" is a metadata filter, not a semantic search.

Two-turn flow in app.py:
1. Visitor asks "give me 5 sample columns" → app detects catalog query →
   if no year is in the query, app asks "for which year?".
2. Visitor replies with a year → app queries ChromaDB metadata for columns
   matching that year, returns up to N with title, date, and a short preview.

If the visitor specifies the year in the original query ("give me 5 columns
from 2023"), we skip the clarification turn and answer directly.
"""

from __future__ import annotations

import re

# Patterns matching list/catalog-style queries.
_CATALOG_PATTERNS = [
    re.compile(
        r"\b(list|show|give\s+me|provide)\s+(?:\w+\s+){0,4}"
        r"(columns?|writings?|articles?|essays?|works?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(some|sample|five|three|ten|\d+)\s+(?:\w+\s+){0,3}"
        r"(columns?|writings?|articles?|essays?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhat\s+(have|did|do)\s+you\s+(write|written|wrote)\s+about\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhat\s+(columns?|articles?)\s+have\s+you\s+(written|wrote)\b",
        re.IGNORECASE,
    ),
]

_YEAR_RE = re.compile(r"\b(19[7-9]\d|20\d{2})\b")
_HEADER_STRIP_RE = re.compile(r"^\[Excerpt from[^\]]+\]\s*")


def is_catalog_query(text: str) -> bool:
    """True iff `text` looks like a request to LIST columns/writings."""
    if not text:
        return False
    return any(p.search(text) for p in _CATALOG_PATTERNS)


def extract_year(text: str) -> int | None:
    """Pull the first 4-digit year out of `text`, or None if absent."""
    if not text:
        return None
    m = _YEAR_RE.search(text)
    return int(m.group()) if m else None


def list_columns_by_year(year: int, n: int = 5) -> list[dict]:
    """Return up to `n` unique sources (columns / book chapters) whose
    publication_date starts with `year`. One entry per source URL,
    sorted by date descending. Each entry has title, date, url, bucket,
    and a short cleaned text preview from the source's first chunk."""
    from backend.retrieval import _collection

    coll = _collection()
    items = coll.get(include=["metadatas", "documents"])

    by_source: dict[str, dict] = {}
    metadatas = items["metadatas"] or []
    documents = items["documents"] or []
    for i, meta in enumerate(metadatas):
        if not meta:
            continue
        date = meta.get("publication_date", "") or ""
        if not date.startswith(str(year)):
            continue
        url = meta.get("source_url")
        if not url:
            continue
        chunk_index = meta.get("chunk_index", 0)
        if url in by_source and chunk_index >= by_source[url]["chunk_index"]:
            continue
        text_doc = (documents[i] or "") if i < len(documents) else ""
        # Drop the synthetic chapter-excerpt header we prepend at ingest time.
        cleaned = _HEADER_STRIP_RE.sub("", text_doc).strip()
        by_source[url] = {
            "title": meta.get("title", "(untitled)"),
            "date": date,
            "url": url,
            "bucket": meta.get("bucket"),
            "chunk_index": chunk_index,
            "preview": cleaned,
        }

    return sorted(by_source.values(), key=lambda x: x["date"], reverse=True)[:n]


def format_catalog_response(year: int, items: list[dict]) -> str:
    """Build a visitor-facing response listing the matched sources."""
    if not items:
        return (
            f"I do not have columns from {year} in my current materials. "
            "My published columns span roughly from 2011 through 2026 — "
            "perhaps try a different year."
        )
    parts = [f"From {year}, here are some of my columns:"]
    for i, item in enumerate(items, 1):
        parts.append("")
        parts.append(f"{i}. \"{item['title']}\" ({item['date']})")
        preview = item["preview"].replace("\n", " ").strip()
        if preview:
            preview = preview[:200].rstrip(",.;: ")
            parts.append(f"   {preview}...")
    return "\n".join(parts)
