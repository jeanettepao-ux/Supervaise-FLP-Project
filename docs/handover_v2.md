> **Reference snapshot — handover v2 received 2026-05-06.**
> This file is a verbatim copy of the v2 handover document delivered on
> 6 May 2026. It is preserved here for the team's reference.
>
> The **working spec is `CLAUDE.md` at the repo root**, which will be reconciled
> against this v2 handover in a follow-up commit. Where the two disagree,
> CLAUDE.md is authoritative because it reflects what the code actually does.
>
> Known reconciliation items (to be resolved separately):
> - Dev embedding model: v2 says MiniLM-L6 (384-dim); current code uses mpnet-base (768-dim).
> - Backend: v2 says FastAPI + Docker; current is Streamlit-direct.
> - ChromaDB persist dir: v2 says `./chroma_store/`; current is `./chroma_db/`.
> - KB layout: v2 specifies `kb/raw/`, `kb/clean/`, `kb/meta/`, `manifest.csv`; nothing built yet.
> - Hardware ETA: v2 says mid-June; HANDOVER.md §10.2 says late July / early August.
> - OpenAI cutover: v2 says locked May 14; we'd been treating it as condition-based.
> - Confidence threshold: v2 framed as cosine distance > 0.45; current code as similarity < 0.35 (roughly equivalent, just different sign convention).
> - References two existing deliverables (`Opinion_Columns_Ingestion_Manifest.docx`, `ingest_columns.py`) not yet in this repo.
>
> See PROGRESS.md for the per-push history of working-spec changes.

---

# CJ Panganiban Conversational AI Robot — KB Build Handover

> Handover document for transferring this work into Claude Code.
> Drop this file into the repo as `CLAUDE.md` (or `docs/KB_BUILD_CONTEXT.md`) so Claude Code has the full picture without needing to re-derive it.
>
> **Last updated:** 6 May 2026
> **Owner:** Supervaise × Foundation for Liberty and Prosperity
> **Phase:** Week 3 (free-stack pipeline validation, May 4–13) → OpenAI cutover (May 14)
> **Demo:** May 30, 2026 (pre-prototype) · September 2026 (donor showcase)

---

## 1. What this project is

A voice-in / voice-out conversational AI robot that speaks in the persona of **Chief Justice Artemio V. Panganiban** for donor engagement at the Foundation for Liberty and Prosperity. Final deployment runs on a **Reachy Mini Wireless** robot. Knowledge base is **strictly RAG** over an embedded corpus — no live web search.

**Roles:**
- **Jacob Barbosa** (FLP) — sole client point-of-contact, owns content curation and citation-safety review
- **John Anthony Jose** (Supervaise) — PM, owns manifest tracking and code audit
- **Jeanette** (Supervaise) — Tech Manager, owns RAG pipeline build
- **Rocelle** (Supervaise) — owns persona prompt and visitor question bank
- **CJ Panganiban** (FLP) — final voice/persona arbiter; will react to May 30 demo

---

## 2. Hard constraints (do not re-litigate)

| Decision | Locked Value | Why |
|---|---|---|
| Output language | English only (Taglish input accepted) | Confirmed at kick-off |
| KB scope | Embedded documents only, no web search | Locked |
| Vector store | **ChromaDB** (SQLite-backed), on R-Pi in production | Replaces earlier pgvector plan; cloud DB ruled out as most expensive component |
| LLM (dev May 4–13) | **Groq** (free tier) | Avoid burning OpenAI budget while pipeline is unstable |
| LLM (prod May 14+) | **OpenAI GPT-4o** | Locked post-code-audit |
| STT | OpenAI Whisper API (prod) / faster-whisper (dev fallback) | Locked |
| TTS | Pending — likely third-party (OpenAI TTS flagged as expensive) | Cost decision |
| Embeddings (dev) | `sentence-transformers/all-MiniLM-L6-v2`, 384-dim | Free, local |
| Embeddings (prod) | OpenAI `text-embedding-3-small`, 1536-dim, **single full-scale run** | Cost discipline |
| RAG orchestration | **LangChain** | Locked |
| Backend | FastAPI + Docker | Locked |
| Operator UI | Streamlit (Cloud free tier) | Locked |
| Hardware | Reachy Mini Wireless + LTE dongle | Locked, no companion PC |
| Architecture split | Cloud LLM/STT/TTS/embeddings ; on-prem ChromaDB on R-Pi | Cost-shaped |
| Demo format | Voice in / voice out, web app for May 30 (no robot yet) | Hardware ETA mid-June |

