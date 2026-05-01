# CJ Panganiban Conversational AI Robot — Technical Handover for Development

**Version:** 3.0 (May 30 demo scope, simplified local stack)
**Date:** 2 May 2026
**Audience:** Developer starting work in Claude Code with no prior conversation context
**Read time:** 15 minutes — read all 10 sections before writing any code

> **What changed from v2.0:**
> 1. **Vector store: ChromaDB (embedded, local) for the May 30 demo** — not PostgreSQL + pgvector. PostgreSQL + pgvector becomes the post-demo production target.
> 2. **Frontend: Streamlit** as the primary May 30 demo surface — not Gradio. The Reachy Mini conversation app (Gradio-based) is now a Phase 3 integration target, not the May 30 starting point.
> 3. **Everything runs on the developer's laptop** for the demo — no Docker, no Railway, no cloud DB. Only Groq is remote (free tier).
> 4. **Two-track build plan** (parallel work, converges Day 15) replaces the linear Section 6 task list.

---

## 1. Project Overview

**Product.** A Reachy Mini robot ("Reachy Mini Wireless") that holds short, voice-based conversations about Chief Justice Artemio V. Panganiban — his life, his writing, his foundation, and his commentary on current events. The robot is positioned as a **donor-engagement instrument**: one-on-one interactions where prospective donors talk to "the Chief Justice" and get knowledge-grounded, in-character responses sourced strictly from his published writings.

**Client.** Foundation for Liberty and Prosperity (FLP). The single FLP point of contact for everything — content approvals, materials delivery, sign-offs — is **Jacob Barbosa**. Do not route requests to anyone else on the FLP side.

**Vendor.** Supervaise Inc. (Manila/PH).

**Goal of v1.** A working conversational robot demonstrated to donors at the **September 2026 showcase** (date locked). The robot should sound like CJ, answer only from his writings, refer FLP for unsupported questions, and never hallucinate.

**Hard deadlines (in order):**
1. **30 May 2026** — Pre-prototype demo with Chief Justice Panganiban. **Web app only, no robot.** Streamlit running on a laptop. Goal is directional feedback on persona, tone, content focus, and answer style.
2. **End of July / first week of August 2026** — Reachy Mini hardware integration begins (revised ETA; was previously mid-June — see Section 8 Flag A).
3. **September 2026** — Donor showcase. Hard, fixed.

**What "v1" is not.** Not legal education. Not Filipino/Tagalog output. Not a museum buildout. Not multiple stations. Not mobile apps. The first prototype is one robot, English-out, biography + current events focus.

---

## 2. Confirmed Tech Stack

The May 30 demo stack is deliberately minimal: everything runs on the developer's laptop, with Groq as the only remote dependency. Production-stack components (PostgreSQL + pgvector, Railway, Reachy Mini conversation app, OpenAI services) are listed under "Post-demo migration" — they are not in scope for the demo.

### 2.1 May 30 demo stack — runs entirely on the laptop

