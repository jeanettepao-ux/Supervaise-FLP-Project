# PROGRESS — CJ Panganiban Conversational AI

A running log of what was built, when, and why. **Updated on every push to GitHub.**

How to read this file:
- **Reverse chronological** — newest first.
- Each entry: date · commit hash · what was built · gotchas.
- The Sitrep at the top is a snapshot of current state; entries below it are the per-push history.

---

## Sitrep — 2026-05-04

### What's working end-to-end right now

A visitor opens `http://localhost:8501`, sees the "CJ Panganiban — May 30 Demo" Streamlit chat page, can either click the mic to record a question or type one in the text fallback. Their voice gets transcribed locally by faster-whisper, the question is sent through the backend orchestrator (which prepends the CJ persona system prompt) to Groq's `llama-3.3-70b-versatile` model, the answer comes back, gets read aloud by gTTS, and renders in the chat with placeholders for citations, latency, and a fallback warning indicator. Conversation history persists across reruns.

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
| 1.8 TTS via gTTS (free cloud) | done | `backend/tts.py` |
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

### 2026-05-05 · Feature · male TTS voice (edge-tts) + 5 fallback variants

User confirmed STT and TTS now work end-to-end in the browser. Two requested changes:

- **Voice gender:** gTTS uses Google's translate-tts which is locked to a single (female) voice per language. Switched to `edge-tts` (Microsoft Edge's TTS — free, no API key, much higher quality, large voice catalog). Default `TTS_VOICE=en-US-GuyNeural` (US male, gravitas-leaning); configurable via env. Other male English options documented in `backend/tts.py` and `.env.example`. Run `edge-tts --list-voices` for the full catalog.
- **Fallback variants:** `prompts/fallback.txt` now has 5 variant phrasings separated by `---`. `backend/prompts.py` parses them and `fallback()` picks a random variant per call. `system_prompt()` substitutes a freshly-picked variant into the persona prompt on each Groq call (was previously @lru_cached with one fixed variant).
- All variants still placeholders for Jacob to revise per OD-8.

Test: 5 variants loaded, all 5 reached across 10 random picks. edge-tts produced 29 KB mp3 with the male voice on a sample sentence. `gTTS` left in `requirements.txt` in case we need to switch back.

### 2026-05-05 · Bugfix · disable Streamlit file watcher (Windows + heavy deps)

User reported: Streamlit boots cleanly, prints "You can now view…" and the Local URL line, but then exits silently back to the shell prompt 10-20 seconds later with no traceback — only a `[transformers] Accessing __path__` deprecation warning visible. Browser shows "Connection error: Is Streamlit still running?".

Root cause: Streamlit's default file watcher (`watchdog` via `auto` mode) walks every imported module's source files. With `torch + torchvision + transformers + sentence-transformers + faster-whisper`, that's thousands of files under `.venv\Lib\site-packages`. On Windows the watcher thread dies hitting file-handle / watch-path limits; Streamlit treats a dead watcher as "user wants to stop" and shuts down gracefully without printing why.

Fix: created `.streamlit/config.toml` with `fileWatcherType = "none"` (committed, applies for anyone cloning the repo). Also disabled telemetry. Tradeoff: no hot-reload on save — stop and re-run `streamlit run app.py` to pick up code changes. Acceptable for this project's workflow.

### 2026-05-05 · Bugfix · `torchvision` added to fix Streamlit startup crash

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