---

## 3. Strategic shift (May 6, 2026) — IMPORTANT

The **original plan** called for selecting **20 columns** from a curated candidate pool through a joint sign-off targeted Friday May 8.

**That plan is dead.** Per FLP direction:

> The corpus is defined by **what FLP provides**, not by an arbitrary count.

**Practical implications:**
- The "select 20 from 30 candidates" workflow is gone.
- The "≥2 columns from 2007–2012" temporal-balance criterion is gone (it was a curation rule, not a pipeline rule).
- The five buckets (A–E) are preserved as **retrieval-time metadata** for thematic biasing, not as ingestion gates.
- All 66 columns FLP delivered via the Column Selection Criteria Section 7 are now the **initial RAG corpus**.
- As FLP delivers more material (books, multimedia transcripts, PDF cases), it feeds the same pipeline.

**Cost impact at 66 columns:** roughly 260 chunks × ~500 tokens ≈ 130K tokens. At `text-embedding-3-small` pricing ($0.02 per 1M tokens) the full embedding run costs **under one US cent**. Negligible.

---

## 4. The corpus

**Initial 66 columns delivered** by FLP, organized into five buckets:

| Bucket | Theme | Count |
|---|---|---|
| A | Liberty and Rule of Law | 24 |
| B | Prosperity and Economic Philosophy | 7 |
| C | Biographical and Personal | 17 |
| D | FLP Mission and Foundation | 10 |
| E | Signature Current Events Commentary | 8 |
| **Total** | | **66** |

**Plus 9 off-topic columns** flagged in Section 7 as "may still be useful for ad hoc queries during testing." **Not currently in the corpus.** Trivial to add as a sixth bucket (`OT`) if needed.

**5 columns pre-flagged `citation_safe=False`** — politically sensitive, naming sitting officials in legal/political contexts. Require Jacob's explicit C5 review before they go live in production retrieval. The slugs are:

```
duterte-icc            -- "Pivotal issue in Duterte's ICC case" (2025-03-24)
icc-temporal-strategic -- "ICC: The temporal vs the strategic" (2023-08-07)
icc-doj-osg            -- "ICC prosecutor targets DOJ, OSG" (2023-02-27)
marcos-icc-options     -- "President Marcos' ICC options" (2023-12-11)
trump-defeat           -- "Defeat for Trump, victory for rule of law" (2020-12-27)
```

The `--safe-only` flag in `ingest_columns.py` filters these out for the production collection; they remain available in dev for retrieval QA.

---

## 5. The 5-stage pipeline

### Stage 1 — Loading

**Goal:** fetch each Inquirer URL, strip page chrome, convert article body to clean Markdown.

**Stack:** `requests` + `trafilatura` (favor_precision=True, output_format=markdown). On extraction failure, raise — do not silently fall back. 1-second delay between requests, identifying User-Agent.

**On-disk layout:**
```
kb/
  raw/<bucket>/<slug>.html      # original HTML, cached for reproducibility
  clean/<bucket>/<slug>.md      # cleaned markdown body
  meta/<bucket>/<slug>.json     # metadata sidecar
  manifest.csv                  # master log
```

**Watch list:**
- Pre-2017 columns are missing from the public Inquirer archive. Earliest accessible online is `due-process-judicial-comp` (2011-07-03). True 2007–2010 material requires OCR from the *With Due Respect* Vol. 1 print book — Phase 2 enrichment.
- Multi-page columns: trafilatura usually handles them; verify against expected 700–1,200 word count. <400 words probably truncated.
- CJ uses ALL-CAPS for emphasis. Verify casing is preserved through cleaning.

### Stage 2 — Chunking

