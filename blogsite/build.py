from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from blogsite.content import discover_articles, load_about_page, load_series_map
from blogsite.render import render_about, render_article, render_home, render_index
from blogsite.urls import slugify_series
from blogsite.validate import (
    assert_canonical_unchanged,
    snapshot_canonical,
    validate_generated_links,
    validate_source_slugs,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_site(repo_root: Path, output_dir: Path, base_path: str) -> None:
    canonical_before = snapshot_canonical(repo_root)
    validate_source_slugs(repo_root / "journal")
    metadata = load_series_map(repo_root / "blogsite" / "metadata.json")
    articles = discover_articles(repo_root / "journal", metadata)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    _write(output_dir / "index.html", render_home(articles, base_path))
    _write(
        output_dir / "journal" / "index.html",
        render_index("Журнал", articles, base_path),
    )

    chronological = list(reversed(articles))
    for index, article in enumerate(chronological):
        previous = chronological[index - 1] if index > 0 else None
        next_ = chronological[index + 1] if index + 1 < len(chronological) else None
        _write(
            output_dir / "journal" / article.slug / "index.html",
            render_article(article, previous, next_, base_path),
        )

    series_names = sorted({name for article in articles for name in article.series})
    for name in series_names:
        _write(
            output_dir / "series" / slugify_series(name) / "index.html",
            render_index(
                name,
                [article for article in articles if name in article.series],
                base_path,
            ),
        )

    for name in ("continuity", "method"):
        page = load_about_page(repo_root / "about" / f"{name}.md")
        _write(
            output_dir / "about" / name / "index.html",
            render_about(page, base_path),
        )

    shutil.copytree(repo_root / "blogsite" / "static", output_dir / "static")
    validate_generated_links(output_dir, base_path)
    assert_canonical_unchanged(repo_root, canonical_before)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Jester GitHub Pages site.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("public"))
    parser.add_argument("--base-path", default="/nakama-test/")
    args = parser.parse_args()
    build_site(args.repo_root, args.output, args.base_path)


if __name__ == "__main__":
    main()
