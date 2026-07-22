import unittest

from blogsite.urls import article_url, history_url, series_url, site_url, source_url


class UrlTests(unittest.TestCase):
    def test_project_pages_base_path(self):
        self.assertEqual(
            article_url("post", "/nakama-test/"), "/nakama-test/journal/post/"
        )
        self.assertEqual(
            site_url("static/style.css", "/nakama-test/"),
            "/nakama-test/static/style.css",
        )

    def test_series_slug(self):
        self.assertEqual(
            series_url("Квантовый чай", "/nakama-test/"),
            "/nakama-test/series/kvantovyi-chai/",
        )

    def test_source_history(self):
        self.assertIn("/blob/main/journal/", source_url("x.md"))
        self.assertIn("/commits/main/journal/", history_url("x.md"))
