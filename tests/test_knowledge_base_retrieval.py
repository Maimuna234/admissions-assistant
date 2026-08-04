import unittest

from rag_orchestrator import KnowledgeBaseFallbackRetriever


class KnowledgeBaseFallbackRetrieverTests(unittest.TestCase):
    def test_finds_year_one_curriculum_evidence(self):
        retriever = KnowledgeBaseFallbackRetriever()
        docs = retriever.search("What are the Year 1 core modules?", top_k=3)

        self.assertGreater(len(docs), 0)
        text = " ".join(doc.page_content for doc in docs).lower()
        self.assertIn("year 1", text)
        self.assertIn("procedural coding", text)

    def test_finds_entry_requirements_and_student_support_evidence(self):
        retriever = KnowledgeBaseFallbackRetriever()
        docs = retriever.search("What are the entry requirements and student support options?", top_k=3)

        self.assertGreater(len(docs), 0)
        text = " ".join(doc.page_content for doc in docs).lower()
        self.assertTrue(
            "entry requirements" in text or "student support" in text or "personal tutoring" in text,
            msg=f"Expected admissions support evidence in retrieved content, got: {text}",
        )

    def test_prioritizes_university_named_in_query(self):
        retriever = KnowledgeBaseFallbackRetriever()
        docs = retriever.search("What are the entry requirements for Leeds Computer Science?", top_k=3)

        self.assertGreater(len(docs), 0)
        self.assertEqual(docs[0].metadata.get("institution"), "University of Leeds")


if __name__ == "__main__":
    unittest.main()
