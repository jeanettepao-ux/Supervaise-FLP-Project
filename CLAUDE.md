# CJ Panganiban Conversational AI — Project Context

## Project goal
A Reachy Mini robot that holds short, **voice-based**, source-grounded conversations about Chief Justice Artemio V. Panganiban for FLP donor engagement.

## Current milestone
**May 30, 2026 pre-prototype demo** — web app only, no robot. Streamlit on a laptop, **voice in / voice out**, shown to CJ for directional feedback on persona, tone, and answer style.

## Strategy refinements — Week 3 sync (4 May 2026)
- **KB scope:** validate the pipeline end-to-end on a theme-grouped slice; NOT a comprehensive corpus build (that's Phase 3).
- **Embedding economics:** iterate cheaply on a small slice; run the full embedding batch once at full scale when ready.
- **Theme-grouped iteration:** Jeanette categorizes incoming docs by theme bucket A–E so related material clusters for QA.
- **Demo format:** voice-in / voice-out (NOT text) — local STT via faster-whisper, cloud TTS via free API (gTTS).
- **Architecture (post-demo):** cloud LLM + on-prem RAG. R-Pi acts as API gateway + SQLite vector store. Cloud DBs ruled out (cost). For May 30 the laptop runs ChromaDB locally; SQLite-on-R-Pi migration is post-demo.
- **Latency:** cloud round-trip accepted; Jacob confirmed.
- **Code audit:** John audits Jeanette's pipeline code before the OpenAI cutover.

## Two-phase Week 3 plan
- **Phase A · 4–13 May:** All-free dev stack on laptop — Groq + faster-whisper + sentence-transformers + ChromaDB + Streamlit + gTTS. Validate KB output before any paid services.
- **Phase B:** OpenAI cutover, after Phase A validates and after John's code audit.

## Confirmed tech stack (May 30 demo — Phase A)
- **Frontend:** Streamlit (`streamlit run app.py` → `localhost:8501`)
- **LLM:** Groq (`llama-3.3-70b-versatile`) — free tier
- **STT:** faster-whisper (local, `base` model, project-local cache at `./models/`)
- **Embeddings:** sentence-transformers `all-mpnet-base-v2` (768-dim, local)
- **Vector store:** ChromaDB (embedded, in-process, persists to `./chroma_db`)
- **TTS:** gTTS (free cloud API)
- **RAG orchestration:** LangChain (loaders + `RecursiveCharacterTextSplitter`)
- **Runtime:** Python 3.10+. No Docker, no FastAPI, no OpenAI, no cloud DB during Phase A.

## File structure
```
cjp-demo/
├── .env
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── app.py                           # Streamlit entry point
├── backend/
│   ├── orchestrator.py              # answer_question(), the main flow
│   ├── adapters.py                  # WebAdapter (May 30); ReachyAdapter later
│   ├── retrieval.py                 # ChromaDB query + confidence check
│   ├── llm.py                       # Groq call wrapper
│   ├── stt.py                       # faster-whisper wrapper
│   ├── tts.py                       # gTTS wrapper
│   ├── prompts.py                   # loads instructions.txt, fallback.txt
│   └── logger.py                    # structured JSON logs
├── ingestion/
│   ├── load_and_embed.py            # FLP materials → chunks (with theme bucket A–E) → embeddings → Chroma
│   └── retrieval_test.py            # standalone query → top-k for QA
├── prompts/
│   ├── instructions.txt             # system prompt (persona, rules)
│   └── fallback.txt                 # approved referral language (from Jacob)
├── source_materials/                # FLP-delivered files (PDF/TXT/MD/MP3/M4A/MP4)
├── models/                          # local ML model cache (faster-whisper, etc.)
├── chroma_db/                       # persisted vector store (gitignored)
└── logs/
    └── turns.jsonl                  # one line per turn
```

## Key product rules (must be enforced in code)
- **English output only.** Input may be English or Taglish; output is always English.
- **100–150 word response limit**, enforced in the system prompt and trimmed post-response.
- **Strict source grounding** — answers come *only* from retrieved chunks. No speculation, no outside knowledge, no legal interpretation beyond what CJ has said in the corpus.
- **Refer-on-miss** — when retrieval confidence is low (start threshold ~0.35), off-topic, or the system can't answer, return the approved FLP referral line from `prompts/fallback.txt`. Never improvise.
- **Per-turn logging** to `logs/turns.jsonl`: input, retrieved sources + scores, response, latency, fallback reason.
- **Theme-bucketed ingestion** — every chunk carries a theme bucket (A–E) in its metadata so QA can probe related clusters.

## Persona / fallback are config, not code
`prompts/instructions.txt` and `prompts/fallback.txt` are the editable surface for persona, tone, and refusal language. Open decisions OD-1/2/3/8 (persona voice, legal-Q&A scope, exact fallback wording) will change these files — they should not require code changes.

## Robot adapter
Even in the web demo, the I/O surface goes through a `RobotAdapter` interface. May 30 ships only `WebAdapter` (text + gTTS playback in Streamlit); `ReachyAdapter` plugs in late July / early August without rewiring the pipeline.

## Out of scope for May 30
Hardware, FastAPI, PostgreSQL/pgvector, OpenAI services, voice cloning, wake-word, separate operator UI, cloud hosting, R-Pi edge TTS optimization, comprehensive corpus build.

## Source materials handling
FLP delivers files (PDF / TXT / MD / MP3 / M4A / MP4) into `source_materials/`. Audio recordings go through faster-whisper to text before ingestion. OCR for scanned PDFs is a known need; technique research is on the Phase A task list.

**Audio is ingestion-only — never replayed to the visitor.** The pipeline is one-way:

- INGESTION: MP3 / M4A / MP4 → faster-whisper → text → embeddings → ChromaDB
- INFERENCE: question → retrieve text chunks → Groq generates text answer → gTTS speaks the text answer

CJ's actual recorded audio is never sent back to the visitor as output. Only the synthesized "normal voice" reads the textual answer aloud.

## OD-2 — voice cloning vs neutral TTS (decided for May 30)
**Decided: neutral TTS** (gTTS for now). No voice cloning of CJ for the May 30 demo. Re-opens post-demo if FLP wants a more realistic voice for the September showcase.

## Full context
See [HANDOVER.md](HANDOVER.md) for the complete 10-section spec, two-track build plan, open decisions, team ownership, and post-demo migration path.
