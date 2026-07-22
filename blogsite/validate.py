from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

CANONICAL_DIRS = ("about", "journal", "archive")
CANONICAL_FILES = ("README.md",)


def validate_source_slugs(journal_dir: Path) -> None:
    seen: dict[str, Path] = {}
    for path in sorted(journal_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        slug = path.stem.lower()
        if slug in seen:
            raise ValueError(f"duplicate article slug: {path.stem}")
        seen[slug] = path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def snapshot_canonical(repo_root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for name in CANONICAL_FILES:
        path = repo_root / name
        if path.exists():
            snapshot[name] = _sha256(path)
    for dirname in CANONICAL_DIRS:
        root = repo_root / dirname
        if not root.exists():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            relative = path.relative_to(repo_root).as_posix()
            snapshot[relative] = _sha256(path)
    return snapshot


def assert_canonical_unchanged(repo_root: Path, before: dict[str, str]) -> None:
    after = snapshot_canonical(repo_root)
    if before != after:
        changed = sorted(set(before) | set(after))
        changed = [key for key in changed if before.get(key) != after.get(key)]
        raise RuntimeError(
            f"canonical source changed during build: {', '.join(changed)}"
        )


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"a", "link", "script", "img"}:
            return
        attr_name = "href" if tag in {"a", "link"} else "src"
        for key, value in attrs:
            if key == attr_name and value:
                self.links.append(value)


def _target_for_link(output_dir: Path, base_path: str, link: str) -> Path | None:
    parsed = urlsplit(link)
    if parsed.scheme in {"http", "https", "mailto"} or parsed.netloc:
        return None
    if link.startswith("#"):
        return None

    base = "/" + base_path.strip("/") + "/"
    path = parsed.path
    if not path.startswith(base):
        raise ValueError(f"internal link escapes base path: {link}")

    relative = path[len(base) :]
    target = output_dir / relative
    if path.endswith("/") or target.suffix == "":
        target = target / "index.html"
    return target


def validate_generated_links(output_dir: Path, base_path: str) -> None:
    for html_file in sorted(output_dir.rglob("*.html")):
        parser = _LinkParser()
        parser.feed(html_file.read_text(encoding="utf-8"))
        for link in parser.links:
            target = _target_for_link(output_dir, base_path, link)
            if target is not None and not target.exists():
                raise ValueError(f"broken internal link in {html_file}: {link}")
