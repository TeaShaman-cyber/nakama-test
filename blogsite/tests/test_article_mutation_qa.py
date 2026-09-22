import json
import unittest
from pathlib import Path

from tools.article_mutation_qa import expected_matches, load_manifest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "qa" / "mutation" / "2026-09-22-readme-baseline.json"


class ArticleMutationQaTests(unittest.TestCase):
    def test_baseline_declares_multiple_kills_and_an_intentional_survivor(self):
        manifest = load_manifest(MANIFEST)
        cases = manifest["cases"]
        self.assertGreaterEqual(len(cases), 6)
        self.assertGreaterEqual(sum(case["expected"] == "killed" for case in cases), 5)
        self.assertGreaterEqual(
            sum(case["expected"] == "survived" for case in cases), 1
        )
        kinds = {case.get("kind") for case in cases}
        purposes = {case.get("purpose") for case in cases}
        self.assertIn("semantic_strengthening", kinds)
        self.assertIn("source_binding", kinds)
        self.assertIn("metamorphic_paraphrase", kinds)
        self.assertIn("metamorphic_formatting", kinds)
        self.assertIn("known_semantic_gap", purposes)
        self.assertIn("metamorphic_invariance", purposes)

    def test_expected_outcome_mapping_is_explicit(self):
        self.assertTrue(expected_matches("killed", "KILLED_DETERMINISTIC"))
        self.assertTrue(expected_matches("survived", "SURVIVED"))
        self.assertFalse(expected_matches("killed", "SURVIVED"))
        self.assertFalse(expected_matches("survived", "KILLED_DETERMINISTIC"))

    def test_manifest_is_json_roundtrip_stable(self):
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(raw["schema"], "nakama.article-mutation.v1")
        self.assertTrue(raw["article"].startswith("journal/"))

    def test_valid_source_swap_is_expected_to_be_killed(self):
        manifest = load_manifest(MANIFEST)
        case = next(
            case
            for case in manifest["cases"]
            if case["id"] == "swap-valid-interpretability-sources"
        )
        self.assertEqual(case["expected"], "killed")
        self.assertEqual(case["purpose"], "fault_injection")
        self.assertIn("openai.com/index/understanding-neural-networks", case["old"])
        self.assertIn(
            "anthropic.com/research/tracing-thoughts-language-model", case["old"]
        )
        self.assertIn("openai.com/index/understanding-neural-networks", case["new"])
        self.assertIn(
            "anthropic.com/research/tracing-thoughts-language-model", case["new"]
        )

    def test_metamorphic_cases_are_expected_to_survive(self):
        manifest = load_manifest(MANIFEST)
        cases = [
            case
            for case in manifest["cases"]
            if case.get("purpose") == "metamorphic_invariance"
        ]
        self.assertGreaterEqual(len(cases), 2)
        self.assertTrue(all(case["expected"] == "survived" for case in cases))
