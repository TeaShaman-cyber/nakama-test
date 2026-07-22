from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Article:
    source_name: str
    slug: str
    title: str
    date: date
    markdown: str
    excerpt: str
    series: tuple[str, ...] = ()
    origin: str | None = None
    mode: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class AboutPage:
    source_name: str
    slug: str
    title: str
    markdown: str


@dataclass(frozen=True)
class SiteMetadata:
    series_by_source: dict[str, tuple[str, ...]]
