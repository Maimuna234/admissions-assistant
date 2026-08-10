import unittest
from pathlib import Path


class StreamlitDeploymentTests(unittest.TestCase):
    def test_streamlit_entrypoint_and_requirements_exist(self):
        repo_root = Path(__file__).resolve().parents[1]

        self.assertTrue((repo_root / "app.py").exists(), "Expected a Streamlit entrypoint at app.py")

        requirements = (repo_root / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("streamlit", requirements.lower())
        self.assertIn("rank-bm25", requirements.lower())
        self.assertIn("python-dotenv", requirements.lower())


if __name__ == "__main__":
    unittest.main()
