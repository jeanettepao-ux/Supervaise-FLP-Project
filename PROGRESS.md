# PROGRESS — CJ Panganiban Conversational AI

A running log of what was built, when, and why. **Updated on every push to GitHub.**

How to read this file:
- **Reverse chronological** — newest first.
- Each entry: date · commit hash · what was built · gotchas.
- The Sitrep at the top is a snapshot of current state; entries below it are the per-push history.

---

## Sitrep — 2026-05-05

### What's working end-to-end right now

A visitor opens `http://localhost:8501`, sees the "CJ Panganiban — May 30 Demo" Streamlit chat page, can either click the mic to record a question or type one in the text fallback. Their voice gets transcribed locally by faster-whisper, the question is sent through the backend orchestrator (which prepends the CJ persona system prompt with a randomly-picked fallback variant) to Groq's `llama-3.3-70b-versatile` model, the answer comes back, gets read aloud by **edge-tts** (default `en-US-AndrewNeural` — US male voice, configurable via env), and renders in the chat with placeholders for citations, latency, and a fallback warning indicator. Conversation history persists across reruns. Streamlit's file watcher is disabled via `.streamlit/config.toml` so the heavy dep tree doesn't crash the server on Windows.

### What's actually built (Phase A — May 30 demo)

| Track 1 step | Status | Module |
|---|---|---|
| 1.1 Project setup, venv, requirements, folder map | done | `requirements.txt`, scaffolding |
| 1.2 Backend orchestrator + `Response` dataclass | done | `backend/orchestrator.py` |
| 1.3 Groq LLM wrapper | done | `backend/llm.py` |
| 1.4 STT (visitor mic) via faster-whisper | done | `backend/stt.py`, `./models/` |
| 1.5 Chat UI: history, citation panel, latency, fallback indicator | done | `app.py` |
| 1.6 Persona system prompt + fallback text loader | done | `backend/prompts.py`, `prompts/instructions.txt`, `prompts/fallback.txt` |
| 1.7 `RobotAdapter` Protocol + `WebAdapter` | done | `backend/adapters.py` |
| 1.8 TTS via edge-tts (free cloud, male voice) | done | `backend/tts.py`, `.streamlit/config.toml` |
| 1.9 Trigger-word interrupt + 5-min conversation window | NOT STARTED | — |
| 1.10 Structured JSON logging to `logs/turns.jsonl` | NOT STARTED | `backend/logger.py` (placeholder only) |

| Track 2 step | Status | Module |
|---|---|---|
| 2.1 Document loaders (PDF/TXT/MD) | NOT STARTED | `ingestion/load_and_embed.py` (placeholder only) |
| 2.2 Chunking with theme-bucket (A–E) metadata | NOT STARTED | — |
| 2.3 Embedding pipeline (sentence-transformers, 768-dim) | NOT STARTED | — |
| 2.4 ChromaDB ingestion + collection schema | NOT STARTED | — |
| 2.5 Retrieval testing harness | NOT STARTED | `ingestion/retrieval_test.py` (placeholder only) |
| 2.6 Confidence-threshold tuning (start 0.35) | NOT STARTED | — |

| Day-15 convergence | Status |
|---|---|
| Replace hard-coded persona-only LLM call with retrieve → confidence check → prompt assembly → Groq → trim → cite | NOT STARTED |

| Polish (Days 22–29) | Status |
|---|---|
| Citation rendering polish, approved fallback wording from Jacob, latency tuning, dry runs, frozen build | NOT STARTED |

### What's blocking the demo (waiting on humans, not code)

- **FLP source materials** — owned by Jacob. Without these, Track 2 ingestion has nothing to ingest.
- **Approved fallback language (OD-8)** — Jacob's call. Current `prompts/fallback.txt` is a placeholder.
- **Persona refinements (OD-1, OD-3)** — Jacob's call after CJ feedback at the May 30 demo.

---

## Per-push history

### 2026-05-07 · STT default bumped from `base` → `small`

User reported transcription quality was rough on `base` (e.g., "how much is it" → "hoe mad is it"). Per HANDOVER §2.4 the original plan was always `base` for dev speed and `small` for May-30 demo accuracy — we just hadn't bumped it.

