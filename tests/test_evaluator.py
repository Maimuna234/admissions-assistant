import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from evaluator import NO_INFO_CANONICAL, RAGEvaluator, align_ground_truth_to_rag


class EvaluatorTests(unittest.TestCase):
    def test_align_ground_truth_normalizes_wrapped_no_info_responses(self):
        value = align_ground_truth_to_rag(
            "Based on the provided Context Chunks, here is the output:\n\n• Information Not Available in Source Documentation"
        )
        self.assertEqual(value, NO_INFO_CANONICAL)

    def test_build_evaluation_query_includes_target_institution_context(self):
        evaluator = RAGEvaluator()
        query = evaluator._build_evaluation_query({
            "question": "What are the core modules taught in Year 1?",
            "target_competitor": "University of Leeds",
        })
        self.assertIn("University of Leeds", query)
        self.assertIn("Computer Science BSc", query)

    def test_run_evaluations_writes_numeric_metric_scores(self):
        evaluator = RAGEvaluator()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_csv = os.path.join(tmp_dir, "evaluation_results.csv")
            evaluator.run_evaluations(output_csv=output_csv)

            with open(output_csv, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertTrue(rows, "No evaluation rows were written")

            for row in rows:
                for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                    value = row.get(metric, "")
                    self.assertNotEqual(value, "", f"{metric} was not populated")
                    numeric_value = float(value)
                    self.assertGreaterEqual(numeric_value, 0.0)
                    self.assertLessEqual(numeric_value, 1.0)


if __name__ == "__main__":
    unittest.main()
