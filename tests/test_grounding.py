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

    def test_uses_selected_priorities_in_comparison_summary(self):
        docs = [
            Document(
                page_content="University of Leeds: entry tariff 160 UCAS points; BCS accredited; median salary £32,000; tuition fee £9,250/year; NSS teaching satisfaction 82%.",
                metadata={"university": "University of Leeds"},
            ),
            Document(
                page_content="University of Sheffield: entry tariff 150 UCAS points; BCS accredited; median salary £30,000; tuition fee £9,250/year; NSS teaching satisfaction 80%.",
                metadata={"university": "University of Sheffield"},
            ),
        ]

        answer = self.orchestrator._synthesize_answer(
            "Compare the target programme against the selected competitor university and return a short decision summary.",
            docs,
            priorities=["Entry Requirements", "Graduate Outcomes & Salary"],
        )

        self.assertIn("Entry Requirements", answer)
        self.assertIn("Graduate Outcomes & Salary", answer)
        self.assertIn("160 UCAS", answer)
        self.assertIn("£32,000", answer)

    def test_repairs_insufficient_comparison_with_evidence_summary(self):
        docs = [
            Document(
                page_content="University of Leeds: entry tariff 160 UCAS points; median salary £32,000.",
                metadata={"university": "University of Leeds"},
            ),
            Document(
                page_content="University of Sheffield: entry tariff 150 UCAS points; median salary £30,000.",
                metadata={"university": "University of Sheffield"},
            ),
        ]

        repaired = self.orchestrator._repair_insufficient_comparison_answer(
            "Insufficient information in the provided context to answer this question reliably.",
            docs,
            priorities=["Entry Requirements", "Graduate Outcomes & Salary"],
        )

        self.assertIn("Decision summary", repaired)
        self.assertIn("Entry Requirements", repaired)
        self.assertIn("Graduate Outcomes & Salary", repaired)
        self.assertNotIn("Insufficient information", repaired)

    def test_priority_coverage_snapshot_flags_low_coverage_priority(self):
        baseline_row = {
            "entry_tariff": 160,
            "alevel_requirement": "AAA",
            "pct_entrants_alevel": 72.1,
            "has_foundation_year": True,
            "median_salary_leo3": 32000,
            "employment_rate_15m": 91.0,
            "_career_text": "Strong employment outcomes.",
        }
        competitor_row = {
            "entry_tariff": 150,
            "alevel_requirement": "AAB",
            "pct_entrants_alevel": 68.4,
            "has_foundation_year": False,
            "median_salary_leo3": 30000,
            "employment_rate_15m": 88.2,
            "_career_text": "Good employability.",
        }

        snapshot = self.orchestrator._priority_coverage_snapshot(
            ["Entry Requirements", "Fees & Cost"],
            baseline_row,
            competitor_row,
        )

        by_priority = {item["priority"]: item for item in snapshot}
        self.assertTrue(by_priority["Entry Requirements"]["usable"])
        self.assertFalse(by_priority["Fees & Cost"]["usable"])
        self.assertEqual(by_priority["Fees & Cost"]["baseline_ratio"], 0.0)
        self.assertEqual(by_priority["Fees & Cost"]["competitor_ratio"], 0.0)

    def test_priority_answer_usability_rejects_low_information_text(self):
        usable = self.orchestrator._is_priority_answer_usable(
            "Insufficient information in the provided context to answer this question reliably.",
            ["Entry Requirements", "Fees & Cost"],
        )

        self.assertFalse(usable)

        usable_structured = self.orchestrator._is_priority_answer_usable(
            "## 1. Entry Requirements\nWinner: University of Leeds — higher tariff evidence.\n## OVERALL RECOMMENDATION",
            ["Entry Requirements", "Fees & Cost"],
        )

        self.assertTrue(usable_structured)

    def test_build_local_priority_summary_returns_decision_summary(self):
        baseline_row = {
            "entry_tariff": 160,
            "median_salary_leo3": 32000,
            "tuition_fee_uk": "£9,250/year",
            "bcs_accredited": True,
        }
        competitor_row = {
            "entry_tariff": 150,
            "median_salary_leo3": 30000,
            "tuition_fee_uk": "£9,250/year",
            "bcs_accredited": False,
        }

        summary = self.orchestrator._build_local_priority_summary(
            ["Entry Requirements", "Graduate Outcomes & Salary", "Fees & Cost", "Curriculum & Accreditation"],
            "University of Liverpool",
            "Lancaster University",
            baseline_row,
            competitor_row,
        )

        self.assertIn("Decision summary", summary)
        self.assertIn("Entry Requirements", summary)
        self.assertIn("Winner", summary)
        self.assertIn("Overall recommendation", summary)


if __name__ == "__main__":
    unittest.main()
