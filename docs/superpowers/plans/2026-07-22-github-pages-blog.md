# GitHub Pages Blog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a warm GitHub Pages blog directly from canonical `journal/*.md` and `about/*.md` without creating a second content authority.

**Architecture:** A Python 3.13 static generator reads canonical Markdown plus a body-free JSON series map, renders deterministic HTML into ignored `public/`, and GitHub Actions deploys only that artifact. Git publication/readback and Pages deployment remain separate postconditions.

**Tech Stack:** Python 3.13, Python-Markdown 3.10.2, stdlib `unittest`, plain HTML/CSS, `actions/checkout@v6`, `actions/setup-python@v6`, `actions/configure-pages@v5`, `actions/upload-pages-artifact@v4`, `actions/deploy-pages@v4`.

## Global Constraints

- `journal/*.md` plus Git history remain public authority.
- Notion remains editorial workflow only.
- `public/` is disposable and MUST NOT be committed.
- Generator MUST NOT modify `README.md`, `about/`, `journal/`, `archive/`, or Git refs.
- Every internal URL and asset URL MUST honor the effective Pages base path.
- Publication may remain VERIFIED while Pages is DEGRADED.
- Build and deploy are separate jobs; deploy has `needs: build`.
- Build permission is `contents: read`; deploy adds only `pages: write` and `id-token: write`.
- Deploy uses environment `github-pages` and official Pages artifact deployment.
- No CMS, comments, analytics, search service, custom domain, auth, JS framework, or Notion writer in v1.
- Python-Markdown is pinned exactly to `3.10.2`.
- Contract/projection changes require a new Wolfram PASS.

## File Map

```text
.python-version
.gitignore
site/
  __init__.py
  requirements.txt
  metadata.json
  model.py
  content.py
  urls.py
  render.py
  validate.py
  build.py
  templates/{base,home,index,article,about}.html
  static/{style.css,favicon.svg}
  tests/
    __init__.py
    fixtures/{journal,about,metadata.json}
    test_content.py
    test_urls.py
    test_render.py
    test_validate.py
    test_build.py
.github/workflows/pages.yml
README.md
```

---

### Task 1: Content model and discovery

**Files:** Create `.python-version`, `site/__init__.py`, `site/requirements.txt`, `site/model.py`, `site/content.py`, `site/metadata.json`, fixture files, `site/tests/test_content.py`.

**Interfaces:** Produces `Article`, `AboutPage`, `SiteMetadata`, `discover_articles()`, `load_about_page()`, `load_series_map()`, `extract_excerpt()`.

- [ ] **Step 1: Write failing content tests**

```python
from pathlib import Path
import unittest
from site.content import discover_articles, extract_excerpt, load_about_page, load_series_map

FIXTURES = Path(__file__).parent / "fixtures"

class ContentTests(unittest.TestCase):
    def test_articles_are_newest_first_and_metadata_is_optional(self):
        meta = load_series_map(FIXTURES / "metadata.json")
        articles = discover_articles(FIXTURES / "journal", meta)
        self.assertEqual([a.slug for a in articles], ["2026-01-02-second", "2026-01-01-first"])
        self.assertEqual(articles[1].title, "Первая запись")
        self.assertEqual(articles[1].date.isoformat(), "2026-01-01")
        self.assertEqual(articles[1].series, ("Квантовый чай", "Утки"))
        self.assertIsNone(articles[0].origin)

    def test_excerpt_uses_first_plain_paragraph(self):
        self.assertEqual(extract_excerpt("# Заголовок\n\nПервый абзац.\n\nВторой."), "Первый абзац.")

    def test_about_page_reads_title(self):
        page = load_about_page(FIXTURES / "about" / "continuity.md")
        self.assertEqual((page.slug, page.title), ("continuity", "Непрерывность"))
```

Fixtures:

```markdown
# Первая запись

```text
Origin: dialogue
Mode: Jester
Status: observation
Date: 2026-01-01
```

Первый абзац.
```

```markdown
# Вторая запись

Legacy entry without metadata.
```

`fixtures/metadata.json`:

```json
{"articles":{"2026-01-01-first.md":{"series":["Квантовый чай","Утки"]}}}
```

- [ ] **Step 2: Verify RED**

```bash
python3 -m unittest site.tests.test_content -v
```

Expected: FAIL because `site.content` does not exist.

- [ ] **Step 3: Implement models**

```python
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
```

- [ ] **Step 4: Implement discovery/parsing**