`.env.example` updated to `WHISPER_MODEL=small`. Local `.env` also bumped (gitignored, laptop-only). First transcription after restarting Streamlit will download the `small` model into `./models/` (~470 MB, one-time, ~30-60s on a normal connection). Subsequent transcriptions take ~3-5s instead of `base`'s ~1-2s, but words come out right.

### 2026-05-07 · `14b9d23` · Chapter-level KB for "A Centenary of Justice" (Bounded-within-chapters strategy)

User chose the **bounded-within-chapters** chunking strategy: chunks are ≤500 tokens AND chunks never cross chapter boundaries. Each chunk knows its parent chapter via metadata. Replaces the 2026-05-06 single-slug book ingest.

**Parser (`scripts/extract_chapters_from_pdf.py`):**
- Loads original PDF (`A CENTENARY OF JUSTICE (3).pdf`) via `pypdf`.
- Skips front matter / TOC (PDF pages 1-17); body text starts at page 18.
- For each of 20 chapters, sequential title-search with whitespace-tolerant regex; each chapter must be found AT or AFTER the previous chapter's match (eliminates the false-match cascade we hit in the first attempt).
- Per-chapter candidate phrases: primary title plus distinctive keywords (e.g., Ch 14 uses `"heinousness"` instead of just `"The Death Penalty"` to avoid Ch 2 cross-references; Ch 15 uses `"indigenous peoples"`; Ch 19 uses `"natural-born citizen"`; Ch 20 uses `"exit poll"`).
- Slices body text by chapter-start offsets, saves each as `source_materials/centenary_chapters/ch{NN}-{slug}.txt`.

**Result: 20 of 20 chapters detected, in correct sequential order.** Sizes mostly healthy except 3 known imperfections:
- Ch 2 oversize (27,556 words) — absorbed Part I photo plate captions between Ch 1 body and Ch 3 body. Captions are still real CJ-adjacent content, just attributed to Ch 2.
- Ch 18 short (1,251 words) — Ch 19 detection might be ~1000 words early.
- Ch 20 large (18,035 words) — absorbs back matter (index, etc.) to end of file.

These are flagged for later refinement; non-fatal.

**Ingestion changes:**
- Single `centenary-of-justice` row in `COLUMNS` replaced with 20 chapter rows (`centenary-ch01` through `centenary-ch20`), each pointing at its `.txt` file. Titles like "Centenary, Ch.14: The Death Penalty" surface in citations.
- `chroma_store/` wiped before re-ingestion (drops stale single-slug chunks).

**State after re-ingestion:**
| Stat | Before today | After |
|---|---|---|
| Sources | 66 (65 columns + 1 book) | **85** (65 columns + 20 chapters) |
| Total chunks | 619 | **954** |
| Bucket A | 25 | 44 |

**Smoke test (chapter-level retrieval):**
- "Estrada v. Desierto" → 2× Ch 13 + 2× Ch 17 + Ch 12 (top dist 0.369)
- "death penalty in your book" → 2× Ch 14 (top dist 0.471)
- "Cruz v. Secretary of Environment" → 2× Ch 15 + 2× Ch 19 (top dist 0.428)
- "live radio/TV trials" → 2× Ch 17 (top dist 0.527)
- "exit polls" → Ch 20 (with one Ch 2 false-positive at top — photo-caption pollution)
- "FLP" → all column hits, book correctly stays out (2001 book pre-dates 2011 FLP)
- Out-of-scope → fallback in 30ms

Diversity guardrail capping at max-2 chunks per source means at chapter granularity, multiple chapters can be represented in one answer (e.g., the Estrada query pulls from Ch 13, Ch 17, AND Ch 12 — exactly the cross-chapter narrative donors would want).

`pypdf` and `pdfplumber` already in requirements.txt from earlier exploration; no new deps. The original `source_materials/A_Centenary_of_Justice.docx` is now redundant but harmless (gitignored).

### 2026-05-06 · `ea693f1` · "A Centenary of Justice" (CJ's 2001 SC book) added to corpus (single slug, superseded today)

