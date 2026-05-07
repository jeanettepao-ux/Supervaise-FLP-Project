import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Render the page shell first (cheap), then defer heavy backend imports
# into a cached resource loader so the user sees the title immediately
# and a labelled spinner during the 10-15s cold start instead of a blank
# black page.
st.set_page_config(page_title="CJ Panganiban - May 30 Demo", layout="centered")
st.title("CJ Panganiban - May 30 Demo")
st.caption(
    "Pre-prototype. Voice in / voice out. Answers are not yet source-grounded - "
    "RAG retrieval arrives at the Day-15 convergence."
)


# =============================================================
# Trigger-word interrupt (Step 1.9, HANDOVER §3 rule #7)
# =============================================================
# When the visitor says one of these exact phrases (after normalization),
# end the conversation: speak a brief farewell, clear history, and reset
# state for the next visitor.
TRIGGER_WORDS: set[str] = {
    t.strip().lower()
    for t in os.environ.get("TRIGGER_WORDS", "").split(",")
    if t.strip()
}

FAREWELL_TEXT = (
    "Thank you for the conversation. I hope my reflections have been useful. "
    "The session is now cleared for the next visitor."
)


def _is_trigger_word(text: str) -> bool:
    """Return True iff `text` exactly matches a configured trigger phrase
    after lowercase + trailing-punctuation normalization. Exact match is
    intentional — 'thank you' triggers, but 'thank you, tell me about X'
    does not (visitor is being polite while continuing the conversation)."""
    if not TRIGGER_WORDS or not text:
        return False
    normalized = text.lower().strip().rstrip(".,!?;: ")
    return normalized in TRIGGER_WORDS


@st.cache_resource(
    show_spinner=(
        "Warming up the knowledge base — loading the embedding model, the "
        "954-chunk vector index, and the local voice model. This happens "
        "once per session."
    )
)
def _load_backend():
    """Heavy backend imports + warm up the embedder, ChromaDB collection,
    and Piper voice so the first user question doesn't pay the cold-start
    cost. Cached across script reruns; runs ONCE per Streamlit server
    session."""
    from backend.adapters import WebAdapter
    from backend.orchestrator import answer_question
    from backend.stt import transcribe
    from backend.tts import synthesize
    from backend.tts import _voice as _piper_voice
    from backend.retrieval import _model, _collection
    from backend import catalog

    # Pre-load the heavy stuff so the first question is fast.
    _model()         # sentence-transformers model into memory
    _collection()    # open ChromaDB (fast but caches the SQLite handle)
    _piper_voice()   # download (if needed) + load Piper TTS voice into memory

    return WebAdapter, answer_question, transcribe, synthesize, catalog


WebAdapter, answer_question, transcribe, synthesize, catalog = _load_backend()


if "history" not in st.session_state:
    st.session_state.history = []
if "last_audio_key" not in st.session_state:
    st.session_state.last_audio_key = None
if "pending_catalog" not in st.session_state:
    st.session_state.pending_catalog = None  # original catalog query, awaiting year

adapter = WebAdapter()


def _catalog_meta(items: list[dict]) -> dict:
    """Build the meta dict for a catalog answer — items become citations."""
    return {
        "citations": [
            {
                "title": item.get("title"),
                "date": item.get("date"),
                "url": item.get("url"),
                "bucket": item.get("bucket"),
                "distance": 0.0,
                "citation_safe": True,
            }
            for item in items
        ],
        "latency_ms": 0,
        "fallback": False,
        "fallback_reason": None,
    }


def _empty_meta() -> dict:
    return {
        "citations": [],
        "latency_ms": 0,
        "fallback": False,
        "fallback_reason": None,
    }


@st.cache_data(show_spinner=False)
def _transcribe_audio(audio_bytes: bytes) -> str:
    return transcribe(audio_bytes)


@st.cache_data(show_spinner=False)
def _synthesize_cached(text: str) -> bytes:
    """Cached TTS for historical replays. Returns b'' on failure so we don't
    poison the cache with exceptions and don't break the conversation if
    Microsoft's TTS endpoint hiccups for one chunk."""
    try:
        return synthesize(text)
    except Exception:  # noqa: BLE001 — TTS hiccups are non-fatal for the chat
        return b""


def _render_meta(meta: dict) -> None:
    citations = meta.get("citations") or []
    if citations:
        with st.expander(f"Sources ({len(citations)})"):
            for c in citations:
                if isinstance(c, dict):
                    safe_tag = "" if c.get("citation_safe", True) else " ⚠ unsafe"
                    line = (
                        f"**[{c.get('bucket','?')}] {c.get('title','?')}** "
                        f"({c.get('date','?')}) — distance {c.get('distance','?')}{safe_tag}"
                    )
                    if c.get("url"):
                        line += f"  \n[{c['url']}]({c['url']})"
                    st.markdown(line)
                else:
                    st.caption(str(c))
    else:
        st.caption("Sources: none (retrieval found no chunks above threshold)")
    if meta.get("fallback"):
        st.warning(
            f"Fallback used - {meta.get('fallback_reason') or 'low retrieval confidence'}"
        )
    st.caption(f"Latency: {meta['latency_ms']:.0f} ms")


