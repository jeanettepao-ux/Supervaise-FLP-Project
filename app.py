import streamlit as st

from backend.adapters import WebAdapter
from backend.orchestrator import answer_question
from backend.stt import transcribe
from backend.tts import synthesize

st.set_page_config(page_title="CJ Panganiban - May 30 Demo", layout="centered")
st.title("CJ Panganiban - May 30 Demo")
st.caption(
    "Pre-prototype. Voice in / voice out. Answers are not yet source-grounded - "
    "RAG retrieval arrives at the Day-15 convergence."
)

if "history" not in st.session_state:
    st.session_state.history = []
if "last_audio_key" not in st.session_state:
    st.session_state.last_audio_key = None

adapter = WebAdapter()


@st.cache_data(show_spinner=False)
def _transcribe_audio(audio_bytes: bytes) -> str:
    return transcribe(audio_bytes)


@st.cache_data(show_spinner=False)
def _synthesize_cached(text: str) -> bytes:
    return synthesize(text)


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
            try:
                st.audio(_synthesize_cached(turn["content"]), format="audio/mp3")
            except Exception:
                pass
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
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    llm_history = [
        {"role": t["role"], "content": t["content"]}
        for t in st.session_state.history[:-1]
    ]
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

    st.session_state.history.append(
        {"role": "assistant", "content": response.text, "meta": meta}
    )
