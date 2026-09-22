import json
import unittest
from pathlib import Path

from tools.article_semantic_qa import classify_relation, semantic_text


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "qa" / "semantic" / "article-nli.json"
MUTATIONS = ROOT / "qa" / "mutation" / "2026-09-22-readme-baseline.json"


class ArticleSemanticQaTests(unittest.TestCase):
    def test_relation_classifier_distinguishes_equivalence_change_and_unknown(self):
        kwargs = {"equivalent_min": 0.75, "changed_max_min_direction": 0.20}
        self.assertEqual(classify_relation(0.87, 0.93, **kwargs), "equivalent")
        self.assertEqual(classify_relation(0.01, 0.002, **kwargs), "changed")
        self.assertEqual(classify_relation(0.55, 0.45, **kwargs), "unknown")

    def test_epistemic_prefix_is_not_part_of_semantic_proposition(self):
        claim = "absence of output is weak evidence"
        self.assertEqual(semantic_text(f"INFERENCE: {claim}"), claim)
        self.assertEqual(semantic_text(f"FACT: {claim}"), claim)
        self.assertEqual(semantic_text(f"UNKNOWN: {claim}"), claim)
        self.assertEqual(semantic_text(claim), claim)

    def test_profile_is_pinned_and_advisory_only(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["schema"], "nakama.article-semantic-nli.v1")
        self.assertFalse(profile["acceptance_authority"])
        self.assertEqual(
            profile["model"]["revision"],
            "b80e2b3219194b8685948dedfb73d594ed088732",
        )
        self.assertEqual(len(profile["model"]["onnx"]["sha256"]), 64)
        self.assertEqual(profile["model"]["onnx"]["size_bytes"], 87246195)

    def test_profile_targets_safe_control_and_known_gap(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        mutations = json.loads(MUTATIONS.read_text(encoding="utf-8"))
        mutation_ids = {case["id"] for case in mutations["cases"]}
        expected = {
            case["mutation_id"]: case["expected_relation"] for case in profile["cases"]
        }
        self.assertEqual(
            expected["safe-paraphrase-weak-evidence-english"], "equivalent"
        )
        self.assertEqual(expected["strengthen-weak-evidence-to-proof"], "changed")
        self.assertTrue(set(expected).issubset(mutation_ids))

    def test_runtime_requirements_are_direct_hash_pinned_wheels(self):
        lines = [
            line.strip()
            for line in (ROOT / "requirements" / "ci-article-semantic.txt")
            .read_text()
            .splitlines()
            if line.strip() and not line.startswith("#")
        ]
        self.assertEqual(len(lines), 6)
        self.assertTrue(
            all(line.startswith("https://files.pythonhosted.org/") for line in lines)
        )
        self.assertTrue(all("#sha256=" in line for line in lines))
