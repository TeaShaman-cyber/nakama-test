import json
import unittest
from pathlib import Path

from tools.article_qa import QAFailure, verify_source_bindings


ROOT = Path(__file__).resolve().parents[2]
ARTICLE = ROOT / "journal" / "2026-09-22-readme-byl-velikolepen-sistema-ne-rabotala.md"
BINDINGS = (
    ROOT
    / "qa"
    / "source-bindings"
    / "2026-09-22-readme-byl-velikolepen-sistema-ne-rabotala.json"
)


class ArticleSourceBindingTests(unittest.TestCase):
    def test_current_article_matches_versioned_bindings(self):
        article = ARTICLE.read_text(encoding="utf-8")
        count = verify_source_bindings(
            article,
            ARTICLE.relative_to(ROOT).as_posix(),
            BINDINGS,
        )
        self.assertGreaterEqual(count, 5)

    def test_swapped_valid_urls_fail_binding_contract(self):
        article = ARTICLE.read_text(encoding="utf-8")
        contract = json.loads(BINDINGS.read_text(encoding="utf-8"))
        openai = next(
            binding
            for binding in contract["bindings"]
            if binding["id"] == "openai-interpretability"
        )
        anthropic = next(
            binding
            for binding in contract["bindings"]
            if binding["id"] == "anthropic-interpretability"
        )
        mutated = article.replace(openai["url"], "__OPENAI_SOURCE__", 1)
        mutated = mutated.replace(anthropic["url"], openai["url"], 1)
        mutated = mutated.replace("__OPENAI_SOURCE__", anthropic["url"], 1)
        with self.assertRaisesRegex(QAFailure, "source binding mismatch"):
            verify_source_bindings(
                mutated,
                ARTICLE.relative_to(ROOT).as_posix(),
                BINDINGS,
            )
