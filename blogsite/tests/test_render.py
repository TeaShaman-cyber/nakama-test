from datetime import date
import unittest

from blogsite.model import Article
from blogsite.render import render_article, render_home

ARTICLE = Article(
    "2026-01-01-test.md",
    "2026-01-01-test",
    "Тестовая запись",
    date(2026, 1, 1),
    "# Тестовая запись\n\n> Цитата\n\n```text\nPASS\n```",
    "Цитата",
    ("Квантовый чай",),
)


class RenderTests(unittest.TestCase):
    def test_article(self):
        html = render_article(ARTICLE, None, None, "/nakama-test/")
        self.assertIn("<blockquote>", html)
        self.assertIn("/nakama-test/static/style.css", html)
        self.assertIn("blob/main/journal/2026-01-01-test.md", html)
        self.assertIn("commits/main/journal/2026-01-01-test.md", html)

    def test_home(self):
        html = render_home([ARTICLE], "/nakama-test/")
        self.assertIn("Привет, мир. Я — Шут.", html)
        self.assertIn("/nakama-test/journal/2026-01-01-test/", html)
