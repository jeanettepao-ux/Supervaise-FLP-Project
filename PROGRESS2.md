# PROGRESS2 — Day-of work log · 2026-05-08

A focused snapshot of today's changes and strategy decisions, separated from the main `PROGRESS.md` which holds the per-push history since the project started. Use this for stand-ups, end-of-day reviews, or sharing with the team.

## TL;DR

Heavy day. Sixteen commits. Major themes: **a complete TTS overhaul** (edge-tts retired in favor of local Piper neural TTS), **a new catalog-mode flow** for visitors who want to browse columns instead of asking topical questions, **the first half of Step 1.9** (trigger-word visitor handoff), several **RAG quality fixes** (markdown stripping, complete-sentence truncation), an **STT accuracy push** (vocab biasing + post-correction), and **two DX wins** (warm-up splash + restart.bat + hot-reload back). All pushed to `main`.

## Quick stats

| | |
|---|---|
| Commits | **16** (all on `main`) |
| Range | `7dc84c9` → `13fbef6` |
| Files touched | `app.py`, `backend/tts.py`, `backend/orchestrator.py`, `backend/catalog.py` (new), `backend/stt.py`, `prompts/instructions.txt`, `ingest_columns.py`, `.streamlit/config.toml`, `.env.example`, `restart.bat` (new) |
| New deps | `piper-tts==1.4.2` |
| Effectively retired | `edge-tts==7.2.8` (left pinned as fallback) |
| New env vars | `TTS_VOICE_PIPER`, `TTS_SENTENCE_PAUSE`, `TTS_CLAUSE_PAUSE`, `TTS_LONG_SENTENCE_WORDS`, `STT_DOMAIN_CORRECT` |
| Tests added | 70+ inline assertions across STT correction, catalog detection, sentence splitter, markdown stripper |

---

## Theme 1 — TTS overhaul (the biggest thread)