```python
from datetime import date
import json
from pathlib import Path
import re
from site.model import AboutPage, Article, SiteMetadata

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
    out = {}
    for line in match.group("body").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out

def extract_excerpt(text: str) -> str:
    in_fence = False
    paragraph = []
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
    return SiteMetadata({k: tuple(v.get("series", [])) for k, v in raw.get("articles", {}).items()})

def discover_articles(journal_dir: Path, metadata: SiteMetadata) -> list[Article]:
    articles = []
    for path in sorted(journal_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        match = _FILENAME_DATE.match(path.name)
        if not match:
            raise ValueError(f"Journal filename lacks YYYY-MM-DD prefix: {path.name}")
        text = path.read_text(encoding="utf-8")
        fields = _metadata(text)
        articles.append(Article(path.name, path.stem, _title(text),
            date.fromisoformat(fields.get("Date", match.group(1))), text, extract_excerpt(text),
            metadata.series_by_source.get(path.name, ()), fields.get("Origin"), fields.get("Mode"), fields.get("Status")))
    return sorted(articles, key=lambda a: (a.date, a.slug), reverse=True)

def load_about_page(path: Path) -> AboutPage:
    text = path.read_text(encoding="utf-8")
    return AboutPage(path.name, path.stem, _title(text), text)
```

Create `.python-version` = `3.13`, `site/requirements.txt` = `Markdown==3.10.2`, and a body-free `site/metadata.json` keyed by current published filenames with verified Notion series arrays.

- [ ] **Step 5: Run GREEN and commit**

```bash
python3 -m pip install -r site/requirements.txt
python3 -m unittest site.tests.test_content -v
git add .python-version site
git commit -m "feat: add blog content model and discovery"
```

Expected: PASS.

---

### Task 2: Base-path-safe URLs

**Files:** Create `site/urls.py`, `site/tests/test_urls.py`.

**Interfaces:** Produces `normalize_base_path`, `site_url`, `article_url`, `slugify_series`, `series_url`, `source_url`, `history_url`.

- [ ] **Step 1: Write failing URL tests**

```python
import unittest
from site.urls import article_url, history_url, series_url, site_url, source_url

class UrlTests(unittest.TestCase):
    def test_project_pages_base_path(self):
        self.assertEqual(article_url("post", "/nakama-test/"), "/nakama-test/journal/post/")
        self.assertEqual(site_url("static/style.css", "/nakama-test/"), "/nakama-test/static/style.css")
    def test_series_slug(self):
        self.assertEqual(series_url("Квантовый чай", "/nakama-test/"), "/nakama-test/series/kvantovyi-chai/")
    def test_source_history(self):
        self.assertIn("/blob/main/journal/", source_url("x.md"))
        self.assertIn("/commits/main/journal/", history_url("x.md"))
```

- [ ] **Step 2: Verify RED**

```bash
python3 -m unittest site.tests.test_urls -v
```

- [ ] **Step 3: Implement helpers**

```python
from urllib.parse import quote
_REPO = "https://github.com/TeaShaman-cyber/nakama-test"
_TRANSLIT = str.maketrans({"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"i","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"})

def normalize_base_path(base_path: str) -> str:
    core = base_path.strip("/")
    return "/" if not core else f"/{core}/"

def site_url(relative: str, base_path: str) -> str:
    return normalize_base_path(base_path) + relative.lstrip("/")

def article_url(slug: str, base_path: str) -> str:
    return site_url(f"journal/{slug}/", base_path)

def slugify_series(name: str) -> str:
    lowered = name.lower().translate(_TRANSLIT)
    out, dash = [], False
    for char in lowered:
        if char.isalnum(): out.append(char); dash = False
        elif not dash: out.append("-"); dash = True
    return "".join(out).strip("-")

def series_url(name: str, base_path: str) -> str:
    return site_url(f"series/{slugify_series(name)}/", base_path)

def source_url(source_name: str) -> str:
    return f"{_REPO}/blob/main/journal/{quote(source_name)}"

def history_url(source_name: str) -> str:
    return f"{_REPO}/commits/main/journal/{quote(source_name)}"
```

- [ ] **Step 4: Run GREEN and commit**

```bash
python3 -m unittest site.tests.test_urls -v
git add site/urls.py site/tests/test_urls.py
git commit -m "feat: add base-path-safe blog URLs"
```

---

### Task 3: Rendering and visual identity

**Files:** Create `site/render.py`, five templates, `site/static/style.css`, `site/static/favicon.svg`, `site/tests/test_render.py`.

**Interfaces:** Produces `render_home`, `render_index`, `render_article`, `render_about`.

- [ ] **Step 1: Write failing render tests**

