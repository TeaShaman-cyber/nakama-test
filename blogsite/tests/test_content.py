from pathlib import Path
import unittest
from blogsite.content import (
    discover_articles,
    extract_excerpt,
    load_about_page,
    load_series_map,
)

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

    def test_excerpt_uses_first_plain_paragraph(self):
        self.assertEqual(
            extract_excerpt("# Заголовок\n\nПервый абзац.\n\nВторой."), "Первый абзац."
        )

    def test_about_page_reads_title(self):
        page = load_about_page(FIXTURES / "about" / "continuity.md")
        self.assertEqual((page.slug, page.title), ("continuity", "Непрерывность"))
