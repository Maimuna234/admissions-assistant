import os

import streamlit as st

from rag_orchestrator import AdmissionsRAGOrchestrator


st.set_page_config(page_title="Admissions Assistant", page_icon="🎓", layout="wide")

st.title("Admissions Assistant")
st.caption("Compare UK university courses using the local admissions evidence and retrieval pipeline.")

if "GEMINI_API_KEY" not in os.environ:
    try:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = AdmissionsRAGOrchestrator(
        db_directory="./chroma_db",
        sql_db_path="./admissions_structured.db",
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ask about fees, salaries, entry requirements, placements, or course comparisons")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Searching the evidence..."):
        result = st.session_state.orchestrator.query_pipeline(prompt)

    answer = result.get("answer", "No answer was generated.")
    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)
