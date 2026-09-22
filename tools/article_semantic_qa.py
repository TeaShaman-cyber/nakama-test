from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SemanticQaError(RuntimeError):
    pass


EPISTEMIC_PREFIX = re.compile(r"^(?:FACT|INFERENCE|UNKNOWN):\s*", re.IGNORECASE)


def semantic_text(value: str) -> str:
    return EPISTEMIC_PREFIX.sub("", value.strip(), count=1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def classify_relation(
    forward_entailment: float,
    reverse_entailment: float,
    *,
    equivalent_min: float,
    changed_max_min_direction: float,
) -> str:
    if min(forward_entailment, reverse_entailment) >= equivalent_min:
        return "equivalent"
    if min(forward_entailment, reverse_entailment) <= changed_max_min_direction:
        return "changed"
    return "unknown"


def verify_model_files(profile: dict, model_dir: Path) -> dict:
    receipts = {}
    for key in ("config", "tokenizer", "onnx"):
        spec = profile["model"][key]
        path = model_dir / spec["path"]
        if not path.is_file():
            raise SemanticQaError(f"missing model artifact: {spec['path']}")
        observed = sha256(path)
        if observed != spec["sha256"]:
            raise SemanticQaError(
                f"model artifact hash mismatch: {spec['path']} expected={spec['sha256']} observed={observed}"
            )
        if key == "onnx" and path.stat().st_size != int(spec["size_bytes"]):
            raise SemanticQaError(
                f"model artifact size mismatch: {spec['path']} expected={spec['size_bytes']} observed={path.stat().st_size}"
            )
        receipts[key] = {
            "path": spec["path"],
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }
    return receipts


def mutation_cases(profile: dict) -> dict[str, dict]:
    path = ROOT / profile["mutation_manifest"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return {case["id"]: case for case in manifest["cases"]}


def infer_pairs(profile: dict, model_dir: Path) -> list[dict]:
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    config = json.loads((model_dir / profile["model"]["config"]["path"]).read_text())
    labels = {int(key): value for key, value in config["id2label"].items()}
    entailment_index = next(
        index for index, label in labels.items() if label.lower() == "entailment"
    )
    tokenizer = Tokenizer.from_file(
        str(model_dir / profile["model"]["tokenizer"]["path"])
    )
    tokenizer.enable_truncation(max_length=256)
    session = ort.InferenceSession(
        str(model_dir / profile["model"]["onnx"]["path"]),
        providers=["CPUExecutionProvider"],
    )
    cases = mutation_cases(profile)
    equivalent_min = float(
        profile["thresholds"]["equivalent_min_bidirectional_entailment"]
    )
    changed_max = float(profile["thresholds"]["changed_max_min_directional_entailment"])

    def entailment(premise: str, hypothesis: str) -> float:
        encoded = tokenizer.encode(premise, hypothesis)
        feed = {
            "input_ids": np.asarray([encoded.ids], dtype=np.int64),
            "attention_mask": np.asarray([encoded.attention_mask], dtype=np.int64),
        }
        logits = session.run(None, feed)[0][0]
        exp = np.exp(logits - logits.max())
        probs = exp / exp.sum()
        return float(probs[entailment_index])

    results = []
    for spec in profile["cases"]:
        mutation = cases.get(spec["mutation_id"])
        if mutation is None:
            raise SemanticQaError(f"missing mutation case: {spec['mutation_id']}")
        original = mutation.get("old")
        mutant = mutation.get("new")
        if not isinstance(original, str) or not isinstance(mutant, str):
            raise SemanticQaError(
                f"semantic case requires text old/new: {spec['mutation_id']}"
            )
        original_semantic = semantic_text(original)
        mutant_semantic = semantic_text(mutant)
        forward = entailment(original_semantic, mutant_semantic)
        reverse = entailment(mutant_semantic, original_semantic)
        observed = classify_relation(
            forward,
            reverse,
            equivalent_min=equivalent_min,
            changed_max_min_direction=changed_max,
        )
        results.append(
            {
                "mutation_id": spec["mutation_id"],
                "expected_relation": spec["expected_relation"],
                "observed_relation": observed,
                "expected_match": observed == spec["expected_relation"],
                "forward_entailment": forward,
                "reverse_entailment": reverse,
                "semantic_normalization": "strip_epistemic_prefix",
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()

    profile_path = (ROOT / args.profile).resolve()
    model_dir = Path(args.model_dir).resolve()
    receipt_path = Path(args.receipt).resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        if profile.get("schema") != "nakama.article-semantic-nli.v1":
            raise SemanticQaError("unsupported semantic NLI profile schema")
        artifacts = verify_model_files(profile, model_dir)
        results = infer_pairs(profile, model_dir)
        matched = sum(result["expected_match"] for result in results)
        status = (
            "SEMANTIC_BASELINE_CONFIRMED"
            if matched == len(results)
            else "SEMANTIC_BASELINE_REGRESSION"
        )
        receipt = {
            "schema": "nakama.article-semantic-nli.receipt.v1",
            "status": status,
            "source_sha": git_head(),
            "acceptance_authority": False,
            "profile": profile_path.relative_to(ROOT).as_posix(),
            "model": {
                "repo": profile["model"]["repo"],
                "revision": profile["model"]["revision"],
                "artifacts": artifacts,
            },
            "thresholds": profile["thresholds"],
            "results": results,
            "counts": {
                "total": len(results),
                "expected_matches": matched,
                "equivalent": sum(
                    result["observed_relation"] == "equivalent" for result in results
                ),
                "changed": sum(
                    result["observed_relation"] == "changed" for result in results
                ),
                "unknown": sum(
                    result["observed_relation"] == "unknown" for result in results
                ),
            },
        }
        code = 0 if status == "SEMANTIC_BASELINE_CONFIRMED" else 1
    except Exception as exc:
        receipt = {
            "schema": "nakama.article-semantic-nli.receipt.v1",
            "status": "SEMANTIC_RUNTIME_FAILED",
            "source_sha": git_head(),
            "acceptance_authority": False,
            "profile": str(args.profile),
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2

    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"ARTICLE_SEMANTIC_STATUS {receipt['status']}")
    if "counts" in receipt:
        print(
            "ARTICLE_SEMANTIC_COUNTS "
            + " ".join(f"{key}={value}" for key, value in receipt["counts"].items())
        )
        for result in receipt["results"]:
            print(
                "ARTICLE_SEMANTIC_CASE "
                f"id={result['mutation_id']} expected={result['expected_relation']} "
                f"observed={result['observed_relation']} match={str(result['expected_match']).lower()} "
                f"forward={result['forward_entailment']:.6f} reverse={result['reverse_entailment']:.6f}"
            )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
