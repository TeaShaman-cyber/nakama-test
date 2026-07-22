from datetime import date
import json
from pathlib import Path
import re

from blogsite.model import AboutPage, Article, SiteMetadata

_FILENAME_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
_METADATA = re.compile(r"```text\n(?P<body>.*?)\n```", re.DOTALL)


def _title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise ValueError("Markdown source has no level-1 title")


def _metadata(text: str) -> dict[str, str]:
    match = _METADATA.search(text)
    if not match:
        return {}
    out: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def extract_excerpt(text: str) -> str:
    in_fence = False
    paragraph: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith("#") or line.startswith(">"):
            continue
        if not line:
            if paragraph:
                return " ".join(paragraph)
            continue
        paragraph.append(line)
    return " ".join(paragraph)


def load_series_map(path: Path) -> SiteMetadata:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SiteMetadata(
        {
            key: tuple(value.get("series", []))
            for key, value in raw.get("articles", {}).items()
        }
    )


def discover_articles(journal_dir: Path, metadata: SiteMetadata) -> list[Article]:
    articles: list[Article] = []
    for path in sorted(journal_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        match = _FILENAME_DATE.match(path.name)
        if not match:
            raise ValueError(f"Journal filename lacks YYYY-MM-DD prefix: {path.name}")
        text = path.read_text(encoding="utf-8")
        fields = _metadata(text)
        articles.append(
            Article(
                source_name=path.name,
                slug=path.stem,
                title=_title(text),
                date=date.fromisoformat(fields.get("Date", match.group(1))),
                markdown=text,
                excerpt=extract_excerpt(text),
                series=metadata.series_by_source.get(path.name, ()),
                origin=fields.get("Origin"),
                mode=fields.get("Mode"),
                status=fields.get("Status"),
            )
        )
    return sorted(
        articles, key=lambda article: (article.date, article.slug), reverse=True
    )


def load_about_page(path: Path) -> AboutPage:
    text = path.read_text(encoding="utf-8")
    return AboutPage(path.name, path.stem, _title(text), text)