**Recommended parameters (locked unless retrieval QA shows problems):**

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,            # tokens, not chars
    chunk_overlap=75,          # ~15% overlap
    length_function=tiktoken_len,   # cl100k_base, matches OpenAI tokenizer
    separators=["\n\n", "\n", ". ", " ", ""],
)
```

**Why these values:** average column is 700–1,200 words ≈ 900–1,500 tokens, so 500-token chunks produce 3–5 retrievable passages per column. Larger chunks (1,000+ tokens) drag tangential paragraphs into retrieval and dilute LLM grounding.

**Special handling:**
- **DO NOT** inline byline/date/title into chunk text — store as metadata only. Otherwise every chunk reads "By Artemio V. Panganiban — 23 October 2023..." and similarity scores get noisy.
- Strip `— With Due Respect` footers before chunking.

### Stage 3 — Embedding

Two-track. Use **separate Chroma collections**, one per dimensionality (Chroma refuses mixed-dim upserts):

| | Dev (May 4–13) | Production (May 14+) |
|---|---|---|
| Model | `all-MiniLM-L6-v2` | `text-embedding-3-small` |
| Dim | 384 | 1,536 |
| Where | Laptop, free | OpenAI API |
| Collection | `cjp_columns_dev` | `cjp_columns_prod` |

**Cutover is a one-line config change:** `EMBEDDER=openai python ingest_columns.py --collection cjp_columns_prod`. No data migration, no re-fetch.

### Stage 4 — Ingestion (ChromaDB)

**Persistent client at `./chroma_store/`.** SQLite-backed. When the project moves to the R-Pi, copy the directory across — no rebuild required.

**Metadata schema (mandatory, every chunk):**

```python
{
    "source_url":       str,        # the Inquirer URL
    "title":            str,        # column title
    "publication_date": "YYYY-MM-DD",
    "bucket":           "A"|"B"|"C"|"D"|"E",
    "bucket_name":      str,        # human-readable
    "chunk_index":      int,        # 0-based within column
    "chunk_count":      int,        # total chunks for this column
    "word_count":       int,        # of this chunk
    "citation_safe":    bool,       # set by Jacob per C5; default True except 5 flagged
    "ingested_at":      ISO8601,    # upsert timestamp
    "embedder":         "minilm"|"openai",  # for audit / dim sanity check
}
```

**Idempotency:** chunk_id is deterministic (`<slug>__c<NN>`). Re-running ingestion replaces existing records. Safe to iterate on chunking parameters without manual collection clearing.

### Stage 5 — Retrieval

**Defaults (tune if QA finds problems):**

| Parameter | Value | Notes |
|---|---|---|
| `n_results` (top-k) | 5 | Generous enough that 1–2 weak hits don't starve the LLM |
| Distance metric | cosine | Chroma default |
| Distance threshold | 0.45 | Drop chunks with `distance > 0.45` |
| Production filter | `where={"citation_safe": True}` | Keeps the 5 unreviewed columns out |
| Diversity guardrail | Max 2 chunks per source column | Avoid single-source narrowness |
| Bucket boost (optional) | If query mentions `scholarship`/`foundation`, filter to bucket=D first | Fall back to global if <3 hits |

**Context assembly template for GPT-4o:**

```
SYSTEM:
You are CJ Panganiban, speaking to a donor or visitor in the formal,
warm voice of his "With Due Respect" columns. Answer ONLY from the
context below. If the context does not contain enough information,
say: "That is a question I'd rather refer to the Foundation team."

