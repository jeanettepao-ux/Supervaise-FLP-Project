# CJ Panganiban Conversational AI — Project Context

## Project goal
A Reachy Mini robot that holds short, voice-based, source-grounded conversations about Chief Justice Artemio V. Panganiban for FLP donor engagement.

## Current milestone
**May 30, 2026 pre-prototype demo** — web app only, no robot. Streamlit on a laptop, shown to CJ for directional feedback on persona, tone, and answer style. **28-day build** from 2 May 2026.

## Confirmed tech stack (May 30 demo — laptop-only)
- **Frontend:** Streamlit (`streamlit run app.py` → `localhost:8501`)
- **LLM:** Groq (`llama-3.1-70b-versatile`) — only remote dependency, free tier
- **STT:** faster-whisper (local, `base`/`small` model)
- **Embeddings:** sentence-transformers `all-mpnet-base-v2` (768-dim, local)
- **Vector store:** ChromaDB (embedded, in-process, persists to `./chroma_db`)
- **RAG orchestration:** LangChain (loaders + `RecursiveCharacterTextSplitter`)
- **Optional TTS:** gTTS or browser SpeechSynthesis
- **Runtime:** Python 3.10+. No Docker, no FastAPI, no OpenAI, no cloud DB for the demo.

## File structure
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

## Key product rules (must be enforced in code)
- **English output only.** Input may be English or Taglish; output is always English.
- **100–150 word response limit**, enforced in the system prompt and trimmed post-response.
- **Strict source grounding** — answers come *only* from retrieved chunks. No speculation, no outside knowledge, no legal interpretation beyond what CJ has said in the corpus.
- **Refer-on-miss** — when retrieval confidence is low (start threshold ~0.35), off-topic, or the system can't answer, return the approved FLP referral line from `prompts/fallback.txt`. Never improvise.
- **Per-turn logging** to `logs/turns.jsonl`: input, retrieved sources + scores, response, latency, fallback reason.

## Persona / fallback are config, not code
`prompts/instructions.txt` and `prompts/fallback.txt` are the editable surface for persona, tone, and refusal language. Open decisions OD-1/2/3/8 (persona voice, legal-Q&A scope, exact fallback wording) will change these files — they should not require code changes.

## Robot adapter
Even in the web demo, orchestration calls a `RobotAdapter` interface. May 30 ships only `WebAdapter`; `ReachyAdapter` plugs in late July / early August without rewiring the pipeline.

## Out of scope for May 30
Hardware, FastAPI, PostgreSQL/pgvector, OpenAI services, voice cloning, wake-word, separate operator UI, cloud hosting.

## Full context
See [HANDOVER.md](HANDOVER.md) for the complete 10-section spec, two-track build plan, open decisions, team ownership, and post-demo migration path.