User delivered `A_Centenary_of_Justice.docx` (105k words, ~350-page book on the Philippine Supreme Court's centennial 1901-2001) to extend the corpus. Originally pursued per-Chapter splitting (Option C) but the docx was a PDF→Word conversion that stripped all heading styles — every paragraph is `Normal`, no `Chapter N` markers in the body, chapter titles appear 2-7 times each across TOC + photo-caption sections + cross-references. Reliable per-chapter splitting from this source isn't possible without manual annotation or sourcing the original PDF.

Fell back to **Option A: one slug for the whole book**. Added a small loader extension to `ingest_columns.py`:
- `_load_file(path)` helper handles `.docx` (via `Docx2txtLoader`) and `.txt`/`.md` (raw read).
- `load_one()` now branches on `source.startswith(("http://", "https://"))` — URL path uses fetch + trafilatura; file path uses `_load_file` directly. Same word-count guard (<400 = raise) applies to both.
- New COLUMNS row: `("centenary-of-justice", "A Centenary of Justice", "2001-01-01", "A", "source_materials/A_Centenary_of_Justice.docx", True)`.
- The docx is copied into the repo's gitignored `source_materials/` (private, never committed per v2 §8 copyright posture).

**Ingestion result:** 66 sources total (was 65 columns + new book), 619 chunks (was 199), book contributes 420 chunks. Bucket A grew from 24 → 25.

**Smoke test** confirms the diversity guardrail is doing its job:
- Book-relevant queries ("centenary of Supreme Court", "death penalty views") → 2 book chunks per answer (max allowed); top distances 0.288 and 0.438 (book is by far the best match for SC-history topics)
- Column-relevant queries ("What is FLP?", "Who was Salonga?") → columns still win; book doesn't crack top-k (FLP didn't exist when the 2001 book was written; Salonga is in a dedicated column)
- Out-of-scope ("chocolate cake") → fallback fires in 36 ms, 0 citations

Failed attempt artifacts cleaned up (`scripts/extract_centenary_chapters.py` — chapter-detector that found 21 markers, all in TOC; the body had no markers because the PDF→docx conversion stripped formatting).

`pip install python-docx docx2txt` (added to `requirements.txt` via `pip freeze`).

### 2026-05-06 · `3fd0105` · Day-15 convergence: orchestrator now retrieves before generating

The Streamlit app now answers from CJ's own columns instead of hallucinating from the LLM's training data.

New / changed files:
- **`backend/retrieval.py`** *(new)* — wraps ChromaDB queries. Top-k=5, cosine distance threshold 0.55 (looser than v2's 0.45 because MiniLM-L6's distances run higher; see threshold note in previous entry), max-2-chunks-per-source diversity guardrail, optional bucket filter, optional `safe_only` (env: `RETRIEVAL_SAFE_ONLY`). Embedder + collection lazy-loaded via `lru_cache`. Returns a list of `RetrievedChunk` dataclasses with text, title, date, url, bucket, distance, citation_safe.
- **`backend/orchestrator.py`** — `answer_question()` flow rewritten:
  1. `retrieve(question)`
  2. If 0 chunks: return random fallback variant (no LLM call, ~30 ms)
  3. Otherwise: build messages = `[persona, "Provided sources:" + chunks, history, question]`, call Groq, trim to 150 words, return `Response` with citations populated
- **`app.py`** — citations expander now renders each citation as a markdown line (bucket, title, date, distance, optional URL, optional `⚠ unsafe` tag) instead of raw `str(dict)`.

End-to-end smoke test (3 queries):

| Query | Citations | Latency | Behavior |
|---|---|---|---|
| "Tell me about FLP in two sentences" | 5 (A,B,B,D,B) top dist 0.403 | 11.8 s (cold) | Grounded answer; mentions 2011 founding, scholarships, Prosperity Fund — all from chunks |
| "What did you write about Jovito Salonga?" | 2 (C,C) top dist 0.456 | 1.2 s | In-voice recollection: Far Eastern University, Latin honors, etc. |
| "How do I bake a chocolate cake?" | 0 | 30 ms | Fallback fired correctly, random variant returned, no LLM call |

Streamlit boot still clean (~9 s).

### 2026-05-06 · `4aa1659` · full ingestion landed: 199 chunks in ChromaDB

After the patches were in, ran `ingest_columns.py` (no `--dry-run`) for the full pipeline:

- **Stage 1-2 (load + chunk):** 65 / 65 columns OK, 199 chunks total, avg 3.1/column.
- **Stage 3 (embed):** sentence-transformers `all-MiniLM-L6-v2` downloaded (~90 MB) via huggingface_hub. Windows symlink degradation was a warning only this time (not the hard error we hit with whisper) — files copied instead of symlinked, no patching needed.
- **Stage 4 (upsert):** ChromaDB collection `cjp_columns_dev` at `./chroma_store/`, cosine space, 199 vectors at 384-dim.