| Component | Where it runs | Cost / size | Purpose |
|---|---|---|---|
| **Groq LLM** | Cloud (Groq's servers) | Free tier — generous limits | Generates grounded answers from retrieved chunks |
| **faster-whisper STT** | Laptop (local) | Free; downloads ~140 MB model once | Transcribes spoken questions (mic input) |
| **sentence-transformers embeddings** | Laptop (local) | Free; downloads ~420 MB model once | Converts text to 768-dim vectors for retrieval |
| **ChromaDB vector store** | Laptop (embedded, in-process) | Free; no server | Stores chunks + embeddings, returns nearest neighbours |
| **Streamlit frontend** | Laptop (local) | Free | The May 30 demo's "face" — chat UI, citations, optional TTS |
| **(Optional) gTTS or browser SpeechSynthesis** | Laptop / browser | Free | Optional play-button TTS for the demo |

**Why this stack.** Three weeks to demo, no OpenAI budget, no robot. ChromaDB is embedded — a single `pip install`, no Docker, no separate DB process, no schema management. Streamlit is the fastest path to a presentable demo UI with citation rendering. faster-whisper and sentence-transformers ship as `pip install` packages and download models on first use. Groq's free tier covers many days of demo usage without cost.

### 2.2 Language & runtime
- **Python 3.10+** — every component above is Python.
- **Git + GitHub** — code lives in a private repo with folders: `backend/`, `embeddings/`, `ui/`, `docs/` (to be created during P1 wrap).
- **Docker is NOT required for May 30.** Reserved for the post-demo migration to PostgreSQL + pgvector and eventual Railway deployment.

### 2.3 LLM
- **Groq API.** Use `llama-3.1-70b-versatile` or `llama-3.3-70b-versatile` as the default model. OpenAI-compatible chat-completion format.
- *Why:* OpenAI keys are not budgeted during the dev phase. Groq is free and good enough for retrieval-grounded summarization (which is what we need — the LLM is paraphrasing CJ's words, not doing creative reasoning).
- *Library:* `groq` Python SDK.

### 2.4 STT (Speech-to-Text)
- **`faster-whisper`** — local, no API key, drop-in conceptually for OpenAI Whisper.
- *Default model:* `base` for dev speed; `small` for May 30 demo accuracy. Model files cache to `~/.cache/huggingface` after first download (~140 MB for `base`).
- *Install:* `pip install faster-whisper`.
- *Taglish handling:* Whisper handles Taglish out of the box — Filipino is in its multilingual training set. Mid-sentence code-switching is the only real risk. Optional hint: `language="tl"`, but auto-detect generally works. **Output of the system is always English** (see Section 3).

### 2.5 Embeddings
- **`sentence-transformers`** locally — free, no API key.
- *Default model:* `all-mpnet-base-v2` (768-dim) for May 30. Good balance of quality and size (~420 MB).
- *Install:* `pip install sentence-transformers`.
- The 768-dim choice is a deliberate dev-phase decision; expect re-embedding when migrating to OpenAI 1,536-dim later (see Section 8 Flag B).

### 2.6 Vector store — **ChromaDB** (changed in v3.0)
- **`chromadb`** — embedded vector store, runs in-process, persists to a local directory.
- *Install:* `pip install chromadb`.
- *Why ChromaDB and not pgvector for the demo:* embedded means no Docker, no separate DB process, no schema migrations. Single laptop, single process, single `Collection` object. Migration to PostgreSQL + pgvector happens after the demo (see Section 2.10).
- *Persistence:* point ChromaDB at a local directory (e.g., `./chroma_db`); the index survives restarts.

### 2.7 Frontend — **Streamlit** (changed in v3.0)
- **`streamlit`** — the May 30 demo's primary surface.
- *Install:* `pip install streamlit`.
- *Run:* `streamlit run app.py` → opens at `http://localhost:8501`.
- *What the UI shows:* chat history, current response, **on-screen citations** for every answer (source title, date, link if available), optional "Play" button for TTS, latency indicator, fallback indicator when retrieval is low-confidence, conversation-clear cue at the end of the 5-minute window.
- *Why Streamlit and not Gradio:* the v2.0 plan was to inherit Gradio from the Reachy Mini conversation app repo. For a no-robot, web-only demo, that buys us nothing — we'd be carrying robot-specific scaffolding for a Streamlit-equivalent UI. Build a clean Streamlit app for May 30; integrate with the Reachy Mini conversation app repo when the robot arrives.

### 2.8 Optional TTS for the demo
- **Primary experience on May 30 is text + on-screen citations.** TTS is a "play" button — secondary.
- *Easy options (pick one):* browser SpeechSynthesis (zero install, JS in Streamlit component), or `gTTS` (`pip install gTTS`, Google Translate TTS, returns mp3 bytes Streamlit can play directly).
- *Why not OpenAI TTS:* no OpenAI budget in May.
- *Voice cloning (ElevenLabs / Coqui XTTS):* still an open decision (Section 8 OD-2). Don't preempt it for May 30.

### 2.9 RAG orchestration
- **LangChain** for document loaders, chunking, and prompt assembly.
- *Why over hand-rolled:* three weeks. Don't build PDF loaders and chunking from scratch.
- *Use only what you need:* `langchain-community` document loaders (PDF, TXT, MD), `RecursiveCharacterTextSplitter` for chunking, plain Python for retrieval (call ChromaDB directly — no need for a LangChain retriever wrapper for this demo).
- *Caveat:* LangChain abstractions can hide bugs. Log retrieved chunks, scores, and final prompts at every step (see Section 3 logging requirements).

### 2.10 Post-demo migration path (NOT in May 30 scope)

These items become relevant after the demo, in priority order:

| Component | Replaces | Trigger |
|---|---|---|
| **PostgreSQL + pgvector** (Railway-hosted) | ChromaDB | When the system needs multi-machine access (robot calling cloud backend over LTE). Re-export embeddings from ChromaDB; recreate as pgvector rows. |
| **OpenAI GPT-4o** (chat completions) | Groq Llama | June 2026, before robot integration. Same prompt format, change base URL and model name. |
| **OpenAI text-embedding-3-small** (1,536-dim) | sentence-transformers (768-dim) | June 2026 migration. **Re-embedding the entire KB is a real 1–2 day task** — see Section 8 Flag B. |
| **OpenAI Whisper API** | faster-whisper | Optional. Local works fine; only swap if latency or accuracy demands it. |
| **OpenAI TTS** (or ElevenLabs / Coqui XTTS) | Browser SpeechSynthesis / gTTS | June 2026 — robot speaker needs a real voice. |
| **FastAPI backend on Railway** | Direct Python imports inside Streamlit | When the robot needs to call a remote orchestration service. |
| **Reachy Mini conversation app integration** | Standalone Streamlit | When the robot arrives (late July / early August). Port the working RAG pipeline into a custom `Tool` subclass in the Reachy app's profile system. |
| **Reachy Mini Python SDK + Reachy2 Simulator (MuJoCo) + Git LFS + Docker** | n/a (robot-specific) | Late July / early August. |

### 2.11 What is NOT in the stack — May 30 or later
- No live web search. No GPT browsing. Knowledge base is strictly embedded documents.
- No fine-tuning or training of any model.
- No mobile app. No native desktop app.
- No third-party RAG hosting (Pinecone, Weaviate). ChromaDB now, pgvector later.

### 2.12 Items still TBD
- **Voice provider** (cloning vs neutral) — see Section 8 OD-2.
- **Final cloud platform sign-off** for post-demo hosting — Railway is the working assumption; confirm with Jeanette before deploying.
- **LTE backup router model** for venue connectivity — owned by John, not blocking.

---

## 3. Confirmed Product Decisions

These decisions are signed off and should be coded against. Anything not in this list is either open (Section 8) or out of scope.

| # | Decision | Source / Date |
|---|---|---|
| 1 | **Project purpose** is donor engagement (biography + current events), **not** legal education Q&A. | FLP, kickoff 28 Apr 2026 |
| 2 | **Output language:** English only. **Input language:** English + Taglish. Filipino/Tagalog output is out of scope for v1. | FLP, 28 Apr 2026 |
| 3 | **Content priority:** Inquirer opinion columns are the primary backbone. Books and legal opinions are secondary depth material. | FLP, 28 Apr 2026 |
| 4 | **Knowledge base scope:** strictly defined by FLP-provided materials. No assumed quantity. The 5 theme buckets (A Liberty / B Prosperity / C Biographical / D FLP Mission / E Current Events) and the 7-criterion rubric are a **guideline for FLP's selection**, not a Supervaise-curated list. | Handover Revision #5, #6 |
| 5 | **Response length limit:** **100–150 words max per response,** enforced in the system prompt. | Confirmed pre-Phase-3 |
| 6 | **Conversational style:** concise, respectful, educational, family-friendly. One question at a time. | Confirmed pre-Phase-3 |
| 7 | **Trigger-word interrupt handling.** Listen for and act on: *"That's enough,"* *"Okay thank you,"* *"Thank you,"* *"Next question."* On any of these, stop the current TTS playback and reset to listening. | Confirmed pre-Phase-3 |
| 8 | **"Thinking" behavior** during pipeline latency: subtle indicator to prevent dead silence. On May 30 (web only), an animated indicator suffices. Robot-side head movement comes with hardware integration. | Confirmed pre-Phase-3 |
| 9 | **Conversation window timeout:** ~5 minutes of inactivity, then clear active conversation context for the next visitor. **Make this configurable.** When clearing, give an intuitive cue. | Confirmed pre-Phase-3 |
| 10 | **Strict source grounding.** Answers come only from retrieved chunks. No speculation. No legal interpretation beyond what CJ has said in the corpus. | FLP requirement |
| 11 | **Fallback / referral.** When the system cannot answer (low retrieval confidence, off-topic question, API timeout, content outside approved scope), it gives an approved referral line directing the visitor to FLP resources. **Never** improvise. | FLP requirement |
| 12 | **No live web search.** Embedded documents only. | FLP, 28 Apr 2026 |
| 13 | **Logging requirements.** Every turn must log: speech transcript (or typed input), retrieved sources (titles + IDs + similarity scores), final response, end-to-end latency, fallback reason if any. | Phase 3 spec |
| 14 | **May 30 demo format:** web app only, no robot. Text response with on-screen citation is **primary**. TTS is **optional** (a play button). | Handover Revision #7, #8 |
| 15 | **Robot adapter abstraction.** Even in the May 30 web app, orchestration code calls a `RobotAdapter` interface (web implementation only for now) so the same pipeline plugs into the Reachy Mini SDK later without rewiring. | Architecture decision |

**Wake-word / proactive-greeting behavior** is **not yet decided** — formal decision sits in Week 9. Until then, assume push-to-talk (or text input) in the Streamlit app.

---

## 4. Architecture Overview

### 4.1 May 30 demo architecture (single laptop)

```
┌──────────────────────────────────────────────────────────┐
│                    DEVELOPER'S LAPTOP                    │
│                                                          │
│   ┌─────────────────────────────────────────────────┐    │
│   │          Streamlit app (localhost:8501)         │    │
│   │  • Text input box (and/or mic button)           │    │
│   │  • Chat transcript                              │    │
│   │  • Response + citation list                     │    │
│   │  • Optional TTS play button                     │    │
│   │  • Latency / fallback indicators                │    │
│   └────────────────────┬────────────────────────────┘    │
│                        │ Python function calls           │
│                        │ (no HTTP layer in May 30 demo)  │
│                        ▼                                 │
│   ┌─────────────────────────────────────────────────┐    │
│   │       Orchestration module (Python)             │    │
│   │       — calls RobotAdapter (WebAdapter only)    │    │
│   └──┬───────────┬──────────┬──────────┬────────────┘    │
│      │           │          │          │                 │
│      ▼           ▼          ▼          ▼                 │
│  ┌────────┐ ┌─────────┐ ┌────────┐ ┌────────┐            │
│  │ faster-│ │sentence-│ │Chroma  │ │ gTTS / │            │
│  │whisper │ │trans-   │ │  DB    │ │browser │            │
│  │ (STT)  │ │formers  │ │(vector │ │ TTS    │            │
│  │        │ │(embed)  │ │ store) │ │(opt'l) │            │
│  └────────┘ └─────────┘ └────────┘ └────────┘            │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTPS (Groq's free tier)
                         ▼
                 ┌──────────────────┐
                 │   Groq Cloud     │
                 │  (Llama 3.1/3.3) │
                 └──────────────────┘
```

**Single process.** Streamlit imports the orchestration module directly. No FastAPI, no HTTP boundary, no separate backend service for the demo. This keeps the dev loop tight and removes whole categories of bugs (CORS, port management, async coordination) that don't pay off until the robot is in the picture.

### 4.2 Per-turn pipeline

```
1. Visitor input (text in Streamlit, or mic → faster-whisper → text)
2. Trigger-word check (if matches "thank you" etc., reset state, stop)
3. Embed the question (sentence-transformers)
4. ChromaDB similarity search → top-k chunks + scores (k=5 to start)
5. Confidence check
   • Top score < threshold (~0.35) → fallback referral path, skip LLM
6. Prompt assembly:
   - System prompt (persona, 150-word limit, source-only rule)
   - Retrieved chunks (with citation metadata)
   - Recent conversation turns (within 5-minute window)
   - Visitor question
7. Groq chat completion
8. Post-process: trim to 150 words, attach citation list
9. Log: input, retrieved sources + scores, response, latency, fallback flag
10. Render in Streamlit + offer optional TTS play
```

### 4.3 Robot adapter layer (still required for May 30)

Even in the web demo, the orchestration module talks to a `RobotAdapter` interface. May 30 only needs `WebAdapter`. `ReachyAdapter` arrives in Phase 3 with no rewrite of the pipeline.

```python
class RobotAdapter(Protocol):
    def listen(self) -> bytes | str: ...        # audio bytes or typed text
    def speak(self, text: str) -> None: ...     # TTS + playback
    def head_move(self, pose) -> None: ...      # no-op on Web
    def gaze_track(self, target) -> None: ...   # no-op on Web
    def thinking_motion(self) -> None: ...      # animated cue on Web
    def handle_interrupt(self, trigger: str) -> None: ...
```

`WebAdapter` implementations:
- `listen()` → reads from Streamlit input box or mic component.
- `speak(text)` → `st.write(text)` plus optional `gTTS` audio bytes via `st.audio`.
- `head_move`, `gaze_track` → no-op.
- `thinking_motion()` → spinner / "thinking..." indicator in Streamlit.
- `handle_interrupt(trigger)` → stop any current TTS playback, reset state.

### 4.4 Post-demo evolution (for context, not in May 30 scope)

Once the demo lands and feedback is in:
- Stand up FastAPI on Railway, move orchestration module behind HTTP.
- Migrate ChromaDB → PostgreSQL + pgvector (re-export embeddings, recreate rows).
- Migrate sentence-transformers → OpenAI text-embedding-3-small (re-embed everything at 1,536-dim).
- Migrate Groq → OpenAI GPT-4o.
- When robot arrives: integrate the working RAG pipeline as a custom `Tool` in the Reachy Mini conversation app. The robot's mic/speaker/head-movement use the existing Reachy app scaffolding; our RAG tool plugs in via the conversation app's tool framework.

---

## 5. What Already Exists

### 5.1 For the May 30 demo: nothing

The demo is a clean Streamlit + ChromaDB build. We are not inheriting an existing codebase for the demo path. This is a deliberate change from v2.0 of this handover — for a no-robot, web-only demo, building on top of the Reachy Mini conversation app gives us nothing useful and forces us to carry robot-specific scaffolding into a non-robot context.

What exists conceptually:
- The 7-criterion column selection rubric and 5 theme buckets (`Column_Selection_Criteria_May30_Demo.docx`) — a guideline for FLP's source selection.
- The system prompt direction (persona, English output, 150-word limit, source-grounded, refer-on-miss).
- The trigger words list and the 5-minute conversation-window rule.
- This handover and the AI App Development Basics primer.

### 5.2 For the post-demo path: the Reachy Mini conversation app repo

When the robot arrives, the Pollen Robotics Reachy Mini conversation app becomes the integration target. It provides:

| Component | Why it matters post-demo |
|---|---|
| Voice loop scaffolding (mic → STT → LLM → TTS → speaker) | The robot-side voice loop is non-trivial; this gives it for free. |
| Profile/persona system via `instructions.txt`, `tools.txt`, `voice.txt` | Drop a `cj_panganiban` profile folder and ship. |
| External profile support (`external_content/external_profiles/`) | Where our profile lives. |
| Locked profile mode (`LOCKED_PROFILE` config) | Prevents visitors from switching personas. |
| Gradio web UI with live transcripts | Useful as an internal monitor at venue. |
| Built-in tools: head pose, gaze tracking, dance, emotion clips, camera capture | Robot motion behaviors we need. |
| Custom tool support — subclass `Tool`, drop in profile folder | This is how we'll port our RAG pipeline in. |
| Optional vision pipeline (PyTorch, YOLO, MediaPipe) | Future gaze-tracking work. |

What needs to change in that repo at integration time:
- **Swap** its default OpenAI GPT Realtime API call to OpenAI standard chat completions (or Groq, depending on where we are at the time). The Realtime API is not what we need.
- **Swap** its STT to `faster-whisper` (or OpenAI Whisper API once budget allows).
- **Add** our RAG pipeline as a custom `Tool` subclass that the conversation app calls.

None of this is in May 30 scope.

---

## 6. What Needs to Be Built — Two-Track Plan

The May 30 demo is **28 days** from today (2 May 2026 → 30 May 2026). Two tracks run in parallel; they converge around Day 15 when the RAG pipeline is wired into the Streamlit backend and the full demo becomes testable end-to-end. Days 22–29 are pure polish and rehearsal.

```
Track 1 (start now):       Setup → Backend → Frontend → Persona prompt → TTS
Track 2 (waits on FLP):    Document loaders → Chunking → Embedding → Ingestion → RAG retrieval testing
Convergence point:         ~Day 15 — RAG wired to backend, full pipeline testable
Polish + rehearsal:        Days 22–29
```

### Track 1 — App scaffolding (start Day 1; does NOT wait on FLP materials)

| Step | What | Days | Notes |
|---|---|---|---|
| 1.1 | **Setup.** Repo, venv, `pip install streamlit groq faster-whisper sentence-transformers chromadb langchain langchain-community python-dotenv gTTS`. `.env` with `GROQ_API_KEY`. | 1 | One day, ends with `streamlit run` showing a "hello world" page. |
| 1.2 | **Backend orchestration module.** Pure Python, no Streamlit imports. Exposes one function: `answer_question(text: str, history: list) -> Response`. Initially returns a hard-coded reply so Streamlit can be wired up before LLM is plumbed. | 2–3 | Defines the contract everything else will hit. |
| 1.3 | **Wire Groq** into the backend. Send a single-shot chat completion. Confirm a real response comes back. | 3–4 | Just plumbing — no system prompt yet. |
| 1.4 | **Wire faster-whisper** for mic input (or skip mic for v0.1 and use text input only — text-input-only is acceptable for the demo if mic causes friction). | 4–5 | Browser mic via Streamlit `audio_input` component. |
| 1.5 | **Streamlit frontend.** Chat history, input box, response area, citation panel (empty for now), latency display, fallback indicator placeholder. | 5–7 | Looks like the demo. No real answers yet. |
| 1.6 | **Persona prompt.** Write `instructions` system prompt: persona ("You are an AI representation of Chief Justice Artemio V. Panganiban..."), 150-word limit, English-only output, source-grounded rule, refer-on-miss rule. Inject into every Groq call. | 7–9 | Prompt is text — easy to iterate. Move to its own `.txt` file so it's editable without code changes. |
| 1.7 | **Robot adapter scaffolding.** `WebAdapter` class implementing the protocol from Section 4.3. Backend calls `adapter.listen()` and `adapter.speak()`. | 9–10 | Lays groundwork for `ReachyAdapter` later — small effort now, big save later. |
| 1.8 | **Optional TTS** play button (`gTTS` or browser SpeechSynthesis). Don't over-invest. | 10–11 | A "Play" button on each response. |
| 1.9 | **Trigger-word interrupt** handling (web-only behavior: cancel TTS, reset state) and **5-minute conversation window** with visible clear cue. | 11–13 | Both configurable via env var. |
| 1.10 | **Logging layer.** Structured JSON logs to `logs/turns.jsonl`. One line per turn: input, retrieved sources + scores (when wired), response, latency, fallback reason. | 12–14 | Used for QA and demo-day debugging. |

### Track 2 — RAG pipeline (waits on FLP delivery to start ingestion; can start scaffolding earlier)

| Step | What | Days | Notes |
|---|---|---|---|
| 2.1 | **Document loaders.** LangChain loaders for the file formats FLP delivers (likely PDF, TXT, MD). Build a loader script: input folder of files → list of `Document` objects with metadata (title, date, source URL, theme bucket A–E). | 1–4 | Can build and test on dummy text files before FLP delivers. |
| 2.2 | **Chunking strategy.** `RecursiveCharacterTextSplitter` with ~500–800 token chunks and ~100 token overlap as a starting point. Confirm exact numbers with Rocelle. Preserve metadata on each chunk. | 4–6 | One CJ column → ~3–5 chunks at this size. |
| 2.3 | **Embedding pipeline.** `sentence-transformers` `all-mpnet-base-v2` (768-dim). Batch-embed all chunks. Cache embeddings to disk so re-runs are fast. | 6–8 | First embedding run downloads ~420 MB model. |
| 2.4 | **ChromaDB ingestion.** Create persistent collection `cjp_v1`. Insert chunks with embeddings + metadata. | 8–10 | Persists to `./chroma_db`. |
| 2.5 | **Retrieval testing.** Standalone script: take a query, return top-5 chunks with scores. Eyeball-check quality on a sample of demo questions (biography, FLP mission, current events, deliberate out-of-scope). | 10–13 | This is where retrieval quality issues surface. Tune chunk size and `k` here, not at the convergence point. |
| 2.6 | **Confidence threshold tuning.** Pick a similarity score below which the system triggers fallback. Start at 0.35; adjust based on real corpus behavior. | 13–14 | Test deliberate out-of-scope questions to verify fallback fires. |

### Convergence — Day 15

- Replace the hard-coded reply in `answer_question()` with the real flow:
  1. Embed query (sentence-transformers).
  2. ChromaDB top-k.
  3. Confidence check → fallback path if low.
  4. Build prompt with retrieved chunks + persona + history.
  5. Call Groq.
  6. Trim to 150 words, attach citations.
  7. Log everything.
- Render citations in Streamlit (source title, date, link if available, similarity score in a debug-only view).
- Run a smoke test of 10–15 questions across the demo categories. Fix obvious retrieval issues (missing material flagged to FLP; chunking re-tuned).

### Polish + rehearsal — Days 22–29

| Day range | Focus |
|---|---|
| 22–24 | **Citation rendering polish** — make sources legible, not noisy. Approved fallback language (from Jacob) wired in. Verify all 15 demo questions answer well. |
| 25–26 | **Latency tuning** — measure end-to-end on a real network. If Groq is slow at peak, prefetch nothing; just live with it (free tier). |
| 27–28 | **Dry runs** — rehearse with Rocelle / Jeanette / John playing the role of CJ. Build the demo question bank including deliberate trickies (off-topic, hostile, factually loaded). |
| 29 | **Frozen build** — tag the repo, document run instructions in `README.md`, prepare a fallback laptop with the same environment. |

### What is explicitly out of scope for May 30
- FastAPI separate backend (Streamlit calls Python directly).
- PostgreSQL + pgvector (ChromaDB only).
- OpenAI services (Groq + free-local only).
- Voice cloning or high-quality TTS (gTTS / browser is fine).
- Reachy Mini integration of any kind.
- Wake-word detection (push-to-talk / text input only).
- Streamlit operator/QA app distinct from the demo app (Phase 3 deliverable).
- Cloud hosting (laptop only).

---

## 7. Current Phase and Immediate Next Task

**Phase:** P1 — Discovery, Alignment & Hardware Procurement (week 2 of 26).
**Today:** Saturday 2 May 2026.
**Phase 1 closes:** 3 May 2026. **Phase 2 (Knowledge Base Build) opens:** 4 May 2026.

**Next concrete deliverable:** May 30 pre-prototype demo. **28 days from today.** Web-only, Streamlit, on-laptop.

**Immediate next task for the developer (Day 1 of Track 1):**

```bash
# 1. Create project repo and venv
mkdir cjp-demo && cd cjp-demo
python -m venv .venv && source .venv/bin/activate
pip install streamlit groq faster-whisper sentence-transformers chromadb \
            langchain langchain-community python-dotenv gTTS

# 2. .env
echo "GROQ_API_KEY=<your-key>" > .env
echo "GROQ_MODEL=llama-3.1-70b-versatile" >> .env

# 3. app.py — minimal hello-world Streamlit
cat > app.py <<'EOF'
import streamlit as st
st.title("CJ Panganiban — May 30 Demo")
question = st.text_input("Ask a question:")
if question:
    st.write("(answer placeholder — orchestration not wired yet)")
EOF

# 4. Run
streamlit run app.py
```

End of Day 1: a Streamlit page is live at `localhost:8501`, with text input and placeholder output.

By Day 3: Groq is plumbed in and answering generic questions (no RAG yet, no persona yet).

By Day 7: persona prompt, robot adapter scaffolding, basic citation panel UI (empty for now).

By Day 10: Track 2 has ingested whatever FLP has delivered into ChromaDB; standalone retrieval test runs.

By Day 15: convergence — full pipeline answers grounded questions with citations.

Days 22–29: polish + rehearsal.

---

## 8. Open Decisions That Will Affect Code

These are not blockers right now, but will affect later choices. Code defensively around them.

| ID | Open Question | Why it matters for code | Owner / target |
|---|---|---|---|
| OD-1 | **Persona: replicate exact CJ voice vs. adapt for donor audience?** | Drives the system prompt's tone instructions. | Jacob → CJ feedback at May 30 demo |
| OD-2 | **Voice cloning vs. neutral TTS?** | If cloning, integrate ElevenLabs or Coqui XTTS later. May 30 doesn't decide this. | Jacob → CJ feedback at May 30 demo |
| OD-3 | **Legal-case Q&A — engage substantively or refer?** | Affects system prompt allow/deny lists and fallback triggers. | Jacob → CJ feedback at May 30 demo |
| OD-4 | **Wake-word vs. proactive greeting** when a visitor approaches. | Default for May 30: text input or push-to-talk. Wake-word work is post-demo. | Week 9 (June 14–21) |
| OD-5 | **Hardware timeline.** Mid-June (original) vs. July–August (per Handover Revisions). **Flag A.** | Affects when robot integration code can begin. Doesn't affect May 30. | John (PM), needs answer |
| OD-6 | **Embedding migration as a real Phase 3 task.** **Flag B.** | 768→1,536 means re-embedding the entire KB. Real cost, plan in June. | Tech lead (Jeanette/Rocelle) |
| OD-7 | **Corpus quantity phrasing.** **Flag C.** "FLP-provided subset, exact count TBD" vs strict "TBD pending FLP delivery." | Affects ingestion estimates and demo-readiness messaging. | John / Jacob |
| OD-8 | **Approved fallback / referral language.** | The exact words the system uses when it can't answer. Must be in the demo. | Jacob (FLP) |
| OD-9 | **Cloud platform final sign-off.** Railway is the working assumption for post-demo hosting. | Affects post-demo deploy scripts. Doesn't affect May 30. | Jeanette |
| OD-10 | **Vector store migration timing.** ChromaDB → PostgreSQL + pgvector. | Re-export embeddings; recreate as pgvector rows. Schedule with the embedding-dim migration so we only re-process once. | Tech lead |

Build the system so that any of OD-1, OD-2, OD-3, OD-8 can be changed by editing `instructions.txt` and the fallback-language config — no code change needed.

---

## 9. Team and Ownership

### Supervaise (delivery side)

- **John Anthony Jose** — Project Manager / CTO. Owns: client comms, timeline, hardware procurement, shipment tracking. Final escalation point inside Supervaise.
- **Jeanette Pao** — Technical Manager. Owns: tech stack final sign-off, post-demo cloud platform decision, RAG architecture call (LangChain — already decided).
- **Rocelle Andrea Belandres** — AI Engineer. Owns: chunking strategy + embedding parameters, RAG pipeline implementation, eventual Streamlit operator UI for Phase 3. **Closest engineering lane to the developer reading this.**
- **Sireen** — Document support / admin. Not engineering.

### FLP (client side)

- **Jacob Barbosa** — FLP project director. Owns: all FLP-side approvals, content sign-offs, source materials delivery, the three persona decisions (OD-1/2/3), approved fallback language (OD-8). All FLP requests go through Jacob.

### The developer reading this

You are operating in the **junior app developer / AI engineering** lane, supporting Rocelle. Concretely:

- You own day-to-day implementation of Track 1 and Track 2 in Section 6 (the May 30 demo build).
- You do **not** own product decisions, content sign-offs, persona calls, or hardware procurement. Surface those to Rocelle/Jeanette, not to Jacob directly.
- You do **not** correspond directly with Jacob; that goes through John.
- When you hit an open decision (Section 8), default to the most reversible option, log the assumption in code comments, and flag it in the next standup.

---

## 10. Known Constraints and Risks

### 10.1 Budget / API constraints
- **No OpenAI API budget during May 2026.** This is the entire reason the dev stack is Groq + faster-whisper + sentence-transformers + ChromaDB. Do not introduce OpenAI calls in dev unless explicitly approved.
- **Groq free-tier rate limits exist** — generous, but if a long rehearsal session hits them, expect 429s. Mitigation: keep the rehearsal question bank to ~20–30 distinct questions; don't loop the same prompts mindlessly.
- **OpenAI migration scheduled for June 2026** before the August robot integration. Don't pre-optimize for OpenAI; don't lock yourself out of it either.
- **Post-project ChatGPT API and cloud hosting costs are FLP's responsibility,** not Supervaise's.

### 10.2 Hardware constraints
- **No physical Reachy Mini until late July / early August 2026** (revised ETA — was originally mid-June). All May 30 demo work is laptop-only. Nothing in the demo path depends on hardware.
- **Plans B–D on standby:** UK borrow, web-app-only demo (the current May 30 plan), 3D-print mockup. Daily shipment tracking owned by John.

### 10.3 Data / content constraints
- **Working corpus = whatever FLP delivers.** Not a fixed number. Not assumed to be 1,000 columns or 20 columns or any specific count. The 5 theme buckets and 7-criterion rubric are guidelines for FLP's selection.
- **Track 2 cannot fully start until FLP delivers materials.** Track 1 is independent. The two-track structure is designed around this dependency.
- **Strict source grounding** — answers come only from retrieved chunks. The system must refuse (referral) rather than guess. This is contractual with FLP.
- **No live web search.** Embedded documents only.

### 10.4 Migration / re-work risks (post-demo, not May 30)
- **ChromaDB → PostgreSQL + pgvector** at robot integration time. Re-export embeddings is straightforward but takes a day; do it in the same window as the embedding-dim migration so the corpus only gets re-processed once.
- **Embedding dimension migration (768 → 1,536)** is real work, plan it as a Phase 3 task in June. Re-embedding compute time depends on KB size at that point.
- **LLM swap (Groq → OpenAI) in June** is mostly format-compatible; verify streaming behavior and token limits.

### 10.5 Operational risks at the May 30 demo
- **Internet at the meeting venue.** The laptop needs to reach Groq's API. If venue Wi-Fi is unreliable, mobile hotspot is the fallback. Test before demo day.
- **Laptop battery / charger.** Bring both. Bring a backup laptop with the same environment if practical.
- **Chrome / Streamlit version drift.** Pin all versions in `requirements.txt`. Don't `pip install --upgrade` the day before the demo.

### 10.6 Scope-creep risks
- Out of scope for v1: Filipino/Tagalog **output**, additional robot units, mobile apps, ongoing API/hosting fees beyond project end, content creation (logos/photo/video), full museum buildout, event logistics. If a request comes in matching one of these, route to John for change-order discussion.
- Out of scope for the May 30 demo specifically: hardware, FastAPI, PostgreSQL, OpenAI, voice cloning, wake-word, separate operator UI, cloud hosting. See Section 6 final list.

---

## Appendix A — May 30 demo quick-start

```bash
# Day 1 — full setup
mkdir cjp-demo && cd cjp-demo
git init
python -m venv .venv && source .venv/bin/activate

pip install streamlit groq faster-whisper sentence-transformers chromadb \
            langchain langchain-community python-dotenv gTTS

# .env
cat > .env <<'EOF'
GROQ_API_KEY=<paste-key>
GROQ_MODEL=llama-3.1-70b-versatile
WHISPER_MODEL=base
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_DIM=768
CHROMA_DIR=./chroma_db
TOP_K=5
RETRIEVAL_CONFIDENCE_THRESHOLD=0.35
RESPONSE_WORD_LIMIT=150
CONVERSATION_WINDOW_MINUTES=5
TRIGGER_WORDS=that's enough,okay thank you,thank you,next question
EOF

# Suggested folder layout
mkdir -p backend ui ingestion prompts logs chroma_db source_materials
touch app.py backend/__init__.py backend/orchestrator.py \
      backend/adapters.py ingestion/load_and_embed.py \
      prompts/instructions.txt prompts/fallback.txt
```

## Appendix B — Suggested file map

```
cjp-demo/
├── .env
├── .gitignore                       # ignore .venv, chroma_db, logs, *.mp3
├── README.md
├── requirements.txt                 # pinned versions
├── app.py                           # Streamlit entry point
├── backend/
│   ├── orchestrator.py              # answer_question(), the main flow
│   ├── adapters.py                  # WebAdapter (May 30); ReachyAdapter later
│   ├── retrieval.py                 # ChromaDB query + confidence check
│   ├── llm.py                       # Groq call wrapper
│   ├── stt.py                       # faster-whisper wrapper
│   ├── tts.py                       # gTTS wrapper (optional play button)
│   ├── prompts.py                   # loads instructions.txt, fallback.txt
│   └── logger.py                    # structured JSON logs
├── ingestion/
│   ├── load_and_embed.py            # FLP materials → chunks → embeddings → Chroma
│   └── retrieval_test.py            # standalone query → top-k for QA
├── prompts/
│   ├── instructions.txt             # system prompt (persona, rules)
│   └── fallback.txt                 # approved referral language (from Jacob)
├── source_materials/                # FLP-delivered files (PDF/TXT/MD)
├── chroma_db/                       # persisted vector store (gitignored)
└── logs/
    └── turns.jsonl                  # one line per turn
```

## Appendix C — Reference documents in the project drive

- `Conversational_AI_Robot_Proposal.docx` — original SOW, six-phase structure.
- `Project_Timeline_v1.docx` — week-by-week task plan through Week 26.
- `Column_Selection_Criteria_May30_Demo.docx` — 7-criterion rubric, 5 theme buckets. **Now a guideline for FLP, not a Supervaise list** (per Handover Revisions #5–6).
- `AI_App_Development_Basics.pdf` — primer for engineers new to the AI stack. Read first if any concept above is unfamiliar.
- `Handover_Doc_Revisions.pdf` — the nine confirmed revisions and three open flags this document is built from. Source of truth for all changes vs. earlier handover drafts.
- `index.html` — internal project dashboard (decisions, risks, KB ingestion progress).

---

*End of handover v3.0. Read sections 1–6 before writing code; sections 7–10 before estimating. When in doubt, ask Rocelle on the engineering side and let Jacob decisions filter through John.*
