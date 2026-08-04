import os
import tempfile
import unittest

from rag_orchestrator import AdmissionsRAGOrchestrator, Document


class ConfidenceTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = object.__new__(AdmissionsRAGOrchestrator)

    def test_abstains_when_retrieved_docs_have_low_overlap_with_query(self):
        docs = [Document(page_content="The campus has a large library and student union.", metadata={"source_url": "u1"})]
        self.assertTrue(
            self.orchestrator._should_abstain(docs, "[Record 1] The campus has a large library and student union.", "What is the tuition fee?")
        )

    def test_assigns_higher_confidence_when_docs_match_query_terms(self):
        docs = [Document(page_content="Tuition fee for the program is £9,250.", metadata={"source_url": "u1"})]
        score = self.orchestrator._confidence_score(docs, "[Record 1] Tuition fee for the program is £9,250.", "What is the tuition fee?")
        self.assertGreaterEqual(score, 0.4)

    def test_logs_low_confidence_event_to_review_file(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".jsonl", delete=False) as handle:
            review_path = handle.name
        try:
            self.orchestrator.review_log_path = review_path
            self.orchestrator._log_low_confidence_event("What is the tuition fee?", 0.2, "weak evidence")
            with open(review_path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("weak evidence", content)
            self.assertIn("What is the tuition fee?", content)
        finally:
            if os.path.exists(review_path):
                os.remove(review_path)


if __name__ == "__main__":
    unittest.main()
