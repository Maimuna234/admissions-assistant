import re
import numpy as np
from typing import List, Dict, Any

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - optional dependency fallback
    BM25Okapi = None


class HybridRetriever:
    def __init__(self, chroma_collection):
        self.collection = chroma_collection
        all_docs = self.collection.get()
        self.doc_ids = all_docs["ids"]
        self.documents = all_docs["documents"]
        self.metadatas = all_docs["metadatas"]

        tokenized_corpus = [doc.lower().split(" ") for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized_corpus) if BM25Okapi and tokenized_corpus else None
        self.synonym_map = {
            "module": ["module", "modules", "curriculum", "coursework"],
            "year": ["year", "years", "level"],
            "fee": ["fee", "tuition", "cost"],
            "salary": ["salary", "earnings", "employment"],
            "code": ["code", "ucas", "ucas code"],
        }

    def _expand_query(self, query: str) -> List[str]:
        q = query.lower().strip()
        expanded = []
        tokens = re.findall(r"[a-z0-9]+", q)
        for token in tokens:
            expanded.append(token)
            for canonical, variants in self.synonym_map.items():
                if token in {canonical, *variants}:
                    expanded.extend(variants)
        if any(term in q for term in ["module", "modules", "curriculum", "year"]):
            expanded.extend(["curriculum", "module", "year", "modules", "coursework"])
        if any(term in q for term in ["tuition", "fee", "salary", "employment", "statistical", "duration"]):
            expanded.extend(["tuition", "fee", "salary", "employment", "financial", "stats"])
        if any(term in q for term in ["ucas", "code"]):
            expanded.extend(["ucas", "code", "course"])
        return list(dict.fromkeys(expanded))

    def _metadata_bonus(self, metadata: Dict[str, Any], query: str) -> float:
        q = query.lower()
        bonus = 0.0
        if not metadata:
            return bonus

        if any(term in q for term in ["module", "modules", "curriculum", "year"]):
            if metadata.get("content_type") == "curriculum":
                bonus += 0.55
            if metadata.get("academic_year") is not None:
                bonus += 0.15
            if metadata.get("academic_year") == 1 and "year 1" in q:
                bonus += 0.2
            if metadata.get("academic_year") == 2 and "year 2" in q:
                bonus += 0.2

        if any(term in q for term in ["tuition", "fee", "salary", "employment", "statistical", "duration", "how long"]):
            if metadata.get("content_type") == "financial_stats":
                bonus += 0.55
            if metadata.get("content_type") == "curriculum":
                bonus -= 0.1

        if any(term in q for term in ["ucas", "code"]):
            if metadata.get("course_code"):
                bonus += 0.25

        return bonus

    def _phrase_overlap_score(self, query: str, document_text: str) -> float:
        query_terms = [term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 2]
        if not query_terms:
            return 0.0

        text = document_text.lower()
        overlap = 0
        for term in query_terms:
            if term in text:
                overlap += 1
        base = overlap / max(1, len(query_terms))

        if any(term in query.lower() for term in ["year 1", "year 2", "year 3"]):
            year_match = re.search(r"year\s*(\d)", text)
            if year_match and year_match.group(1) in query.lower():
                base += 0.2

        return min(1.0, base)

    def search(self, query: str, top_k: int = 5, rrf_k: int = 60, where_clause: Dict = None) -> List[Dict]:
        expanded_terms = self._expand_query(query)
        tokenized_query = expanded_terms
        bm25_scores = None
        bm25_top_indices = []
        if self.bm25 is not None:
            bm25_scores = self.bm25.get_scores(tokenized_query)
            bm25_top_indices = np.argsort(bm25_scores)[::-1][:top_k * 2]

        vector_results = self.collection.query(
            query_texts=[query],
            n_results=top_k * 2,
            where=where_clause
        )
        vector_ids = vector_results["ids"][0] if vector_results["ids"] else []

        rrf_scores = {}
        for rank, idx in enumerate(bm25_top_indices):
            doc_id = self.doc_ids[idx]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (1.0 / (rrf_k + rank + 1))

        for rank, doc_id in enumerate(vector_ids):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (1.0 / (rrf_k + rank + 1))

        reranked_results = []
        for d_id in rrf_scores:
            idx = self.doc_ids.index(d_id)
            metadata = self.metadatas[idx]
            document_text = self.documents[idx]
            phrase_overlap = self._phrase_overlap_score(query, document_text)
            bm25_component = 0.0
            if self.bm25 is not None and bm25_scores is not None:
                bm25_component = float(bm25_scores[self.doc_ids.index(d_id)]) if self.doc_ids.index(d_id) < len(bm25_scores) else 0.0
            reranked_results.append({
                "id": d_id,
                "document": document_text,
                "metadata": metadata,
                "rrf_score": rrf_scores[d_id],
                "rerank_score": rrf_scores[d_id] + self._metadata_bonus(metadata, query) + phrase_overlap * 0.35 + (bm25_component / max(1.0, abs(bm25_component)) * 0.1),
            })

        reranked_results.sort(key=lambda item: (item["rerank_score"], item["rrf_score"]), reverse=True)
        return reranked_results[:top_k]