# Render existing history (no autoplay on past turns)
for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.write(turn["content"])
        if turn["role"] == "assistant":
            audio = _synthesize_cached(turn["content"])
            if audio:
                st.audio(audio, format="audio/wav")
            _render_meta(turn["meta"])

# Inputs: voice (primary) + text fallback
st.divider()
audio_input = st.audio_input("Record your question:")
typed_question = st.chat_input("...or type it (fallback)")

question: str | None = None
if audio_input is not None:
    audio_bytes = audio_input.getvalue()
    audio_key = hash(audio_bytes)
    if audio_key != st.session_state.last_audio_key:
        with st.spinner("Transcribing..."):
            question = _transcribe_audio(audio_bytes)
        st.session_state.last_audio_key = audio_key
elif typed_question:
    question = typed_question

if question:
    # Trigger-word check first — visitor saying "thank you" / "next question"
    # / "that's enough" ends the session for the next visitor. No LLM call,
    # no history append, just a brief CJ-voice farewell + state reset.
    if _is_trigger_word(question):
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            adapter.speak(FAREWELL_TEXT, autoplay=True)
        st.session_state.history = []
        st.session_state.last_audio_key = None
        st.session_state.pending_catalog = None
        st.success("Conversation cleared — ready for the next visitor.")
        st.stop()

    # Catalog-mode turn 2 — we previously asked "for which year?" and the
    # visitor's reply may contain that year. If yes, answer directly with
    # the column list. If no year, cancel pending and treat as a new query.
    if st.session_state.pending_catalog:
        year = catalog.extract_year(question)
        if year:
            with st.chat_message("user"):
                st.write(question)
            items = catalog.list_columns_by_year(year, n=5)
            response_text = catalog.format_catalog_response(year, items)
            with st.chat_message("assistant"):
                adapter.speak(response_text, autoplay=True)
                meta = _catalog_meta(items)
                _render_meta(meta)
            st.session_state.history.append({"role": "user", "content": question})
            st.session_state.history.append(
                {"role": "assistant", "content": response_text, "meta": meta}
            )
            st.session_state.pending_catalog = None
            st.stop()
        else:
            # Reply didn't contain a year — drop pending state and let this
            # message flow through as a normal question (or new catalog query).
            st.session_state.pending_catalog = None

    # Catalog-mode turn 1 — detect catalog query and either answer (if year
    # is in the query) or ask for the year as a clarification turn.
    if catalog.is_catalog_query(question):
        year = catalog.extract_year(question)
        if year:
            # User specified the year directly — single-turn catalog answer.
            with st.chat_message("user"):
                st.write(question)
            items = catalog.list_columns_by_year(year, n=5)
            response_text = catalog.format_catalog_response(year, items)
            with st.chat_message("assistant"):
                adapter.speak(response_text, autoplay=True)
                meta = _catalog_meta(items)
                _render_meta(meta)
            st.session_state.history.append({"role": "user", "content": question})
            st.session_state.history.append(
                {"role": "assistant", "content": response_text, "meta": meta}
            )
            st.stop()
        else:
            # Ask for the year as a clarification turn.
            with st.chat_message("user"):
                st.write(question)
            clarification = (
                "I would be glad to share. For which year? "
                "My published columns span roughly from 2011 through 2026."
            )
            with st.chat_message("assistant"):
                adapter.speak(clarification, autoplay=True)
                _render_meta(_empty_meta())
            st.session_state.history.append({"role": "user", "content": question})
            st.session_state.history.append(
                {"role": "assistant", "content": clarification, "meta": _empty_meta()}
            )
            st.session_state.pending_catalog = question
            st.stop()

    # Render the user message immediately for responsiveness; only commit to
    # history once the assistant turn fully succeeds, so a mid-turn failure
    # never leaves an orphan user message in the conversation.
    with st.chat_message("user"):
        st.write(question)

    llm_history = [
        {"role": t["role"], "content": t["content"]}
        for t in st.session_state.history
    ]

    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = answer_question(question, llm_history)
            meta = {
                "citations": response.citations,
                "latency_ms": response.latency_ms,
                "fallback": response.fallback,
                "fallback_reason": response.fallback_reason,
            }
            adapter.speak(response.text, autoplay=True)
            _render_meta(meta)

        # Both turns succeeded — commit atomically.
        st.session_state.history.append({"role": "user", "content": question})
        st.session_state.history.append(
            {"role": "assistant", "content": response.text, "meta": meta}
        )
    except Exception as e:  # noqa: BLE001 — friendly catch-all for the chat
        st.error(
            f"Sorry, something went wrong on this turn: "
            f"`{type(e).__name__}: {e}`. Please try asking again."
        )
