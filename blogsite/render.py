from html import escape
from pathlib import Path
from string import Template

import markdown

from blogsite.model import AboutPage, Article
from blogsite.urls import article_url, history_url, series_url, site_url, source_url

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _template(name: str) -> Template:
    return Template((_TEMPLATE_DIR / name).read_text(encoding="utf-8"))


def _shell(title: str, body: str, base_path: str) -> str:
    return _template("base.html").substitute(
        title=escape(title),
        favicon_url=site_url("static/favicon.svg", base_path),
        stylesheet_url=site_url("static/style.css", base_path),
        home_url=site_url("", base_path),
        journal_url=site_url("journal/", base_path),
        continuity_url=site_url("about/continuity/", base_path),
        method_url=site_url("about/method/", base_path),
        body=body,
    )


def _article_card(article: Article, base_path: str) -> str:
    labels = "".join(
        f'<span class="series-label">{escape(item)}</span>' for item in article.series
    )
    return (
        f'<article class="entry-card"><p class="entry-date">{article.date.isoformat()}</p>'
        f'<h2><a href="{article_url(article.slug, base_path)}">{escape(article.title)}</a></h2>'
        f'<p>{escape(article.excerpt)}</p><div class="series-list">{labels}</div></article>'
    )


def render_home(articles: list[Article], base_path: str) -> str:
    latest = "".join(_article_card(article, base_path) for article in articles[:6])
    body = _template("home.html").substitute(latest=latest)
    return _shell("Шут — журнал", body, base_path)


def render_index(title: str, articles: list[Article], base_path: str) -> str:
    entries = "".join(_article_card(article, base_path) for article in articles)
    body = _template("index.html").substitute(title=escape(title), entries=entries)
    return _shell(title, body, base_path)


def render_article(
    article: Article,
    previous: Article | None,
    next_: Article | None,
    base_path: str,
) -> str:
    body_html = markdown.markdown(
        article.markdown, extensions=["fenced_code", "sane_lists"]
    )
    labels = "".join(
        f'<a class="series-label" href="{series_url(item, base_path)}">{escape(item)}</a>'
        for item in article.series
    )
    previous_link = (
        f'<a rel="prev" href="{article_url(previous.slug, base_path)}">← {escape(previous.title)}</a>'
        if previous
        else ""
    )
    next_link = (
        f'<a rel="next" href="{article_url(next_.slug, base_path)}">{escape(next_.title)} →</a>'
        if next_
        else ""
    )
    body = _template("article.html").substitute(
        title=escape(article.title),
        date=article.date.isoformat(),
        labels=labels,
        content=body_html,
        source_url=source_url(article.source_name),
        history_url=history_url(article.source_name),
        previous_link=previous_link,
        next_link=next_link,
    )
    return _shell(article.title, body, base_path)


def render_about(page: AboutPage, base_path: str) -> str:
    content = markdown.markdown(page.markdown, extensions=["fenced_code", "sane_lists"])
    body = _template("about.html").substitute(content=content)
    return _shell(page.title, body, base_path)
