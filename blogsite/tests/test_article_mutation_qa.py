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
        self.assertIn("semantic_strengthening", {case.get("kind") for case in cases})

    def test_expected_outcome_mapping_is_explicit(self):
        self.assertTrue(expected_matches("killed", "KILLED_DETERMINISTIC"))
        self.assertTrue(expected_matches("survived", "SURVIVED"))
        self.assertFalse(expected_matches("killed", "SURVIVED"))
        self.assertFalse(expected_matches("survived", "KILLED_DETERMINISTIC"))

    def test_manifest_is_json_roundtrip_stable(self):
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(raw["schema"], "nakama.article-mutation.v1")
        self.assertTrue(raw["article"].startswith("journal/"))
