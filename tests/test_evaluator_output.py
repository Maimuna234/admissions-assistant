import unittest
import csv
import os
import tempfile

from evaluator import RAGEvaluator


class EvaluatorOutputTests(unittest.TestCase):
    def test_evaluator_writes_summary_columns(self):
        evaluator = RAGEvaluator()
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as handle:
            output_path = handle.name

        try:
            evaluator.run_evaluations(output_csv=output_path)
            with open(output_path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertGreater(len(rows), 0)
            self.assertIn("confidence_score", rows[0])
            self.assertIn("should_abstain", rows[0])
            self.assertIn("faithfulness", rows[0])
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_write_summary_csv_creates_workspace_summary_file(self):
        evaluator = RAGEvaluator()
        summary_path = os.path.join(os.path.dirname(os.path.abspath(evaluator.__class__.__module__.replace('.', os.sep))), "evaluation_summary.csv")
        if os.path.exists(summary_path):
            os.remove(summary_path)

        evaluator._write_summary_csv([], "ignored.csv", summary_path=summary_path)

        self.assertTrue(os.path.exists(summary_path))
        if os.path.exists(summary_path):
            os.remove(summary_path)


if __name__ == "__main__":
    unittest.main()
