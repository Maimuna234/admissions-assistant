# Admissions Assistant — MSc Research Project

A **Retrieval-Augmented Generation (RAG)** system for UK university admissions comparison, built as part of an MSc research project. The system enables students and admissions tutors to compare Computer Science undergraduate programmes across 11 UK universities using structured data, vector search, and large language model synthesis.

---

## Project Overview

The system answers questions like:
- *"Compare University of Liverpool vs University of Leeds Computer Science BSc across entry requirements, salary outcomes, and NSS teaching quality"*
- *"What is the tuition fee and employment rate for Computer Science at these universities?"*
- *"Which university has the better BCS accreditation and placement year options?"*

It combines three evidence layers — a structured SQLite database (2,739 course records), a ChromaDB vector store (206 documents), and a curated JSON knowledge base (11 universities) — and routes each query to the right engine before synthesising a grounded, cited answer via Google Gemini.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser UI  (served at /ui)                                         │
│  Three-column layout: Tutor Controls | Comparison Summary | Citations│
└──────────────────────────┬──────────────────────────────────────────┘
                           │ POST /api/chat
┌──────────────────────────▼──────────────────────────────────────────┐
│  FastAPI Layer  (openwebui_api.py)                                   │
│  - Sanitises & enriches tutor prompt with selected priorities        │
│  - Maps priority labels → SQL column keywords for routing            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  RAG Orchestrator  (rag_orchestrator.py)                             │
│                                                                      │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────────────┐   │
│  │ QueryRouter │   │ CustomHybrid │   │ KnowledgeBase          │   │
│  │ SQL routing │   │ Retriever    │   │ FallbackRetriever      │   │
│  │ Intent clfy │   │ BM25 + dense │   │ JSON KB search         │   │
│  └──────┬──────┘   └──────┬───────┘   └────────────┬───────────┘   │
│         │                 │                        │               │
│  ┌──────▼──────────────────▼────────────────────────▼──────────┐   │
│  │          Evidence Fusion & Grounding Layer                   │   │
│  │  _run_priority_comparison() — full structured comparison     │   │
│  │  _format_structured_response() — table/summary formatter     │   │
│  │  _synthesize_answer() — evidence-backed synthesis            │   │
│  │  _postprocess_grounded_answer() — citation + token overlap   │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                        │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │  Google Gemini LLM  (gemini-2.0-flash / 2.5-flash)           │   │
│  │  - Structured priority comparison with section-by-section     │   │
│  │    Winner + Overall Recommendation table                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

Data Sources
┌────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐
│ admissions_        │  │ chroma_db/           │  │ clearing_        │
│ structured.db      │  │ (ChromaDB)           │  │ knowledge_base   │
│ 2,739 course rows  │  │ 206 vector documents │  │ .json            │
│ 34 columns per row │  │ BM25 + dense search  │  │ 11 universities  │
│ SQLite             │  │ all-MiniLM-L6-v2     │  │ 8 knowledge      │
│                    │  │ embeddings           │  │ layers each      │
└────────────────────┘  └──────────────────────┘  └──────────────────┘
```

---

## Data Sources

### 1. `admissions_structured.db` — Structured Course Facts (2,739 rows × 34 columns)
Scraped and normalised from Discover Uni, UCAS, and university websites.

| Column group | Fields |
|---|---|
| Identity | `university`, `course_title`, `ucas_code`, `kis_course_id`, `kis_mode` |
| Course structure | `duration_years`, `is_honours`, `has_placement_year`, `has_year_abroad`, `has_foundation_year` |
| Entry | `alevel_requirement`, `entry_tariff`, `pct_entrants_alevel`, `pct_entrants_bacc` |
| Fees | `tuition_fee_uk`, `tuition_fee_intl` |
| Outcomes | `employment_rate_15m`, `pct_professional_managerial`, `median_salary_go`, `median_salary_leo3`, `median_salary_leo5` |
| Quality | `nss_teaching_satisfaction`, `nss_facilities_resources`, `nss_mental_wellbeing`, `tef_overall_rating`, `tef_student_experience` |
| Accreditation | `bcs_accredited`, `final_year_project_credits` |
| Rankings | `guardian_rank`, `cug_rank`, `qs_rank` |

### 2. `chroma_db/` — Vector Store (206 documents)
Chunked and embedded using `all-MiniLM-L6-v2`. Retrieved via **Hybrid BM25 + dense Reciprocal Rank Fusion (RRF)**. Covers curriculum, placements, facilities, and entry requirements for 11 universities.

### 3. `clearing_knowledge_base.json` — Curated KB (11 universities)
Hand-curated and scraper-enriched JSON with 8 knowledge layers per university:
`curriculum_year_1/2/3`, `industrial_placements`, `infrastructure_and_facilities`, `entry_requirements`, `student_support`, `career_outcomes`

---

## Universities Covered

| University | DB Name |
|---|---|
| University of Liverpool | The University of Liverpool |
| University of Leeds | University of Leeds |
| University of Manchester | The University of Manchester |
| University of Sheffield | University of Sheffield |
| Lancaster University | Lancaster University |
| University of Birmingham | University of Birmingham |
| University of Nottingham | University of Nottingham |
| Newcastle University | Newcastle University |
| Manchester Metropolitan University | Manchester Metropolitan University |
| Liverpool John Moores University | Liverpool John Moores University |
| Queen Mary University London | Queen Mary University London |

---

## Student Priorities (UI)

The UI exposes 6 comparison priorities, each mapped to specific DB columns:

| Priority | DB columns used |
|---|---|
| Entry Requirements | `alevel_requirement`, `entry_tariff`, `pct_entrants_alevel`, `has_foundation_year` |
| Curriculum & Accreditation | `bcs_accredited`, `final_year_project_credits`, `has_placement_year`, `has_year_abroad` + KB curriculum layers |
| Graduate Outcomes & Salary | `median_salary_leo3`, `median_salary_leo5`, `employment_rate_15m`, `pct_professional_managerial` |
| Fees & Cost | `tuition_fee_uk`, `tuition_fee_intl` |
| Teaching Quality & NSS | `nss_teaching_satisfaction`, `nss_mental_wellbeing`, `nss_facilities_resources`, `tef_overall_rating` |
| University Rankings | `guardian_rank`, `cug_rank`, `qs_rank` |

When priorities are selected, the system runs `_run_priority_comparison()` which fetches SQL + KB data for both universities and calls Gemini with a structured prompt to produce a section-by-section comparison with a Winner and Overall Recommendation table.

---

## Key Files

| File | Purpose |
|---|---|
| `rag_orchestrator.py` | Core RAG pipeline: routing, retrieval, grounding, Gemini synthesis |
| `openwebui_api.py` | FastAPI server + embedded browser UI served at `/ui` |
| `seed_db.py` | DB schema management: import, migrate, seed `course_facts` |
| `ingest.py` | Document chunking + ChromaDB ingestion pipeline |
| `build_knowledge_base.py` | Builds `clearing_knowledge_base.json` from scrapers |
| `evaluator.py` | RAG evaluation suite (ROUGE, BERTScore, token overlap) |
| `competitor_scraper.py` | Scrapes qualitative course data from university websites |
| `ucas_scraper.py` | Scrapes UCAS entry data |
| `ranking_scraper.py` | Scrapes Guardian/CUG/QS rankings |
| `vector_indexer.py` | Indexes documents into ChromaDB |
| `golden_dataset.csv` | Ground-truth Q&A pairs for evaluation |
| `evaluation_results_final.csv` | Latest evaluation run results |

---

## Running the System

### Prerequisites
- Python 3.11+
- A Google Gemini API key in `.env` as `GEMINI_API_KEY`

### Install
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt.txt
```

