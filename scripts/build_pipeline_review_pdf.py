"""Build the pipeline-review PDF (one-shot generator).

Output: docs/pipeline_review_2026-05-07.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

OUT_PATH = Path("docs/pipeline_review_2026-05-07.pdf")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)


# =============================================================
# Styles
# =============================================================
styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "TitleBig",
    parent=styles["Title"],
    fontSize=26,
    leading=32,
    alignment=TA_CENTER,
    spaceAfter=12,
)
SUBTITLE_STYLE = ParagraphStyle(
    "Sub",
    parent=styles["Normal"],
    fontSize=14,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#444444"),
    leading=18,
    spaceAfter=6,
)
META_STYLE = ParagraphStyle(
    "Meta",
    parent=styles["Normal"],
    fontSize=11,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#666666"),
    leading=14,
)
H1_STYLE = ParagraphStyle(
    "H1",
    parent=styles["Heading1"],
    fontSize=16,
    leading=20,
    spaceBefore=18,
    spaceAfter=10,
    textColor=colors.HexColor("#1a3a5c"),
)
H2_STYLE = ParagraphStyle(
    "H2",
    parent=styles["Heading2"],
    fontSize=13,
    leading=17,
    spaceBefore=10,
    spaceAfter=6,
    textColor=colors.HexColor("#2c5d8f"),
)
BODY_STYLE = ParagraphStyle(
    "Body",
    parent=styles["BodyText"],
    fontSize=10,
    leading=14,
    spaceAfter=6,
    alignment=TA_LEFT,
)
NOTE_STYLE = ParagraphStyle(
    "Note",
    parent=BODY_STYLE,
    textColor=colors.HexColor("#555555"),
    fontSize=9,
)
CODE_STYLE = ParagraphStyle(
    "Code",
    parent=styles["Code"],
    fontSize=8,
    leading=10,
    backColor=colors.HexColor("#f4f4f4"),
    leftIndent=4,
    rightIndent=4,
    spaceBefore=4,
    spaceAfter=8,
    borderColor=colors.HexColor("#dddddd"),
    borderWidth=0.5,
    borderPadding=4,
)


def _table(data, col_widths=None, *, header=True, zebra=True):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#1a3a5c")) if header else ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#cccccc")),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#cccccc")),
    ]
    if header:
        style.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f8")),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ])
    if zebra:
        for row_idx in range(1 if header else 0, len(data)):
            if row_idx % 2 == (0 if header else 1):
                style.append(
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#fafbfd"))
                )
    t.setStyle(TableStyle(style))
    return t


def _para(text):
    return Paragraph(text, BODY_STYLE)


def _h1(text):
    return Paragraph(text, H1_STYLE)


def _h2(text):
    return Paragraph(text, H2_STYLE)


def _code(text):
    return Preformatted(text, CODE_STYLE)


def _spacer(pts=6):
    return Spacer(1, pts)


# =============================================================
# Page footer with page numbers
# =============================================================
def _on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(0.75 * inch, 0.55 * inch,
                      "CJ Panganiban Conversational AI — Pipeline Review · 2026-05-07")
    canvas.drawRightString(letter[0] - 0.75 * inch, 0.55 * inch,
                           f"Page {doc.page}")
    canvas.restoreState()


def _on_first_page(canvas, doc):
    # Title page — no page number on cover
    pass


# =============================================================
# Build the story
# =============================================================
story = []

# ---- Title page ----
story.append(Spacer(1, 2.3 * inch))
story.append(Paragraph("CJ Panganiban Conversational AI", TITLE_STYLE))
story.append(Paragraph("Pipeline Review", TITLE_STYLE))
story.append(Spacer(1, 0.2 * inch))
story.append(Paragraph("As of 2026-05-07", SUBTITLE_STYLE))
story.append(Spacer(1, 1.0 * inch))
story.append(Paragraph("Supervaise &times; Foundation for Liberty and Prosperity", META_STYLE))
story.append(Spacer(1, 0.1 * inch))
story.append(Paragraph(
    "Phase A · all-free dev stack on the laptop · pre-OpenAI cutover", META_STYLE
))
story.append(PageBreak())

# ---- Section 1 ----
story.append(_h1("1. High-level architecture (Phase A — May 30 demo)"))
story.append(_para(
    "Everything runs on the dev laptop except the Groq LLM call. "
    "Streamlit imports the orchestrator directly (no HTTP layer)."
))
arch_diagram = """\
                    Visitor's browser (Edge / incognito)
                                      |  HTTP
                                      v
              +---------------------------------------+
              |    Streamlit 1.57 on localhost:8501   |
              |    (app.py - chat UI, history,        |
              |     citation panel, latency,          |
              |     fallback warning)                 |
              +---------------------------------------+
                           |  Python imports
                           v
              +---------------------------------------+
              |  backend/orchestrator.py              |
              |  answer_question(text, history)       |
              |  -> returns Response                  |
              +---+---+---+---+---+-------------------+
                  |   |   |   |   |
           +------+   |   |   |   +---------+
           v          v   v   v             v
      +--------+ +-----+ +---+ +-----+  +-------------+
      |faster- | |chro | |   | | groq|  |edge-tts     |
      |whisper | |maDB | |   | |  -> |  |(Microsoft   |
      |(small) | |+    | |   | |HTTPS|  | Edge cloud) |
      |        | |Mini | |   | |     |  |             |
      |STT     | |LM   | |   | |LLM  |  | TTS cloud   |
      |local   | |embed| |   | |free |  | (free)      |
      +--------+ +-----+ +---+ +-----+  +-------------+
                                              ^
                                              |  back to browser as
                                              |  autoplaying audio
