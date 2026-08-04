import unittest

from hybrid_retriever import HybridRetriever


class FakeCollection:
    def __init__(self):
        self.docs = [
            {
                "id": "doc-1",
                "document": "Curriculum: Year 1 modules include procedural coding and discrete mathematics.",
                "metadata": {"content_type": "curriculum", "academic_year": 1},
            },
            {
                "id": "doc-2",
                "document": "Annual tuition fee is 9250 pounds and salary is 31000.",
                "metadata": {"content_type": "financial_stats", "academic_year": 0},
            },
        ]

    def get(self):
        return {
            "ids": [item["id"] for item in self.docs],
            "documents": [item["document"] for item in self.docs],
            "metadatas": [item["metadata"] for item in self.docs],
        }

    def query(self, query_texts, n_results, where=None):
        return {"ids": [[self.docs[0]["id"], self.docs[1]["id"]]]}


class HybridRetrieverTests(unittest.TestCase):
    def test_search_prioritizes_relevant_curriculum_chunk(self):
        retriever = HybridRetriever(FakeCollection())
        results = retriever.search("What are the Year 1 core modules?", top_k=2)

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["id"], "doc-1")
        self.assertIn("curriculum", results[0]["document"].lower())

    def test_phrase_overlap_score_prefers_exact_matches(self):
        retriever = HybridRetriever(FakeCollection())
        exact_score = retriever._phrase_overlap_score("tuition fee", "The tuition fee is £9,250.")
        weak_score = retriever._phrase_overlap_score("tuition fee", "The course includes modules and placements.")

        self.assertGreater(exact_score, weak_score)


if __name__ == "__main__":
    unittest.main()
