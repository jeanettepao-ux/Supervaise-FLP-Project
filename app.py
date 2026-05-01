import streamlit as st

from backend.orchestrator import answer_question

st.set_page_config(page_title="CJ Panganiban - May 30 Demo", layout="centered")
st.title("CJ Panganiban - May 30 Demo")
st.caption(
    "Pre-prototype. Answers are not yet source-grounded - "
    "RAG retrieval arrives at the Day-15 convergence."
)

if "history" not in st.session_state:
    st.session_state.history = []


def _render_assistant(content: str, meta: dict) -> None:
    st.write(content)
    citations = meta.get("citations") or []
    if citations:
        with st.expander(f"Sources ({len(citations)})"):
            for c in citations:
                st.caption(str(c))
    else:
        st.caption("Sources: none yet (retrieval pipeline not wired)")
    if meta.get("fallback"):
        st.warning(
            f"Fallback used - {meta.get('fallback_reason') or 'low retrieval confidence'}"
        )
    st.caption(f"Latency: {meta['latency_ms']:.0f} ms")


for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        if turn["role"] == "assistant":
            _render_assistant(turn["content"], turn["meta"])
        else:
            st.write(turn["content"])


if question := st.chat_input("Ask CJ a question..."):
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
        _render_assistant(response.text, meta)

    st.session_state.history.append(
        {"role": "assistant", "content": response.text, "meta": meta}
    )
