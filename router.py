import sqlite3
import json
from typing import Any, Dict


class QueryRouter:
    def __init__(self, db_path: str, hybrid_retriever):
        self.db_path = db_path
        self.retriever = hybrid_retriever

    def classify_intent(self, query: str) -> str:
        """Determines if query targets structured stats or qualitative curriculum text."""
        keywords_sql = ["available seats", "grade threshold", "duration", "tuition fee", "salary"]
        if any(kw in query.lower() for kw in keywords_sql):
            return "SQL"
        return "HYBRID_VECTOR"

    def execute_sql_query(self, query: str) -> str:
        """Maps query to structured SQLite execution."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Example rule-based router logic (can be driven by an LLM function call)
        if "duration" in query.lower():
            cursor.execute("SELECT university, degree_name, duration_years FROM course_stats")
            rows = cursor.fetchall()
            conn.close()
            return f"Structured Database Results: {json.dumps(rows)}"
        
        conn.close()
        return "No matching SQL record found."

    def _build_where_clause(self, query: str) -> Dict[str, Any]:
        q = query.lower()
        where_clause = {}

        if any(term in q for term in ["year 1", "year one", "first year"]):
            where_clause["academic_year"] = 1
        elif any(term in q for term in ["year 2", "year two", "second year"]):
            where_clause["academic_year"] = 2
        elif any(term in q for term in ["year 3", "year three", "third year"]):
            where_clause["academic_year"] = 3

        if any(term in q for term in ["module", "modules", "curriculum", "syllabus"]):
            where_clause["content_type"] = "curriculum"
        elif any(term in q for term in ["tuition", "fee", "salary", "employment", "statistical"]):
            where_clause["content_type"] = "financial_stats"

        return where_clause

    def route_and_fetch(self, query: str) -> Dict[str, Any]:
        intent = self.classify_intent(query)
        if intent == "SQL":
            data = self.execute_sql_query(query)
            return {"source_type": "SQL", "data": data}
        else:
            where_clause = self._build_where_clause(query)
            context = self.retriever.search(query, top_k=5, where_clause=where_clause)
            return {"source_type": "HYBRID_VECTOR", "data": context}