# CJ Panganiban Conversational AI — Pipeline Review

**As of 2026-05-07 · post-`5a58664`**
**Phase:** A — all-free dev stack on the laptop · pre-OpenAI cutover

This document is the canonical reference for the current state of the demo's pipeline. For per-push history see [`PROGRESS.md`](../PROGRESS.md). For the strategic spec see [`CLAUDE.md`](../CLAUDE.md) and [`docs/handover_v2.md`](handover_v2.md). A frozen PDF snapshot of this same content lives at [`pipeline_review_2026-05-07.pdf`](pipeline_review_2026-05-07.pdf) — regenerable with `python scripts/build_pipeline_review_pdf.py`.

---

## 1. High-level architecture

Everything runs on the dev laptop except the Groq LLM call. Streamlit imports the orchestrator directly — no HTTP layer in Phase A.

```
                    Visitor's browser (Edge / incognito)
                                      │ HTTP
                                      ▼
              ┌─────────────────────────────────────┐
              │    Streamlit 1.57 on localhost:8501  │
              │    (app.py — chat UI, history,       │
              │     citation panel, latency,         │
              │     fallback warning)                │
              └────────────┬─────────────────────────┘
                           │ Python imports
                           ▼
              ┌─────────────────────────────────────┐
              │  backend/orchestrator.py            │
              │  answer_question(text, history)     │
              │  → returns Response                 │
              └─┬──┬──┬──┬──┬──────────────────────┘
                │  │  │  │  │
        ┌───────┘  │  │  │  └──────────┐
        │          │  │  │             │
        ▼          ▼  ▼  ▼             ▼
   ┌────────┐  ┌─────┐ ┌────┐  ┌────────────┐
   │faster- │  │chro │ │groq│  │edge-tts    │
   │whisper │  │maDB │ │ →  │  │(Microsoft  │
   │(small) │  │+    │ │HTTPS  Edge cloud)  │
   │        │  │Mini │ │     │              │
   │STT     │  │LM   │ │LLM  │  TTS cloud   │
   │local   │  │embed│ │free │  (free)      │
   └────────┘  └─────┘ └────┘  └────────────┘
                                     ▲
                                     │ Audio MP3
                                     ▼
                    (back to browser as autoplaying audio)
```

---

## 2. Frontend layer

| Item | Value |
|---|---|
| Framework | Streamlit `1.57.0` |
| Entry point | `app.py` |
| URL | `http://localhost:8501` |
| Chat primitives | `st.chat_input` + `st.chat_message` + `st.audio_input` (mic) + `st.audio` (TTS playback) |
| Conversation history | `st.session_state.history` — list of `{role, content, meta}` dicts |
| Citation rendering | `_render_meta()` shows bucket / title / date / cosine distance / URL / unsafe-tag |
| File watcher | **DISABLED** via `.streamlit/config.toml` (`fileWatcherType = "none"`) — Windows watchdog crash fix |
| Telemetry | Disabled (`gatherUsageStats = false`) |

**Visitor flow:** record (or type) → see "Heard:" caption → see "Thinking…" spinner → see assistant message + citations + latency + (optional) fallback warning → hear voice playback.

---

## 3. STT (Speech-to-Text)

| Item | Value |
|---|---|
| Library | `faster-whisper==1.2.1` |
| Wrapper | `backend/stt.py` |
| Model | **`small`** (bumped from `base` post-`5a58664`) |
| Disk size | ~470 MB |
| Quantization | `int8` (CPU-friendly) |
| Device | `cpu` |
| Decode params | `beam_size=1` (fastest greedy) |
| Cache location | `./models/faster-whisper-small/` (project-local, gitignored) |
| Download mechanism | `huggingface_hub.snapshot_download` with `local_dir` (avoids Windows symlink permission issue) |
| Latency | ~3-5 sec for a 5-15 sec audio clip on a typical laptop CPU |
| Languages | Auto-detect; multilingual; output is English text but Taglish input is fine |
| Configurable via | `WHISPER_MODEL` env var |

---

## 4. LLM (chat completion)

