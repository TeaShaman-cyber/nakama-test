from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPY_DIRS = ("journal", "qa")
COPY_FILES = ("tools/article_qa.py",)


class MutationError(RuntimeError):
    pass


def load_manifest(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "nakama.article-mutation.v1":
        raise MutationError("unsupported mutation manifest schema")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise MutationError("mutation manifest has no cases")
    return value


def copy_fixture(destination: Path) -> None:
    for rel in COPY_DIRS:
        source = ROOT / rel
        shutil.copytree(source, destination / rel)
    for rel in COPY_FILES:
        source = ROOT / rel
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def replace_text(path: Path, old: str, new: str, replace_all: bool) -> int:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0:
        raise MutationError(f"anchor not found in {path}: {old!r}")
    if not replace_all and count != 1:
        raise MutationError(f"expected one anchor in {path}, found {count}: {old!r}")
    updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    path.write_text(updated, encoding="utf-8")
    return count if replace_all else 1


def apply_case(workspace: Path, case: dict) -> dict:
    operator = case["operator"]
    files = case.get("files")
    if not isinstance(files, list) or not files:
        raise MutationError(f"{case['id']}: files must be a non-empty list")
    touched = []
    mutation_count = 0
    if operator in {"replace", "replace_all"}:
        old = case.get("old")
        new = case.get("new")
        if not isinstance(old, str) or not isinstance(new, str):
            raise MutationError(f"{case['id']}: replace operator needs string old/new")
        for rel in files:
            path = workspace / rel
            if not path.is_file():
                raise MutationError(f"{case['id']}: missing mutation file {rel}")
            mutation_count += replace_text(path, old, new, operator == "replace_all")
            touched.append(rel)
    elif operator == "delete_file":
        for rel in files:
            path = workspace / rel
            if not path.is_file():
                raise MutationError(f"{case['id']}: missing deletion target {rel}")
            path.unlink()
            touched.append(rel)
            mutation_count += 1
    else:
        raise MutationError(f"{case['id']}: unsupported operator {operator}")
    return {"files": touched, "mutation_count": mutation_count}


def run_article_qa(workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/article_qa.py"],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def classify(returncode: int) -> str:
    return "KILLED_DETERMINISTIC" if returncode != 0 else "SURVIVED"


def expected_matches(expected: str, verdict: str) -> bool:
    if expected == "killed":
        return verdict == "KILLED_DETERMINISTIC"
    if expected == "survived":
        return verdict == "SURVIVED"
    raise MutationError(f"unsupported expected outcome: {expected}")


def run_case(case: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="nakama-article-mutant-") as tmp:
        workspace = Path(tmp)
        copy_fixture(workspace)
        mutation = apply_case(workspace, case)
        proc = run_article_qa(workspace)
        verdict = classify(proc.returncode)
        return {
            "id": case["id"],
            "kind": case.get("kind"),
            "operator": case["operator"],
            "expected": case["expected"],
            "verdict": verdict,
            "expected_match": expected_matches(case["expected"], verdict),
            "mutation": mutation,
            "qa_returncode": proc.returncode,
            "qa_stdout_tail": proc.stdout[-1200:],
            "qa_stderr_tail": proc.stderr[-1200:],
        }


def git_head() -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--receipt", default=os.environ.get("MUTATION_TEST_RECEIPT"))
    args = parser.parse_args()

    manifest_path = (ROOT / args.manifest).resolve()
    receipt_path = (
        Path(args.receipt)
        if args.receipt
        else Path(tempfile.gettempdir()) / "article-mutation-receipt.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        manifest = load_manifest(manifest_path)
        results = [run_case(case) for case in manifest["cases"]]
        all_expected = all(result["expected_match"] for result in results)
        status = "BASELINE_CONFIRMED" if all_expected else "BASELINE_REGRESSION"
        code = 0 if all_expected else 1
        receipt = {
            "schema": "nakama.article-mutation.receipt.v1",
            "status": status,
            "source_sha": git_head(),
            "manifest": manifest_path.relative_to(ROOT).as_posix(),
            "acceptance_authority": False,
            "results": results,
            "counts": {
                "total": len(results),
                "killed_deterministic": sum(
                    r["verdict"] == "KILLED_DETERMINISTIC" for r in results
                ),
                "survived": sum(r["verdict"] == "SURVIVED" for r in results),
                "expected_matches": sum(r["expected_match"] for r in results),
            },
        }
    except (
        MutationError,
        json.JSONDecodeError,
        KeyError,
        subprocess.TimeoutExpired,
    ) as exc:
        status = "MUTATION_RUNTIME_FAILED"
        code = 2
        receipt = {
            "schema": "nakama.article-mutation.receipt.v1",
            "status": status,
            "source_sha": git_head(),
            "manifest": str(args.manifest),
            "acceptance_authority": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"ARTICLE_MUTATION_STATUS {status}")
    if "counts" in receipt:
        print(
            "ARTICLE_MUTATION_COUNTS "
            + " ".join(f"{k}={v}" for k, v in receipt["counts"].items())
        )
        for result in receipt["results"]:
            print(
                "ARTICLE_MUTATION_CASE "
                f"id={result['id']} verdict={result['verdict']} expected={result['expected']} "
                f"match={str(result['expected_match']).lower()}"
            )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