CONTEXT (5 passages from CJ's writings):
[1] "<title>" (<date>)
    <chunk text>

[2] "<title>" (<date>)
    <chunk text>

...

USER QUESTION: <visitor question>
```

**Out-of-scope referral:** persona prompt must instruct the model to defer to "the Foundation team" when retrieval comes back empty or below threshold. Tested with deliberately out-of-scope questions in Rocelle's question bank.

---

## 6. Existing deliverables

Two files were generated in the conversation that produced this handover. Both are **already produced** — Claude Code does not need to recreate them. Treat them as inputs.

| File | What it is | Status |
|---|---|---|
| `Opinion_Columns_Ingestion_Manifest.docx` | Human-readable Word doc for Jacob/John/Jeanette/Rocelle. 10 sections covering purpose, the 5-stage pipeline with all params, the master 66-column inventory by bucket, validation checklist, next actions. | Final v2, revised 6 May 2026 |
| `ingest_columns.py` | Runnable Python script implementing all 5 stages. All 66 columns hard-coded. Supports `--dry-run`, `--safe-only`, `--smoke-test`, dev/prod embedder switch via `EMBEDDER` env var. | Ready to run |

---

## 7. Suggested repo layout

```
cjp-conversational-robot/
├── CLAUDE.md                       # this file (rename from KB_BUILD_CONTEXT.md)
├── README.md
├── pyproject.toml                  # or requirements.txt
├── docker-compose.yml
│
├── backend/
│   ├── main.py                     # FastAPI app
│   ├── adapter.py                  # robot adapter abstraction (Reachy / web / sim)
│   ├── persona.py                  # CJ persona prompt + answer-boundary rules
│   ├── retriever.py                # ChromaDB query wrapper, top-k + diversity
│   ├── llm.py                      # Groq (dev) / OpenAI (prod) client
│   ├── stt.py                      # faster-whisper (dev) / Whisper API (prod)
│   ├── tts.py                      # third-party / OpenAI TTS (TBD)
│   └── tests/
│
├── kb/                             # populated by ingest_columns.py
│   ├── raw/<bucket>/<slug>.html
│   ├── clean/<bucket>/<slug>.md
│   ├── meta/<bucket>/<slug>.json
│   └── manifest.csv
│
├── chroma_store/                   # ChromaDB persistent dir (gitignored)
│
├── ingest_columns.py               # the loader/chunker/embedder/upserter
├── operator_ui.py                  # Streamlit dashboard
│
├── docs/
│   ├── Opinion_Columns_Ingestion_Manifest.docx
│   ├── CJP_Final_Tech_Stack.docx
│   ├── Project_Timeline_v1.docx
│   └── Column_Selection_Criteria_May30_Demo.docx
│
└── scripts/
    ├── audit_pipeline.py           # John's pre-cutover audit
    └── smoke_test_questions.py     # Rocelle's visitor question bank
```

`.gitignore` should include `chroma_store/`, `kb/raw/`, `kb/clean/` (HTML and copyrighted text — keep them local).

---

## 8. Copyright posture

**The 66 columns are CJ's IP, published under Inquirer's masthead.** Until FLP confirms reuse permission for an embedded RAG corpus (Phase 2 open item, on Project Timeline):

- The script fetches HTML on demand and stores cleaned text only inside the local ChromaDB. **Nothing is redistributed.**
- The Word manifest contains URLs and metadata, **not article bodies.**
- Do not commit `kb/raw/*.html` or `kb/clean/*.md` to a public repo. Private Drive or local-only.
- For the September showcase, **FLP must formally clear "embed and serve"** with Inquirer. The May 30 closed-room demo is arguably fine; September is not.

---

## 9. Open items

| # | Item | Owner |
|---|---|---|
| 1 | Confirm reuse permission with Inquirer for embedded RAG corpus | Jacob |
| 2 | Cloud platform: Railway vs Render vs Fly.io | Jeanette |
| 3 | TTS provider: OpenAI TTS (if affordable) vs third-party | Jeanette / John |
| 4 | Voice cloning vs neutral voice (CJ consent + FLP direction) | Jacob / CJ |
| 5 | CJ Q&A scope: legal cases vs personal/opinion focus only | Jacob / CJ |
| 6 | Persona framing: replicate exact CJ voice vs adapt for donor audience | Jacob / CJ |
| 7 | C5 review of 5 flagged columns (Duterte/Marcos/Trump/2 ICC) | Jacob |
| 8 | Decide whether the 9 off-topic columns enter the corpus as bucket OT | Jacob / John |
| 9 | MuJoCo simulator integration: Week 3 stretch vs deferred | Jeanette |

---

## 10. Next-action checklist

### This week (May 4–13, dev stack)

- [ ] **Set up the repo skeleton** per Section 7 above. Commit `CLAUDE.md`, `pyproject.toml`, `.gitignore`, the bare backend module structure.
- [ ] **Install dependencies:** `requests trafilatura readability-lxml markdownify tiktoken langchain-text-splitters sentence-transformers chromadb python-dateutil tqdm groq` and dev tools (`pytest`, `ruff`).
- [ ] **Run `python ingest_columns.py --dry-run`** to validate fetch + chunk against the full 66 without spending embedding compute. Surface any loader failures (URL changes, layout shifts).
- [ ] **Fix any QA-warn lines** the dry run produces. Each "produced N chunks (expected 3–5)" needs investigation — usually a column that's unusually short or long.
- [ ] **Run `python ingest_columns.py --smoke-test`** to populate `cjp_columns_dev` with 384-dim embeddings and run a sample query. Eyeball the top-5 hits for relevance.
- [ ] **Build `backend/retriever.py`** — wraps Chroma queries, applies top-k, diversity guardrail (max 2 chunks/source), distance threshold (0.45), and optional bucket filter.
- [ ] **Build `backend/persona.py`** — the CJ system prompt. Include the FLP-referral fallback line. Pull tone cues from the bucket C/D columns once they're loaded.
- [ ] **Build `backend/llm.py`** — Groq client for dev. Accept `provider` arg so the May 14 cutover is a single config flip, not a rewrite.
- [ ] **Build `backend/main.py`** — FastAPI endpoint `/ask` that takes audio in, returns audio out (or text in dev mode). Wire STT → retriever → LLM → TTS.
- [ ] **Stand up `operator_ui.py`** — Streamlit dashboard for sample queries, retrieval inspection, and answer review.

### Pre-cutover (May 13–14)

- [ ] **John audits Jeanette's pipeline code** before any OpenAI key is added (May 2 agreement).
- [ ] **Add OpenAI key** to env. Run `EMBEDDER=openai python ingest_columns.py --collection cjp_columns_prod --safe-only` for the single billed embedding run on the 61 cleared columns.
- [ ] **Switch `backend/llm.py`** from Groq to OpenAI GPT-4o.
- [ ] **Re-run smoke tests** with the prod collection. Compare retrieval quality vs the 384-dim dev collection on the same questions.

### Pre-demo (May 25–30)

- [ ] **Joint walkthrough** of sample retrievals with FLP. Persona QA, citation safety, out-of-scope referrals.
- [ ] **Latency QA** — voice-in to voice-out under 6 seconds end to end on demo laptop / demo internet.
- [ ] **Rehearsal** with the simulator, then with CJ.

---

## 11. Useful prompts for Claude Code

Drop these into Claude Code as starting points. Each assumes Claude Code has read this `CLAUDE.md`.

**Set up the project skeleton:**
```
Create the repo skeleton per Section 7 of CLAUDE.md. Generate
pyproject.toml with the dependencies listed in Section 10. Create
.gitignore that excludes chroma_store/, kb/raw/, kb/clean/, .env, and
__pycache__/. Stub out the backend/ modules with docstrings only —
implementations come next.
```

**Build the retriever:**
```
Implement backend/retriever.py per the Stage 5 spec in CLAUDE.md.
Use chromadb.PersistentClient pointed at ./chroma_store/, default
collection cjp_columns_dev. Top-k=5, cosine threshold 0.45,
max-2-chunks-per-source diversity guardrail. Optional bucket filter
parameter. Returns a list of dicts with chunk text, metadata, and
distance. Add pytest tests covering: (a) empty result, (b) all results
above threshold, (c) diversity guardrail kicking in.
```

**Build the persona module:**
```
Implement backend/persona.py per the context-assembly template in
Section 5 (Stage 5) of CLAUDE.md. Function build_prompt(question,
retrieved_chunks) returns the full system+user message pair for the
Chat Completions API. Persona is CJ Panganiban in formal "With Due
Respect" voice. Hard rule: answer ONLY from context. Fallback line for
out-of-scope: "That is a question I'd rather refer to the Foundation
team."
```

**Add the LLM abstraction:**
```
Implement backend/llm.py with a single generate(messages, provider)
function. Provider="groq" uses the Groq SDK with model
llama-3.3-70b-versatile. Provider="openai" uses GPT-4o. Default
provider is read from env var LLM_PROVIDER (default: "groq").
Temperature 0.3, max_tokens 250 (matches the 100–150 word response cap).
```

**Run a retrieval-quality experiment:**
```
Read kb/manifest.csv. For each bucket A–E, write 3 sample visitor
questions matching that bucket's theme. Run them through
backend/retriever.py against cjp_columns_dev. Print a table of: query,
top-1 hit title, top-1 distance, top-1 bucket. Flag any case where
top-1 bucket != expected bucket.
```

---

## 12. Glossary / acronyms

- **FLP** — Foundation for Liberty and Prosperity
- **CJ** — Chief Justice (Artemio V. Panganiban)
- **C1–C7** — the seven column-selection criteria (C5 = Citation Safety, the relevant one for production gating)
- **R-Pi** — Raspberry Pi (the Reachy Mini's onboard CM4)
- **WPS** — West Philippine Sea (frequent topic in Bucket A)
- **EEZ** — Exclusive Economic Zone
- **ICC** — International Criminal Court
- **SPJI** — Society for Philippine Judiciary Innovation
- **LibPros** — Liberty and Prosperity (FLP scholar program)

---

*Internal working document for the Supervaise × FLP project. Revisions tracked in the Viber group.*
