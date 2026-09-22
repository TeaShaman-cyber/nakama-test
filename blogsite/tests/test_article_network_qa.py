from pathlib import Path
import unittest

from tools.article_network_qa import (
    classify_formal_mutation,
    external_provider_degraded,
    graph_edges,
    mutated_graph_text,
    parse_wolfram_result,
    wolfram_code,
)


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
        self.assertIn("rootsPresent=And@@(MemberQ[vertices,#]&/@roots)", code)
        self.assertIn("allRootsReach=If[rootsPresent&&conclusionPresent", code)

    def test_exa_rate_limit_is_degraded_not_no_signal(self):
        payload = {
            "_meta": {"ai.exa/rateLimited": True},
            "content": [
                {"type": "text", "text": "You've hit Exa's free MCP rate limit."}
            ],
        }
        self.assertTrue(external_provider_degraded(payload))

    def test_normal_search_payload_is_not_degraded(self):
        payload = {"content": [{"type": "text", "text": "search results"}]}
        self.assertFalse(external_provider_degraded(payload))

    def test_graph_mutation_removes_astra_edge_from_versioned_case(self):
        graph, case = mutated_graph_text(
            Path("qa/mutation/2026-09-22-readme-baseline.json"),
            "cut-astra-argument-edge",
            "qa/argument-graphs/2026-09-22-readme-byl-velikolepen-sistema-ne-rabotala.mmd",
        )
        self.assertEqual(case["kind"], "argument_graph")
        self.assertNotIn("  A --> S\n", graph)
        self.assertNotIn(("A", "S"), graph_edges(graph))

    def test_formal_mutation_verdict_inverts_canonical_failure_semantics(self):
        self.assertEqual(classify_formal_mutation("FAIL_ASSERTION"), "KILLED_FORMAL")
        self.assertEqual(classify_formal_mutation("PASS"), "SURVIVED_FORMAL")
        self.assertEqual(
            classify_formal_mutation("DEGRADED_EXTERNAL_WITNESS"),
            "DEGRADED_EXTERNAL_WITNESS",
        )
