from pathlib import Path
import tempfile
import unittest

from blogsite.validate import (
    assert_canonical_unchanged,
    snapshot_canonical,
    validate_generated_links,
    validate_source_slugs,
)


class ValidateTests(unittest.TestCase):
    def test_duplicate_slugs_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "journal"
            journal.mkdir()
            (journal / "2026-01-01-a.md").write_text("# A\n", encoding="utf-8")
            (journal / "2026-01-01-a.MD").write_text("# B\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_source_slugs(journal)

    def test_broken_internal_link_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "index.html").write_text(
                '<a href="/nakama-test/missing/">broken</a>', encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                validate_generated_links(out, "/nakama-test/")

    def test_canonical_mutation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("before", encoding="utf-8")
            (root / "journal").mkdir()
            (root / "journal" / "a.md").write_text("entry", encoding="utf-8")
            before = snapshot_canonical(root)
            (root / "journal" / "a.md").write_text("changed", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                assert_canonical_unchanged(root, before)