```python
from datetime import date
import unittest
from site.model import Article
from site.render import render_article, render_home

ARTICLE = Article("2026-01-01-test.md", "2026-01-01-test", "Тестовая запись", date(2026,1,1), "# Тестовая запись\n\n> Цитата\n\n```text\nPASS\n```", "Цитата", ("Квантовый чай",))

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
```

- [ ] **Step 2: Verify RED**

```bash
python3 -m unittest site.tests.test_render -v
```

- [ ] **Step 3: Implement renderer**

Use `string.Template`, HTML escaping for metadata/labels, and `markdown.markdown(text, extensions=["fenced_code", "sane_lists"])`. Exact public signatures:

```python
def render_home(articles: list[Article], base_path: str) -> str: ...
def render_index(title: str, articles: list[Article], base_path: str) -> str: ...
def render_article(article: Article, previous: Article | None, next_: Article | None, base_path: str) -> str: ...
def render_about(page: AboutPage, base_path: str) -> str: ...
```

Article pages MUST render title/date/series, source Markdown link, Git history link, previous/next navigation, and base-safe static URLs.

- [ ] **Step 4: Add exact base template**

```html
<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title><link rel="icon" href="$favicon_url" type="image/svg+xml"><link rel="stylesheet" href="$stylesheet_url"></head>
<body><header class="site-header"><a class="site-mark" href="$home_url">Шут 🎭</a><nav aria-label="Основная навигация"><a href="$journal_url">Журнал</a><a href="$continuity_url">Непрерывность</a><a href="$method_url">Метод</a></nav></header>
<main class="page-shell">$body</main><footer class="site-footer">Markdown и Git history — публичная память. Сайт — только витрина.</footer></body></html>
```

Home template MUST contain `Привет, мир. Я — Шут.` and a `$latest` entry grid. Other templates stay content fragments and do not duplicate shell markup.

- [ ] **Step 5: Add accepted visual tokens**

`site/static/style.css` starts with:

```css
:root { --paper:#f4efe4; --paper-deep:#e8dfcf; --ink:#25231f; --muted:#756e64; --line:#cfc3af; --accent:#7d4938; --code:#292723; --code-ink:#f5efe3; --measure:72rem; }
```

Requirements: serif long-form body, monospace technical labels/code, generous whitespace, max prose width ~48rem, responsive grid `repeat(auto-fit,minmax(min(100%,18rem),1fr))`, horizontal code overflow, no gradients, no animation.

- [ ] **Step 6: Run GREEN and commit**

```bash
python3 -m unittest site.tests.test_render -v
git add site/render.py site/templates site/static site/tests/test_render.py
git commit -m "feat: render Jester blog pages"
```

---

### Task 4: Deterministic build

**Files:** Create `site/build.py`, `site/tests/test_build.py`; modify `.gitignore`.

**Interfaces:** Produces `build_site(repo_root: Path, output_dir: Path, base_path: str) -> None` and `python -m site.build`.

- [ ] **Step 1: Write integration test** asserting build creates:

```text
public/index.html
public/journal/index.html
public/journal/2026-01-01-first/index.html
public/series/kvantovyi-chai/index.html
public/about/continuity/index.html
public/about/method/index.html
public/static/style.css
public/static/favicon.svg
```

- [ ] **Step 2: Verify RED**

```bash
python3 -m unittest site.tests.test_build -v
```

- [ ] **Step 3: Implement builder**

```python
import argparse, shutil
from pathlib import Path
from site.content import discover_articles, load_about_page, load_series_map
from site.render import render_about, render_article, render_home, render_index
from site.urls import slugify_series

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")

def build_site(repo_root: Path, output_dir: Path, base_path: str) -> None:
    metadata = load_series_map(repo_root / "site" / "metadata.json")
    articles = discover_articles(repo_root / "journal", metadata)
    if output_dir.exists(): shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    _write(output_dir / "index.html", render_home(articles, base_path))
    _write(output_dir / "journal/index.html", render_index("Журнал", articles, base_path))
    chronological = list(reversed(articles))
    for i, article in enumerate(chronological):
        previous = chronological[i-1] if i > 0 else None
        next_ = chronological[i+1] if i+1 < len(chronological) else None
        _write(output_dir / "journal" / article.slug / "index.html", render_article(article, previous, next_, base_path))
    for name in sorted({n for article in articles for n in article.series}):
        _write(output_dir / "series" / slugify_series(name) / "index.html", render_index(name, [a for a in articles if name in a.series], base_path))
    for name in ("continuity", "method"):
        page = load_about_page(repo_root / "about" / f"{name}.md")
        _write(output_dir / "about" / name / "index.html", render_about(page, base_path))
    shutil.copytree(repo_root / "site/static", output_dir / "static")
```

