import os
import re
import time
import json
import sqlite3
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Okapi
from dotenv import load_dotenv


class KnowledgeBaseFallbackRetriever:
    """A deterministic fallback retriever over the local knowledge base JSON file."""

    def __init__(self, knowledge_base_path="clearing_knowledge_base.json"):
        self.knowledge_base_path = knowledge_base_path
        self._entries = None

    def _load_entries(self):
        if not os.path.exists(self.knowledge_base_path):
            return []
        with open(self.knowledge_base_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def search(
        self,
        query: str,
        top_k: int = 5,
        rrf_k: int = 60,
        target_competitor: str | None = None,
        allowed_institutions: list[str] | None = None,
    ):
        if self._entries is None:
            self._entries = self._load_entries()
        if not self._entries:
            return []

        query_lower = query.lower()
        expanded_terms = set()
        for term in query_lower.replace("?", "").split():
            if len(term) > 2:
                expanded_terms.add(term)

        if any(term in query_lower for term in ["entry", "admission", "admissions", "requirements", "requirement"]):
            expanded_terms.update(["entry", "requirements", "requirement", "admission", "admissions"])
        if any(term in query_lower for term in ["support", "student", "students", "wellbeing", "tutoring"]):
            expanded_terms.update(["student", "students", "support", "wellbeing", "tutoring", "personal"])
        if any(term in query_lower for term in ["career", "salary", "employment", "graduate", "outcomes"]):
            expanded_terms.update(["career", "salary", "employment", "graduate", "outcomes"])
        if any(term in query_lower for term in ["leeds", "sheffield", "manchester", "lancaster", "birmingham", "nottingham", "newcastle", "liverpool", "queen mary"]):
            expanded_terms.update(["university", "course", "computer science", "bsc"])

        scored_docs = []
        allowed_set = {name.lower() for name in (allowed_institutions or []) if name}
        for entry in self._entries:
            institution_name = entry.get("university_name", "")
            if target_competitor and institution_name.lower() != target_competitor.lower():
                continue
            if allowed_set and institution_name.lower() not in allowed_set:
                continue

            text_parts = []
            text_parts.append(institution_name)
            text_parts.append(entry.get("course_code", ""))
            text_parts.append(json.dumps(entry.get("metrics", {})))
            for layer_name, layer_content in entry.get("knowledge_layers", {}).items():
                text_parts.append(f"{layer_name}: {layer_content}")
            text = " ".join(text_parts).lower()

            overlap = 0
            for term in expanded_terms:
                if len(term) > 2 and term in text:
                    overlap += 1
                else:
                    singular = term[:-1] if len(term) > 3 else term
                    if singular and singular in text:
                        overlap += 0.5

            institution_bonus = 0.0
            for token in query_lower.replace("?", "").split():
                if len(token) > 2 and token in institution_name.lower():
                    institution_bonus += 0.6

            metadata_bonus = 0.0
            if any(term in query_lower for term in ["module", "modules", "curriculum", "year"]):
                if any("curriculum" in layer_name for layer_name in entry.get("knowledge_layers", {}).keys()):
                    metadata_bonus += 0.4
            if any(term in query_lower for term in ["tuition", "fee", "salary", "employment", "statistical", "duration", "how long"]):
                metadata_bonus += 0.2
            if any(term in query_lower for term in ["ucas", "code"]):
                metadata_bonus += 0.2

            score = overlap + metadata_bonus + institution_bonus
            scored_docs.append((score, entry))

        scored_docs.sort(key=lambda item: item[0], reverse=True)

        results = []
        for _, entry in scored_docs[:top_k]:
            content = []
            content.append(f"Institution: {entry.get('university_name', 'Unknown')}")
            content.append(f"Course Code: {entry.get('course_code', 'N/A')}")
            for layer_name, layer_content in entry.get("knowledge_layers", {}).items():
                content.append(f"{layer_name}: {layer_content}")
            results.append(
                Document(
                    page_content="\n".join(content),
                    metadata={
                        "source_url": entry.get("metadata_reference", {}).get("source_url", "local_knowledge_base"),
                        "data_layer": "knowledge_base_fallback",
                        "institution": entry.get("university_name", "Unknown"),
                    },
                )
            )
        return results

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - environment fallback
    genai = None

# Vector DB & Embedding Imports
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
except ImportError:  # pragma: no cover - environment fallback
    class Document:
        def __init__(self, page_content, metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}

    HuggingFaceEmbeddings = None
    Chroma = None

# LLM & Chain Imports
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_ollama import OllamaLLM
    from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough
except ImportError:  # pragma: no cover - environment fallback
    class ChatGoogleGenerativeAI:
        def __init__(self, *args, **kwargs):
            pass

    class OllamaLLM:
        def __init__(self, *args, **kwargs):
            pass

    class _ChainFallback:
        def __ror__(self, other):
            return self

        def __or__(self, other):
            return self

        def invoke(self, value):
            return "Insufficient information in the provided context to answer this question reliably."

    class ChatPromptTemplate(_ChainFallback):
        @classmethod
        def from_messages(cls, messages):
            return cls()

    class SystemMessagePromptTemplate(_ChainFallback):
        @classmethod
        def from_template(cls, template):
            return cls()

    class HumanMessagePromptTemplate(_ChainFallback):
        @classmethod
        def from_template(cls, template):
            return cls()

    class StrOutputParser(_ChainFallback):
        pass

    class RunnablePassthrough(_ChainFallback):
        pass

# Disable ChromaDB telemetry logging
os.environ["CHROMA_TELEMETRY_IMPL"] = "None"

# Load environment variables (.env)
project_root = Path(__file__).resolve().parent
load_dotenv(dotenv_path=project_root / ".env")


class CustomHybridRetriever:
    """Combines BM25 sparse retrieval, dense vector search, and metadata-aware reranking."""

    def __init__(self, chroma_store):
        self.collection = chroma_store._collection
        all_docs = self.collection.get()
        self.doc_ids = all_docs.get("ids", [])
        self.documents = all_docs.get("documents", [])
        self.metadatas = all_docs.get("metadatas", [])

        tokenized_corpus = [str(doc).lower().split() for doc in self.documents] if self.documents else []
        self.bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

    def _expand_query(self, query: str):
        q = query.lower()
        expanded_terms = [q]

        if any(term in q for term in ["module", "modules", "curriculum", "year"]):
            expanded_terms.append("module curriculum year")
        if any(term in q for term in ["tuition", "fee", "salary", "employment", "statistical"]):
            expanded_terms.append("tuition fee salary employment")
        if any(term in q for term in ["ucas", "code"]):
            expanded_terms.append("ucas code course")
        if any(term in q for term in ["duration", "how long", "years"]):
            expanded_terms.append("duration years")

        return " ".join(expanded_terms)

    def _metadata_score(self, metadata: dict, query: str):
        q = query.lower()
        score = 0.0
        if not metadata:
            return score

        if "year" in q and metadata.get("academic_year"):
            score += 0.2
        if any(term in q for term in ["module", "modules", "curriculum"]):
            if metadata.get("content_type") == "curriculum":
                score += 0.3
        if any(term in q for term in ["tuition", "fee", "salary", "employment", "statistical", "duration"]):
            if metadata.get("content_type") == "financial_stats":
                score += 0.3
        if any(term in q for term in ["ucas", "code"]):
            if metadata.get("course_code"):
                score += 0.2
        return score

    def _phrase_overlap_score(self, query: str, document_text: str) -> float:
        query_terms = [term for term in query.lower().replace("?", "").split() if len(term) > 2]
        if not query_terms:
            return 0.0

        text = str(document_text or "").lower()
        overlap = sum(1 for term in query_terms if term in text)
        return overlap / max(1, len(query_terms))

    def search(
        self,
        query: str,
        top_k: int = 5,
        rrf_k: int = 60,
        target_competitor: str | None = None,
        allowed_institutions: list[str] | None = None,
    ):
        if not self.bm25:
            return []

        expanded_query = self._expand_query(query)
        tokenized_query = expanded_query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_top_indices = np.argsort(bm25_scores)[::-1][:top_k * 3]

        query_kwargs = {
            "query_texts": [expanded_query],
            "n_results": top_k * 3,
        }
        if target_competitor and not allowed_institutions:
            query_kwargs["where"] = {"institution": target_competitor}

        vector_results = self.collection.query(**query_kwargs)
        vector_ids = vector_results["ids"][0] if vector_results["ids"] else []

        rrf_scores = {}
        for rank, idx in enumerate(bm25_top_indices):
            d_id = self.doc_ids[idx]
            rrf_scores[d_id] = rrf_scores.get(d_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        for rank, d_id in enumerate(vector_ids):
            rrf_scores[d_id] = rrf_scores.get(d_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        allowed_set = {name.lower() for name in (allowed_institutions or []) if name}
        scored_results = []
        for d_id, score in rrf_scores.items():
            if d_id not in self.doc_ids:
                continue
            idx = self.doc_ids.index(d_id)
            metadata = self.metadatas[idx] if idx < len(self.metadatas) else {}
            if target_competitor and metadata.get("institution", "").lower() != target_competitor.lower():
                continue
            if allowed_set and metadata.get("institution", "").lower() not in allowed_set:
                continue
            document_text = self.documents[idx] if idx < len(self.documents) else ""
            phrase_overlap = self._phrase_overlap_score(query, document_text)
            scored_results.append((score + self._metadata_score(metadata, query) + phrase_overlap * 0.3, d_id, idx))

        scored_results.sort(key=lambda item: item[0], reverse=True)
        selected = scored_results[:top_k]

        results = []
        for _, d_id, idx in selected:
            results.append(
                Document(
                    page_content=self.documents[idx],
                    metadata=self.metadatas[idx]
                )
            )
        return results


class FallbackHybridRetriever:
    """No-op retriever used when the vector stack is unavailable."""
    def search(
        self,
        query: str,
        top_k: int = 5,
        rrf_k: int = 60,
        target_competitor: str | None = None,
        allowed_institutions: list[str] | None = None,
    ):
        return []


class QueryRouter:
    """Routes queries to structured SQL or unstructured Hybrid Retrieval."""
    def __init__(self, db_path="./university_stats.db"):
        self.db_path = db_path
        self._init_mock_db()
        self._ensure_structured_admissions_db()

    def _init_mock_db(self):
        """Creates a local SQLite DB for demonstration of structured data routing."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS course_stats (university TEXT, degree TEXT, duration_years INT, tuition_fee REAL, median_salary REAL)")
        c.execute("SELECT count(*) FROM course_stats")
        if c.fetchone()[0] == 0:
            stats = [
                ('University of Leeds', 'Computer Science BSc', 3, 9250.0, 31000.0),
                ('University of Sheffield', 'Computer Science BSc', 3, 9250.0, 31000.0),
                ('Lancaster University', 'Computer Science BSc', 3, 9250.0, 31000.0)
            ]
            c.executemany("INSERT INTO course_stats VALUES (?, ?, ?, ?, ?)", stats)
            conn.commit()
        conn.close()

    def _ensure_structured_admissions_db(self):
        source_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admissions_structured.db")
        if os.path.exists(self.db_path):
            try:
                conn = sqlite3.connect(self.db_path)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_facts'")
                has_table = cur.fetchone() is not None
                if has_table:
                    existing_cols = {col[1] for col in cur.execute("PRAGMA table_info(course_facts)").fetchall()}
                    # Re-import if the working DB is missing new schema columns.
                    schema_stale = not existing_cols.issuperset({"tuition_fee_uk", "median_salary_leo3", "alevel_requirement"})
                    if not schema_stale:
                        try:
                            from seed_db import ensure_course_facts_schema
                            ensure_course_facts_schema(self.db_path)
                        except Exception:
                            pass
                        cur.execute("SELECT COUNT(*) FROM course_facts")
                        if cur.fetchone()[0] > 0:
                            conn.close()
                            return
                conn.close()
            except Exception:
                pass

        if os.path.exists(source_db_path):
            try:
                from seed_db import import_structured_admissions_db
                import_structured_admissions_db(source_db_path, self.db_path)
                try:
                    from seed_db import ensure_course_facts_schema
                    ensure_course_facts_schema(self.db_path)
                except Exception:
                    pass
            except Exception as exc:
                print(f"⚠️ Failed to import admissions facts from {source_db_path}: {exc}")
                return
            return

        try:
            from seed_db import seed_verified_database
            seed_verified_database(self.db_path)
            try:
                from seed_db import ensure_course_facts_schema
                ensure_course_facts_schema(self.db_path)
            except Exception:
                pass
        except Exception:
            pass

    def classify_intent(self, query: str) -> str:
        """Determines if query targets structured stats or qualitative syllabus text."""
        sql_keywords = [
            "available seats", "grade threshold", "duration", "tuition", "fee", "salary",
            "credits", "how long", "placement", "project credits", "entry requirement",
            "ranking", "rank", "guardian", "league table", "qs rank", "tef", "nss",
            "satisfaction", "wellbeing", "accredited", "bcs", "entry tariff", "ucas points",
            "tariff", "a-level", "a level", "year abroad", "foundation year",
            "international fee", "employment rate", "median salary",
        ]
        if any(kw in query.lower() for kw in sql_keywords):
            return "SQL"
        return "HYBRID_VECTOR"

    def _programme_like_patterns(self, target_programme: str | None) -> list[str]:
        if not target_programme:
            return []

        raw = target_programme.strip()
        if not raw:
            return []

        patterns = [raw]
        lowered = raw.lower()
        for suffix in [" bsc", " bsc (hons)", " bsc hons", " (hons)", " hons"]:
            if lowered.endswith(suffix):
                trimmed = raw[: -len(suffix)].strip()
                if trimmed:
                    patterns.append(trimmed)

        if "computer science" in lowered:
            patterns.append("Computer Science")

        # Deduplicate while preserving order.
        seen = set()
        result = []
        for item in patterns:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def execute_sql(
        self,
        query: str,
        target_competitor: str | None = None,
        target_programme: str | None = None,
        target_baseline: str | None = None,
    ):
        """Executes query and returns results wrapped as standard Context Documents."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_facts'")
        has_richer_db = c.fetchone() is not None
        conn.close()

        if has_richer_db:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            column_info = c.execute("PRAGMA table_info(course_facts)").fetchall()
            available_columns = [column[1] for column in column_info]
            preferred_columns = [
                "university",
                "course_title",
                "ucas_code",
                "kis_course_id",
                "kis_mode",
                "duration_years",
                "is_honours",
                "has_foundation_year",
                "has_placement_year",
                "has_year_abroad",
                "is_distance_learning",
                "entry_tariff",
                "alevel_requirement",
                "pct_entrants_alevel",
                "pct_entrants_bacc",
                "tuition_fee_uk",
                "tuition_fee_intl",
                "tef_overall_rating",
                "tef_student_experience",
                "bcs_accredited",
                "employment_rate_15m",
                "pct_professional_managerial",
                "median_salary_go",
                "median_salary_leo3",
                "median_salary_leo5",
                "final_year_project_credits",
                "guardian_rank",
                "cug_rank",
                "qs_rank",
                "nss_teaching_satisfaction",
                "nss_facilities_resources",
                "nss_mental_wellbeing",
            ]
            selected_columns = [name for name in preferred_columns if name in available_columns]
            if not selected_columns:
                selected_columns = available_columns
            where_clauses = []
            params = []
            if "university" in available_columns:
                institutions = [name for name in [target_baseline, target_competitor] if name]
                if institutions:
                    placeholders = ", ".join(["?" for _ in institutions])
                    where_clauses.append(f"university IN ({placeholders})")
                    params.extend(institutions)
            if target_programme and "course_title" in available_columns:
                programme_patterns = self._programme_like_patterns(target_programme)
                if programme_patterns:
                    placeholders = " OR ".join(["course_title LIKE ?" for _ in programme_patterns])
                    where_clauses.append(f"({placeholders})")
                    params.extend([f"%{pattern}%" for pattern in programme_patterns])

            if where_clauses:
                c.execute(
                    f"SELECT {', '.join(selected_columns)} FROM course_facts WHERE {' AND '.join(where_clauses)}",
                    params,
                )
            else:
                c.execute(f"SELECT {', '.join(selected_columns)} FROM course_facts")
            rows = c.fetchall()
            columns = selected_columns
            conn.close()
            structured_data = [dict(zip(columns, row)) for row in rows]
            return [
                Document(
                    page_content=f"Structured Database Results: {json.dumps(structured_data, indent=2)}",
                    metadata={"source_url": "SQLite: course_facts table", "data_layer": "Structured DB"}
                )
            ]

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        where_clauses = []
        params = []
        institutions = [name for name in [target_baseline, target_competitor] if name]
        if institutions:
            placeholders = ", ".join(["?" for _ in institutions])
            where_clauses.append(f"university IN ({placeholders})")
            params.extend(institutions)
        if target_programme:
            programme_patterns = self._programme_like_patterns(target_programme)
            if programme_patterns:
                placeholders = " OR ".join(["degree LIKE ?" for _ in programme_patterns])
                where_clauses.append(f"({placeholders})")
                params.extend([f"%{pattern}%" for pattern in programme_patterns])

        if where_clauses:
            c.execute(f"SELECT * FROM course_stats WHERE {' AND '.join(where_clauses)}", params)
        else:
            c.execute("SELECT * FROM course_stats")
        rows = c.fetchall()
        columns = [description[0] for description in c.description]
        conn.close()

        structured_data = [dict(zip(columns, row)) for row in rows]
        return [
            Document(
                page_content=f"Structured Database Results: {json.dumps(structured_data, indent=2)}",
                metadata={"source_url": "SQLite: course_stats table", "data_layer": "Structured DB"}
            )
        ]


class AdmissionsRAGOrchestrator:
    def __init__(self, db_directory="./chroma_db", sql_db_path="./university_stats.db"):
        self.db_directory = db_directory
        
        # 1. Resolve API Key
        self.api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GIMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        self.gemini_models = None

        # 2. Initialize lightweight defaults; heavy dependencies are loaded lazily.
        self.embedding_engine = None
        self.vector_store = None
        self.hybrid_retriever = FallbackHybridRetriever()
        self.knowledge_base_retriever = KnowledgeBaseFallbackRetriever()

        # 3. Initialize Pipeline Components
        self.query_router = QueryRouter(db_path=sql_db_path)

        # 4. Construct Multi-Competitor System Prompt
        system_template = """You are an expert academic advisor system for undergraduate admissions.

STRICT GUARDRAILS & INSTRUCTIONS:
1. Answer ONLY from the provided context or database records. Do not use outside knowledge.
2. For factual questions, give a concise answer first, then a short evidence note with citations like [1], [2], [3].
3. For comparisons, use a compact markdown table with columns: University, Key Point, Evidence.
4. If a requested detail is not found in the context, say "Not Available" and keep it factual.
5. If the context is weak or ambiguous, say "Insufficient information in the provided context" rather than guessing.
6. Keep the tone professional, supportive, and admissions-focused.
7. Prioritize clarity over verbosity; avoid filler and speculative statements."""

        human_template = """Context / Database Records:
{context}

User Query:
{question}

Admissions Advisor Response:"""

        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ])
        self.review_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "review_log.jsonl")
        self.trace_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trace_log.jsonl")

    def _ensure_gemini_models(self):
        if self.gemini_models is None:
            configured_models = [
                model.strip()
                for model in os.getenv("GEMINI_MODELS", os.getenv("GEMINI_MODEL", "gemini-2.0-flash,gemini-2.5-flash,gemini-1.5-flash")).split(",")
                if model.strip()
            ]
            if self.api_key and configured_models:
                self.gemini_models = configured_models
            else:
                self.gemini_models = self._discover_available_gemini_models()
        return self.gemini_models

    def _ensure_vector_store(self):
        if self.vector_store is not None or not isinstance(self.hybrid_retriever, FallbackHybridRetriever):
            return

        if HuggingFaceEmbeddings is None or Chroma is None:
            print("⚠️ Vector store dependencies are unavailable. Running offline fallback mode.")
            return

        print("🔄 Loading vector database index...")
        try:
            self.embedding_engine = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self.vector_store = Chroma(
                persist_directory=self.db_directory,
                embedding_function=self.embedding_engine,
            )
            self.hybrid_retriever = CustomHybridRetriever(self.vector_store)
        except Exception as exc:
            print(f"⚠️ Unable to initialize Chroma vector store: {exc}. Falling back to offline mode.")
            self.embedding_engine = None
            self.vector_store = None
            self.hybrid_retriever = FallbackHybridRetriever()

    def _is_structured_admissions_query(self, user_query: str) -> bool:
        """Return True for SQL-style admissions questions that are best answered with structured summaries."""
        query_lower = user_query.lower()
        return any(term in query_lower for term in [
            "tuition",
            "fee",
            "salary",
            "employment",
            "median",
            "duration",
            "standard duration",
            "how long",
            "placement",
            "project credits",
            "entry requirement",
            "credits",
            "ranking",
            "rank",
            "guardian",
            "league table",
            "qs rank",
            "tef",
            "nss",
            "satisfaction",
            "wellbeing",
            "accredited",
            "bcs",
            "entry tariff",
            "ucas points",
            "tariff",
            "a-level",
            "a level",
            "year abroad",
            "foundation year",
            "international fee",
            "professional",
            "managerial",
        ])

    def _resolve_word_limit(self, user_query: str) -> int | None:
        """Return a word limit when the prompt requests concise output."""
        query_lower = user_query.lower()

        explicit_match = re.search(
            r"(?:under|within|at\s+most|max(?:imum)?)\s*(\d{1,3})\s*words?",
            query_lower,
        )
        if explicit_match:
            try:
                limit = int(explicit_match.group(1))
                if limit > 0:
                    return min(limit, 200)
            except ValueError:
                pass

        if any(term in query_lower for term in ["short decision summary", "short summary", "concise summary"]):
            return 80

        return None

    def _enforce_word_limit(self, answer: str, word_limit: int | None) -> str:
        """Trim long answers while preserving citations for traceability."""
        if not answer or not word_limit:
            return answer

        words = answer.split()
        if len(words) <= word_limit:
            return answer

        trimmed = " ".join(words[:word_limit]).rstrip(" ,;:")
        if not trimmed.endswith((".", "!", "?")):
            trimmed += "..."

        citations = []
        for token in re.findall(r"\[\d+\]", answer):
            if token not in citations:
                citations.append(token)

        citation_suffix = f" {' '.join(citations[:3])}" if citations else ""
        return f"{trimmed}{citation_suffix}".strip()

    def _format_structured_response(self, user_query: str, docs, raw_response: str) -> str:
        """Convert structured database records into a natural admissions-style summary."""
        if not docs:
            return raw_response or self._build_fallback_response("no evidence")

        query_lower = user_query.lower()
        is_structured_query = self._is_structured_admissions_query(user_query)
        if not is_structured_query:
            return raw_response

        for doc in docs:
            content = str(getattr(doc, "page_content", "") or "")
            if "Structured Database Results:" not in content:
                continue

            try:
                payload = content.split("Structured Database Results:", 1)[1].strip()
                records = json.loads(payload)
                if not isinstance(records, list) or not records:
                    break

                summary_lines = []
                table_rows = []
                for record in records:
                    university = record.get("university") or record.get("institution") or "Unknown"
                    detail_parts = []

                    course_title = record.get("course_title") or record.get("degree")
                    if course_title:
                        detail_parts.append(f"Course: {course_title}")

                    ucas_code = record.get("ucas_code")
                    if ucas_code:
                        detail_parts.append(f"UCAS code: {ucas_code}")

                    duration_years = record.get("duration_years")
                    if duration_years is not None:
                        detail_parts.append(f"Duration: {duration_years} years")

                    # Tuition fees — new column names with legacy fallback
                    tuition_fee = record.get("tuition_fee_uk") or record.get("uk_tuition_fee") or record.get("tuition_fee")
                    if tuition_fee is not None:
                        try:
                            detail_parts.append(f"UK tuition fee: £{float(tuition_fee):,.0f} per year")
                        except (ValueError, TypeError):
                            detail_parts.append(f"UK tuition fee: {tuition_fee}")

                    tuition_intl = record.get("tuition_fee_intl") or record.get("international_tuition_fee")
                    if tuition_intl is not None:
                        try:
                            detail_parts.append(f"Intl tuition fee: £{float(tuition_intl):,.0f}")
                        except (ValueError, TypeError):
                            detail_parts.append(f"Intl tuition fee: {tuition_intl}")

                    entry_tariff = record.get("entry_tariff")
                    if entry_tariff is not None:
                        detail_parts.append(f"Avg entry tariff: {entry_tariff:.0f} UCAS pts")

                    alevel_req = record.get("alevel_requirement") or record.get("a_level_requirement")
                    if alevel_req:
                        detail_parts.append(f"A-level requirement: {alevel_req}")

                    placement = record.get("has_placement_year")
                    if placement is not None:
                        detail_parts.append(f"Placement year: {'Yes' if placement else 'No'}")

                    has_year_abroad = record.get("has_year_abroad")
                    if has_year_abroad is not None:
                        detail_parts.append(f"Year abroad: {'Yes' if has_year_abroad else 'No'}")

                    # Salary — new columns preferred, with legacy fallback
                    salary = (
                        record.get("median_salary_leo3")
                        or record.get("median_salary_go")
                        or record.get("median_salary_3yr")
                        or record.get("median_salary")
                    )
                    if salary is not None:
                        detail_parts.append(f"Median salary (3yr): £{salary:,.0f}")

                    salary_leo5 = record.get("median_salary_leo5")
                    if salary_leo5 is not None:
                        detail_parts.append(f"Median salary (5yr): £{salary_leo5:,.0f}")

                    emp_rate = record.get("employment_rate_15m")
                    if emp_rate is not None:
                        detail_parts.append(f"Employment rate (15m): {emp_rate:.1f}%")

                    pct_prof = record.get("pct_professional_managerial")
                    if pct_prof is not None:
                        detail_parts.append(f"Professional/managerial jobs: {pct_prof:.1f}%")

                    project_credits = record.get("final_year_project_credits")
                    if project_credits is not None:
                        detail_parts.append(f"Final year project credits: {project_credits}")

                    bcs = record.get("bcs_accredited")
                    if bcs is not None:
                        detail_parts.append(f"BCS accredited: {'Yes' if bcs else 'No'}")

                    tef = record.get("tef_overall_rating")
                    if tef:
                        detail_parts.append(f"TEF rating: {tef}")

                    nss_teach = record.get("nss_teaching_satisfaction")
                    if nss_teach is not None:
                        detail_parts.append(f"NSS teaching satisfaction: {nss_teach:.1f}%")

                    nss_wellbeing = record.get("nss_mental_wellbeing")
                    if nss_wellbeing is not None:
                        detail_parts.append(f"NSS mental wellbeing: {nss_wellbeing:.1f}%")

                    guardian_rank = record.get("guardian_rank")
                    if guardian_rank is not None:
                        detail_parts.append(f"Guardian rank: #{guardian_rank}")

                    qs_rank = record.get("qs_rank")
                    if qs_rank is not None:
                        detail_parts.append(f"QS rank: #{qs_rank}")

                    summary_lines.append(f"- {university}: " + "; ".join(detail_parts))
                    try:
                        tuition_fee_numeric = float(tuition_fee) if tuition_fee is not None else None
                    except (ValueError, TypeError):
                        tuition_fee_numeric = None
                    table_rows.append((university, tuition_fee_numeric, duration_years, salary))

                if summary_lines:
                    if len(table_rows) > 1:
                        compact_requested = self._resolve_word_limit(user_query) is not None
                        if compact_requested:
                            compact_rows = []
                            seen_universities = set()
                            for university, tuition_fee, duration_years, median_salary in table_rows:
                                uni_key = str(university).lower()
                                if uni_key in seen_universities:
                                    continue
                                seen_universities.add(uni_key)
                                compact_rows.append((university, tuition_fee, duration_years, median_salary))
                                if len(compact_rows) == 2:
                                    break

                            if len(compact_rows) == 2:
                                first = compact_rows[0]
                                second = compact_rows[1]
                                first_fee = f"£{first[1]:,.0f}" if first[1] is not None else "N/A"
                                second_fee = f"£{second[1]:,.0f}" if second[1] is not None else "N/A"
                                first_duration = f"{first[2]}y" if first[2] is not None else "N/A"
                                second_duration = f"{second[2]}y" if second[2] is not None else "N/A"
                                first_salary = f"£{first[3]:,.0f}" if first[3] is not None else "N/A"
                                second_salary = f"£{second[3]:,.0f}" if second[3] is not None else "N/A"

                                decision = "Both options are closely matched."
                                if first[3] is not None and second[3] is not None and first[3] != second[3]:
                                    better_salary_uni = first[0] if first[3] > second[3] else second[0]
                                    decision = f"{better_salary_uni} has the salary edge."

                                return (
                                    f"{first[0]} vs {second[0]}: tuition {first_fee} vs {second_fee}; "
                                    f"duration {first_duration} vs {second_duration}; "
                                    f"salary {first_salary} vs {second_salary}. {decision}"
                                )

                        table_lines = [
                            "| University | Tuition Fee | Duration | Median Salary |",
                            "|---|---:|---:|---:|",
                        ]
                        for university, tuition_fee, duration_years, median_salary in table_rows:
                            tuition_text = f"£{tuition_fee:,.0f}" if tuition_fee is not None else "N/A"
                            duration_text = f"{duration_years} yrs" if duration_years is not None else "N/A"
                            salary_text = f"£{median_salary:,.0f}" if median_salary is not None else "N/A"
                            table_lines.append(f"| {university} | {tuition_text} | {duration_text} | {salary_text} |")

                        affordability_note = ""
                        if table_rows:
                            cheapest = min([row for row in table_rows if row[1] is not None], key=lambda item: item[1], default=None)
                            if cheapest:
                                affordability_note = f"For a student considering value for money, {cheapest[0]} stands out as the most affordable option based on the current record."
                            else:
                                affordability_note = "For a student considering value for money, the most affordable option is the one with the lowest listed tuition fee."

                        duration_note = ""
                        if table_rows:
                            shortest = min([row for row in table_rows if row[2] is not None], key=lambda item: item[2], default=None)
                            if shortest:
                                duration_note = f"If you want the shortest study period, {shortest[0]} is the most compact option in this set."

                        closing = " ".join(part for part in [affordability_note, duration_note] if part)
                        return "For a student considering these options, here's a practical summary: \n" + "\n".join(summary_lines) + "\n\n" + "\n".join(table_lines) + (f"\n\n{closing}" if closing else "") + " [1]"

                    if any(term in query_lower for term in ["duration", "how long", "years", "year"]):
                        return "For a student considering these options, here's a practical summary: \n" + "\n".join(summary_lines) + " [1]"

                    return "For a student considering these options, here's a practical summary: \n" + "\n".join(summary_lines) + " [1]"
            except Exception:
                continue

        return raw_response

    def _rewrite_structured_summary_with_gemini(self, user_query: str, structured_summary: str) -> str | None:
        """Use Gemini to turn a fetched structured summary into a concise priority-aware sentence."""
        gemini_models = self._ensure_gemini_models()
        if not structured_summary or not gemini_models:
            return None

        word_limit = self._resolve_word_limit(user_query) or 80
        rewrite_prompt = (
            "You are rewriting a verified university comparison summary. "
            "Use only the supplied summary, preserve factual meaning, and write one concise meaningful paragraph. "
            f"Keep it under {word_limit} words, prioritize the student's stated priorities, and do not invent facts.\n\n"
            f"User query:\n{user_query}\n\n"
            f"Verified summary:\n{structured_summary}\n\n"
            "Return only the rewritten comparison sentence."
        )

        generation_errors = []
        for model_name in gemini_models:
            try:
                primary_llm = ChatGoogleGenerativeAI(
                    model=model_name,
                    temperature=0.0,
                    google_api_key=self.api_key,
                )
                rewrite_chain = ChatPromptTemplate.from_messages([
                    HumanMessagePromptTemplate.from_template("{prompt}")
                ]) | primary_llm | StrOutputParser()
                text = rewrite_chain.invoke({"prompt": rewrite_prompt})
                if isinstance(text, str) and text.strip():
                    return text.strip()
            except Exception as exc:
                generation_errors.append(f"{model_name}: {exc}")

        if generation_errors:
            print(f"⚠️ Structured summary Gemini rewrite failed: {' | '.join(generation_errors)}")
        return None

    def _synthesize_answer(self, user_query: str, docs) -> str:
        """Create a concise admissions-style answer from the retrieved evidence."""
        if not docs:
            return self._build_fallback_response("no evidence")

        query_lower = user_query.lower()
        evidence_blocks = []
        for doc in docs:
            page_content = str(getattr(doc, "page_content", "") or "")
            if page_content:
                evidence_blocks.append(page_content)

        combined_text = "\n".join(evidence_blocks).lower()

        if any(term in query_lower for term in ["ucas", "code"]):
            for doc in docs:
                content = str(getattr(doc, "page_content", "") or "")
                if "course code" in content.lower() or "cs303" in content.lower() or "cs505" in content.lower() or "cs606" in content.lower():
                    return f"The available records point to the course code in the retrieved context: {content.split(':', 1)[-1].strip()} [1]"
            return self._build_fallback_response("missing code evidence")

        if any(term in query_lower for term in ["year 1", "year 2", "module", "modules", "curriculum"]):
            curriculum_docs = [doc for doc in docs if "module" in str(getattr(doc, "page_content", "") or "").lower() or "curriculum" in str(getattr(doc, "page_content", "") or "").lower()]
            if curriculum_docs:
                if any(term in query_lower for term in ["compare", "difference", "between", "which"]) and len(curriculum_docs) >= 2:
                    summaries = []
                    seen = set()
                    for doc in curriculum_docs:
                        content = str(getattr(doc, "page_content", "") or "")
                        institution = ""
                        metadata = getattr(doc, "metadata", {}) or {}
                        if metadata.get("university"):
                            institution = metadata.get("university")
                        elif "for " in content and " (" in content:
                            institution = content.split("for ", 1)[1].split(" (", 1)[0]
                        if institution and institution.lower() not in seen:
                            seen.add(institution.lower())
                            summaries.append(f"{institution}: {content}")
                    if summaries:
                        return "The retrieved curriculum evidence shows: " + " | ".join(summaries[:3]) + " [1][2][3]"
                first_content = str(getattr(curriculum_docs[0], "page_content", "") or "")
                match = re.search(r"year\s*(\d)\s+modules?\s*(.+)", first_content, re.IGNORECASE)
                if match:
                    year_number = match.group(1)
                    module_text = re.sub(r"\s+", " ", match.group(2).strip())
                    return f"Year {year_number} core modules include {module_text} [1]"
                return f"The curriculum evidence indicates: {first_content} [1]"
            return self._build_fallback_response("missing curriculum evidence")

        if any(term in query_lower for term in ["tuition", "fee", "salary", "employment", "median", "duration",
                                                 "ranking", "rank", "tef", "nss", "satisfaction", "wellbeing",
                                                 "accredited", "bcs", "tariff", "a-level", "year abroad",
                                                 "foundation year", "international fee", "professional"]):
            structured_summary = self._format_structured_response(user_query, docs, "")
            if structured_summary and structured_summary != "":
                return structured_summary
            for doc in docs:
                content = str(getattr(doc, "page_content", "") or "")
                if any(term in content.lower() for term in ["tuition", "salary", "fee", "rank", "tef", "nss"]):
                    return f"The available statistics indicate: {content} [1]"
            return self._build_fallback_response("missing statistics evidence")

        if any(term in query_lower for term in ["compare", "difference", "which"]):
            summaries = []
            for doc in docs[:3]:
                content = str(getattr(doc, "page_content", "") or "")
                summaries.append(content)
            return "The retrieved evidence suggests the following comparison: " + " | ".join(summaries[:2]) + " [1][2]"

        return f"The retrieved evidence supports the following answer: {evidence_blocks[0]} [1]"

    def _postprocess_grounded_answer(self, answer: str, docs) -> str:
        """Enforce grounding by adding citations and replacing unsupported claims with a fallback."""
        if not answer or not docs:
            return "Insufficient information in the provided context to answer this question reliably."

        cleaned_answer = answer.strip()
        if not cleaned_answer:
            return "Insufficient information in the provided context to answer this question reliably."

        if "not available" in cleaned_answer.lower() or "insufficient information" in cleaned_answer.lower():
            return cleaned_answer

        structured_evidence = any("structured database results" in str(getattr(doc, "page_content", "") or "").lower() for doc in docs)
        if structured_evidence and (
            "available records indicate" in cleaned_answer.lower()
            or "here’s a clear summary" in cleaned_answer.lower()
            or "tuition fee" in cleaned_answer.lower()
            or "duration:" in cleaned_answer.lower()
            or ("tuition" in cleaned_answer.lower() and "salary" in cleaned_answer.lower())
        ):
            citation_suffix = ""
            if len(docs) > 0:
                citation_suffix = " " + " ".join(f"[{i}]" for i in range(1, min(len(docs), 3) + 1))
            return f"{cleaned_answer}{citation_suffix}"

        evidence_terms = []
        for doc in docs:
            content = str(doc.page_content or "").lower()
            evidence_terms.extend([word for word in content.split() if len(word) > 3])

        evidence_terms = set(evidence_terms)
        answer_words = [word for word in cleaned_answer.lower().split() if len(word) > 3]
        token_overlap = sum(1 for word in answer_words if word in evidence_terms)

        if token_overlap == 0 and len(answer_words) >= 2:
            return f"Not Available. The provided context does not support this claim. [1]"

        if len(answer_words) >= 6 and token_overlap / len(answer_words) < 0.2:
            return f"Not Available. The provided context does not support this claim. [1]"

        citation_suffix = ""
        if len(docs) > 0:
            citation_suffix = " " + " ".join(f"[{i}]" for i in range(1, min(len(docs), 3) + 1))

        return f"{cleaned_answer}{citation_suffix}"

    def _select_best_response(self, llm_response: str, user_query: str, docs) -> str:
        """Prefer an evidence-backed synthesis answer when the model output is generic or unsupported."""
        if not docs:
            return llm_response or self._build_fallback_response("no evidence")

        synthesized = self._synthesize_answer(user_query, docs)
        if not synthesized:
            return llm_response or self._build_fallback_response("no evidence")

        llm_lower = (llm_response or "").strip().lower()
        if not llm_lower:
            return synthesized

        if any(term in llm_lower for term in ["i can help", "in general terms", "insufficient information", "not available", "i don't know"]):
            return synthesized

        if any(term in user_query.lower() for term in ["year 1", "year 2", "module", "modules", "curriculum",
                                                         "tuition", "fee", "salary", "duration", "placement",
                                                         "project", "entry requirement", "credits", "ranking",
                                                         "rank", "tef", "nss", "satisfaction", "wellbeing",
                                                         "accredited", "bcs", "tariff"]):
            if any(term in self._build_fallback_response("x").lower() for term in ["insufficient information"]):
                return synthesized

        return llm_response

    def _normalize_answer_from_context(self, user_query: str, answer: str, docs) -> str:
        """Refine generic model output so it cites the retrieved evidence and preserves admissions-specific details."""
        if not answer or not docs:
            return answer or self._build_fallback_response("no evidence")

        query_lower = user_query.lower()
        evidence_text = "\n".join(str(getattr(doc, "page_content", "") or "") for doc in docs)
        evidence_lower = evidence_text.lower()

        if any(term in query_lower for term in ["year 1", "year 2", "module", "modules", "curriculum"]):
            if any(term in evidence_lower for term in ["module", "curriculum", "procedural coding", "discrete mathematics", "systems architecture", "database systems", "software engineering"]):
                info = []
                for doc in docs:
                    content = str(getattr(doc, "page_content", "") or "")
                    if "module" in content.lower() or "curriculum" in content.lower():
                        info.append(content)
                if info:
                    content = info[0]
                    match = re.search(r"(?:year\s*(\d))\s+modules?\s*(.+)", content, re.IGNORECASE)
                    if match:
                        year_number = match.group(1)
                        module_text = re.sub(r"\s+", " ", match.group(2).strip())
                        return f"Year {year_number} core modules include {module_text} [1]"
                    return "The retrieved curriculum evidence indicates: " + " | ".join(info[:3]) + " [1][2][3]"

        if any(term in query_lower for term in ["tuition", "fee", "salary", "duration", "placement", "project",
                                                 "entry requirement", "credits", "ranking", "rank", "tef", "nss",
                                                 "satisfaction", "wellbeing", "accredited", "bcs", "tariff",
                                                 "a-level", "year abroad", "foundation year", "international fee"]):
            if any(term in evidence_lower for term in ["tuition", "salary", "duration", "placement", "project",
                                                       "entry requirement", "credits", "rank", "tef", "nss"]):
                return self._format_structured_response(user_query, docs, answer) or answer

        return answer

    def _build_fallback_response(self, reason: str) -> str:
        """Return a concise, trustworthy fallback message for unavailable generation paths."""
        return "I don’t know based on the available evidence. Insufficient information."

    def _log_low_confidence_event(self, user_query: str, confidence_score: float, reason: str) -> None:
        """Write a structured review log entry for low-confidence or abstained responses."""
        log_path = getattr(self, "review_log_path", "review_log.jsonl")
        if not log_path:
            return
        entry = {
            "event": "low_confidence_review",
            "query": user_query,
            "confidence_score": round(confidence_score, 4),
            "reason": reason,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def _write_trace_event(self, user_query: str, answer: str, confidence_score: float, should_abstain: bool) -> None:
        """Write a monitoring trace entry for each request/response pair."""
        log_path = getattr(self, "trace_log_path", "trace_log.jsonl")
        if not log_path:
            return
        entry = {
            "event": "response_trace",
            "query": user_query,
            "answer": answer,
            "confidence_score": round(confidence_score, 4),
            "should_abstain": should_abstain,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def _discover_available_gemini_models(self):
        """Discovers and filters valid Gemini text generation models."""
        if not self.api_key or genai is None:
            print("⚠️ No Gemini API key found in environment variables or Gemini SDK is unavailable.")
            return []

        print("🔍 Discovering active Gemini models for your API key...")
        EXCLUDED_KEYWORDS = ["tts", "image", "audio", "video", "clip", "lyria", "robotics", "computer-use"]
        PREFERRED_MODELS = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]

        try:
            genai.configure(api_key=self.api_key)
            discovered_models = []

            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    clean_name = m.name.replace("models/", "")
                    if not any(kw in clean_name.lower() for kw in EXCLUDED_KEYWORDS):
                        discovered_models.append(clean_name)

            def get_priority(model_name):
                name_lower = model_name.lower()
                for index, preferred in enumerate(PREFERRED_MODELS):
                    if preferred in name_lower:
                        return index
                return len(PREFERRED_MODELS) + 1

            discovered_models.sort(key=get_priority)
            if discovered_models:
                print(f"⭐ Top candidate model: [{discovered_models[0]}]")
            return discovered_models

        except Exception as e:
            print(f"⚠️ Failed to list Gemini models automatically: {e}")
            return []

    def format_docs(self, docs):
        """Formats retrieved chunks and appends source tracking metadata."""
        if not docs:
            return "No relevant context found."
        
        formatted_chunks = []
        for i, doc in enumerate(docs, 1):
            source_url = doc.metadata.get("source_url", "N/A")
            layer = doc.metadata.get("data_layer", "N/A")
            formatted_chunks.append(f"[Record {i} | Layer: {layer} | Source: {source_url}]\n{doc.page_content}")
        return "\n\n".join(formatted_chunks)

    def _build_citations(self, docs):
        """Return ordered unique citation metadata for UI rendering."""
        citations = []
        seen = set()
        for doc in docs:
            metadata = getattr(doc, "metadata", {}) or {}
            source = metadata.get("source_url") or ""
            data_layer = str(metadata.get("data_layer") or "")
            page_content = str(getattr(doc, "page_content", "") or "")
            key = (str(source), page_content[:160])
            if key in seen:
                continue
            seen.add(key)
            label = source or f"Source {len(citations) + 1}"
            if source == "SQLite: course_facts table":
                label = "Structured admissions database"
            elif source == "SQLite: course_stats table":
                label = "Structured course statistics database"
            elif data_layer == "quantitative_profile":
                label = "Graduate outcomes and fee profile"
            elif data_layer == "knowledge_base_fallback":
                label = "University prospectus evidence"
            elif data_layer.startswith("curriculum_year_"):
                label = "Curriculum and module evidence"
            elif data_layer == "industrial_placements":
                label = "Placement year evidence"
            elif data_layer == "infrastructure_and_facilities":
                label = "Facilities and infrastructure evidence"
            elif data_layer == "entry_requirements":
                label = "Entry requirements evidence"
            elif data_layer == "student_support":
                label = "Student support evidence"
            elif data_layer == "career_outcomes":
                label = "Career outcomes evidence"
            elif data_layer == "Unstructured Vector Document":
                label = "Prospectus excerpt"
            elif isinstance(source, str) and "discoveruni.gov.uk" in source:
                label = "Discover Uni evidence"
            elif isinstance(source, str) and source.startswith(("http://", "https://")):
                label = "Official course page"
            citations.append({
                "source": source,
                "url": source if isinstance(source, str) and source.startswith(("http://", "https://")) else "",
                "label": label,
                "snippet": page_content[:240],
                "content": page_content,
            })
        return citations

    def _collect_matched_institutions(self, docs):
        matched_institutions = set()
        for doc in docs:
            metadata = getattr(doc, "metadata", {}) or {}
            institution = str(metadata.get("institution") or metadata.get("university") or "").lower()
            if institution:
                matched_institutions.add(institution)
            content = str(getattr(doc, "page_content", "") or "")
            if "Structured Database Results:" in content:
                try:
                    payload = content.split("Structured Database Results:", 1)[1].strip()
                    rows = json.loads(payload)
                    if isinstance(rows, list):
                        for row in rows:
                            row_uni = str((row or {}).get("university") or (row or {}).get("institution") or "").lower()
                            if row_uni:
                                matched_institutions.add(row_uni)
                except Exception:
                    pass
        return matched_institutions

    def _should_abstain(self, docs, formatted_context: str, user_query: str) -> bool:
        if not docs:
            return True
        if not formatted_context or "No relevant context found." in formatted_context:
            return True

        lower_query = user_query.lower()
        query_terms = {term for term in lower_query.replace("?", "").split() if len(term) > 3}
        evidence_text = " ".join([doc.page_content.lower() for doc in docs if getattr(doc, "page_content", None)])

        structured_keywords = [
            ("tuition", ["tuition", "fee", "cost", "price", "pounds", "£", "tuition_fee_uk", "tuition_fee_intl"]),
            ("duration", ["duration", "year", "years", "duration_years"]),
            ("salary", ["salary", "median", "employment", "graduate", "earnings", "median_salary_leo3", "median_salary_go"]),
            ("placement", ["placement", "project", "credits", "entry", "requirement", "requirements"]),
            ("ranking", ["rank", "guardian", "league", "qs_rank", "guardian_rank"]),
            ("nss", ["nss", "satisfaction", "wellbeing", "nss_teaching_satisfaction", "nss_mental_wellbeing"]),
            ("tef", ["tef", "teaching excellence", "tef_overall_rating"]),
        ]

        for keyword, evidence_terms in structured_keywords:
            if keyword in lower_query or any(term in lower_query for term in [
                "how long", "standard duration", "entry requirement", "project credits", "final year",
                "ranking", "league table", "nss score", "tef rating", "bcs accredited",
            ]):
                if any(term in lower_query for term in [
                    "tuition", "fee", "cost", "duration", "salary", "placement", "project",
                    "credits", "entry requirement", "how long", "ranking", "rank", "nss",
                    "tef", "satisfaction", "wellbeing", "bcs", "tariff",
                ]):
                    if any(term in evidence_text for term in evidence_terms):
                        return False
                    return True

        if len(docs) < 2:
            return True

        overlap = sum(1 for term in query_terms if term in evidence_text)
        if overlap == 0 and len(query_terms) > 0:
            return True

        if any(term in lower_query for term in ["compare", "difference", "which", "best"]) and len(docs) < 3:
            return True
        if any(term in lower_query for term in ["ucas", "code", "credits", "project"]) and len(docs) < 2:
            return True

        return False

    def _confidence_score(self, docs, formatted_context: str, user_query: str) -> float:
        if not docs:
            return 0.0
        if "No relevant context found." in formatted_context:
            return 0.0

        score = min(1.0, len(docs) / 5.0)
        lower_query = user_query.lower()
        evidence_text = " ".join([doc.page_content.lower() for doc in docs if getattr(doc, "page_content", None)])
        query_terms = {term for term in lower_query.replace("?", "").split() if len(term) > 3}
        overlap = sum(1 for term in query_terms if term in evidence_text)

        is_structured_query = any(term in lower_query for term in [
            "tuition", "fee", "duration", "salary", "standard duration", "statistical",
            "ranking", "rank", "tef", "nss", "satisfaction", "wellbeing", "bcs", "tariff",
        ])
        if is_structured_query:
            score = max(score, 0.85)

        if overlap > 0:
            score += 0.1 * min(3, overlap)
        else:
            score = max(0.0, score - 0.3)

        if any(term in lower_query for term in ["module", "modules", "curriculum", "year"]):
            score += 0.1
        if any(term in lower_query for term in ["tuition", "fee", "salary", "employment", "statistical", "duration",
                                                 "ranking", "rank", "tef", "nss", "satisfaction", "bcs", "tariff"]):
            score += 0.1
        if any(term in lower_query for term in ["ucas", "code"]):
            score += 0.1

        return round(min(1.0, score), 2)

    def _should_answer(self, confidence_score: float, docs, formatted_context: str, user_query: str) -> tuple[bool, str]:
        if confidence_score < 0.4:
            reason = "confidence below threshold"
            return False, reason
        if not docs or not formatted_context or "No relevant context found." in formatted_context:
            reason = "no evidence"
            return False, reason
        return True, ""

    def query_pipeline(
        self,
        user_query: str,
        target_competitor: str | None = None,
        target_programme: str | None = None,
        target_baseline: str | None = None,
    ):
        """Executes Intent Routing -> Retrieval -> LLM Synthesis."""
        start_time = time.time()
        print(f"\n--- 📥 Incoming Query: \"{user_query}\" ---")

        retrieval_query = user_query
        if target_competitor:
            retrieval_query = f"{user_query}\nTarget competitor: {target_competitor}"
        if target_programme:
            retrieval_query = f"{retrieval_query}\nTarget programme: {target_programme}"
        if target_baseline:
            retrieval_query = f"{retrieval_query}\nBaseline university: {target_baseline}"

        allowed_institutions = [name for name in [target_baseline, target_competitor] if name]

        # Step 1: Route Query Intent
        intent_layer = self.query_router.classify_intent(user_query)
        print(f"🛤️ Intent Router: Navigating query to [{intent_layer}] engine.")

        # Step 2: Fetch Data
        if intent_layer == "SQL":
            retrieved_docs = self.query_router.execute_sql(
                user_query,
                target_competitor=target_competitor,
                target_programme=target_programme,
                target_baseline=target_baseline,
            )
            structured_empty = True
            for doc in retrieved_docs:
                content = str(getattr(doc, "page_content", "") or "")
                if "Structured Database Results: []" not in content:
                    structured_empty = False
                    break
            if structured_empty:
                print("⚠️ Structured SQL lookup returned no targeted rows. Falling back to hybrid retrieval.")
                # Prefer the local KB first to avoid expensive vector startup in obvious miss cases.
                retrieved_docs = self.knowledge_base_retriever.search(
                    retrieval_query,
                    top_k=5,
                    target_competitor=None,
                    allowed_institutions=allowed_institutions,
                )
                if not retrieved_docs:
                    self._ensure_vector_store()
                    retrieved_docs = self.hybrid_retriever.search(
                        retrieval_query,
                        top_k=5,
                        target_competitor=None,
                        allowed_institutions=allowed_institutions,
                    )
        else:
            self._ensure_vector_store()
            retrieved_docs = self.hybrid_retriever.search(
                retrieval_query,
                top_k=5,
                target_competitor=None,
                allowed_institutions=allowed_institutions,
            )
            if not retrieved_docs:
                print("⚠️ No data in Vector DB for hybrid search. Falling back to the local knowledge base.")
                retrieved_docs = self.knowledge_base_retriever.search(
                    retrieval_query,
                    top_k=5,
                    target_competitor=None,
                    allowed_institutions=allowed_institutions,
                )

        if target_baseline and target_competitor:
            matched_institutions = self._collect_matched_institutions(retrieved_docs)
            baseline_lower = target_baseline.lower()
            competitor_lower = target_competitor.lower()
            if intent_layer == "SQL" and (baseline_lower not in matched_institutions or competitor_lower not in matched_institutions):
                print("⚠️ SQL returned incomplete university coverage. Retrying with targeted hybrid retrieval.")
                # Try deterministic local KB first to keep strict-miss responses fast.
                retry_docs = self.knowledge_base_retriever.search(
                    retrieval_query,
                    top_k=5,
                    target_competitor=None,
                    allowed_institutions=allowed_institutions,
                )
                if not retry_docs:
                    self._ensure_vector_store()
                    retry_docs = self.hybrid_retriever.search(
                        retrieval_query,
                        top_k=5,
                        target_competitor=None,
                        allowed_institutions=allowed_institutions,
                    )
                if retry_docs:
                    retrieved_docs = retry_docs
                    matched_institutions = self._collect_matched_institutions(retrieved_docs)
            if baseline_lower not in matched_institutions:
                print("⚠️ Missing baseline evidence for strict Liverpool-vs-competitor comparison.")
                response = self._build_fallback_response("missing baseline evidence")
                grounded_answer = self._enforce_word_limit(response, self._resolve_word_limit(user_query))
                self._write_trace_event(user_query, grounded_answer, 0.0, True)
                return {
                    "answer": grounded_answer,
                    "engine_used": "abstain",
                    "routing_layer": intent_layer,
                    "latency_seconds": round(time.time() - start_time, 3),
                    "sources": [item.get("source") for item in self._build_citations(retrieved_docs)],
                    "citations": self._build_citations(retrieved_docs),
                    "contexts": [doc.page_content for doc in retrieved_docs],
                    "confidence_score": 0.0,
                    "should_abstain": True,
                }
            if competitor_lower not in matched_institutions:
                print("⚠️ Missing competitor evidence for strict Liverpool-vs-competitor comparison.")
                response = self._build_fallback_response("missing competitor evidence")
                grounded_answer = self._enforce_word_limit(response, self._resolve_word_limit(user_query))
                self._write_trace_event(user_query, grounded_answer, 0.0, True)
                return {
                    "answer": grounded_answer,
                    "engine_used": "abstain",
                    "routing_layer": intent_layer,
                    "latency_seconds": round(time.time() - start_time, 3),
                    "sources": [item.get("source") for item in self._build_citations(retrieved_docs)],
                    "citations": self._build_citations(retrieved_docs),
                    "contexts": [doc.page_content for doc in retrieved_docs],
                    "confidence_score": 0.0,
                    "should_abstain": True,
                }
                
        formatted_context = self.format_docs(retrieved_docs)

        confidence_score = self._confidence_score(retrieved_docs, formatted_context, user_query)
        should_abstain = self._should_abstain(retrieved_docs, formatted_context, user_query)
        should_answer, reason = self._should_answer(confidence_score, retrieved_docs, formatted_context, user_query)

        structured_summary_seed = None
        if intent_layer == "SQL" and self._is_structured_admissions_query(user_query):
            should_abstain = False
            should_answer = True
            reason = ""

        if should_abstain or not should_answer:
            print("⚠️ Low-confidence retrieval detected. Returning abstention response.")
            self._log_low_confidence_event(user_query, confidence_score, reason or "low-confidence retrieval")
            response = self._build_fallback_response(reason or "low-confidence retrieval")
            engine_used = "abstain"
        else:
            response = None
            engine_used = None

        if intent_layer == "SQL" and self._is_structured_admissions_query(user_query):
            print("🧾 Structured admissions query detected. Using the structured summary formatter.")
            structured_summary_seed = self._synthesize_answer(user_query, retrieved_docs)
            response = structured_summary_seed
            engine_used = "structured_summary"
            should_abstain = False

        # Step 3: Gemini Generation Loop
        generation_errors = []
        gemini_models = [] if response is not None else self._ensure_gemini_models()
        if response is None and not gemini_models:
            print("⚠️ No Gemini models available. Skipping generation.")
            generation_errors.append("No Gemini models were available for generation.")
            response = None

        if response is None and structured_summary_seed and gemini_models:
            rewritten_summary = self._rewrite_structured_summary_with_gemini(user_query, structured_summary_seed)
            if rewritten_summary:
                response = rewritten_summary
                engine_used = f"Google Gemini ({gemini_models[0]})"
            else:
                response = structured_summary_seed
                engine_used = "structured_summary"

        if response is None and gemini_models:
            for model_name in gemini_models:
                print(f"🚀 Attempting synthesis with [{model_name}]...")
                try:
                    primary_llm = ChatGoogleGenerativeAI(
                        model=model_name,
                        temperature=0.0,
                        google_api_key=self.api_key
                    )
                    chain = (
                        {"context": lambda _: formatted_context, "question": RunnablePassthrough()}
                        | self.prompt
                        | primary_llm
                        | StrOutputParser()
                    )
                    response = chain.invoke(user_query)
                    engine_used = f"Google Gemini ({model_name})"
                    break
                except Exception as e:
                    detail = f"Model [{model_name}] failed: {str(e)}"
                    generation_errors.append(detail)
                    print(f"⚠️ {detail}")

        if response is None:
            error_message = "Generation failed. " + " | ".join(generation_errors) if generation_errors else "Generation failed. No detailed error was provided."
            print(f"❌ {error_message}")
            response = self._build_fallback_response(error_message)
            engine_used = "error"

        if response is None:
            response = self._synthesize_answer(user_query, retrieved_docs)
        elif not isinstance(response, str) or not response.strip():
            response = self._synthesize_answer(user_query, retrieved_docs)
        else:
            if "insufficient information" in response.lower() or "not available" in response.lower():
                response = self._synthesize_answer(user_query, retrieved_docs)
            elif "Structured Database Results:" in response:
                response = self._format_structured_response(user_query, retrieved_docs, response)

        if response is not None:
            response = self._select_best_response(response, user_query, retrieved_docs)

        normalized_answer = self._normalize_answer_from_context(user_query, response, retrieved_docs)
        grounded_answer = self._postprocess_grounded_answer(normalized_answer, retrieved_docs)
        grounded_answer = self._enforce_word_limit(grounded_answer, self._resolve_word_limit(user_query))
        self._write_trace_event(user_query, grounded_answer, confidence_score, should_abstain)

        citations = self._build_citations(retrieved_docs)
        return {
            "answer": grounded_answer,
            "engine_used": engine_used,
            "routing_layer": intent_layer,
            "latency_seconds": round(time.time() - start_time, 3),
            "sources": [item.get("source") for item in citations],
            "citations": citations,
            "contexts": [doc.page_content for doc in retrieved_docs],
            "confidence_score": confidence_score,
            "should_abstain": should_abstain,
        }

# --- Execution Testing Section ---
if __name__ == "__main__":
    rag = AdmissionsRAGOrchestrator()

    # TEST SCENARIO 1: Semantic/Syllabus Intent (Triggers Hybrid Vector+BM25 Search)
    result1 = rag.query_pipeline("Compare Year 1 core modules across University of Leeds and University of Sheffield.")
    
    print("\n--- 🟢 SCENARIO 1: MULTI-COMPETITOR COMPARISON ---")
    print(f"🛤️ Route Level: {result1['routing_layer']}")
    print(f"🤖 Engine Used: {result1['engine_used']}")
    print(f"🔗 Citations  : {result1['sources']}")
    print(f"\n💡 Output:\n{result1['answer']}")

    # TEST SCENARIO 2: Structured Intent (Triggers SQL Engine)
    result2 = rag.query_pipeline("What is the tuition fee and standard duration for these programs?")
    
    print("\n--- 🔵 SCENARIO 2: STRUCTURED DATABASE QUERY ---")
    print(f"🛤️ Route Level: {result2['routing_layer']}")
    print(f"🤖 Engine Used: {result2['engine_used']}")
    print(f"🔗 Citations  : {result2['sources']}")
    print(f"\n💡 Output:\n{result2['answer']}")