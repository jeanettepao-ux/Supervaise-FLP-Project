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

# Patterns matching list/catalog-style queries (visitor wants a list,
# not a topical answer). Plural noun forms ("your columns") are a much
# stronger catalog signal than singular ("your column on FLP" is topical
# about a specific piece). New patterns below favor plural forms.
_CATALOG_PATTERNS = [
    # Imperative verbs: "list / show / give me / provide [some] columns"
    re.compile(
        r"\b(list|show|give\s+me|provide)\s+(?:\w+\s+){0,4}"
        r"(columns?|writings?|articles?|essays?|works?)\b",
        re.IGNORECASE,
    ),
    # Quantifiers: "[N] sample columns" / "five columns" / "10 articles"
    re.compile(
        r"\b(some|sample|five|three|ten|several|many|\d+)\s+(?:\w+\s+){0,3}"
        r"(columns?|writings?|articles?|essays?)\b",
        re.IGNORECASE,
    ),
    # "what have you written about" / "what did you write on" — but ONLY
    # when "about/on" has no specific topic following it (catalog intent).
    # Negative lookahead rejects "what did you write about Estrada" (topical).
    re.compile(
        r"\bwhat\s+(have|did|do)\s+you\s+(write|written|wrote)\s+(about|on)\b(?!\s+\w)",
        re.IGNORECASE,
    ),
    # "what columns/articles/writings have you written"
    re.compile(
        r"\bwhat\s+(columns?|articles?|writings?|essays?|works?)\s+have\s+you\s+(written|wrote)\b",
        re.IGNORECASE,
    ),
    # "tell me about your columns/writings" — catalog intent on plural noun
    re.compile(
        r"\btell\s+me\s+(?:more\s+)?about\s+(?:your\s+|the\s+)?"
        r"(columns|writings|articles|essays|works)\b",
        re.IGNORECASE,
    ),
    # "talk about your columns/writings"
    re.compile(
        r"\btalk\s+(?:to\s+me\s+)?about\s+(?:your\s+|the\s+)?"
        r"(columns|writings|articles|essays|works)\b",
        re.IGNORECASE,
    ),
    # "what are your (sample) columns/writings"
    re.compile(
        r"\bwhat\s+(are|were)\s+(?:your\s+|some\s+(?:of\s+your\s+)?|the\s+)?"
        r"(?:sample\s+)?(columns|writings|articles|essays|works)\b",
        re.IGNORECASE,
    ),
    # "describe your columns" / "any of your writings"
    re.compile(
        r"\b(describe|any\s+(?:of\s+)?(?:your\s+)?)"
        r"(columns|writings|articles|essays|works)\b",
        re.IGNORECASE,
    ),
    # "your columns" / "your writings" as a noun phrase under question intent
    # — only if no specific topic word follows ("about X" / "on X" / "regarding X")
    re.compile(
        r"\byour\s+(columns|writings|articles|essays|works)\b"
        r"(?!\s+(about|on|regarding|concerning|covering)\s+\w)",
        re.IGNORECASE,
    ),
]

_YEAR_RE = re.compile(r"\b(19[7-9]\d|20\d{2})\b")
_HEADER_STRIP_RE = re.compile(r"^\[Excerpt from[^\]]+\]\s*")

# Markdown stripping for clean previews. Streamlit renders the response via
# st.markdown, so any '#' heading or '**bold**' marker in the preview text
# would render at heading size — we want preview to look like normal prose.
_MD_LEADING_HEADING_RE = re.compile(r"^\s*#+\s+[^\n]+\n+")
_MD_HEADING_LINE_RE = re.compile(r"(?m)^\s*#+\s+")
_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MD_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_MD_ITALIC_UNDERSCORE_RE = re.compile(r"(?<![\w_])_([^_]+)_(?![\w_])")
_WS_RE = re.compile(r"\s+")


def _clean_preview(text: str) -> str:
    """Strip markdown formatting that would render as oversized headings or
    weird emphasis when the catalog response is rendered through st.markdown."""
    # Remove the leading heading line (column title — we already show it
    # separately in the list, no need for the preview to repeat it).
    text = _MD_LEADING_HEADING_RE.sub("", text)
    # Demote any remaining '#' heading lines to plain text.
    text = _MD_HEADING_LINE_RE.sub("", text)
    # Strip bold/italic markers.
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_ITALIC_STAR_RE.sub(r"\1", text)
    text = _MD_ITALIC_UNDERSCORE_RE.sub(r"\1", text)
    # Collapse whitespace.
    return _WS_RE.sub(" ", text).strip()


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
        # Drop markdown headings / bold so previews render as plain prose
        # at the same font size as the question text.
        cleaned = _clean_preview(cleaned)
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
