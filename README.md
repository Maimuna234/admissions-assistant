# Admissions Assistant — MSc Research Project

A **Retrieval-Augmented Generation (RAG)** system for UK university admissions comparison, built as part of an MSc research project. The system enables students and admissions tutors to compare Computer Science undergraduate programmes across 11 UK universities using structured data, vector search, and large language model synthesis.

GitHub repository: https://github.com/Maimuna234/admissions-assistant.git

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
| University of Liverpool | University of Liverpool |
| University of Leeds | University of Leeds |
| University of Manchester | University of Manchester |
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

The repository has two entry points:
- The primary interface is the FastAPI app in `openwebui_api.py`, served with a browser UI at `/ui`.
- The older Streamlit prototype is `app.py`; it is useful only for local testing and is not the main project interface.

### Prerequisites
- Python 3.11+
- Git
- A Google Gemini API key
- A local terminal with PowerShell or Command Prompt on Windows

### 1) Clone and open the project
```powershell
cd C:\path\to\admissions-assistant
```

### 2) Create a Python virtual environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use:
```powershell
.\.venv\Scripts\activate.bat
```

### 3) Install dependencies
From the project root:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If you plan to run the legacy Streamlit prototype as well, install it separately:
```powershell
pip install streamlit
```

### 4) Add your Gemini API key
Create a file named `.env` in the project root with:
```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```

This is read automatically by the API layer when the app starts.

### 5) Start the main application
Run the backend server:
```powershell
python -m uvicorn openwebui_api:app --host 127.0.0.1 --port 8000
```

Then open this in your browser:
```text
http://127.0.0.1:8000/ui
```

You can also use the included Windows helper script:
```powershell
.\run_interface.bat
```

### 6) Run the legacy Streamlit prototype (optional)
```powershell
streamlit run app.py
```

This opens the older dashboard interface, but the project’s supported interface is the FastAPI `/ui` page above.

### 7) Rebuild data if needed
If the local indices or database are missing or stale, rebuild them:
```powershell
python seed_db.py
python ingest.py
python vector_indexer.py
```

### 8) Run evaluation scripts
```powershell
python evaluator.py
```

### 9) Docker / OpenWebUI deployment (optional)
```powershell
docker compose -f docker-compose.openwebui.yml up
```

This starts the API and OpenWebUI stack. See `OPENWEBUI_DEPLOYMENT.md` for the full deployment guide.

---

## Troubleshooting

- If Python complains about missing packages, re-run:
  ```powershell
  pip install -r requirements.txt
  ```
- If the app cannot access the model, check that `.env` exists and contains `GEMINI_API_KEY`.
- If the UI loads but retrieval is empty, rebuild the data files:
  ```powershell
  python seed_db.py
  python ingest.py
  python vector_indexer.py
  ```
- If the backend does not start on port 8000, make sure no other process is already using that port and retry the command.

---

## Expected local workflow

1. Create venv and install dependencies.
2. Set your `.env` with `GEMINI_API_KEY`.
3. Start the API with `uvicorn`.
4. Open `http://127.0.0.1:8000/ui`.
5. Query the system, or rebuild the DB/index if you have changed the data source.

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

## Interface Policy

OpenWebUI is the supported main interface for this project in both local testing and production deployments.

- Local testing: run `openwebui_api.py` directly or use `docker-compose.openwebui.yml`
- Production deployment: use the OpenWebUI stack documented in `OPENWEBUI_DEPLOYMENT.md`
- Streamlit is not the primary interface for this repository

---

## Environment Variables

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key (required) |
| `GEMINI_MODELS` | Comma-separated model list (default: `gemini-2.0-flash,gemini-2.5-flash,gemini-1.5-flash`) |
| `EVALUATION_SUMMARY_PATH` | Path to evaluation summary CSV |