**Problem:** edge-tts (Microsoft's cloud TTS) was failing intermittently with `TimeoutError: edge-tts failed after 3 attempts`, costing 45 seconds of dead time before the friendly text-only fallback kicked in. Visitors saw "(TTS unavailable: ...)" captions on a meaningful fraction of turns.

**Decision path:**

1. **Hardened edge-tts first** (`7dc84c9`, `01fab77`)
   - Retry/timeout config: 2 retries × 15s → 1 retry × 8s. Worst case fall-through dropped from 45s to 16s.
   - Atomic per-turn commit in `app.py`: user message + assistant turn are appended to history only after the assistant turn fully succeeds. A mid-turn failure no longer leaves orphan user-only messages.
   - Cached failures return `b""` instead of raising, so Streamlit's `cache_data` doesn't get poisoned.

2. **Decided edge-tts isn't fixable** — Microsoft's endpoint is the issue, not our code. Switched providers.

3. **Swapped to Piper TTS** (`6eb5f4c`)
   - Local neural TTS. ONNX Runtime + small voice models from `rhasspy/piper-voices`.
   - No internet round-trip at synthesis time. No rate limits. No flakiness.
   - Voice models cached project-local in `./models/piper/` (gitignored).
   - First synthesis ~2.5s after warm-up, consistent.
   - Output format changed: MP3 → WAV (`audio/wav`). Updated `WebAdapter` and `_synthesize_cached`.
   - Pre-warmed inside `_load_backend()` so the first user question doesn't pay model-load latency.

4. **Voice exploration** — three swaps before landing somewhere acceptable
   - `en_US-ryan-high` (initial default) — sounded flat
   - `en_US-lessac-high` (`77d60b5`) — turned out **female** despite Arthur Lessac being a male voice coach. The dataset is recorded by a female reader. Ouch.
   - `en_US-bryce-medium` (`8ec2c4c`) — verified male, conversational
   - User iterated through `en_GB-alan-medium`, `en_US-ryan-medium` for personal testing
   - `.env.example` now has a "VERIFIED MALE" voice list with a warning note about lessac/amy being female

5. **Sentence pauses** (`f218936`)
   - Piper 1.4 dropped the built-in `sentence_silence` config field, so we add pauses ourselves.
   - Sentence splitter regex requires 2+ lowercase letters before `.`/`?`/`!` (avoids splitting on `v.` / `Mr.` / `Dr.` / `Sr.`).
   - 0.4s silence inserted between sentences. Configurable via `TTS_SENTENCE_PAUSE`.

6. **Clause-level pauses for long sentences** (`13fbef6`)
   - 24-word sentence with 3 commas was being read as one breathless wall.
   - For sentences > `TTS_LONG_SENTENCE_WORDS` (default 14), split on commas/semicolons too.
   - Insert 0.18s clause pause at each break (configurable via `TTS_CLAUSE_PAUSE`).
   - Sounds like a real person taking breaths.

**Today's TTS final state:**
```
Provider:        Piper (local, neural)
Voice:           en_US-bryce-medium (project default; user can override via env)
Sentence pause:  0.4s
Clause pause:    0.18s (for sentences >14 words)
Output format:   WAV
First synthesis: ~2.5s warm
```

---

## Theme 2 — Catalog mode (new code path)

**Problem:** Visitor asked "Please provide five sample columns of CJ Panganiban" and got the FLP-referral fallback. Retrieval correctly found nothing relevant — chunks are CJ's prose ABOUT topics, not catalog entries listing columns. RAG's topical Q&A is the wrong shape for browse-style queries.

**Solution** (`00157d7`, `ac588e6`, `aa86c30`):

New `backend/catalog.py` module with three layers:

1. **`is_catalog_query(text)`** — regex detection for browse-style queries
   - Started with imperative verbs ("list / show / give / provide")
   - User reported `"Tell me about your columns"` slipping through — added five more pattern families:
     - `tell me about (your|the) <plural noun>`
     - `talk about (your|the) <plural>`
     - `what are (your|some|the) [sample] <plural>`
     - `(describe|any of [your]) <plural>`
     - `your <plural>` as noun phrase NOT followed by topic anchor
   - Tightened `"what did you write about <X>"` with a negative lookahead so "what did you write about Estrada" stays topical (no false catalog routing).

2. **`extract_year(text)`** — pulls a 4-digit year from free text

3. **`list_columns_by_year(year, n=5)`** — queries ChromaDB metadata directly (not vector search), dedupes by source URL, returns sorted by date descending. Each result has title, date, URL, bucket, and a cleaned text preview.

**Two-turn flow in `app.py`:**

```
[turn 1]
Visitor: "tell me about your columns"
App:     "I would be glad to share. For which year?
          My published columns span roughly from 2011 through 2026."

[turn 2]
Visitor: "2023"
App:     "From 2023, here are some of my columns:
          1. 'President Marcos' ICC options' (2023-12-11)
             The recent hearings in the House of Representatives...
          2. 'Supercalifragilisticexpialidocious' (2023-10-30)
             ...
          ..."
```

If the visitor specifies the year inline ("give me 5 columns from 2023") → single-turn answer, no clarification step. If the next message after the clarification doesn't contain a year → pending state cancelled, message processed as a normal query.

**Preview formatting fix** (`aa86c30`):
- Column body markdown sometimes has `# Title` as the first line, which Streamlit was rendering as a giant H1. New `_clean_preview()` strips leading heading lines + bold/italic markers + collapses whitespace.

**Complete-sentence truncation** (`13fbef6`):
- Replaced `preview[:200] + "..."` with `_first_sentences(preview, max_chars=280)` — takes whole leading sentences, never cuts mid-word.

---

## Theme 3 — Step 1.9 part 1 · trigger-word interrupt (`b9bd1a5`)

**Problem:** Donor #1 finishes asking questions and walks away silently. Donor #2 walks up. App still has Donor #1's conversation history → contaminated context for Donor #2.

**Solution:**
- Configured trigger phrases via `TRIGGER_WORDS` env: *that's enough, okay thank you, thank you, next question*
- New `_is_trigger_word(text)` does **exact match after normalization** (lowercase + trailing-punctuation strip). Triggers on `"Thank you."`, `"THANK YOU"`, `"Thank you!"`. Does NOT trigger on `"Thank you, can you tell me about FLP"` — visitor being polite while continuing.
- On match: speak `FAREWELL_TEXT` via `adapter.speak()`, clear `st.session_state.history`, reset `last_audio_key`, show "Conversation cleared — ready for the next visitor" success banner, `st.stop()`.
- Verified on 15/15 inline cases.

**Open:** Part 2 (5-min idle auto-clear, HANDOVER §3 rule #9) still pending. Visitors who walk away silently are not yet handled.

---

## Theme 4 — RAG quality fixes

**Markdown stripping** (`aa86c30`, `01fab77`)
- LLM responses sometimes contained markdown headings (`# Title`) that Streamlit renders as H1, breaking the visual flow.
- Two-layer strip:
  1. Strip leading `# Title` lines from chunks **before** they go to the LLM (so the LLM doesn't see/copy the column title twice).
  2. Strip any heading prefixes from the LLM's response **after** it returns (defense in depth).
- Plus: persona prompt now explicitly instructs the LLM to use plain prose, no markdown headings.

**Complete-sentence truncation everywhere** (`13fbef6`)
- `_trim_to_word_limit` in `orchestrator.py` no longer cuts at the 150-word boundary with "..." — walks back to the last `.` / `?` / `!`. Answers always end on a sentence.
- Same logic for catalog previews (`_first_sentences`).
- Both use the same conservative regex that doesn't false-split on `v.` / `Mr.` / `Dr.` / `Sr.`.

---

## Theme 5 — STT accuracy push (`bed579d`, `868801e`)

User reported transcriptions like *"Ascentinary"* for "A Centenary" and *"Panganibang"* for "Panganiban".

**Two-layer biasing strategy:**

1. **Layer (a) — expanded `initial_prompt`** in `backend/stt.py`
   - Was ~50 words, now ~150 words covering CJ's name + the book + Inquirer column + topics (rule of law, WPS, ICC) + 8 case names + 6 chapter titles.
   - Stronger phonetic bias toward our domain terms during decoding.

2. **Layer (b) — post-transcription correction**
   - **(b1) Explicit known-misheard dictionary** — 25+ regex rules for observed mishearings (Ascentinary, Panganibang, Centinery, Estraja, Comelek, Desyerto) plus acronym normalization (`flp` → `FLP`, etc.).
   - **(b2) Fuzzy fallback** via `difflib.get_close_matches` against a 24-term domain vocabulary, applied only to capitalized tokens of length ≥5 with cutoff 0.85. Catches new mishearings (e.g., `"Estrana"` → `"Estrada"`) without false-positives on common English.
   - Toggleable via `STT_DOMAIN_CORRECT=false`.
   - 15/15 inline test cases pass.

Plus the `WHISPER_MODEL` bump from `base` → `small` from yesterday — first transcription downloads the 470 MB model, subsequent transcriptions are ~3-5s with much better accuracy.

---

## Theme 6 — DX / cold-start UX

**"Warming up the knowledge base…" splash** (`73b03e3`)
- Heavy backend imports (chromadb, torch, transformers, faster-whisper, piper-tts) and model loads were happening synchronously at script-load time, leaving the user staring at a blank black page for 10-15 seconds.
- Fix: title and caption render first, then `_load_backend()` (decorated with `@st.cache_resource(show_spinner=...)`) does the imports + model warm-up while showing a labelled spinner.
- Pre-warms the embedder + ChromaDB + Piper voice → first user question feels fast (1-3s).

**`restart.bat`** (`747cec8`)
- One double-click kills any process holding port 8501 and starts Streamlit fresh.
- Uses `netstat -ano | findstr ":8501"` + `taskkill /F /PID` — won't touch unrelated `python.exe` processes.

**Hot-reload back** (`747cec8`)
- `.streamlit/config.toml` switched from `fileWatcherType = "none"` → `"poll"`.
- Polling sidesteps the watchdog crash that was happening with our heavy dep tree on Windows.
- Code edit + save → app auto-reloads in ~2s. No manual restart needed for most changes.
- `restart.bat` remains the fallback for warmup-state flushes (env changes, voice changes, ChromaDB swaps).

---

## Commits — chronological

| # | Hash | Theme | Title |
|---|---|---|---|
| 1 | `7dc84c9` | TTS | Harden edge-tts against transient failures + atomic per-turn commit |
| 2 | `586092c` | docs | PROGRESS.md log entry |
| 3 | `bed579d` | STT/RAG | STT priming + chapter-aware chunk headers + loosened persona Rule 1 |
| 4 | `868801e` | STT | Expanded primer + domain post-correction (vocab biasing) |
| 5 | `73b03e3` | DX | "Warming up the knowledge base..." splash on cold start |
| 6 | `b9bd1a5` | Step 1.9 | Trigger-word interrupt for visitor handoff |
| 7 | `00157d7` | Catalog | Catalog mode v1 — "list columns from year X" with clarification turn |
| 8 | `ac588e6` | Catalog | Expanded patterns to catch "tell me about your columns" |
| 9 | `aa86c30` | UX | Strip markdown from previews (no more giant H1) |
| 10 | `01fab77` | RAG/TTS | Strip markdown from RAG responses + tighter TTS retry config |
| 11 | `6eb5f4c` | TTS | **Swap edge-tts → Piper** (local neural) |
| 12 | `77d60b5` | TTS | Voice ryan-high → lessac-high *(reverted next commit — was female)* |
| 13 | `8ec2c4c` | TTS | Fix: lessac-high (female!) → bryce-medium (verified male) |
| 14 | `747cec8` | DX | restart.bat + switch file watcher 'none' → 'poll' |
| 15 | `f218936` | TTS | 0.4s pauses between sentences |
| 16 | `13fbef6` | UX | Complete-sentence truncation + clause-level TTS pauses |

---

## What's still open (next-day worklist)

| Item | Where | Effort |
|---|---|---|
| Step 1.9 part 2 — 5-min idle auto-clear | `app.py` session-state timestamp + check on rerun | ~30 min |
| Step 1.10 — structured JSON logging to `logs/turns.jsonl` | new `backend/logger.py` | ~45 min |
| Oversized-chapter strategy for "A Centenary of Justice" | sub-section splitting or back-matter trimming | ~1 hr |
| Bring user's preferred Piper voice into project default | After they pick one for keeps | 5 min |
| Re-run the smoke test question bank end-to-end with all today's fixes in place | Manual QA | ~20 min |

---

## Strategy decisions made today (worth flagging at next sync)

1. **Local TTS over cloud TTS** — Piper instead of edge-tts. Eliminates a flaky external dependency. Same architectural pattern we use for faster-whisper. Same approach will apply post-demo when we move to the R-Pi.

2. **Catalog mode is its own code path, not a RAG variant** — Browse queries query metadata, not vectors. Tried to make the LLM handle this through prompt engineering first; it didn't work, because RAG chunks contain *content about topics*, not *records of writings*. Two different data shapes need two different code paths.

3. **TTS pauses are content-aware, not time-based** — Pause length depends on sentence boundary (long pause) vs clause boundary (short pause), and clause-level only kicks in for sentences over 14 words. Sounds like real prosody, not a metronome.

4. **Sentence-aware truncation everywhere** — Both LLM responses and catalog previews now end on `.` / `?` / `!` instead of `...`. Visitors should never see a half-sentence.

5. **Defense in depth for STT accuracy** — Phonetic biasing during decoding (initial_prompt) plus surface-level correction after (KNOWN_MISHEARDS + fuzzy fallback). Either layer alone catches some mistakes; together they catch most.

6. **Hot-reload back via polling, not watchdog** — Polling watcher avoids the Windows file-handle crash that watchdog hit with our heavy dep tree. Two-second reload latency is acceptable for our dev loop.

---

*End of day-of log. For the cumulative per-push history, see `PROGRESS.md`. For the canonical pipeline reference, see `docs/pipeline.md`.*
