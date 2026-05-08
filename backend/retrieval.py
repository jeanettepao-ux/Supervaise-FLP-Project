"""ChromaDB retrieval wrapper. Stage 5 of the v2 ingestion pipeline.

Used by orchestrator at query time. Returns the top-k most relevant column
chunks for a user question, with cosine-distance threshold + max-N-per-source
diversity guardrail.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

_CHROMA_DIR = Path("./chroma_store")
_DEFAULT_COLLECTION = "cjp_columns_dev"
_DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_TOP_K = 5
# Smoke-tested top-1 distances on MiniLM-L6 range 0.34-0.65 for legitimate
# matches. Out-of-scope sits at 0.85+. 0.65 catches questions where the
# query phrasing differs from the source's exact words (e.g., "Ombudsman's
# powers" vs the column "Powers of the Ombudsman"). v2 spec said 0.45 —
# too tight for our corpus. Re-tune at OpenAI cutover (different distribution).
_DEFAULT_DISTANCE_THRESHOLD = 0.65
_DEFAULT_MAX_CHUNKS_PER_SOURCE = 2


@dataclass
class RetrievedChunk:
    text: str
    title: str
    date: str
    url: str
    bucket: str
    distance: float
    citation_safe: bool


# Patterns to normalize visitor queries before embedding so they match
# the corpus's spelling conventions. CJ writes 'RA 6713' with a space;
# visitors often type 'RA6713' without one; embeddings differ enough
# that vector search misses the match. Same for similar codes.
_QUERY_NORMALIZE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 'RA6713' -> 'RA 6713' (Republic Act + number)
    (re.compile(r"\b(RA)(\d{2,5})\b", re.IGNORECASE), r"\1 \2"),
    # 'EO123' -> 'EO 123' (Executive Order)
    (re.compile(r"\b(EO)(\d{2,4})\b", re.IGNORECASE), r"\1 \2"),
    # 'GR123456' -> 'GR 123456' (G.R. case number)
    (re.compile(r"\b(GR)(\d{4,7})\b", re.IGNORECASE), r"\1 \2"),
]


def _normalize_query(text: str) -> str:
    """Pre-embedding query cleanup: insert spaces in compact abbreviations
    (RA6713 -> RA 6713) so vector search matches the corpus tokenization."""
    out = text
    for pattern, replacement in _QUERY_NORMALIZE_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(_DEFAULT_EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def _collection():
    name = os.environ.get("CHROMA_COLLECTION", _DEFAULT_COLLECTION)
    client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
    return client.get_collection(name=name)


def _build_where(bucket: str | None, safe_only: bool) -> dict | None:
    clauses: list[dict] = []
    if bucket:
        clauses.append({"bucket": bucket})
    if safe_only:
        clauses.append({"citation_safe": True})
    if len(clauses) == 1:
        return clauses[0]
    if len(clauses) > 1:
        return {"$and": clauses}
    return None


def retrieve(
    query: str,
    *,
    top_k: int | None = None,
    bucket: str | None = None,
    safe_only: bool | None = None,
) -> list[RetrievedChunk]:
    top_k = top_k or int(os.environ.get("RETRIEVAL_TOP_K", _DEFAULT_TOP_K))
    threshold = float(
        os.environ.get("RETRIEVAL_DISTANCE_THRESHOLD", _DEFAULT_DISTANCE_THRESHOLD)
    )
    max_per_source = int(
        os.environ.get("RETRIEVAL_MAX_PER_SOURCE", _DEFAULT_MAX_CHUNKS_PER_SOURCE)
    )
    if safe_only is None:
        safe_only = os.environ.get("RETRIEVAL_SAFE_ONLY", "false").lower() == "true"

    where = _build_where(bucket, safe_only)

    qv = _model().encode([_normalize_query(query)]).tolist()
    res = _collection().query(
        query_embeddings=qv,
        n_results=top_k * 3,  # over-fetch so the diversity filter has room
        include=["documents", "metadatas", "distances"],
        where=where,
    )

    chunks: list[RetrievedChunk] = []
    seen_per_source: dict[str, int] = {}

    for i in range(len(res["ids"][0])):
        distance = res["distances"][0][i]
        if distance > threshold:
            break  # results are sorted ascending; nothing useful past this point
        meta = res["metadatas"][0][i]
        url = meta["source_url"]
        if seen_per_source.get(url, 0) >= max_per_source:
            continue
        seen_per_source[url] = seen_per_source.get(url, 0) + 1
        chunks.append(
            RetrievedChunk(
                text=res["documents"][0][i],
                title=meta["title"],
                date=meta["publication_date"],
                url=url,
                bucket=meta["bucket"],
                distance=distance,
                citation_safe=bool(meta.get("citation_safe", True)),
            )
        )
        if len(chunks) >= top_k:
            break

    return chunks
