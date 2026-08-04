import unittest

from ingest import DataIngestionPipeline


class IngestEnrichmentTests(unittest.TestCase):
    def test_extract_metadata_recognizes_financial_and_requirement_terms(self):
        pipeline = DataIngestionPipeline.__new__(DataIngestionPipeline)
        metadata = pipeline.extract_metadata(
            "Official specification for University of Leeds. Entry Requirements: AAA including Mathematics. Fees: Home tuition fee £9,250/year. Median salary £32,000.",
            "sample.pdf",
        )

        self.assertEqual(metadata["university"], "University of Leeds")
        self.assertEqual(metadata["content_type"], "financial_stats")


if __name__ == "__main__":
    unittest.main()