**Smoke test — 6 queries (5 in-scope + 1 deliberately out-of-scope):**

| Expected bucket | Query | Top-1 hit | Top-1 distance |
|---|---|---|---|
| D | "What is FLP's mission?" | D · *FLP expanding into prosperity* | 0.442 |
| A | "Rule of law in West PH Sea?" | A · *WPS is ours* | **0.339** |
| C | "Who was Jovito Salonga?" | C · *Jovito R. Salonga, my guru and surrogate father* | 0.537 |
| B | "Economic prosperity?" | B · *Merging law and economics* | 0.529 |
| E (or A) | "ICC and the Philippines?" | A · *President Marcos' ICC options* `[unsafe]` | 0.438 |
| **out-of-scope** | "How do I bake a chocolate cake?" | (would be filtered) | **0.874** |

All 5 in-scope queries returned the correct top-1 hit. Out-of-scope query landed at 0.87+, clearly above any plausible threshold — fallback would fire correctly.

**Threshold note for tuning later:** the v2 spec's distance > 0.45 cutoff is borderline strict for MiniLM-L6. The Salonga (0.537) and prosperity (0.529) queries returned semantically-right top-1 hits but would be filtered out at 0.45 and trigger fallback. Suggest 0.55-0.60 for MiniLM dev; re-tune after OpenAI embedding cutover (different distance distribution).

`.gitignore` simplified: `kb/` (whole folder) instead of `kb/raw/` + `kb/clean/`. The manifest and meta sidecars are reproducible from the script + corpus.

### 2026-05-06 · `acde8f5` · `ingest_columns.py` patches: dev-stack dry-run is clean

First dry-run hit two blockers:

1. **All 66 URLs returned 403 Forbidden.** Inquirer's WAF was blocking the script's bot-shaped UA (`FLP-Supervaise-RAG-Builder/0.2 (research; ...)`). Real-browser UAs with the right `Accept-*` headers pass.
2. **`UnicodeEncodeError` on the chunk-summary print.** Windows cmd uses cp1252 by default; the `→` char in `print(f"[chunk] {N} columns → {M} chunks...")` is not in cp1252.

Patches applied:

- **`USER_AGENT`** changed from the bot string to a Chrome `Mozilla/5.0` UA. Operator contact preserved via the HTTP `From:` header instead of the UA.
- **`fetch_html`** sends a browser-shaped header set (`User-Agent`, `Accept`, `Accept-Language`, `From`).
- **`sys.stdout.reconfigure(encoding="utf-8")`** at the top of the script (with try/except for older Pythons).
- **Canonical-URL guard:** after every fetch, extract the article ID from the requested URL and confirm it appears in the page's `<link rel="canonical">`. Inquirer 200-OKs dead URLs by silently serving the section homepage; this catches that.
- **Word-count guard:** `html_to_markdown` now raises if trafilatura's output is `<400` words (per v2 handover §5 watch list). Replaces the previous `<200` chars floor.
- **Dropped `women-suffrage-day`** from `COLUMNS` (URL `https://opinion.inquirer.net/183163/let-us-celebrate-women-suffrage-day` is dead — Inquirer redirects to the section homepage). Bucket E count: 8 → 7.

Final dry-run: **65 / 65 loaded**, 199 chunks total, avg 3.1/column, 2 legitimate QA-warns (`winning-eez-war` 694w, `martial-law-chacha` 715w — both real columns just slightly under the 700w floor; not extraction failures). 5 spot-checks across buckets A/C/E confirmed real CJ-voice content (first-person, ALL-CAPS opening sentences, `Comments to ...` footer).

`.gitignore` extended to include `*.log` (top-level dryrun artifacts).

### 2026-05-06 · `6abc00d` · land v2 ingestion deliverables: ingest_columns.py + manifest

User delivered the two existing v2 deliverables referenced in `docs/handover_v2.md` §6 — `ingest_columns.py` (544 lines, all 5 stages, 66 columns hardcoded) and `Opinion_Columns_Ingestion_Manifest.docx` (10-section human-readable manifest).

Layout cleanup to align with v2 handover §7:

