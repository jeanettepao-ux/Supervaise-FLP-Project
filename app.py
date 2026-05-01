import streamlit as st

from backend.orchestrator import answer_question
from backend.stt import transcribe


@st.cache_data(show_spinner=False)
def _transcribe_audio(audio_bytes: bytes) -> str:
    return transcribe(audio_bytes)


st.title("CJ Panganiban — May 30 Demo")

audio = st.audio_input("Record your question:")
typed_question = st.text_input("…or type it:")

question = ""
if audio is not None:
    with st.spinner("Transcribing…"):
        question = _transcribe_audio(audio.getvalue())
    st.caption(f"Heard: {question}")
elif typed_question:
    question = typed_question

if question:
    with st.spinner("Thinking…"):
        response = answer_question(question)
    st.write(response.text)
