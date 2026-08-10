import unittest

from rag_orchestrator import AdmissionsRAGOrchestrator, Document


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = object.__new__(AdmissionsRAGOrchestrator)

    def test_returns_not_available_when_answer_has_no_evidence(self):
        docs = [Document(page_content="Tuition fee is £9,250.", metadata={"source_url": "u1"})]

        answer = self.orchestrator._postprocess_grounded_answer(
            "The degree is free.",
            docs,
        )

        self.assertIn("Not Available", answer)
        self.assertIn("[1]", answer)

    def test_appends_citations_to_grounded_answer(self):
        docs = [Document(page_content="Tuition fee is £9,250.", metadata={"source_url": "u1"})]

        answer = self.orchestrator._postprocess_grounded_answer(
            "Tuition fee is £9,250.",
            docs,
        )

        self.assertIn("Tuition fee is £9,250.", answer)
        self.assertIn("[1]", answer)

    def test_synthesizes_year_one_curriculum_answer_from_evidence(self):
        docs = [
            Document(
                page_content="Context Area [Curriculum Year 1] for University of Leeds (CS303): Year 1 Modules COMP1111 Procedural Coding, COMP1222 Discrete Mathematics, Systems Architecture.",
                metadata={"university": "University of Leeds", "academic_year": 1, "content_type": "curriculum"},
            )
        ]

        answer = self.orchestrator._synthesize_answer(
            "What are the core modules taught in Year 1?",
            docs,
        )

        self.assertIn("Year 1 core modules include", answer)
        self.assertIn("Procedural Coding", answer)
        self.assertIn("Discrete Mathematics", answer)

    def test_prefers_grounded_synthesis_for_generic_model_output(self):
        docs = [
            Document(
                page_content="Context Area [Curriculum Year 1] for University of Leeds (CS303): Year 1 Modules COMP1111 Procedural Coding, COMP1222 Discrete Mathematics, Systems Architecture.",
                metadata={"university": "University of Leeds", "academic_year": 1, "content_type": "curriculum"},
            )
        ]

        answer = self.orchestrator._select_best_response(
            "I can help with that in general terms.",
            "What are the core modules taught in Year 1?",
            docs,
        )

        self.assertIn("Year 1 core modules include", answer)
        self.assertIn("Procedural Coding", answer)

    def test_synthesizes_leeds_sheffield_comparison_answer(self):
        docs = [
            Document(
                page_content="Context Area [Curriculum Year 1] for University of Leeds (CS303): Year 1 Modules COMP1111 Procedural Coding, COMP1222 Discrete Mathematics, Systems Architecture.",
                metadata={"university": "University of Leeds", "academic_year": 1, "content_type": "curriculum"},
            ),
            Document(
                page_content="Context Area [Curriculum Year 1] for University of Sheffield (CS606): Year 1 Modules COMP1111 Procedural Coding, COMP1222 Discrete Mathematics, Systems Architecture.",
                metadata={"university": "University of Sheffield", "academic_year": 1, "content_type": "curriculum"},
            ),
        ]

        answer = self.orchestrator._synthesize_answer(
            "Compare the Year 1 curriculum between Leeds and Sheffield.",
            docs,
        )

        self.assertIn("Leeds", answer)
        self.assertIn("Sheffield", answer)
        self.assertIn("procedural coding", answer.lower())

    def test_uses_polished_decision_summary_for_comparison_queries(self):
        docs = [
            Document(
                page_content="University of Leeds: entry tariff 160 UCAS points; BCS accredited; median salary £32,000.",
                metadata={"university": "University of Leeds"},
            ),
            Document(
                page_content="University of Sheffield: entry tariff 150 UCAS points; BCS accredited; median salary £30,000.",
                metadata={"university": "University of Sheffield"},
            ),
        ]

        answer = self.orchestrator._synthesize_answer(
            "Compare the target programme against the selected competitor university and return a short decision summary.",
            docs,
        )

        self.assertIn("Decision summary", answer)
        self.assertNotIn("The retrieved evidence supports the following answer:", answer)
        self.assertIn("Leeds", answer)
        self.assertIn("Sheffield", answer)


if __name__ == "__main__":
    unittest.main()
