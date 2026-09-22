import unittest

from tools.article_network_qa import graph_edges, parse_wolfram_result, wolfram_code


class ArticleNetworkQaTests(unittest.TestCase):
    def test_graph_edges_only_accept_identifier_edges(self):
        graph = 'A --> B\nB --> C\nX["label"] --> Y\nnot-an-id --> Z\n'
        self.assertEqual(graph_edges(graph), [("A", "B"), ("B", "C")])

    def test_parse_wolfram_exported_json(self):
        payload = {
            "content": [
                {
                    "type": "text",
                    "text": 'Out[1]= "{\\"pass\\":true,\\"vertex_count\\":3}"',
                }
            ]
        }
        self.assertEqual(
            parse_wolfram_result(payload),
            {"pass": True, "vertex_count": 3},
        )

    def test_wolfram_code_contains_only_structural_claims(self):
        code = wolfram_code([("A", "B"), ("B", "C")], ["A"], "C")
        self.assertIn("AcyclicGraphQ", code)
        self.assertIn("ConnectedComponents", code)
        self.assertIn("GraphDistance", code)
        self.assertNotIn("URLRead", code)
        self.assertNotIn("Import[", code)