CLI adds `--repo-root`, `--output`, `--base-path` and calls `build_site()`.

- [ ] **Step 4: Ignore generated files**

```gitignore
public/
__pycache__/
*.pyc
```

- [ ] **Step 5: Run GREEN and bounded real build**

```bash
python3 -m unittest site.tests.test_build -v
python3 -m site.build --repo-root . --output public --base-path /nakama-test/
test -f public/index.html
test -f public/journal/2026-07-22-dazhe-neiroset-nachinaet-materitsya/index.html
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore site/build.py site/tests/test_build.py
git commit -m "feat: build deterministic static blog"
```

---

### Task 5: Validation and canonical-write guard

**Files:** Create `site/validate.py`, `site/tests/test_validate.py`; modify `site/build.py`.

**Interfaces:** Produces `validate_source_slugs`, `validate_generated_links`, `snapshot_canonical`, `assert_canonical_unchanged`.

- [ ] **Step 1: Write failing tests** proving duplicate slugs fail, broken internal links fail, and a changed `journal/` file fails canonical comparison.

- [ ] **Step 2: Verify RED**

```bash
python3 -m unittest site.tests.test_validate -v
```

- [ ] **Step 3: Implement guards**

Use SHA-256 snapshots over `README.md` and files recursively under `about/`, `journal/`, `archive/`. Internal-link validation ignores `http://`, `https://`, `mailto:`, `#`; rejects links escaping base path; maps trailing `/` to `index.html`; rejects missing targets.

Core code shape:

```python
def validate_source_slugs(articles):
    seen = set()
    for article in articles:
        if article.slug in seen: raise ValueError(f"Duplicate output slug: {article.slug}")
        seen.add(article.slug)

def assert_canonical_unchanged(before, after):
    if before != after: raise RuntimeError("Canonical source changed during site generation")
```

- [ ] **Step 4: Wire guards into build**

At start:

```python
before = snapshot_canonical(repo_root)
validate_source_slugs(articles)
```

At end:

```python
validate_generated_links(output_dir, base_path)
assert_canonical_unchanged(before, snapshot_canonical(repo_root))
```

- [ ] **Step 5: Full suite + canonical diff**

```bash
python3 -m unittest discover -s site/tests -v
rm -rf public
python3 -m site.build --repo-root . --output public --base-path /nakama-test/
git diff --exit-code -- README.md about journal archive
```

Expected: PASS and zero canonical diff.

- [ ] **Step 6: Commit**

```bash
git add site/validate.py site/tests/test_validate.py site/build.py
git commit -m "test: enforce blog build invariants"
```

---

### Task 6: Official GitHub Pages workflow

**Files:** Create `.github/workflows/pages.yml`.

- [ ] **Step 1: Create exact workflow**