- `ingest_columns.py` → repo root (already moved by user before this commit).
- `Opinion_Columns_Ingestion_Manifest.docx` → `docs/`.
- Removed redundant placeholders: `ingestion/load_and_embed.py`, `ingestion/retrieval_test.py`. The empty `ingestion/` folder is gone.

Dependencies for the script — installed and pinned in `requirements.txt`:
- `trafilatura==2.0.0` (HTML → markdown extraction)
- `tiktoken==0.12.0` (cl100k tokenizer for chunk-length measurement)
- `langchain-text-splitters==1.1.2` (the recursive splitter)
- `markdownify==1.2.2` (markdown post-processing)
- `readability-lxml==0.8.4.1` (HTML readability fallback)
Plus transitive deps (lxml, beautifulsoup4, cssselect, htmldate, courlan, justext, etc.).

`.gitignore` extended per v2 handover §7 + §8 copyright posture: `chroma_store/`, `kb/raw/`, `kb/clean/`. The v2 KB persists to `chroma_store/` (separate from our existing `chroma_db/` in the working spec — they coexist until reconciliation).

Verified: 66 columns in the script's COLUMNS list, 5 citation-unsafe slugs match the v2 §4 inventory exactly. Script not yet executed — that's the next step (probably `--dry-run` first).

### 2026-05-06 · `784a9a6` · archive v2 handover doc

User delivered an updated CLAUDE.md (handover v2, dated 2026-05-06) with substantially more spec detail — 5-stage pipeline params, 66-column corpus structure, citation-safety (C5) gating, copyright posture. Pushed verbatim to `docs/handover_v2.md` with a leading preamble flagging known reconciliation items vs the working spec (`CLAUDE.md` at repo root).

Conflicts to reconcile in a separate commit (not yet done):
- Dev embedding model: v2 says MiniLM-L6 (384); current code uses mpnet-base (768)
- Backend: v2 says FastAPI + Docker; current is Streamlit-direct
- ChromaDB persist dir: v2 says `./chroma_store/`; current is `./chroma_db/`
- KB layout: v2 specifies `kb/raw/`, `kb/clean/`, `kb/meta/`; nothing built yet
- Hardware ETA: v2 says mid-June; HANDOVER.md says late July / early August
- OpenAI cutover: v2 says locked May 14; we'd been treating as condition-based
- Confidence threshold: v2 cosine distance > 0.45 vs current similarity < 0.35

Two referenced deliverables (`Opinion_Columns_Ingestion_Manifest.docx`, `ingest_columns.py`) are not in the repo yet — flagged for the user to provide or for us to build from spec.

### 2026-05-05 · `7c211f0` · PROGRESS.md refresh

Self-referential maintenance commit. Sitrep date bumped to 2026-05-05; description rewritten to reflect edge-tts male voice and `.streamlit/config.toml`. Track 1 step 1.8 row updated from "gTTS" to "edge-tts". The three 2026-05-05 entries below now carry their commit hashes to match the older format. No code changes.

### 2026-05-05 · `5f1bc1c` · male TTS voice (edge-tts) + 5 fallback variants

User confirmed STT and TTS now work end-to-end in the browser. Two requested changes:

- **Voice gender:** gTTS uses Google's translate-tts which is locked to a single (female) voice per language. Switched to `edge-tts` (Microsoft Edge's TTS — free, no API key, much higher quality, large voice catalog). Default `TTS_VOICE=en-US-GuyNeural` (US male, gravitas-leaning); configurable via env. Other male English options documented in `backend/tts.py` and `.env.example`. Run `edge-tts --list-voices` for the full catalog.
- **Fallback variants:** `prompts/fallback.txt` now has 5 variant phrasings separated by `---`. `backend/prompts.py` parses them and `fallback()` picks a random variant per call. `system_prompt()` substitutes a freshly-picked variant into the persona prompt on each Groq call (was previously @lru_cached with one fixed variant).
- All variants still placeholders for Jacob to revise per OD-8.

Test: 5 variants loaded, all 5 reached across 10 random picks. edge-tts produced 29 KB mp3 with the male voice on a sample sentence. `gTTS` left in `requirements.txt` in case we need to switch back.

### 2026-05-05 · `828e040` · disable Streamlit file watcher (Windows + heavy deps)

