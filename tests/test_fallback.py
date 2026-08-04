import importlib
import os
import unittest
import warnings
from unittest.mock import patch

import rag_orchestrator
from rag_orchestrator import AdmissionsRAGOrchestrator


class DummyDoc:
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = metadata or {}


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = object.__new__(AdmissionsRAGOrchestrator)

    def test_fallback_message_is_trustworthy_and_short(self):
        fallback = self.orchestrator._build_fallback_response("Model unavailable")
        self.assertIn("Insufficient information", fallback)
        self.assertLess(len(fallback), 140)

    def test_reads_gimini_api_key_alias_from_environment(self):
        with patch.dict(os.environ, {"GIMINI_API_KEY": "fake-key"}, clear=True):
            with patch.object(AdmissionsRAGOrchestrator, "_discover_available_gemini_models", return_value=[]):
                orchestrator = AdmissionsRAGOrchestrator()
        self.assertEqual(orchestrator.api_key, "fake-key")

    def test_import_suppresses_google_generativeai_future_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.reload(rag_orchestrator)

        messages = "\n".join(str(w.message) for w in caught)
        self.assertNotIn("google.generativeai", messages)

    def test_structured_sql_context_does_not_abstain(self):
        orchestrator = object.__new__(AdmissionsRAGOrchestrator)
        docs = [
            DummyDoc(
                page_content='Structured Database Results: [{"tuition_fee": 9250.0, "duration_years": 3}]',
                metadata={"data_layer": "Structured DB"},
            )
        ]
        context = "Structured Database Results: [{\"tuition_fee\": 9250.0, \"duration_years\": 3}]"

        self.assertFalse(orchestrator._should_abstain(docs, context, "What is the tuition fee and standard duration for these programs?"))
        self.assertGreater(
            orchestrator._confidence_score(docs, context, "What is the tuition fee and standard duration for these programs?"),
            0.7,
        )

    def test_structured_response_is_human_readable(self):
        orchestrator = object.__new__(AdmissionsRAGOrchestrator)
        docs = [
            DummyDoc(
                page_content='Structured Database Results: [{"university": "University of Leeds", "tuition_fee": 9250.0, "duration_years": 3, "median_salary": 31000.0}]',
                metadata={"data_layer": "Structured DB"},
            )
        ]
        rendered = orchestrator._format_structured_response(
            "What is the tuition fee and standard duration for these programs?",
            docs,
            'Structured Database Results: [{"university": "University of Leeds", "tuition_fee": 9250.0, "duration_years": 3, "median_salary": 31000.0}]',
        )

        self.assertIn("University of Leeds", rendered)
        self.assertIn("tuition fee", rendered.lower())
        self.assertIn("3 years", rendered)
        self.assertNotIn("Structured Database Results:", rendered)

    def test_structured_summary_is_preserved_by_grounding(self):
        orchestrator = object.__new__(AdmissionsRAGOrchestrator)
        docs = [
            DummyDoc(
                page_content='Structured Database Results: [{"university": "University of Leeds", "tuition_fee": 9250.0, "duration_years": 3}]',
                metadata={"data_layer": "Structured DB"},
            )
        ]
        answer = "The available records indicate: University of Leeds: tuition fee £9,250 per year; duration 3 years [1]"
        grounded = orchestrator._postprocess_grounded_answer(answer, docs)

        self.assertIn("University of Leeds", grounded)
        self.assertIn("tuition fee", grounded.lower())
        self.assertNotIn("Not Available", grounded)


if __name__ == "__main__":
    unittest.main()