| Item | Value |
|---|---|
| Provider | **Groq** (free tier) |
| Library | `groq==1.2.0` |
| Wrapper | `backend/llm.py` — single `chat(messages)` function |
| Model | `llama-3.3-70b-versatile` |
| Where it runs | Groq's cloud servers (only remote hop in the whole pipeline) |
| API key env var | `GROQ_API_KEY` |
| Model env var | `GROQ_MODEL` |
| Latency | ~1-2 sec typical; can spike to 3-5 sec under load |
| Phase B target | OpenAI GPT-4o (single config flip) |

---

## 5. TTS (Text-to-Speech)

| Item | Value |
|---|---|
| Library | `edge-tts==7.2.8` (Microsoft Edge's TTS endpoint) |
| Wrapper | `backend/tts.py` — `synthesize(text, voice)` returns mp3 bytes |
| Voice | **`en-US-AndrewNeural`** (US male, configurable via `TTS_VOICE`) |
| Other male options | `en-US-GuyNeural`, `en-US-EricNeural`, `en-GB-RyanNeural`, `en-AU-WilliamNeural` |
| Cost | Free, no API key |
| Latency | ~1-2 sec for a 100-150 word answer |
| Implementation note | Async-only API; wrapped with `asyncio.run()` per call |
| Caching | `@st.cache_data` on the synthesize call so same answer text doesn't re-synth |

---

## 6. Persona & fallback (the LLM's instruction layer)

| Item | Value |
|---|---|
| System prompt file | `prompts/instructions.txt` |
| Loader | `backend/prompts.py` — `system_prompt()` returns persona + substituted fallback |
| Persona rules | (1) source-grounded only; (2) 100-150 word output cap; (3) English only (Taglish input OK); (4) measured / educational style; (5) no legal advice; (6) no persona breaks |
| Fallback file | `prompts/fallback.txt` — **5 variants** separated by `---` |
| Variant selection | Random per call (`random.choice(_fallback_variants())`) |
| Owner of final wording | Jacob Barbosa (FLP) — current text is placeholder per OD-1, OD-3, OD-8 |

The persona prompt is injected as a `system` message prepended to every Groq call.

---

## 7. Embeddings layer

| Item | Value |
|---|---|
| Library | `sentence-transformers==5.4.1` |
| Model | **`all-MiniLM-L6-v2`** (changed from `all-mpnet-base-v2` when we adopted v2 handover spec) |
| Dimensions | **384** (was 768 before v2 handover) |
| Disk size | ~90 MB |
| Where it runs | Local laptop CPU |
| Used in two places | (a) ingestion-time chunk embedding in `ingest_columns.py`; (b) query-time question embedding in `backend/retrieval.py` |
| Cache | `~/.cache/huggingface/hub/` (downloaded on first use; degraded-copy mode on Windows) |
| Phase B target | OpenAI `text-embedding-3-small` (1536-dim) — **requires re-embedding all chunks** |

---

## 8. Vector store

| Item | Value |
|---|---|
| Engine | `chromadb==1.5.8` (embedded, in-process, SQLite-backed) |
| Persist directory | `./chroma_store/` (gitignored) |
| Collection name | `cjp_columns_dev` |
| Distance metric | cosine |
| Index | HNSW (Chroma default) |
| Total chunks | **954** |
| Total sources (slugs) | **85** |
| Phase B collection | `cjp_columns_prod` (new collection at 1536-dim — no in-place migration) |

### Per-chunk metadata schema

Every chunk in `cjp_columns_dev` has these fields:

```text
source_url        e.g. "https://opinion.inquirer.net/167388/..." or
                       "source_materials/centenary_chapters/ch14-the-death-penalty.txt"
title             e.g. "Centenary, Ch.14: The Death Penalty"
publication_date  YYYY-MM-DD
bucket            "A" | "B" | "C" | "D" | "E"
bucket_name       human-readable, e.g. "Liberty and Rule of Law"
chunk_index       0-based within source
chunk_count       total chunks for this source
word_count        of this chunk
citation_safe     bool — Jacob's C5 review flag
ingested_at       ISO8601
embedder          "minilm" (will be "openai" post-cutover)
```

---

## 9. Retrieval layer

| Item | Value |
|---|---|
| Module | `backend/retrieval.py` — `retrieve(query, top_k, bucket, safe_only)` |
| Top-k | **5** (env: `RETRIEVAL_TOP_K`) |
| Distance threshold | **0.55** (env: `RETRIEVAL_DISTANCE_THRESHOLD`; v2 spec said 0.45 but smoke-tested distances on MiniLM run higher) |
| Diversity guardrail | **max 2 chunks per source** (env: `RETRIEVAL_MAX_PER_SOURCE`) |
| Bucket filter | optional, used for thematic biasing (not in default flow) |
| Citation-safe filter | optional via `RETRIEVAL_SAFE_ONLY` env (off in dev; will be `true` in prod) |
| Over-fetch | `n_results = top_k × 3` to give the diversity filter room |
| Returns | List of `RetrievedChunk` dataclasses |

---

## 10. Orchestrator (the per-turn flow)

```python
# backend/orchestrator.py
def answer_question(text, history):
    start_timer()
    chunks = retrieve(text)

    if not chunks:
        # pick a random fallback variant
        return Response(fallback=True, ~30 ms latency, no LLM call)

    messages = [
        {role: system,    content: persona_prompt},
        {role: system,    content: "Provided sources: …" + chunk texts},
        *history,
        {role: user,      content: text},
    ]

    answer = chat(messages)            # → Groq llama-3.3-70b-versatile
    answer = trim_to_150_words(answer)

    citations = [{title, date, url, bucket, distance, citation_safe} for c in chunks]

    return Response(text=answer, citations=citations, latency_ms=…, fallback=False)
```

---

## 11. Robot adapter (future-proofing)

| Item | Value |
|---|---|
| Module | `backend/adapters.py` |
| Protocol | `RobotAdapter` (`speak` / `head_move` / `gaze_track` / `thinking_motion` / `handle_interrupt`) |
| Live impl | `WebAdapter` — `speak()` does `st.write` + `st.audio` autoplay; other methods are no-ops |
| Future impl | `ReachyAdapter` — drops in late July / Aug, no other code changes needed |

---

## 12. Knowledge base composition

| Bucket | Theme | # Sources | # Chunks (approx) |
|---|---|---|---|
| **A** | Liberty and Rule of Law | 44 (24 cols + 20 book chapters) | ~770 |
| **B** | Prosperity and Economic Philosophy | 7 columns | ~25 |
| **C** | Biographical and Personal | 17 columns | ~75 |
| **D** | FLP Mission and Foundation | 10 columns | ~40 |
| **E** | Signature Current Events Commentary | 7 columns | ~30 |
| **Total** | | **85 sources** | **954 chunks** |

5 columns flagged `citation_safe=False` (Duterte ICC, Marcos ICC options, Trump defeat, ICC DOJ-OSG, ICC temporal-strategic) — pending Jacob's C5 review.

---

## 13. Ingestion pipeline

Run via `python ingest_columns.py`. 5 stages, all in `ingest_columns.py`:

```text
Stage 1 — Load
  ├─ if URL  → fetch HTML (browser-shaped headers + canonical URL guard) → trafilatura → markdown
  └─ if file → read .docx (Docx2txtLoader) or .txt/.md (raw read) → markdown
                  ↓
Stage 2 — Chunk
  ├─ RecursiveCharacterTextSplitter, chunk_size=500 tokens, overlap=75 tokens
  ├─ Tokenizer: cl100k_base (matches OpenAI for cutover compatibility)
  └─ Separators: ["\n\n", "\n", ". ", " ", ""]
                  ↓
Stage 3 — Embed
  └─ all-MiniLM-L6-v2, batch_size=32, → 384-dim vector per chunk
                  ↓
Stage 4 — Upsert
  └─ ChromaDB cjp_columns_dev, deterministic chunk IDs ({slug}__c{NN})
                  ↓
Stage 5 — Smoke test (optional, --smoke-test flag)
  └─ Sample query → top-5 → eyeball
```

**Word-count guards:** `<400` words from any source raises (catches truncation / wrong-block extraction).

**Canonical URL guard:** catches Inquirer's silent redirect to the section homepage when a column URL is dead.

**Book chapter split:** "A Centenary of Justice" (2001) was split into 20 chapter `.txt` files via `scripts/extract_chapters_from_pdf.py` (sequential title-search parser over the source PDF) before ingestion. See PROGRESS.md entry 2026-05-07 for parser details and known imperfections.

---

## 14. Configuration files

| File | Purpose | Tracked? |
|---|---|---|
| `.env` | Real config — has Groq key | **gitignored** |
| `.env.example` | Template, no real keys | tracked |
| `.streamlit/config.toml` | Disable file watcher, telemetry | tracked |
| `.gitignore` | excludes `.venv/`, `chroma_store/`, `kb/`, `models/`, `source_materials/`, `.env`, `*.log`, `.claude/...` | tracked |
| `requirements.txt` | Pinned deps (~150 packages) | tracked |
| `prompts/instructions.txt` | Persona prompt | tracked |
| `prompts/fallback.txt` | Fallback variants | tracked |

---

## 15. Environment variables

| Var | Current value | What it controls |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` (your key) | LLM auth |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | LLM model |
| `WHISPER_MODEL` | **`small`** (post-`5a58664`) | STT model size |
| `TTS_VOICE` | `en-US-AndrewNeural` | TTS voice |
| `RETRIEVAL_TOP_K` | not set → defaults to 5 | retrieval breadth |
| `RETRIEVAL_DISTANCE_THRESHOLD` | not set → 0.55 | confidence cutoff |
| `RETRIEVAL_MAX_PER_SOURCE` | not set → 2 | diversity guardrail |
| `RETRIEVAL_SAFE_ONLY` | not set → false (dev) | citation-safe filter |
| `CHROMA_COLLECTION` | not set → `cjp_columns_dev` | ChromaDB collection |
| `CONVERSATION_WINDOW_MINUTES` | `5` | (not yet wired — Step 1.9) |
| `TRIGGER_WORDS` | `that's enough,...` | (not yet wired — Step 1.9) |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | `all-mpnet-base-v2` / `768` | **DEAD CODE** — no longer read by the new code; should clean up |

---

## 16. Phase A → Phase B (OpenAI cutover) checklist

| Component | Phase A (now) | Phase B (after May 14 + John's audit) |
|---|---|---|
| LLM | Groq `llama-3.3-70b-versatile` | OpenAI `gpt-4o` |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (384-dim) | OpenAI `text-embedding-3-small` (1536-dim) |
| STT | faster-whisper `small` local | TBD — open: faster-whisper on Railway, OpenAI Whisper API, or stay local on R-Pi |
| TTS | edge-tts (free cloud) | TBD — possibly OpenAI TTS, possibly stay edge-tts |
| Vector store | ChromaDB `cjp_columns_dev` (laptop) | ChromaDB `cjp_columns_prod` on R-Pi (full re-embed required) |
| Backend host | Streamlit imports orchestrator | Possibly FastAPI behind HTTP, on R-Pi |

---

## 17. What's NOT yet wired (Track 1 leftovers)

- **Step 1.9** — trigger-word interrupt ("thank you" / "next question" → reset state) + 5-min conversation window auto-clear
- **Step 1.10** — structured JSON logging to `logs/turns.jsonl` (per-turn input, citations, latency, fallback reason — required per HANDOVER §3 rule #13)

---

## 18. Known imperfections to revisit

| Issue | Severity | Plan |
|---|---|---|
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` env vars are dead code in `.env.example` | Cosmetic | Remove next push |
| Ch 2 of book is 27,556 words (absorbed photo plate captions) | Medium | Next strategy session for chunking-of-oversized-chapters |
| Ch 18 / 19 boundary off by ~1k words | Low | Same |
| Ch 20 absorbs back matter (index, etc.) | Low-medium | Same |
| LLM occasionally ignores source-grounded rule when context is weak | Low (RAG mostly suppresses this now) | Watch during dry-runs |
| Distance threshold 0.55 is a smoke-test guess for MiniLM | Low (working in practice) | Re-tune at OpenAI cutover (different distance distribution) |

---

*End of pipeline review. For per-push history and recent decisions, see [`PROGRESS.md`](../PROGRESS.md). For the strategic spec, see [`CLAUDE.md`](../CLAUDE.md) and [`docs/handover_v2.md`](handover_v2.md).*