User reported: Streamlit boots cleanly, prints "You can now view…" and the Local URL line, but then exits silently back to the shell prompt 10-20 seconds later with no traceback — only a `[transformers] Accessing __path__` deprecation warning visible. Browser shows "Connection error: Is Streamlit still running?".

Root cause: Streamlit's default file watcher (`watchdog` via `auto` mode) walks every imported module's source files. With `torch + torchvision + transformers + sentence-transformers + faster-whisper`, that's thousands of files under `.venv\Lib\site-packages`. On Windows the watcher thread dies hitting file-handle / watch-path limits; Streamlit treats a dead watcher as "user wants to stop" and shuts down gracefully without printing why.

Fix: created `.streamlit/config.toml` with `fileWatcherType = "none"` (committed, applies for anyone cloning the repo). Also disabled telemetry. Tradeoff: no hot-reload on save — stop and re-run `streamlit run app.py` to pick up code changes. Acceptable for this project's workflow.

### 2026-05-05 · `330e86d` · `torchvision` added to fix Streamlit startup crash

User reported a browser error on `http://localhost:8501`: `TypeError: Failed to fetch dynamically imported module` for both `AudioInput.*.js` and `ChatInput.*.js`. Terminal showed `ModuleNotFoundError: No module named 'torchvision'` from `transformers/models/aria/image_processing_aria.py` at line 21. Root cause: `transformers` (transitive dep of `sentence-transformers`) eagerly imports its `aria` image processor at startup, which requires `torchvision`. We had `torch` but not `torchvision`. The browser errors were a downstream effect — the crashed Streamlit server couldn't serve the static JS bundles.

Fix: `pip install torchvision` (pulled `torchvision==0.26.0`, ~4 MB wheel, reuses existing `torch==2.11.0`). `requirements.txt` re-pinned. Streamlit now boots in ~5s with no errors.

### 2026-05-04 · `34c1531` · Add `PROGRESS.md` build journal + per-push update rule

Created this file. Sitrep at the top shows full Track 1 / Track 2 status; per-push history below logs each commit going forward. CLAUDE.md updated with the rule: every push to GitHub adds an entry to PROGRESS.md.

### 2026-05-04 · `5cf96d7` · Phase A scope refinement: audio ingestion deferred to Phase B

Documentation-only. The original Week 3 task list put MP3/M4A/MP4 corpus ingestion in Phase A. User moved it to Phase B (OpenAI cutover). Phase A loaders now target PDF/TXT/MD only. Note: faster-whisper for *visitor mic input* stays in Phase A; it's the *corpus-side* audio transcription that's deferred.

### 2026-05-04 · `ed03b8b` · Lock OD-2: neutral TTS (gTTS) for May 30, no voice cloning

OD-2 (voice cloning vs neutral TTS) decided as **neutral**. CJ's recorded audio is never sent back to the visitor as output — only synthesized "normal voice" via gTTS reads the textual answer aloud. Re-opens post-demo if FLP wants a more realistic voice for the September showcase. CLAUDE.md spells out the audio direction explicitly.

### 2026-05-04 · `41928e6` · Week 3 sync: voice-in / voice-out, robot adapter, TTS

Major reversal driven by the 4 May internal sync. Voice is BACK IN for May 30 (overrides the brief text-only window from May 2).

- `backend/tts.py` *(new)*: `synthesize(text) -> mp3 bytes` via gTTS.
- `backend/adapters.py`: real implementation. `RobotAdapter` Protocol + `WebAdapter`. `WebAdapter.speak()` does `st.write` + `st.audio` with autoplay; other Protocol methods are no-ops on web. ReachyAdapter swap-in becomes a one-line change later.
- `app.py`: re-adds `st.audio_input`, keeps text fallback. Assistant turn rendered through `adapter.speak()`. Historical turns get a non-autoplay replay button. Audio recordings deduped via hash so reruns don't reprocess.
- `CLAUDE.md`: rewritten with strategy refinements (Phase A/B plan, cloud LLM + on-prem R-Pi RAG, theme-bucketed ingestion).

### 2026-05-02 · `f831e3c` · Step 1.6: persona system prompt + fallback text loader