"""
story.append(_code(arch_diagram))

# ---- Section 2 — Frontend ----
story.append(_h1("2. Frontend layer"))
story.append(_table([
    ["Item", "Value"],
    ["Framework", "Streamlit 1.57.0"],
    ["Entry point", "app.py"],
    ["URL", "http://localhost:8501"],
    ["Chat primitives", "st.chat_input, st.chat_message, st.audio_input, st.audio"],
    ["Conversation history", "st.session_state.history (list of {role, content, meta})"],
    ["Citation rendering", "_render_meta() — bucket, title, date, distance, URL, unsafe-tag"],
    ["File watcher", "DISABLED via .streamlit/config.toml (Windows watchdog crash fix)"],
    ["Telemetry", "Disabled (gatherUsageStats = false)"],
], col_widths=[1.7 * inch, 4.7 * inch]))
story.append(_para(
    "<b>Visitor flow:</b> record (or type) &rarr; see &ldquo;Heard:&rdquo; caption &rarr; "
    "see &ldquo;Thinking&hellip;&rdquo; spinner &rarr; see assistant message + citations + "
    "latency + (optional) fallback warning &rarr; hear voice playback."
))

# ---- Section 3 — STT ----
story.append(_h1("3. STT (Speech-to-Text)"))
story.append(_table([
    ["Item", "Value"],
    ["Library", "faster-whisper 1.2.1"],
    ["Wrapper", "backend/stt.py"],
    ["Model", "small  (just bumped from base)"],
    ["Disk size", "~470 MB"],
    ["Quantization", "int8  (CPU-friendly, smaller memory footprint)"],
    ["Device", "cpu"],
    ["Decode params", "beam_size=1 (fastest greedy decoding)"],
    ["Cache location", "./models/faster-whisper-small/  (gitignored)"],
    ["Download mechanism", "huggingface_hub.snapshot_download with local_dir"],
    ["Latency", "~3-5 sec for a 5-15 sec audio clip on a typical laptop CPU"],
    ["Languages", "Auto-detect; multilingual; output is English (Taglish input fine)"],
    ["Configurable via", "WHISPER_MODEL env var (could go up to 'medium' if needed)"],
], col_widths=[1.7 * inch, 4.7 * inch]))

# ---- Section 4 — LLM ----
story.append(_h1("4. LLM (chat completion)"))
story.append(_table([
    ["Item", "Value"],
    ["Provider", "Groq (free tier)"],
    ["Library", "groq 1.2.0"],
    ["Wrapper", "backend/llm.py — single chat(messages) function"],
    ["Model", "llama-3.3-70b-versatile"],
    ["Where it runs", "Groq's cloud servers (only remote hop in the pipeline)"],
    ["API key env var", "GROQ_API_KEY"],
    ["Model env var", "GROQ_MODEL"],
    ["Latency", "~1-2 sec typical; can spike to 3-5 sec under load"],
    ["Phase B target", "OpenAI GPT-4o (single config flip)"],
], col_widths=[1.7 * inch, 4.7 * inch]))

# ---- Section 5 — TTS ----
story.append(_h1("5. TTS (Text-to-Speech)"))
story.append(_table([
    ["Item", "Value"],
    ["Library", "edge-tts 7.2.8 (Microsoft Edge's TTS endpoint)"],
    ["Wrapper", "backend/tts.py — synthesize(text, voice) returns mp3 bytes"],
    ["Voice", "en-US-AndrewNeural (US male, configurable via TTS_VOICE)"],
    ["Other male options", "en-US-GuyNeural, en-US-EricNeural, en-GB-RyanNeural, en-AU-WilliamNeural"],
    ["Cost", "Free, no API key required"],
    ["Latency", "~1-2 sec for a 100-150 word answer"],
    ["Implementation note", "Async-only API; wrapped with asyncio.run() per call"],
    ["Caching", "@st.cache_data on synthesize so same text doesn't re-synth"],
], col_widths=[1.7 * inch, 4.7 * inch]))

# ---- Section 6 — Persona ----
story.append(_h1("6. Persona &amp; fallback (the LLM's instruction layer)"))
story.append(_table([
    ["Item", "Value"],
    ["System prompt file", "prompts/instructions.txt"],
    ["Loader", "backend/prompts.py — system_prompt() returns persona + substituted fallback"],
    ["Persona rules (6)", "(1) source-grounded only; (2) 100-150 word output cap; (3) English only "
                         "(Taglish input OK); (4) measured/educational style; (5) no legal advice; "
                         "(6) no persona breaks"],
    ["Fallback file", "prompts/fallback.txt — 5 variants separated by '---'"],
    ["Variant selection", "Random per call (random.choice) — different phrasings per visitor"],
    ["Owner of final wording", "Jacob Barbosa (FLP) — current text is placeholder per OD-1, OD-3, OD-8"],
], col_widths=[1.7 * inch, 4.7 * inch]))
story.append(_para(
    "The persona prompt is injected as a <i>system</i> message prepended to every Groq call."
))

# ---- Section 7 — Embeddings ----
story.append(_h1("7. Embeddings layer"))
story.append(_table([
    ["Item", "Value"],
    ["Library", "sentence-transformers 5.4.1"],
    ["Model", "all-MiniLM-L6-v2  (changed from all-mpnet-base-v2 with v2 spec)"],
    ["Dimensions", "384  (was 768 before v2 handover)"],
    ["Disk size", "~90 MB"],
    ["Where it runs", "Local laptop CPU"],
    ["Used in two places", "(a) ingestion-time chunk embedding in ingest_columns.py;\n"
                          "(b) query-time question embedding in backend/retrieval.py"],
    ["Cache", "~/.cache/huggingface/hub/  (downloaded on first use; copy-mode on Windows)"],
    ["Phase B target", "OpenAI text-embedding-3-small (1536-dim) — REQUIRES re-embedding all chunks"],
], col_widths=[1.7 * inch, 4.7 * inch]))

# ---- Section 8 — Vector store ----
story.append(_h1("8. Vector store"))
story.append(_table([
    ["Item", "Value"],
    ["Engine", "chromadb 1.5.8 (embedded, in-process, SQLite-backed)"],
    ["Persist directory", "./chroma_store/  (gitignored)"],
    ["Collection name", "cjp_columns_dev"],
    ["Distance metric", "cosine"],
    ["Index", "HNSW (Chroma default)"],
    ["Total chunks", "954"],
    ["Total sources (slugs)", "85"],
    ["Phase B collection", "cjp_columns_prod (new collection at 1536-dim — no in-place migration)"],
], col_widths=[1.7 * inch, 4.7 * inch]))
story.append(_h2("Per-chunk metadata schema"))
metadata_code = """\
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
"""
story.append(_code(metadata_code))

# ---- Section 9 — Retrieval ----
story.append(_h1("9. Retrieval layer"))
story.append(_table([
    ["Item", "Value"],
    ["Module", "backend/retrieval.py — retrieve(query, top_k, bucket, safe_only)"],
    ["Top-k", "5  (env: RETRIEVAL_TOP_K)"],
    ["Distance threshold", "0.55  (env: RETRIEVAL_DISTANCE_THRESHOLD; smoke-tested for MiniLM)"],
    ["Diversity guardrail", "max 2 chunks per source  (env: RETRIEVAL_MAX_PER_SOURCE)"],
    ["Bucket filter", "optional, used for thematic biasing (not in default flow)"],
    ["Citation-safe filter", "via RETRIEVAL_SAFE_ONLY env (off in dev; will be true in prod)"],
    ["Over-fetch", "n_results = top_k * 3 to give the diversity filter room"],
    ["Returns", "List of RetrievedChunk dataclasses (text, title, date, url, bucket, distance, citation_safe)"],
], col_widths=[1.7 * inch, 4.7 * inch]))

# ---- Section 10 — Orchestrator ----
story.append(_h1("10. Orchestrator (the per-turn flow)"))
flow = """\
answer_question(text, history) — backend/orchestrator.py

  start_timer()

  chunks = retrieve(text)

  if not chunks:
      - pick a random fallback variant
      - return Response(fallback=True, ~30 ms latency, no LLM call)

  build messages = [
      {role: system,    content: persona_prompt},
      {role: system,    content: "Provided sources: ..." + chunk texts},
      *history,
      {role: user,      content: text},
  ]

  answer = chat(messages)            # -> Groq llama-3.3-70b-versatile
  answer = trim_to_150_words(answer)

  citations = [{title, date, url, bucket, distance, citation_safe} for c in chunks]

  return Response(text=answer, citations=citations, latency_ms=..., fallback=False)
