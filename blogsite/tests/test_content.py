import tempfile
import unittest
from pathlib import Path

from blogsite.content import (
    discover_articles,
    extract_excerpt,
    load_about_page,
    load_series_map,
)
from blogsite.model import SiteMetadata

FIXTURES = Path(__file__).parent / "fixtures"


class ContentTests(unittest.TestCase):
    def test_articles_are_newest_first_and_metadata_is_optional(self):
        meta = load_series_map(FIXTURES / "metadata.json")
        articles = discover_articles(FIXTURES / "journal", meta)
        self.assertEqual(
            [a.slug for a in articles], ["2026-01-02-second", "2026-01-01-first"]
        )
        self.assertEqual(articles[1].title, "Первая запись")
        self.assertEqual(articles[1].date.isoformat(), "2026-01-01")
        self.assertEqual(articles[1].series, ("Квантовый чай", "Утки"))
        self.assertIsNone(articles[0].origin)

    def test_publication_state_filters_draft_and_ready_but_keeps_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp)
            cases = {
                "2026-01-01-legacy.md": "",
                "2026-01-02-published.md": "Publication: published\n",
                "2026-01-03-ready.md": "Publication: ready\n",
                "2026-01-04-draft.md": "Publication: draft\n",
            }
            for name, metadata in cases.items():
                (journal / name).write_text(
                    f"# {name}\n\n```text\n{metadata}```\n\nBody.\n",
                    encoding="utf-8",
                )
            articles = discover_articles(journal, SiteMetadata({}))
            self.assertEqual(
                [article.slug for article in articles],
                ["2026-01-02-published", "2026-01-01-legacy"],
            )
            self.assertTrue(
                all(article.publication == "published" for article in articles)
            )

    def test_unknown_publication_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp)
            (journal / "2026-01-01-bad.md").write_text(
                "# Bad\n\n```text\nPublication: maybe\n```\n\nBody.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Unknown Publication state"):
                discover_articles(journal, SiteMetadata({}))

    def test_excerpt_uses_first_plain_paragraph(self):
        self.assertEqual(
            extract_excerpt("# Заголовок\n\nПервый абзац.\n\nВторой."), "Первый абзац."
        )
        self.assertEqual(
            extract_excerpt(
                "Origin: dialogue\nMode: joint note\n\n# Заголовок\n\nПервый абзац."
            ),
            "Первый абзац.",
        )

    def test_about_page_reads_title(self):
        page = load_about_page(FIXTURES / "about" / "continuity.md")
        self.assertEqual((page.slug, page.title), ("continuity", "Непрерывность"))
