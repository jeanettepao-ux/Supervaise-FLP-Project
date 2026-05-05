"""
ingest_columns.py
=================
Loading → Chunking → Embedding → Ingestion → RAG-ready ChromaDB

For the CJ Panganiban Conversational AI Robot.
Runs the all-free dev stack (Phase A, May 4–13). Switching to OpenAI
embeddings post-May 14 is a one-line config change — see EMBEDDER below.

CORPUS STRATEGY (revised 6 May 2026)
------------------------------------
Per FLP's direction, the RAG corpus is defined by what FLP provides, not by
an arbitrary count. This script's COLUMNS list reflects the full inventory
delivered via the Column Selection Criteria, Section 7: 66 opinion columns
across the five theme buckets. Additional source materials (books,
multimedia transcripts, PDF cases) feed the same pipeline as they arrive.

The five buckets are preserved as retrieval-time metadata. They no longer
gate ingestion — every column FLP provides is loaded, chunked, embedded,
and made available to the retriever, with bucket assignment used for
thematic biasing rather than inclusion/exclusion.

Tested on Python 3.11.

INSTALL
-------
    pip install requests trafilatura readability-lxml markdownify \
                tiktoken langchain-text-splitters \
                sentence-transformers chromadb \
                python-dateutil tqdm

USAGE
-----
    # Dry run — fetch + chunk only, no embedding:
    python ingest_columns.py --dry-run

    # Full ingestion into the dev collection (free stack):
    python ingest_columns.py

    # Production embedding run (after 14 May cutover):
    EMBEDDER=openai python ingest_columns.py --collection cjp_columns_prod

    # Re-ingest only columns flagged citation_safe=True (production retrieval):
    python ingest_columns.py --safe-only

    # Smoke test the retriever after ingestion:
    python ingest_columns.py --smoke-test --query "What is FLP's mission?"
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
import trafilatura
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm


# =============================================================
# CONFIG — edit these for your environment
# =============================================================

KB_ROOT = Path("./kb")                      # disk layout per Section 3 of the manifest
CHROMA_DIR = Path("./chroma_store")         # SQLite-backed; portable to R-Pi later
DEFAULT_COLLECTION = "cjp_columns_dev"      # 384-dim dev; use cjp_columns_prod for 1536
EMBEDDER = os.environ.get("EMBEDDER", "minilm")   # "minilm" (free, dev) or "openai" (prod)

USER_AGENT = "FLP-Supervaise-RAG-Builder/0.2 (research; contact: jbarbosa@flp.org.ph)"
REQUEST_DELAY_S = 1.0                       # be polite to opinion.inquirer.net

CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 75
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


# =============================================================
# COLUMN INVENTORY — all 66 columns FLP delivered (Section 7)
# =============================================================
# Tuple format: (slug, title, date_iso, bucket, url, citation_safe)
#
# citation_safe=False is set as a default flag for politically-sensitive
# columns naming sitting officials or contested figures in legal contexts.
# These require explicit C5 review by Jacob before they go live in
# production retrieval. Flip to True after review.

COLUMNS: list[tuple[str, str, str, str, str, bool]] = [
    # ============================================
    # Bucket A · Liberty and Rule of Law (24)
    # ============================================
    ("asean-rule-of-law", "Let the rule of law reign in Asean", "2023-10-23", "A",
     "https://opinion.inquirer.net/167388/let-the-rule-of-law-reign-in-asean", True),
    ("eez-negotiators", "A subtle reminder to EEZ negotiators", "2023-01-16", "A",
     "https://opinion.inquirer.net/160333/a-subtle-reminder-to-eez-negotiators", True),
    ("duterte-icc", "Pivotal issue in Duterte's ICC case", "2025-03-24", "A",
     "https://opinion.inquirer.net/181839/pivotal-issue-in-dutertes-icc-case", False),  # C5 review
    ("due-process-impeachment", "Due process in impeachment", "2012-01-14", "A",
     "https://opinion.inquirer.net/21127/due-process-in-impeachment", True),
    ("due-process-judicial-comp", "Due process and judicial compensation", "2011-07-03", "A",
     "https://opinion.inquirer.net/7199/due-process-and-judicial-compensation", True),
    ("judicial-activism-ph", "Judicial activism in the Philippines", "2023-04-10", "A",
     "https://opinion.inquirer.net/162259/judicial-activism-in-the-philippines", True),
    ("rol-china-sea", "The rule of law in the besieged China Sea", "2024-02-19", "A",
     "https://opinion.inquirer.net/171013/the-rule-of-law-in-the-besieged-china-sea", True),
    ("rol-besieged-world", "The rule of law in the besieged world", "2024-02-12", "A",
     "https://opinion.inquirer.net/170774/the-rule-of-law-in-the-besieged-world", True),
    ("enforcing-arbitral-award", "Enforcing the Arbitral Award", "2021-06-13", "A",
     "https://opinion.inquirer.net/141119/enforcing-the-arbitral-award", True),
    ("understanding-arbitral-award", "Understanding the arbitral award", "2019-08-04", "A",
     "https://opinion.inquirer.net/123043/understanding-the-arbitral-award", True),
    ("wps-no-ifs-buts", "'WPS is ours—no ifs and buts'", "2019-07-28", "A",
     "https://opinion.inquirer.net/122903/wps-is-ours-no-ifs-and-buts", True),
    ("might-vs-right", "'Might is right' vs 'Right is might'", "2021-04-25", "A",
     "https://opinion.inquirer.net/139623/might-is-right-vs-right-is-might", True),
    ("winning-eez-war", "Winning the war to exploit our EEZ", "2019-08-25", "A",
     "https://opinion.inquirer.net/123532/winning-the-war-to-exploit-our-eez", True),
    ("extracting-wps-resources", "Extracting WPS resources beyond the arbitral award", "2019-08-18", "A",
     "https://opinion.inquirer.net/123392/extracting-wps-resources-beyond-the-arbitral-award", True),
    ("afp-rule-of-law", "AFP's role under the rule of law", "2021-02-21", "A",
     "https://opinion.inquirer.net/137908/afps-role-under-the-rule-of-law", True),
    ("rule-of-or-by-law", "Rule of, or by, law", "2018-02-02", "A",
     "https://opinion.inquirer.net/110720/rule-of-or-by-law", True),
    ("icc-temporal-strategic", "ICC: The temporal vs the strategic", "2023-08-07", "A",
     "https://opinion.inquirer.net/165376/icc-the-temporal-vs-the-strategic", False),  # C5 review
    ("icc-doj-osg", "ICC prosecutor targets DOJ, OSG", "2023-02-27", "A",
     "https://opinion.inquirer.net/161338/icc-prosecutor-targets-doj-osg", False),  # C5 review
    ("marcos-icc-options", "President Marcos' ICC options", "2023-12-11", "A",
     "https://opinion.inquirer.net/168916/president-marcos-icc-options", False),  # C5 review
    ("trump-defeat", "Defeat for Trump, victory for rule of law", "2020-12-27", "A",
     "https://opinion.inquirer.net/136462/defeat-for-trump-victory-for-rule-of-law", False),  # C5 review
    ("amparo-success", "An amparo success, though not yet complete", "2024-05-13", "A",
     "https://opinion.inquirer.net/173652/an-amparo-success-though-not-yet-complete", True),
    ("sc-can", "Yes, the Supreme Court can!", "2014-06-01", "A",
     "https://opinion.inquirer.net/75174/yes-the-supreme-court-can", True),
    ("plea-rol", "A plea for the rule of law", "2025-08-11", "A",
     "https://opinion.inquirer.net/185288/a-plea-for-the-rule-of-law", True),
    ("martial-law-chacha", "Martial law, authoritarian rule and Cha-cha", "2017-10-01", "A",
     "https://opinion.inquirer.net/107543/martial-law-authoritarian-rule-cha-cha", True),

    # ============================================
    # Bucket B · Prosperity and Economic Philosophy (7)
    # ============================================
    ("ai-fortifies-rol", "AI fortifies liberty, prosperity, rule of law", "2024-09-09", "B",
     "https://opinion.inquirer.net/176671/ai-fortifies-liberty-prosperity-rule-of-law", True),
    ("national-interest", "Protecting and projecting national interest", "2024-11-25", "B",
     "https://opinion.inquirer.net/178623/protecting-and-projecting-national-interest", True),
    ("law-scholarships", "Law scholarships with a difference", "2019-02-17", "B",
     "https://opinion.inquirer.net/119605/law-scholarships-with-a-difference", True),
    ("negative-vs-positive", "Negative versus positive", "2021-10-31", "B",
     "https://opinion.inquirer.net/145837/negative-versus-positive", True),
    ("law-economics", "Merging law and economics", "2019-11-03", "B",
     "https://opinion.inquirer.net/124992/merging-law-and-economics", True),
    ("entrepreneurial-ingenuity", "Unleashing entrepreneurial ingenuity (1)", "2015-03-01", "B",
     "https://opinion.inquirer.net/82941/unleashing-entrepreneurial-ingenuity-1", True),
    ("sc-economy", "SC decisions on the economy", "2013-04-28", "B",
     "https://opinion.inquirer.net/51551/sc-decisions-on-the-economy", True),

    # ============================================
    # Bucket C · Biographical and Personal (17)
    # ============================================
    ("joy-writing-inquirer", "Joy in writing for the Inquirer", "2017-02-12", "C",
     "https://opinion.inquirer.net/101589/joy-writing-inquirer", True),
    ("salonga-guru", "Jovito R. Salonga, my guru and surrogate father", "2016-03-20", "C",
     "https://opinion.inquirer.net/93911/jovito-r-salonga-my-guru-and-surrogate-father", True),
    ("leni-mom-prof", "My Leni as mom, grand mom, and professor", "2023-04-24", "C",
     "https://opinion.inquirer.net/162603/my-leni-as-mom-grand-mom-and-professor", True),
    ("diokno-salonga-teehankee", "Diokno, Salonga and Teehankee", "2018-04-29", "C",
     "https://opinion.inquirer.net/112794/diokno-salonga-teehankee", True),
    ("right-man-right-job", "Right man for the right job", "2014-02-01", "C",
     "https://opinion.inquirer.net/70776/right-man-for-the-right-job", True),
    ("mapa-high", "For the alumni of Mapa High", "2014-03-02", "C",
     "https://opinion.inquirer.net/72137/for-the-alumni-of-mapa-high", True),
    ("bar-exams-legal-ed", "Bar exams and legal education (1)", "2014-09-07", "C",
     "https://opinion.inquirer.net/78226/bar-exams-and-legal-education-1", True),
    ("keep-doing-best", "'Keep doing my best, let God do the rest'", "2015-01-04", "C",
     "https://opinion.inquirer.net/81448/keep-doing-my-best-let-god-do-the-rest", True),
    ("honor-and-joy", "Overwhelmed with honor and joy", "2022-01-02", "C",
     "https://opinion.inquirer.net/148215/overwhelmed-with-honor-and-joy", True),
    ("reminiscing-praying", "Reminiscing, praying, and caring", "2022-04-18", "C",
     "https://opinion.inquirer.net/152153/reminiscing-praying-and-caring", True),
    ("supercali", "Supercalifragilisticexpialidocious", "2023-10-30", "C",
     "https://opinion.inquirer.net/167631/supercalifragilisticexpialidocious", True),
    ("bar-legends", "The bar exam and the legends of the bar", "2024-09-16", "C",
     "https://opinion.inquirer.net/176846/the-bar-exam-and-the-legends-of-the-bar", True),
    ("best-friends-critics", "Why my best friends are my best critics", "2019-11-17", "C",
     "https://opinion.inquirer.net/125281/why-my-best-friends-are-my-best-critics", True),
    ("student-activism", "Student activism", "2024-05-06", "C",
     "https://opinion.inquirer.net/173470/student-activism", True),
    ("manila-cathedral", "Manila Cathedral: sad news, good news", "2012-04-07", "C",
     "https://opinion.inquirer.net/26335/manila-cathedral-sad-news-good-news", True),
    ("new-evangelization", "New evangelization of Catholic Church", "2016-07-24", "C",
     "https://opinion.inquirer.net/95902/new-evangelization-of-catholic-church", True),
    ("cyberlibel-ressa", "Cyberlibel and Maria Ressa", "2020-06-21", "C",
     "https://opinion.inquirer.net/130986/cyberlibel-and-maria-ressa", True),

    # ============================================
    # Bucket D · FLP Mission and Foundation (10)
    # ============================================
    ("libpros-11-scholars", "11 LibPros scholars", "2016-11-27", "D",
     "https://opinion.inquirer.net/99561/11-libpros-scholars", True),
    ("never-give-up", "Never give up, never say never", "2023-07-31", "D",
     "https://opinion.inquirer.net/165185/never-give-up-never-say-never", True),
    ("flp-grants-2025", "20 law grants at P250k, 5 MBA at P500k", "2025-08-25", "D",
     "https://opinion.inquirer.net/185590/20-law-grants-at-p250k-5-mba-at-p500k", True),
    ("flp-expanding-prosperity", "FLP expanding into prosperity", "2022-04-11", "D",
     "https://opinion.inquirer.net/151988/flp-expanding-into-prosperity", True),
    ("flp-little-things", "For FLP scholars, little things mean a lot", "2020-05-10", "D",
     "https://opinion.inquirer.net/129657/for-flp-scholars-little-things-mean-a-lot", True),
    ("liberty-prosperity-rol", "'Liberty, prosperity, rule of law'", "2021-07-25", "D",
     "https://opinion.inquirer.net/142416/liberty-prosperity-rule-of-law", True),
    ("flp-21-scholars", "FLP's 21 scholars, 10 winners, and 5 fellows", "2022-08-08", "D",
     "https://opinion.inquirer.net/155854/flps-21-scholars-10-winners-and-5-fellows", True),
    ("flp-2024-scholars", "FLP's 2024 law scholars, fellows, and winners", "2024-09-02", "D",
     "https://opinion.inquirer.net/176505/flps-2024-law-scholars-fellows-and-winners", True),
    ("flp-bar-topnotchers", "Hail to the FLP bar topnotchers and passers", "2026-01-12", "D",
     "https://opinion.inquirer.net/188943/hail-to-the-flp-bar-topnotchers-and-passers", True),
    ("spji-reminiscing", "Supreme Court's SPJI: Reminiscing the past", "2022-11-14", "D",
     "https://opinion.inquirer.net/158705/supreme-courts-spji-reminiscing-the-past", True),

    # ============================================
    # Bucket E · Signature Current Events Commentary (8)
    # ============================================
    ("rejuvenating-baguio", "Rejuvenating Baguio", "2025-01-13", "E",
     "https://opinion.inquirer.net/181030/rejuvenating-baguio", True),
    ("women-suffrage-day", "Let us celebrate Women Suffrage Day", "2025-04-21", "E",
     "https://opinion.inquirer.net/183163/let-us-celebrate-women-suffrage-day", True),
    ("ph-sovereignty-defender", "Relentless defender of PH sovereignty", "2026-03-30", "E",
     "https://opinion.inquirer.net/190728/relentless-defender-of-ph-sovereignty", True),
    ("ra-6713-bible", "RA 6713, the 'Bible' of public officials", "2025-10-27", "E",
     "https://opinion.inquirer.net/187016/ra-6713-the-bible-of-public-officials", True),
    ("little-known-sc", "Little known SC decisions", "2024-07-15", "E",
     "https://opinion.inquirer.net/175164/little-known-sc-decisions", True),
    ("ombudsman-powers", "Powers of the Ombudsman", "2024-04-08", "E",
     "https://opinion.inquirer.net/172746/powers-of-the-ombudsman", True),
    ("liberalism-vs-conservatism", "Liberalism vs conservatism", "2024-09-30", "E",
     "https://opinion.inquirer.net/177172/liberalism-vs-conservatism", True),
    ("infidelity-abortion-pcp2", "Marital infidelity, abortion, PCP2", "2024-10-07", "E",
     "https://opinion.inquirer.net/177347/marital-infidelity-abortion-pcp2", True),
]

BUCKET_NAMES = {
    "A": "Liberty and Rule of Law",
    "B": "Prosperity and Economic Philosophy",
    "C": "Biographical and Personal",
    "D": "FLP Mission and Foundation",
    "E": "Signature Current Events Commentary",
}


# =============================================================
# STAGE 1 — LOADING
# =============================================================

@dataclass
class LoadedColumn:
    slug: str
    title: str
    date_iso: str
    bucket: str
    url: str
    citation_safe: bool
    body_md: str
    word_count: int


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.text


def html_to_markdown(html: str) -> str:
    """Extract main article body and convert to clean markdown.

    Trafilatura is the primary path (best at recognizing news-article main
    content). We do NOT silently fall back — if trafilatura returns nothing,
    raise so the operator can investigate (better than ingesting empty).
    """
    md = trafilatura.extract(
        html,
        output_format="markdown",
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not md or len(md) < 200:
        raise RuntimeError(
            "trafilatura returned <200 chars; layout may have changed — "
            "inspect the raw HTML and update the loader."
        )
    return md.strip()


def load_one(col: tuple) -> LoadedColumn:
    slug, title, date_iso, bucket, url, citation_safe = col

    raw_dir = KB_ROOT / "raw" / bucket
    clean_dir = KB_ROOT / "clean" / bucket
    meta_dir = KB_ROOT / "meta" / bucket
    for d in (raw_dir, clean_dir, meta_dir):
        d.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / f"{slug}.html"
    clean_path = clean_dir / f"{slug}.md"
    meta_path = meta_dir / f"{slug}.json"

    # Fetch (cache to disk for reproducibility)
    if not raw_path.exists():
        html = fetch_html(url)
        raw_path.write_text(html, encoding="utf-8")
        time.sleep(REQUEST_DELAY_S)
    else:
        html = raw_path.read_text(encoding="utf-8")

    # Clean
    body_md = html_to_markdown(html)
    clean_path.write_text(body_md, encoding="utf-8")

    word_count = len(body_md.split())

    # Sidecar metadata
    meta = {
        "slug": slug, "title": title, "date_iso": date_iso, "bucket": bucket,
        "url": url, "citation_safe": citation_safe, "word_count": word_count,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return LoadedColumn(slug, title, date_iso, bucket, url, citation_safe, body_md, word_count)


# =============================================================
# STAGE 2 — CHUNKING
# =============================================================

_TOK = tiktoken.get_encoding("cl100k_base")
def _token_len(text: str) -> int:
    return len(_TOK.encode(text))


def chunk_column(col: LoadedColumn) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        length_function=_token_len,
        separators=SEPARATORS,
    )
    pieces = splitter.split_text(col.body_md)
    chunks = []
    for i, piece in enumerate(pieces):
        chunks.append({
            "chunk_id": f"{col.slug}__c{i:02d}",
            "text": piece,
            "metadata": {
                "source_url": col.url,
                "title": col.title,
                "publication_date": col.date_iso,
                "bucket": col.bucket,
                "bucket_name": BUCKET_NAMES[col.bucket],
                "chunk_index": i,
                "chunk_count": len(pieces),
                "word_count": len(piece.split()),
                "citation_safe": col.citation_safe,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "embedder": EMBEDDER,
            }
        })
    return chunks


# =============================================================
# STAGE 3 — EMBEDDING
# =============================================================

def get_embedder():
    """Return (callable: list[str] -> list[list[float]], expected_dim)."""
    if EMBEDDER == "minilm":
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        def embed(texts: list[str]) -> list[list[float]]:
            return model.encode(texts, batch_size=32, show_progress_bar=False).tolist()
        return embed, 384

    elif EMBEDDER == "openai":
        from openai import OpenAI
        client = OpenAI()  # reads OPENAI_API_KEY
        def embed(texts: list[str]) -> list[list[float]]:
            resp = client.embeddings.create(model="text-embedding-3-small", input=texts)
            return [d.embedding for d in resp.data]
        return embed, 1536

    raise ValueError(f"Unknown embedder: {EMBEDDER!r}")


# =============================================================
# STAGE 4 — INGESTION INTO CHROMADB
# =============================================================

def upsert_to_chroma(chunks: list[dict], collection_name: str):
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine", "embedder": EMBEDDER},
    )

    embed_fn, expected_dim = get_embedder()
    texts = [c["text"] for c in chunks]
    print(f"[embed] generating {len(texts)} vectors via {EMBEDDER} (dim={expected_dim})…")
    vectors = embed_fn(texts)
    assert len(vectors[0]) == expected_dim, (
        f"Embedder returned dim {len(vectors[0])} but expected {expected_dim} — "
        f"likely a model/collection mismatch."
    )

    collection.upsert(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=vectors,
        documents=texts,
        metadatas=[c["metadata"] for c in chunks],
    )
    print(f"[chroma] upserted {len(chunks)} chunks → collection '{collection_name}'")
    print(f"[chroma] total chunks now in collection: {collection.count()}")


# =============================================================
# STAGE 5 — RAG SMOKE TEST
# =============================================================

def smoke_test(collection_name: str, query: str, safe_only: bool = False):
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection(collection_name)

    embed_fn, _ = get_embedder()
    qvec = embed_fn([query])[0]

    where = {"citation_safe": True} if safe_only else None
    res = collection.query(query_embeddings=[qvec], n_results=5, where=where)

    print(f"\n=== Smoke test ===\nQuery: {query!r}"
          f"{'  (citation_safe only)' if safe_only else ''}\n")
    for i, (doc, meta, dist) in enumerate(zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    )):
        snippet = re.sub(r"\s+", " ", doc[:160])
        print(f"  [{i+1}] dist={dist:.3f}  bucket={meta['bucket']}  "
              f"{meta['title']!r}  ({meta['publication_date']})")
        print(f"       \"{snippet}…\"\n")


# =============================================================
# DRIVER
# =============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Ingest CJ Panganiban opinion columns into ChromaDB"
    )
    parser.add_argument("--collection", default=DEFAULT_COLLECTION,
                        help=f"ChromaDB collection name (default: {DEFAULT_COLLECTION})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and chunk only — skip embedding and upsert")
    parser.add_argument("--safe-only", action="store_true",
                        help="Ingest only columns flagged citation_safe=True (production retrieval)")
    parser.add_argument("--smoke-test", action="store_true",
                        help="Run a sample retrieval after ingestion")
    parser.add_argument("--query", default="What is FLP's mission?",
                        help="Smoke-test query")
    args = parser.parse_args()

    KB_ROOT.mkdir(parents=True, exist_ok=True)

    # Filter corpus if --safe-only
    columns = COLUMNS
    if args.safe_only:
        original_count = len(columns)
        columns = [c for c in columns if c[5] is True]
        print(f"[filter] --safe-only: {len(columns)} of {original_count} columns "
              f"({original_count - len(columns)} flagged for C5 review)")

    # Distribution by bucket — quick sanity
    by_bucket = {}
    for c in columns:
        by_bucket[c[3]] = by_bucket.get(c[3], 0) + 1
    print(f"[corpus] {len(columns)} columns: " +
          ", ".join(f"{k}={v}" for k, v in sorted(by_bucket.items())))

    # Stage 1 — Loading
    print(f"[load] fetching {len(columns)} columns…")
    loaded: list[LoadedColumn] = []
    for col in tqdm(columns, desc="loading"):
        try:
            loaded.append(load_one(col))
        except Exception as e:
            print(f"  [WARN] {col[0]}: {e}")

    # Manifest CSV
    manifest_path = KB_ROOT / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["slug", "title", "date", "bucket", "url",
                    "word_count", "citation_safe"])
        for c in loaded:
            w.writerow([c.slug, c.title, c.date_iso, c.bucket, c.url,
                        c.word_count, c.citation_safe])
    print(f"[load] manifest written: {manifest_path}")

    # Stage 2 — Chunking
    all_chunks: list[dict] = []
    qa_warnings = 0
    for col in loaded:
        chunks = chunk_column(col)
        if not (3 <= len(chunks) <= 5):
            qa_warnings += 1
            print(f"  [QA-warn] {col.slug}: produced {len(chunks)} chunks "
                  f"(expected 3–5; column word_count={col.word_count})")
        all_chunks.extend(chunks)
    print(f"[chunk] {len(loaded)} columns → {len(all_chunks)} chunks "
          f"(avg {len(all_chunks)/max(len(loaded),1):.1f}/column, "
          f"{qa_warnings} QA warnings)")

    if args.dry_run:
        print("[dry-run] stopping before embedding/upsert.")
        return

    # Stages 3 + 4 — Embed and upsert
    upsert_to_chroma(all_chunks, args.collection)

    # Stage 5 — Optional smoke test
    if args.smoke_test:
        smoke_test(args.collection, args.query, safe_only=args.safe_only)


if __name__ == "__main__":
    main()