"""
story.append(_code(flow))

# ---- Section 11 — Robot adapter ----
story.append(_h1("11. Robot adapter (future-proofing)"))
story.append(_table([
    ["Item", "Value"],
    ["Module", "backend/adapters.py"],
    ["Protocol", "RobotAdapter (speak / head_move / gaze_track / thinking_motion / handle_interrupt)"],
    ["Live impl", "WebAdapter — speak() does st.write + st.audio autoplay; others are no-ops"],
    ["Future impl", "ReachyAdapter — drops in late July / Aug, no other code changes needed"],
], col_widths=[1.7 * inch, 4.7 * inch]))

# ---- Section 12 — KB composition ----
story.append(_h1("12. Knowledge base composition"))
story.append(_table([
    ["Bucket", "Theme", "# Sources", "# Chunks"],
    ["A", "Liberty and Rule of Law", "44 (24 cols + 20 chapters)", "~770"],
    ["B", "Prosperity and Economic Philosophy", "7 columns", "~25"],
    ["C", "Biographical and Personal", "17 columns", "~75"],
    ["D", "FLP Mission and Foundation", "10 columns", "~40"],
    ["E", "Signature Current Events Commentary", "7 columns", "~30"],
    ["Total", "", "85 sources", "954 chunks"],
], col_widths=[0.7 * inch, 2.6 * inch, 1.8 * inch, 1.3 * inch]))
story.append(_para(
    "<b>Citation-safe flag:</b> 5 columns flagged citation_safe=False (Duterte ICC, "
    "Marcos ICC options, Trump defeat, ICC DOJ-OSG, ICC temporal-strategic) — pending Jacob's C5 review."
))

# ---- Section 13 — Ingestion pipeline ----
story.append(_h1("13. Ingestion pipeline"))
story.append(_para(
    "Run via <font name='Courier'>python ingest_columns.py</font>. 5 stages, all in ingest_columns.py:"
))
ingestion = """\
Stage 1 - Load
  +- if URL  -> fetch HTML (browser-shaped headers + canonical URL guard)
  |              -> trafilatura -> markdown
  +- if file -> read .docx (Docx2txtLoader) or .txt/.md (raw read) -> markdown
                  v
