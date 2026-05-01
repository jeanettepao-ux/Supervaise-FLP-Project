import streamlit as st

from backend.orchestrator import answer_question

st.title("CJ Panganiban — May 30 Demo")

question = st.text_input("Ask a question:")

if question:
    response = answer_question(question)
    st.write(response.text)
