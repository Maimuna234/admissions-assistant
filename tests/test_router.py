import unittest

from router import QueryRouter


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def search(self, query, top_k=5, where_clause=None):
        self.calls.append((query, where_clause))
        return []


class QueryRouterTests(unittest.TestCase):
    def test_route_and_fetch_uses_metadata_filter_for_curriculum_queries(self):
        retriever = FakeRetriever()
        router = QueryRouter(db_path=":memory:", hybrid_retriever=retriever)

        router.route_and_fetch("What are the Year 1 core modules?")

        self.assertEqual(len(retriever.calls), 1)
        self.assertEqual(retriever.calls[0][1]["academic_year"], 1)
        self.assertEqual(retriever.calls[0][1]["content_type"], "curriculum")


if __name__ == "__main__":
    unittest.main()