Stage 2 - Chunk
  +- RecursiveCharacterTextSplitter, chunk_size=500 tokens, overlap=75 tokens
  +- Tokenizer: cl100k_base (matches OpenAI for cutover compatibility)
  +- Separators: ["\\n\\n", "\\n", ". ", " ", ""]
                  v
Stage 3 - Embed
  +- all-MiniLM-L6-v2, batch_size=32, -> 384-dim vector per chunk
                  v
Stage 4 - Upsert
  +- ChromaDB cjp_columns_dev, deterministic chunk IDs ({slug}__c{NN})
                  v
Stage 5 - Smoke test (optional, --smoke-test flag)
  +- Sample query -> top-5 -> eyeball
"""
story.append(_code(ingestion))
story.append(_para(
    "<b>Word-count guards:</b> &lt;400 words from any source raises (catches truncation / "
    "wrong-block extraction). The canonical-URL guard catches Inquirer's silent redirect to "
    "the section homepage when a column URL is dead."
))
story.append(_para(
    "<b>Book chapter split:</b> The 2001 book &ldquo;A Centenary of Justice&rdquo; was split "
    "into 20 chapter <font name='Courier'>.txt</font> files via "
    "<font name='Courier'>scripts/extract_chapters_from_pdf.py</font> "
    "(sequential title-search parser over the source PDF) before ingestion."
))

# ---- Section 14 — Configuration files ----
story.append(_h1("14. Configuration files"))
story.append(_table([
    ["File", "Purpose", "Tracked?"],
    [".env", "Real config — has Groq key", "GITIGNORED"],
    [".env.example", "Template, no real keys", "tracked"],
    [".streamlit/config.toml", "Disable file watcher, telemetry", "tracked"],
    [".gitignore", "excludes .venv/, chroma_store/, kb/, models/, source_materials/, .env, *.log", "tracked"],
    ["requirements.txt", "Pinned deps (~150 packages)", "tracked"],
    ["prompts/instructions.txt", "Persona prompt", "tracked"],
    ["prompts/fallback.txt", "Fallback variants (5)", "tracked"],
], col_widths=[2.0 * inch, 3.4 * inch, 1.0 * inch]))

# ---- Section 15 — Env vars ----
story.append(_h1("15. Environment variables"))
story.append(_table([
    ["Var", "Current value", "What it controls"],
    ["GROQ_API_KEY", "(your key)", "LLM auth"],
    ["GROQ_MODEL", "llama-3.3-70b-versatile", "LLM model"],
    ["WHISPER_MODEL", "small  (just bumped)", "STT model size"],
    ["TTS_VOICE", "en-US-AndrewNeural", "TTS voice"],
    ["RETRIEVAL_TOP_K", "(default 5)", "retrieval breadth"],
    ["RETRIEVAL_DISTANCE_THRESHOLD", "(default 0.55)", "confidence cutoff"],
    ["RETRIEVAL_MAX_PER_SOURCE", "(default 2)", "diversity guardrail"],
    ["RETRIEVAL_SAFE_ONLY", "(default false in dev)", "citation-safe filter"],
    ["CHROMA_COLLECTION", "(default cjp_columns_dev)", "ChromaDB collection"],
    ["CONVERSATION_WINDOW_MINUTES", "5  (not yet wired)", "Step 1.9"],
    ["TRIGGER_WORDS", "that's enough,...  (not yet wired)", "Step 1.9"],
    ["EMBEDDING_MODEL / EMBEDDING_DIM", "DEAD CODE", "no longer read; needs cleanup"],
], col_widths=[2.3 * inch, 1.9 * inch, 2.2 * inch]))

# ---- Section 16 — Phase A vs B ----
story.append(_h1("16. Phase A &rarr; Phase B (OpenAI cutover) checklist"))
story.append(_table([
    ["Component", "Phase A (now)", "Phase B (after May 14 + audit)"],
    ["LLM", "Groq llama-3.3-70b-versatile", "OpenAI gpt-4o"],
    ["Embeddings", "sentence-transformers all-MiniLM-L6-v2 (384-dim)", "OpenAI text-embedding-3-small (1536-dim)"],
    ["STT", "faster-whisper small local", "TBD — open: cloud-hosted faster-whisper, OpenAI Whisper API, or stay local on R-Pi"],
    ["TTS", "edge-tts (free cloud)", "TBD — possibly OpenAI TTS, possibly stay edge-tts"],
    ["Vector store", "ChromaDB cjp_columns_dev (laptop)", "ChromaDB cjp_columns_prod on R-Pi (full re-embed required)"],
    ["Backend host", "Streamlit imports orchestrator", "Possibly FastAPI behind HTTP, on R-Pi"],
], col_widths=[1.0 * inch, 2.4 * inch, 3.0 * inch]))

# ---- Section 17 — Not yet wired ----
story.append(_h1("17. What's NOT yet wired (Track 1 leftovers)"))
story.append(_para(
    "<b>Step 1.9</b> — trigger-word interrupt (&ldquo;thank you&rdquo; / &ldquo;next question&rdquo; "
    "&rarr; reset state) and the 5-min conversation window auto-clear."
))
story.append(_para(
    "<b>Step 1.10</b> — structured JSON logging to <font name='Courier'>logs/turns.jsonl</font> "
    "(per-turn input, citations, latency, fallback reason — required per HANDOVER §3 rule #13)."
))

# ---- Section 18 — Known imperfections ----
story.append(_h1("18. Known imperfections to revisit"))
story.append(_table([
    ["Issue", "Severity", "Plan"],
    ["EMBEDDING_MODEL / EMBEDDING_DIM env vars are dead code", "Cosmetic", "Remove next push"],
    ["Ch 2 of book is 27,556 words (photo-plate captions absorbed)", "Medium", "Bring to next strategy session for chunking-of-oversized-chapters"],
    ["Ch 18 / 19 boundary off by ~1k words", "Low", "Same"],
    ["Ch 20 absorbs back matter (index, etc.)", "Low-medium", "Same"],
    ["LLM occasionally ignores source-grounded rule on weak context", "Low (RAG mostly suppresses this now)", "Watch during dry-runs"],
    ["Distance threshold 0.55 was a smoke-test guess for MiniLM", "Low (working in practice)", "Re-tune at OpenAI cutover"],
], col_widths=[2.6 * inch, 1.4 * inch, 2.4 * inch]))

# ---- End ----
story.append(Spacer(1, 0.3 * inch))
story.append(Paragraph(
    "<i>End of pipeline review. For per-push history and recent decisions, see "
    "<font name='Courier'>PROGRESS.md</font> in the repo. For the strategic spec, "
    "see <font name='Courier'>CLAUDE.md</font> and <font name='Courier'>docs/handover_v2.md</font>.</i>",
    NOTE_STYLE,
))


# =============================================================
# Build the doc
# =============================================================
doc = BaseDocTemplate(
    str(OUT_PATH),
    pagesize=letter,
    leftMargin=0.75 * inch,
    rightMargin=0.75 * inch,
    topMargin=0.75 * inch,
    bottomMargin=0.85 * inch,
    title="CJ Panganiban Conversational AI — Pipeline Review",
    author="Supervaise × Foundation for Liberty and Prosperity",
)

frame = Frame(
    doc.leftMargin, doc.bottomMargin,
    doc.width, doc.height,
    id="content"
)
doc.addPageTemplates([
    PageTemplate(id="cover", frames=[frame], onPage=_on_first_page),
    PageTemplate(id="body", frames=[frame], onPage=_on_page),
])

doc.build(story)
print(f"wrote {OUT_PATH}  ({OUT_PATH.stat().st_size:,} bytes)")