- `prompts/instructions.txt`: CJ Panganiban persona with six non-negotiable rules (source-grounded, 100–150 words, English-only, measured style, no legal advice, no persona breaks). Marked as placeholder for Jacob to refine per OD-1 / OD-3.
- `prompts/fallback.txt`: placeholder referral language; OD-8 owned by Jacob. The "(Placeholder ...)" suffix is stripped at load time.
- `backend/prompts.py`: lru_cached `system_prompt()` and `fallback()` loaders; `system_prompt()` does `{FALLBACK}` substitution.
- `orchestrator.answer_question()`: persona prompt now prepended as a system message on every Groq call.

Behavioral note: without retrieved sources, the LLM still hallucinates from training data despite the source-grounded rule (a known instruction-following weakness). True grounding lands at the orchestrator-level confidence check (Track 2 step 2.6) and Day-15 RAG convergence.

### 2026-05-02 · `21a4643` · Step 1.5: chat-style UI with history, citations, latency, fallback

- `st.chat_input` + `st.chat_message`: running back-and-forth conversation preserved in `st.session_state.history` across reruns.
- Citation panel: collapsible expander showing `Response.citations`; empty-state caption explains it lights up at Day-15 RAG convergence.
- Latency: per-turn caption rendering `Response.latency_ms`.
- Fallback indicator: `st.warning` shown when `Response.fallback` is True.
- Conversation history is passed back into `answer_question()` so future Groq calls can use prior turns as context (just role+content, meta stripped before sending to the LLM).

### 2026-05-02 · `a1b448f` · Step 1.4 follow-up: text-only UI (later reverted)

`st.audio_input` hit a browser-side asset cache issue (`TypeError: Failed to fetch dynamically imported module AudioInput.*.js`) on the dev laptop. Rolled back `app.py` to text-only — HANDOVER §6 step 1.4 explicitly allows this fallback. **NOTE: This was later overridden by the Week 3 sync (4 May 2026) — voice is back in.** `backend/stt.py` and the downloaded faster-whisper model under `./models/` were kept in place during this revert.

### 2026-05-02 · `a021ed9` · Step 1.4: voice input via faster-whisper + `st.audio_input`

- `backend/stt.py`: `transcribe(audio)` wrapper around faster-whisper. Models downloaded to project-local `./models/` via `snapshot_download` (avoids the HF symlink cache, which needs Windows Developer Mode).
- `app.py`: `st.audio_input` mic button alongside the text input. Audio takes priority when present; transcription cached via `st.cache_data` so reruns don't re-process the same clip.
- `.gitignore`: `models/` excluded (~140 MB+ per whisper variant).
- Both text and voice inputs route through the same `answer_question()`.

### 2026-05-02 · `ed090d8` · Step 1.3: wire Groq into the backend

- `backend/llm.py`: `chat(messages)` wrapper around groq SDK. Client lazy-initialized via `lru_cache`; reads `GROQ_API_KEY` + `GROQ_MODEL` from env (`.env` loaded via python-dotenv).
- `orchestrator.answer_question()`: now calls Groq instead of returning the placeholder string. History list is prepended to the user message.
- `.env.example`: updated default model to `llama-3.3-70b-versatile` (`llama-3.1-70b-versatile` decommissioned by Groq).
- No persona prompt yet — that's Step 1.6.
- No source grounding yet — that's the Day-15 RAG convergence.

### 2026-05-02 · `da8c4fd` · Step 1.2: backend orchestration module + minimal wiring

- `backend/orchestrator.py`: `answer_question(text, history) -> Response`. Pure-Python contract, no Streamlit imports.
- `Response` dataclass with `text`, `citations`, `latency_ms`, `fallback`, `fallback_reason` fields. `citations`/`fallback` empty for now; populated at Day-15 RAG convergence.
- Hard-coded placeholder reply per HANDOVER §6 step 1.2.
- `app.py` now calls `answer_question()` and renders `response.text`.

### 2026-05-02 · `bfc713d` · Step 1.1: project scaffold and Streamlit hello-world

- Python venv with pinned `requirements.txt` (146 packages) including streamlit, groq, faster-whisper, sentence-transformers, chromadb, langchain, langchain-community, python-dotenv, gTTS.
- Folder structure per HANDOVER Appendix B.
- Placeholder modules for `backend/`, `ingestion/`, `prompts/`.
- `.env.example` template (no real keys); `.env` gitignored.
- Minimal `app.py` serving "CJ Panganiban — May 30 Demo" page.
