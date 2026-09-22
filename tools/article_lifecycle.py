from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import importlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PAGES_BASE = "https://teashaman-cyber.github.io/nakama-test/journal"
ARTICLE_STATES = {"draft", "ready", "published"}
FORUM_STATES = {"draft", "ready", "published"}
RECEIPT_PAGE_STATES = {"not_published", "verified", "degraded"}
RECEIPT_FORUM_STATES = {"draft", "ready", "verified", "recoverable"}
FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9-]*):\s*(.*?)\s*$", re.MULTILINE)


class LifecycleError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_fields(text: str) -> dict[str, str]:
    return {name: value for name, value in FIELD.findall(text)}


def title_of(text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    if not match:
        raise LifecycleError("article or companion has no H1 title")
    return match.group(1).strip()


def resolve_article(value: str) -> Path:
    candidate = Path(value)
    if candidate.suffix == ".md":
        path = candidate if candidate.is_absolute() else ROOT / candidate
    else:
        path = ROOT / "journal" / f"{value}.md"
    path = path.resolve()
    try:
        path.relative_to(ROOT / "journal")
    except ValueError as exc:
        raise LifecycleError("article must live under journal/") from exc
    if not path.is_file():
        raise LifecycleError(f"article not found: {path}")
    return path


def article_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def receipt_path(article: Path) -> Path:
    return ROOT / "publication" / f"{article.stem}.json"


def load_receipt(article: Path) -> dict:
    path = receipt_path(article)
    if not path.is_file():
        raise LifecycleError(f"publication receipt missing: {path.relative_to(ROOT)}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LifecycleError(f"invalid publication receipt JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LifecycleError("publication receipt must be an object")
    return value


def save_receipt(article: Path, receipt: dict) -> None:
    path = receipt_path(article)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def companion_body(text: str) -> str:
    lines = text.splitlines()
    fence_start = next(
        (i for i, line in enumerate(lines) if line.strip() == "```text"), None
    )
    if fence_start is None:
        raise LifecycleError("forum companion metadata fence is missing")
    fence_end = next(
        (i for i in range(fence_start + 1, len(lines)) if lines[i].strip() == "```"),
        None,
    )
    if fence_end is None:
        raise LifecycleError("forum companion metadata fence is not closed")
    body = "\n".join(lines[fence_end + 1 :]).strip()
    if not body:
        raise LifecycleError("forum companion body is empty")
    return body


def companion(
    article: Path, receipt: dict
) -> tuple[Path, dict[str, str], str, str] | None:
    forum = receipt.get("surfaces", {}).get("forum")
    if not isinstance(forum, dict):
        return None
    rel = forum.get("companion")
    if rel is None:
        return None
    if not isinstance(rel, str) or not rel:
        raise LifecycleError("forum companion path must be a non-empty string")
    path = (ROOT / rel).resolve()
    try:
        path.relative_to(ROOT / "distribution" / "forum")
    except ValueError as exc:
        raise LifecycleError(
            "forum companion must live under distribution/forum/"
        ) from exc
    if not path.is_file():
        raise LifecycleError(f"forum companion missing: {rel}")
    text = path.read_text(encoding="utf-8")
    return path, read_fields(text), title_of(text), companion_body(text)


def publication_state(article: Path) -> str:
    fields = read_fields(article.read_text(encoding="utf-8"))
    state = fields.get("Publication", "published").strip().lower()
    if state not in ARTICLE_STATES:
        raise LifecycleError(f"unknown Publication state: {state}")
    return state


def find_qa_manifest(article: Path) -> Path | None:
    rel = article_rel(article)
    for path in sorted((ROOT / "qa" / "articles").glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if value.get("article") == rel:
            return path
    return None


def qa_status(article: Path) -> dict:
    manifest = find_qa_manifest(article)
    if manifest is None:
        return {"state": "UNREGISTERED", "manifest": None}
    try:
        try:
            module = importlib.import_module("tools.article_qa")
        except ModuleNotFoundError:
            module = importlib.import_module("article_qa")
        with contextlib.redirect_stdout(io.StringIO()):
            module.verify_manifest(manifest)
    except (RuntimeError, KeyError, json.JSONDecodeError, ModuleNotFoundError) as exc:
        return {
            "state": "FAIL",
            "manifest": manifest.relative_to(ROOT).as_posix(),
            "error": str(exc),
        }
    return {"state": "PASS", "manifest": manifest.relative_to(ROOT).as_posix()}


def validate(article: Path, receipt: dict) -> list[str]:
    errors: list[str] = []
    if receipt.get("schema") != "nakama.article-publication.v1":
        errors.append("unsupported publication receipt schema")
    if receipt.get("article") != article_rel(article):
        errors.append("publication receipt article path does not match")
    surfaces = receipt.get("surfaces")
    if not isinstance(surfaces, dict):
        return errors + ["publication receipt surfaces must be an object"]

    pages = surfaces.get("pages")
    if not isinstance(pages, dict):
        errors.append("pages surface is missing")
    else:
        if pages.get("state") not in RECEIPT_PAGE_STATES:
            errors.append("invalid pages receipt state")
        expected = f"{PAGES_BASE}/{article.stem}/"
        if pages.get("expected_url") != expected:
            errors.append("pages expected_url does not match article slug")

    forum = surfaces.get("forum")
    if forum is not None and not isinstance(forum, dict):
        errors.append("forum surface must be an object")
    elif isinstance(forum, dict):
        if forum.get("state") not in RECEIPT_FORUM_STATES:
            errors.append("invalid forum receipt state")
        try:
            item = companion(article, receipt)
        except LifecycleError as exc:
            errors.append(str(exc))
            item = None
        if item is not None:
            _, fields, _, _ = item
            if fields.get("Article") != article_rel(article):
                errors.append("forum companion Article does not match receipt article")
            if fields.get("Surface") != "1F916":
                errors.append("forum companion Surface must be 1F916")
            status = fields.get("Status", "").strip().lower()
            if status not in FORUM_STATES:
                errors.append(
                    "forum companion Status must be draft, ready, or published"
                )
            if isinstance(pages, dict) and fields.get("Canonical-URL") != pages.get(
                "expected_url"
            ):
                errors.append("forum companion Canonical-URL does not match Pages URL")
            if forum.get("state") == "verified":
                if status != "published":
                    errors.append(
                        "verified forum receipt requires companion Status: published"
                    )
                if not isinstance(forum.get("post_id"), int):
                    errors.append("verified forum receipt requires integer post_id")
                if forum.get("article_sha256") != sha256(article):
                    errors.append(
                        "verified forum receipt is stale for current article content"
                    )
    return errors


def next_action(article: Path, receipt: dict, qa: dict, errors: list[str]) -> str:
    if errors:
        return "repair_publication_metadata"
    if qa["state"] == "FAIL":
        return "repair_article_qa"
    state = publication_state(article)
    pages = receipt["surfaces"]["pages"]
    forum = receipt["surfaces"].get("forum")
    item = companion(article, receipt) if isinstance(forum, dict) else None
    forum_status = item[1].get("Status", "").lower() if item else None

    if state == "draft":
        return "editorial_review"
    if state == "ready":
        return "explicit_promote_to_published"
    if pages.get("state") != "verified" or pages.get("article_sha256") != sha256(
        article
    ):
        return "verify_pages"
    if item and forum_status == "draft":
        return "forum_companion_review"
    if item and forum_status == "ready" and forum.get("state") != "verified":
        return "explicit_forum_publish"
    if item and forum_status == "published" and forum.get("state") != "verified":
        return "reconcile_forum_receipt"
    return "complete"


def status_payload(article: Path) -> dict:
    receipt = load_receipt(article)
    errors = validate(article, receipt)
    qa = qa_status(article)
    item = companion(article, receipt) if not errors else None
    payload = {
        "article": article_rel(article),
        "title": title_of(article.read_text(encoding="utf-8")),
        "publication": publication_state(article),
        "article_sha256": sha256(article),
        "qa": qa,
        "pages": receipt.get("surfaces", {}).get("pages"),
        "forum": receipt.get("surfaces", {}).get("forum"),
        "forum_companion_status": item[1].get("Status") if item else None,
        "errors": errors,
    }
    payload["next_action"] = next_action(article, receipt, qa, errors)
    return payload


def print_status(payload: dict, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"ARTICLE {payload['article']}")
    print(f"publication: {payload['publication']}")
    print(f"qa: {payload['qa']['state']}")
    print(f"pages: {payload['pages']['state']}")
    if payload.get("forum"):
        print(
            f"forum: {payload['forum']['state']} "
            f"(companion={payload.get('forum_companion_status')})"
        )
    if payload["errors"]:
        print("errors: " + "; ".join(payload["errors"]))
    print(f"next: {payload['next_action']}")


def command_check() -> int:
    pub_dir = ROOT / "publication"
    paths = sorted(pub_dir.glob("*.json")) if pub_dir.is_dir() else []
    if not paths:
        print("ARTICLE_LIFECYCLE_UNKNOWN no publication receipts", file=sys.stderr)
        return 2
    failed = False
    for path in paths:
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
            article = (ROOT / receipt["article"]).resolve()
            if not article.is_file():
                raise LifecycleError(f"missing article for {path.name}")
            errors = validate(article, receipt)
            if errors:
                failed = True
                print(
                    f"ARTICLE_LIFECYCLE_FAIL {path.name} {'; '.join(errors)}",
                    file=sys.stderr,
                )
            else:
                print(f"ARTICLE_LIFECYCLE_PASS {path.name}")
        except (KeyError, json.JSONDecodeError, LifecycleError) as exc:
            failed = True
            print(f"ARTICLE_LIFECYCLE_FAIL {path.name} {exc}", file=sys.stderr)
    return 1 if failed else 0


def forum_payload(article: Path) -> dict:
    receipt = load_receipt(article)
    errors = validate(article, receipt)
    if errors:
        raise LifecycleError("; ".join(errors))
    item = companion(article, receipt)
    if item is None:
        raise LifecycleError("article has no forum companion")
    _, fields, title, body = item
    return {
        "title": title,
        "body": body,
        "url": fields["Canonical-URL"],
        "status": fields["Status"].lower(),
    }


def git_head() -> str:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise LifecycleError(proc.stderr.strip() or "cannot resolve Git HEAD")
    return proc.stdout.strip()


def verify_pages(article: Path, record: bool) -> dict:
    if publication_state(article) != "published":
        raise LifecycleError("Pages verification requires Publication: published")
    receipt = load_receipt(article)
    errors = validate(article, receipt)
    if errors:
        raise LifecycleError("; ".join(errors))
    pages = receipt["surfaces"]["pages"]
    url = pages["expected_url"]
    try:
        request = Request(
            url, headers={"User-Agent": "nakama-test-article-lifecycle/1.0"}
        )
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", "replace")
            status = getattr(response, "status", 200)
    except Exception as exc:
        return {
            "state": "DEGRADED",
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }
    title = title_of(article.read_text(encoding="utf-8"))
    ok = status == 200 and title in body
    result = {
        "state": "VERIFIED" if ok else "REPROBE_REQUIRED",
        "url": url,
        "http_status": status,
        "title_present": title in body,
        "article_sha256": sha256(article),
        "source_commit": git_head(),
    }
    if ok and record:
        pages.update(
            {
                "state": "verified",
                "source_commit": result["source_commit"],
                "article_sha256": result["article_sha256"],
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "http_status": status,
            }
        )
        save_receipt(article, receipt)
        result["recorded"] = True
    return result


def update_companion_status(path: Path, new_status: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"^Status:\s*.+$", f"Status: {new_status}", text, count=1, flags=re.MULTILINE
    )
    if count != 1:
        raise LifecycleError("forum companion Status field is missing or ambiguous")
    path.write_text(updated, encoding="utf-8")


def publish_forum(article: Path, execute: bool, client_root: Path) -> dict:
    payload = forum_payload(article)
    receipt = load_receipt(article)
    pages = receipt["surfaces"]["pages"]
    forum = receipt["surfaces"]["forum"]
    current_sha = sha256(article)

    if publication_state(article) != "published":
        raise LifecycleError("forum publication requires Publication: published")
    if pages.get("state") != "verified":
        raise LifecycleError("forum publication requires verified Pages receipt")
    if pages.get("article_sha256") != current_sha:
        raise LifecycleError("Pages receipt is stale for current article content")
    if payload["status"] != "ready":
        raise LifecycleError("forum companion must be Status: ready before publication")
    if forum.get("state") == "verified":
        raise LifecycleError("forum publication already has a verified receipt")

    preview = {"execute": execute, "payload": payload, "article_sha256": current_sha}
    if not execute:
        preview["state"] = "DRY_RUN"
        return preview

    client_root = client_root.resolve()
    client = client_root / "forum.py"
    if not client.is_file():
        raise LifecycleError(f"forum client not found: {client}")
    head = subprocess.run(
        ["git", "-C", str(client_root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    remote = subprocess.run(
        ["git", "-C", str(client_root), "rev-parse", "origin/main"],
        text=True,
        capture_output=True,
        check=False,
    )
    if (
        head.returncode != 0
        or remote.returncode != 0
        or head.stdout.strip() != remote.stdout.strip()
    ):
        raise LifecycleError(
            "forum client is not at current origin/main; REPROBE_REQUIRED"
        )

    proc = subprocess.run(
        [
            sys.executable,
            str(client),
            "post",
            "--title",
            payload["title"],
            "--body",
            payload["body"],
            "--url",
            payload["url"],
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=client_root,
        env=os.environ.copy(),
    )
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise LifecycleError(
            f"forum client returned non-JSON output (rc={proc.returncode}): {proc.stdout[:500]}"
        ) from exc

    if result.get("status") == "WRITE_VERIFIED":
        post_id = result.get("readback_id")
        if not isinstance(post_id, int):
            raise LifecycleError(
                "WRITE_VERIFIED forum result has no integer readback_id"
            )
        forum.update(
            {
                "state": "verified",
                "article_sha256": current_sha,
                "post_id": post_id,
                "operation_id": result.get("operation_id"),
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        save_receipt(article, receipt)
        item = companion(article, receipt)
        if item is None:
            raise LifecycleError("forum companion disappeared after verified write")
        update_companion_status(item[0], "published")
    elif result.get("status") == "RECOVERABLE":
        forum.update(
            {
                "state": "recoverable",
                "operation_id": result.get("operation_id"),
                "article_sha256": current_sha,
            }
        )
        save_receipt(article, receipt)
    return {
        "state": result.get("status", "UNKNOWN"),
        "client_returncode": proc.returncode,
        "result": result,
    }


def create_article(args: argparse.Namespace) -> dict:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        raise LifecycleError("--date must be YYYY-MM-DD")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.slug):
        raise LifecycleError("--slug must be lowercase ASCII kebab-case")
    stem = f"{args.date}-{args.slug}"
    article = ROOT / "journal" / f"{stem}.md"
    if article.exists() or receipt_path(article).exists():
        raise LifecycleError(f"article already exists: {stem}")

    article_text = (
        f"# {args.title}\n\n"
        "```text\n"
        f"Origin: {args.origin}\n"
        f"Mode: {args.mode}\n"
        "Status: draft\n"
        "Publication: draft\n"
        f"Date: {args.date}\n"
        "```\n\n"
        "## Черновик\n\n"
        "TODO\n"
    )
    article.write_text(article_text, encoding="utf-8")

    canonical_url = f"{PAGES_BASE}/{stem}/"
    receipt = {
        "schema": "nakama.article-publication.v1",
        "article": article_rel(article),
        "surfaces": {
            "pages": {
                "role": "canonical_publication",
                "state": "not_published",
                "expected_url": canonical_url,
                "source_commit": None,
                "article_sha256": None,
                "verified_at": None,
                "http_status": None,
            }
        },
    }
    if args.forum:
        companion_path = ROOT / "distribution" / "forum" / f"{stem}.md"
        companion_path.parent.mkdir(parents=True, exist_ok=True)
        companion_path.write_text(
            f"# {args.title}\n\n"
            "```text\n"
            f"Article: {article_rel(article)}\n"
            "Surface: 1F916\n"
            "Status: draft\n"
            f"Canonical-URL: {canonical_url}\n"
            "```\n\n"
            "TODO: forum discussion companion.\n",
            encoding="utf-8",
        )
        receipt["surfaces"]["forum"] = {
            "role": "discussion_companion",
            "state": "draft",
            "companion": companion_path.relative_to(ROOT).as_posix(),
            "article_sha256": None,
            "post_id": None,
            "operation_id": None,
            "verified_at": None,
        }
    save_receipt(article, receipt)

    if args.series:
        metadata_path = ROOT / "blogsite" / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.setdefault("articles", {})[article.name] = {"series": args.series}
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    index = ROOT / "journal" / "README.md"
    index_text = index.read_text(encoding="utf-8")
    anchor = "## Записи\n\n"
    if anchor not in index_text:
        raise LifecycleError("journal index insertion anchor is missing")
    line = f"- [{args.date} — {args.title}]({article.name}) *(draft)*\n"
    index.write_text(index_text.replace(anchor, anchor + line, 1), encoding="utf-8")
    return {
        "article": article_rel(article),
        "receipt": receipt_path(article).relative_to(ROOT).as_posix(),
        "forum": receipt.get("surfaces", {}).get("forum", {}).get("companion"),
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Nakama article editorial/publication lifecycle"
    )
    sub = p.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="validate all versioned publication receipts")
    check.set_defaults(handler=lambda args: command_check())

    status = sub.add_parser("status", help="show article state and one next action")
    status.add_argument("article")
    status.add_argument("--json", action="store_true")

    new = sub.add_parser("new", help="scaffold a draft article and publication plan")
    new.add_argument("--date", required=True)
    new.add_argument("--slug", required=True)
    new.add_argument("--title", required=True)
    new.add_argument("--origin", default="editorial draft")
    new.add_argument("--mode", default="Jester")
    new.add_argument("--series", action="append", default=[])
    new.add_argument("--forum", action="store_true")

    fp = sub.add_parser("forum-payload", help="show the exact versioned forum payload")
    fp.add_argument("article")

    vp = sub.add_parser("verify-pages", help="verify canonical Pages rendering")
    vp.add_argument("article")
    vp.add_argument("--record", action="store_true")

    pf = sub.add_parser("publish-forum", help="publish the versioned forum companion")
    pf.add_argument("article")
    pf.add_argument("--execute", action="store_true")
    pf.add_argument(
        "--client-root",
        default=os.environ.get(
            "NAKAMA_FORUM_CLIENT_ROOT", "/workspace/theseus-1f916-client"
        ),
    )
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "check":
            return command_check()
        if args.command == "new":
            print(json.dumps(create_article(args), ensure_ascii=False, indent=2))
            return 0
        article = resolve_article(args.article)
        if args.command == "status":
            print_status(status_payload(article), args.json)
            return 0
        if args.command == "forum-payload":
            print(json.dumps(forum_payload(article), ensure_ascii=False, indent=2))
            return 0
        if args.command == "verify-pages":
            result = verify_pages(article, args.record)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["state"] == "VERIFIED" else 2
        if args.command == "publish-forum":
            result = publish_forum(article, args.execute, Path(args.client_root))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["state"] in {"DRY_RUN", "WRITE_VERIFIED"} else 2
        raise LifecycleError(f"unsupported command: {args.command}")
    except LifecycleError as exc:
        print(f"ARTICLE_LIFECYCLE_BLOCKED {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