### Start the API server
```bash
.venv\Scripts\python.exe -m uvicorn openwebui_api:app --host 127.0.0.1 --port 8000
```

Or use the provided batch file:
```bash
run_interface.bat
```

Then open **http://127.0.0.1:8000/ui** in your browser.

### Rebuild the vector index (if needed)
```bash
python ingest.py
python vector_indexer.py
```

### Re-import the structured DB
```bash
python seed_db.py
```

### Run evaluations
```bash
python evaluator.py
```

---

## Query Routing Logic

```
Incoming query
     │
     ▼
classify_intent()
     ├── SQL keywords detected? (fee, salary, ranking, nss, tef, tariff, ...)
     │        └── execute_sql() → course_facts table
     │
     └── No → HYBRID_VECTOR
              └── CustomHybridRetriever (BM25 + ChromaDB dense)
                       └── fallback → KnowledgeBaseFallbackRetriever (JSON)

If priorities given AND both universities targeted:
     └── _run_priority_comparison()
              ├── SQL: fetch all 34 columns for both unis
              ├── KB: supplement null/placeholder fields
              ├── Vector: fetch curriculum/qualitative docs
              └── Gemini: structured prompt → section-by-section output
```

---

## Evaluation

The system is evaluated against a golden dataset of 50+ question-answer pairs using:
- **ROUGE-1/2/L** — lexical overlap
- **BERTScore** — semantic similarity  
- **Token overlap** — custom grounding metric
- **Abstention rate** — how often the system correctly declines to answer

Results are written to `evaluation_results_final.csv` and summarised in `evaluation_summary.csv`.

---

## Docker Deployment (OpenWebUI integration)

```bash
docker compose -f docker-compose.openwebui.yml up
```

This starts:
- `admissions-api` — the FastAPI RAG server on port 8000
- `open-webui` — the OpenWebUI frontend connected to the API as model `admissions-rag`

See `OPENWEBUI_DEPLOYMENT.md` for full setup instructions.

## Streamlit Community Cloud Deployment

This repository also supports deployment to Streamlit Community Cloud. The app entrypoint is `app.py` and the deployment guide is available in `STREAMLIT_DEPLOYMENT.md`.

### Quick steps
1. Push the repository to GitHub.
2. Create a Streamlit Cloud app pointing to `app.py`.
3. Add your Gemini API key as a Streamlit secret named `GEMINI_API_KEY`.
4. Deploy.

---

## Environment Variables

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key (required) |
| `GEMINI_MODELS` | Comma-separated model list (default: `gemini-2.0-flash,gemini-2.5-flash,gemini-1.5-flash`) |
| `EVALUATION_SUMMARY_PATH` | Path to evaluation summary CSV |
