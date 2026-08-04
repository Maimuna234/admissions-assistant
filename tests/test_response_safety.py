import os
import tempfile
import unittest

from rag_orchestrator import AdmissionsRAGOrchestrator, Document


class ResponseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = object.__new__(AdmissionsRAGOrchestrator)

    def test_rejects_unrelated_answer_when_context_is_weak(self):
        docs = [Document(page_content="Tuition fee is £9,250.", metadata={"source_url": "u1"})]
        answer = self.orchestrator._postprocess_grounded_answer("The university offers scholarships for international students.", docs)
        self.assertIn("Not Available", answer)

    def test_abstains_for_structured_queries_without_matching_evidence(self):
        docs = [Document(page_content="The course includes modules in Year 1 and Year 2.", metadata={"source_url": "u1"})]
        formatted_context = self.orchestrator.format_docs(docs)

        should_abstain = self.orchestrator._should_abstain(
            docs,
            formatted_context,
            "Which university has the lowest tuition fee?",
        )

        self.assertTrue(should_abstain)

    def test_writes_trace_entry_for_monitoring(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".jsonl", delete=False) as handle:
            trace_path = handle.name
        try:
            self.orchestrator.trace_log_path = trace_path
            self.orchestrator._write_trace_event("demo-query", "demo-answer", 0.42, False)
            with open(trace_path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("demo-query", content)
            self.assertIn("demo-answer", content)
        finally:
            if os.path.exists(trace_path):
                os.remove(trace_path)


if __name__ == "__main__":
    unittest.main()
