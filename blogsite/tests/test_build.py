from pathlib import Path
import tempfile
import unittest

from blogsite.build import build_site


class BuildTests(unittest.TestCase):
    def test_build_creates_expected_routes_and_static_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "public"
            build_site(Path.cwd(), out, "/nakama-test/")
            expected = [
                out / "index.html",
                out / "journal" / "index.html",
                out / "about" / "continuity" / "index.html",
                out / "about" / "method" / "index.html",
                out / "static" / "style.css",
                out / "static" / "favicon.svg",
            ]
            for path in expected:
                self.assertTrue(path.exists(), str(path))
            article_pages = list((out / "journal").glob("*/index.html"))
            self.assertGreaterEqual(len(article_pages), 1)
