import os

import streamlit as st

from rag_orchestrator import AdmissionsRAGOrchestrator


st.set_page_config(page_title="Admissions Assistant", page_icon="🎓", layout="wide")

st.title("Admissions Assistant")
st.caption("Admissions tutor dashboard for grounded programme comparisons.")

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

if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_error" not in st.session_state:
    st.session_state.last_error = None

priority_options = [
    "Entry Requirements",
    "Curriculum & Accreditation",
    "Graduate Outcomes & Salary",
    "Fees & Cost",
    "Teaching Quality & NSS",
    "University Rankings",
]

with st.sidebar:
    st.header("Admissions Tutor Input")
    target_programme = st.text_input("Target programme", value="Computer Science BSc - University of Liverpool")
    baseline_university = st.text_input("Baseline university", value="University of Liverpool")
    competitor_university = st.selectbox(
        "Competitor university",
        [
            "University of Leeds",
            "University of Sheffield",
            "University of Manchester",
            "Lancaster University",
            "University of Nottingham",
        ],
        index=0,
    )
    priorities = st.multiselect(
        "Student priorities",
        priority_options,
        default=["Entry Requirements", "Curriculum & Accreditation", "Graduate Outcomes & Salary"],
    )
    tutor_prompt = st.text_area(
        "Tutor prompt",
        value="Compare the target programme against the selected competitor university and return a short decision summary.",
    )
    submitted = st.button("Compare", use_container_width=True)

if submitted:
    with st.spinner("Searching the evidence..."):
        try:
            st.session_state.last_result = st.session_state.orchestrator.query_pipeline(
                tutor_prompt,
                target_competitor=competitor_university,
                target_programme=target_programme,
                target_baseline=baseline_university,
                priorities=priorities,
            )
            st.session_state.last_error = None
        except Exception as exc:
            st.session_state.last_result = {
                "answer": f"The comparison could not be generated. Please try again. Error: {exc}",
                "citations": [],
                "confidence_score": 0.0,
            }
            st.session_state.last_error = str(exc)

left_col, right_col = st.columns([1.35, 0.95], gap="large")

with left_col:
    st.subheader("Comparison summary")
    if st.session_state.last_result:
        answer = st.session_state.last_result.get("answer", "No answer was generated.")
        st.markdown(
            f"<div style='padding:1rem 1.1rem;border:1px solid #dce7e0;border-radius:16px;background:#f8fcfa;line-height:1.6;'>\n{answer}\n</div>",
            unsafe_allow_html=True,
        )
        confidence = st.session_state.last_result.get("confidence_score")
        if confidence is not None:
            st.caption(f"Confidence score: {confidence:.2f}")
        if st.session_state.last_error:
            st.warning(st.session_state.last_error)
    else:
        st.info("Your verified comparison will appear here.")

with right_col:
    st.subheader("Evidence")
    if st.session_state.last_result:
        citations = st.session_state.last_result.get("citations", []) or []
        if citations:
            for idx, item in enumerate(citations[:5], start=1):
                source = item.get("source") or "Local evidence"
                snippet = item.get("snippet") or item.get("content") or ""
                st.markdown(f"**[{idx}] {source}**")
                if snippet:
                    st.write(snippet)
                st.divider()
        else:
            st.write("No citations returned.")
    else:
        st.write("Citations will appear here once a comparison is run.")
