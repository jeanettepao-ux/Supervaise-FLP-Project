# CJ Panganiban Conversational AI — May 30 Demo

Streamlit-based pre-prototype demo of a conversational AI representing Chief Justice Artemio V. Panganiban for FLP donor engagement. Web-only, runs entirely on the developer's laptop (Groq is the only remote dependency).

See [HANDOVER.md](HANDOVER.md) for the full technical spec and [CLAUDE.md](CLAUDE.md) for working context.

## Setup

```bash
# 1. Create and activate venv
python -m venv .venv
# Windows (bash):
source .venv/Scripts/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# then edit .env and set GROQ_API_KEY

# 4. Run the demo
streamlit run app.py
```

The app opens at http://localhost:8501.

## Status

Currently at **Track 1, Step 1.1 — Setup complete.** The Streamlit page renders a title and a text input with a placeholder response. No LLM, no retrieval, no persona yet — those are Steps 1.2 onward.