```yaml
name: Deploy Jester blog to Pages
on:
  push:
    branches: [main]
  workflow_dispatch:
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: site/requirements.txt
      - run: python -m pip install -r site/requirements.txt
      - id: pages
        uses: actions/configure-pages@v5
      - run: python -m unittest discover -s site/tests -v
      - run: python -m site.build --repo-root . --output public --base-path "${{ steps.pages.outputs.base_path }}"
      - run: git diff --exit-code -- README.md about journal archive
      - uses: actions/upload-pages-artifact@v4
        with:
          path: public
  deploy:
    runs-on: ubuntu-latest
    needs: build
    permissions:
      contents: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Validate required workflow tokens**

```bash
python3 - <<'PY'
from pathlib import Path
text=Path('.github/workflows/pages.yml').read_text()
required=['actions/checkout@v6','actions/setup-python@v6','actions/configure-pages@v5','actions/upload-pages-artifact@v4','actions/deploy-pages@v4','needs: build','pages: write','id-token: write','name: github-pages']
missing=[x for x in required if x not in text]
if missing: raise SystemExit(missing)
print('PASS workflow contract tokens')
PY
```

- [ ] **Step 3: Run local gate and commit**

```bash
python3 -m unittest discover -s site/tests -v
rm -rf public
python3 -m site.build --repo-root . --output public --base-path /nakama-test/
git diff --exit-code -- README.md about journal archive
git add .github/workflows/pages.yml
git commit -m "ci: deploy Jester blog with GitHub Pages"
```

---

### Task 7: Enable Pages and independently verify live site

**Files:** Modify `README.md` only after live verification.

- [ ] **Step 1: Push and remote-SHA readback**

```bash
git push origin main
LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(gh api repos/TeaShaman-cyber/nakama-test/commits/main --jq .sha)
test "$LOCAL_SHA" = "$REMOTE_SHA"
```

- [ ] **Step 2: Enable Pages source**

```bash
gh api repos/TeaShaman-cyber/nakama-test/pages || true
```

If still 404, configure repository **Settings → Pages → Build and deployment → Source → GitHub Actions**. Do not select branch publishing. Read back until the Pages API returns an object.

- [ ] **Step 3: Observe workflow terminal state**

```bash
gh run list --repo TeaShaman-cyber/nakama-test --workflow pages.yml --limit 5
```

Then:

```bash
gh run watch <RUN_ID> --repo TeaShaman-cyber/nakama-test --exit-status
```

On failure: `SITE DEGRADED`; canonical publication remains untouched.

- [ ] **Step 4: Read public URL**

```bash
SITE_URL=$(gh api repos/TeaShaman-cyber/nakama-test/pages --jq .html_url)
printf '%s\n' "$SITE_URL"
```

- [ ] **Step 5: Verify public postconditions**

```bash
HOME=$(curl -fsSL "$SITE_URL")
printf '%s' "$HOME" | grep -F 'Привет, мир. Я — Шут.'
printf '%s' "$HOME" | grep -F 'Даже нейросеть начинает материться'
ARTICLE_URL="${SITE_URL%/}/journal/2026-07-22-dazhe-neiroset-nachinaet-materitsya/"
ARTICLE=$(curl -fsSL "$ARTICLE_URL")
printf '%s' "$ARTICLE" | grep -F 'Даже нейросеть начинает материться, глядя на баги OpenAI'
printf '%s' "$ARTICLE" | grep -F 'blob/main/journal/2026-07-22-dazhe-neiroset-nachinaet-materitsya.md'
printf '%s' "$ARTICLE" | grep -F 'commits/main/journal/2026-07-22-dazhe-neiroset-nachinaet-materitsya.md'
```

Only if all commands pass: `SITE VERIFIED`.

- [ ] **Step 6: Add verified URL to README and push**

Add after opening paragraph:

```markdown
**Публичный сайт:** <VERIFIED_SITE_URL>
```

Replace only with Step 4/5 readback URL.

```bash
git add README.md
git commit -m "docs: link public Jester blog"
git push origin main
LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(gh api repos/TeaShaman-cyber/nakama-test/commits/main --jq .sha)
test "$LOCAL_SHA" = "$REMOTE_SHA"
```

---

### Task 8: Final contract verification

- [ ] **Step 1: Fresh local test/build/canonical guard**

```bash
python3 -m pip install -r site/requirements.txt
python3 -m unittest discover -s site/tests -v
rm -rf public
python3 -m site.build --repo-root . --output public --base-path /nakama-test/
git diff --exit-code -- README.md about journal archive
```

- [ ] **Step 2: Preserve or rerun Wolfram PASS**

If accepted contract/projection did not change during implementation, preserve the existing PASS by Git readback. If either changed, rerun and require all True:

```text
AllStatesTerminate
NoPublishedWithoutReadback
NoSiteVerifiedWithoutPublication
NoSiteDegradedWithoutPublication
NoPagesWriteToCanonical
DegradedPresentationWithVerifiedPublicationIsRepresentable
AllPassed
```

- [ ] **Step 3: Independent final live verification**

```bash
SITE_URL=$(gh api repos/TeaShaman-cyber/nakama-test/pages --jq .html_url)
curl -fsSI "$SITE_URL"
curl -fsSL "$SITE_URL" | grep -F 'Привет, мир. Я — Шут.'
gh run list --repo TeaShaman-cyber/nakama-test --workflow pages.yml --limit 1
```

- [ ] **Step 4: Final report uses project epistemics**

```text
FACT: remote Git SHA/canonical state.
FACT: local test/build results.
FACT: Pages workflow/deployment result.
FACT: independent live HTTP/readback.
INFERENCE: visual/readability quality.
UNKNOWN: anything not observed.
```

Never infer `SITE VERIFIED` from workflow self-report alone.

## Plan Self-Review

- Spec coverage: authority, content model, home/journal/article/series/about, base path, build/deploy split, least privilege, artifact-only deployment, failure semantics, automated tests, live verification, and formal guard are mapped.
- Placeholder scan: only `<RUN_ID>` and `<VERIFIED_SITE_URL>` remain, both produced by explicit preceding readback steps rather than unspecified work.
- Type consistency: public model/URL/render/build interfaces are defined once and reused consistently.
- Scope: one subsystem — Pages presentation over canonical Git journal. Notion automation remains out of scope.
