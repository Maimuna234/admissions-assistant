import os
import sqlite3
import tempfile
import unittest

from rag_orchestrator import AdmissionsRAGOrchestrator, Document, QueryRouter
from seed_db import import_structured_admissions_db, seed_verified_database


class StructuredDBTests(unittest.TestCase):
    def test_seeded_structured_db_contains_admissions_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "admissions_structured.db")
            seed_verified_database(db_path)

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT university, ucas_code, uk_tuition_fee, duration_years, has_placement_year, final_year_project_credits FROM course_facts WHERE university = ?",
                ("University of Leeds",),
            ).fetchone()
            conn.close()

            self.assertIsNotNone(row)
            self.assertEqual(row[1], "G400")
            self.assertEqual(row[2], 9250)
            self.assertEqual(row[3], 3)
            self.assertEqual(row[4], 1)
            self.assertEqual(row[5], 40)

    def test_execute_sql_returns_richer_structured_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "admissions_structured.db")
            seed_verified_database(db_path)
            router = QueryRouter(db_path=db_path)

            docs = router.execute_sql("Which university has the lowest tuition fee?")

            self.assertGreater(len(docs), 0)
            content = docs[0].page_content.lower()
            self.assertIn("ucas_code", content)
            self.assertIn("uk_tuition_fee", content)
            self.assertIn("placement", content)

    def test_should_not_abstain_for_single_structured_sql_result(self):
        orchestrator = AdmissionsRAGOrchestrator.__new__(AdmissionsRAGOrchestrator)
        doc = Document(
            page_content='Structured Database Results: [{"university": "University of Leeds", "duration_years": 3, "uk_tuition_fee": 9250, "median_salary_3yr": 32000}]',
            metadata={"source_url": "SQLite: course_facts table", "data_layer": "Structured DB"},
        )

        self.assertFalse(
            orchestrator._should_abstain([doc], "Structured database context", "How long is the standard BSc degree program?")
        )

    def test_format_structured_response_uses_sql_field_names(self):
        orchestrator = AdmissionsRAGOrchestrator.__new__(AdmissionsRAGOrchestrator)
        doc = Document(
            page_content='Structured Database Results: [{"university": "University of Leeds", "duration_years": 3, "uk_tuition_fee": 9250, "median_salary_3yr": 32000}]',
            metadata={"source_url": "SQLite: course_facts table", "data_layer": "Structured DB"},
        )

        response = orchestrator._format_structured_response("How long is the standard BSc degree program?", [doc], "")

        self.assertIn("3 years", response)
        self.assertIn("University of Leeds", response)

    def test_normalize_answer_uses_context_for_curriculum_queries(self):
        orchestrator = AdmissionsRAGOrchestrator.__new__(AdmissionsRAGOrchestrator)
        doc = Document(
            page_content='Context Area [Curriculum Year 1] for University of Leeds (CS303): Year 1 Modules COMP1111 Procedural Coding, COMP1222 Discrete Mathematics, Systems Architecture.',
            metadata={"university": "University of Leeds", "course_code": "CS303", "content_type": "curriculum"},
        )

        normalized = orchestrator._normalize_answer_from_context(
            "What are the core modules taught in Year 1?",
            "I can help with that in general terms.",
            [doc],
        )

        self.assertIn("Year 1 core modules include", normalized)
        self.assertIn("COMP1111", normalized)
        self.assertIn("Procedural Coding", normalized)

    def test_import_structured_admissions_db_into_project_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_db = os.path.join(tmpdir, "source.db")
            target_db = os.path.join(tmpdir, "target.db")

            conn = sqlite3.connect(source_db)
            conn.execute(
                "CREATE TABLE course_facts (university TEXT, course_title TEXT, ucas_code TEXT, duration_years INTEGER, has_placement_year INTEGER, employment_rate_15m REAL, median_salary_3yr REAL, entry_tariff REAL, bcs_accredited INTEGER)"
            )
            conn.execute(
                "INSERT INTO course_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("University of Leeds", "Computer Science BSc", "G400", 3, 1, 88.5, 32000.0, 160.0, 1),
            )
            conn.commit()
            conn.close()

            import_structured_admissions_db(source_db, target_db)

            conn = sqlite3.connect(target_db)
            row = conn.execute(
                "SELECT university, course_title, ucas_code, duration_years, has_placement_year, median_salary_3yr, employment_rate_15m FROM course_facts WHERE university = ?",
                ("University of Leeds",),
            ).fetchone()
            conn.close()

            self.assertIsNotNone(row)
            self.assertEqual(row[1], "Computer Science BSc")
            self.assertEqual(row[3], 3)
            self.assertEqual(row[5], 32000.0)
