import streamlit as st

st.title("CJ Panganiban — May 30 Demo")

question = st.text_input("Ask a question:")

if question:
    st.write("(answer placeholder — orchestration not wired yet)")
