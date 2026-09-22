from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
EDGE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*-->\s*([A-Za-z][A-Za-z0-9_]*)", re.MULTILINE
)


def run_process(
    command: list[str], timeout: int = 90
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (
        FileNotFoundError,
        PermissionError,
        OSError,
        subprocess.TimeoutExpired,
    ) as exc:
        return subprocess.CompletedProcess(
            command, 127, "", f"{type(exc).__name__}: {exc}"
        )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def json_payload(proc: subprocess.CompletedProcess[str]):
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def inventory(mcporter: str, config: str, provider: str, out_dir: Path) -> dict:
    proc = run_process(
        [mcporter, "--config", config, "list", provider, "--json"], timeout=45
    )
    payload = json_payload(proc)
    receipt = {
        "provider": provider,
        "returncode": proc.returncode,
        "result": (
            "PASS"
            if isinstance(payload, dict) and payload.get("status") == "ok"
            else "DEGRADED_EXTERNAL_WITNESS"
        ),
        "payload": payload,
        "stderr_excerpt": proc.stderr[:2000],
    }
    write_json(out_dir / f"inventory-{provider}.json", receipt)
    return receipt


def graph_edges(graph_text: str) -> list[tuple[str, str]]:
    return [(match.group(1), match.group(2)) for match in EDGE.finditer(graph_text)]


def wolfram_code(
    edges: list[tuple[str, str]], roots: list[str], conclusion: str
) -> str:
    edge_expr = ",".join(f'"{source}"->"{target}"' for source, target in edges)
    root_expr = ",".join(json.dumps(root) for root in roots)
    conclusion_expr = json.dumps(conclusion)
    return (
        f"edges={{{edge_expr}}};"
        "g=Graph[edges,DirectedEdges->True];"
        "ug=UndirectedGraph[g];"
        f"roots={{{root_expr}}};"
        f"conclusion={conclusion_expr};"
        "payload=<|"
        '"pass"->(AcyclicGraphQ[g]&&Length[ConnectedComponents[ug]]==1&&'
        "And@@(GraphDistance[g,#,conclusion]<Infinity&/@roots)),"
        '"vertex_count"->VertexCount[g],'
        '"edge_count"->EdgeCount[g],'
        '"acyclic"->AcyclicGraphQ[g],'
        '"weak_component_count"->Length[ConnectedComponents[ug]],'
        '"all_roots_reach_conclusion"->'
        "And@@(GraphDistance[g,#,conclusion]<Infinity&/@roots)"
        "|>;"
        'ExportString[payload,"RawJSON"]'
    )


def parse_wolfram_result(payload) -> dict | None:
    if not isinstance(payload, dict):
        return None
    for item in payload.get("content", []):
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text", "")
        match = re.search(r"Out\[\d+\]\s*=\s*(.+)\s*$", text, re.DOTALL)
        if not match:
            continue
        try:
            exported = json.loads(match.group(1))
            result = json.loads(exported)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def run_wolfram(
    mcporter: str,
    config: str,
    provider: str,
    tool: str,
    graph_path: Path,
    roots: list[str],
    conclusion: str,
    out_dir: Path,
) -> dict:
    graph_text = graph_path.read_text(encoding="utf-8")
    edges = graph_edges(graph_text)
    code = wolfram_code(edges, roots, conclusion)
    args = json.dumps({"code": code, "timeConstraint": 60}, ensure_ascii=False)
    proc = run_process(
        [
            mcporter,
            "--config",
            config,
            "call",
            f"{provider}.{tool}",
            "--no-oauth",
            "--output",
            "json",
            "--args",
            args,
        ]
    )
    payload = json_payload(proc)
    result_payload = parse_wolfram_result(payload)
    if proc.returncode != 0 or result_payload is None:
        result = "DEGRADED_EXTERNAL_WITNESS"
    elif result_payload.get("pass") is True:
        result = "PASS"
    elif result_payload.get("pass") is False:
        result = "FAIL_ASSERTION"
    else:
        result = "DEGRADED_EXTERNAL_WITNESS"
    receipt = {
        "provider": provider,
        "tool": tool,
        "graph": str(graph_path.relative_to(ROOT)),
        "graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "returncode": proc.returncode,
        "payload": result_payload,
        "result": result,
        "stderr_excerpt": proc.stderr[:2000],
    }
    write_json(out_dir / "wolfram-graph.json", receipt)
    return receipt


def normalize_url(value: str) -> str:
    return value.strip().rstrip("/")


def run_search_probe(mcporter: str, config: str, probe: dict, out_dir: Path) -> dict:
    provider = probe["provider"]
    tool = probe["tool"]
    proc = run_process(
        [
            mcporter,
            "--config",
            config,
            "call",
            f"{provider}.{tool}",
            "--no-oauth",
            "--output",
            "json",
            "--args",
            json.dumps(probe["args"], ensure_ascii=False),
        ]
    )
    payload = json_payload(proc)
    raw = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if payload is not None
        else ""
    )
    target = normalize_url(probe["target_url"])
    found = target in raw.replace("\\/", "/")
    if proc.returncode != 0 or payload is None:
        result = "DEGRADED_EXTERNAL_WITNESS"
    elif found:
        result = "FOUND_EXPECTED_SOURCE"
    else:
        result = "NO_SIGNAL"
    receipt = {
        "probe_id": probe["id"],
        "provider": provider,
        "tool": tool,
        "target_url": probe["target_url"],
        "returncode": proc.returncode,
        "found_expected_source": found,
        "result": result,
        "payload": payload,
        "stderr_excerpt": proc.stderr[:2000],
    }
    write_json(out_dir / f"search-{probe['id']}.json", receipt)
    return receipt


def run_http_probe(probe: dict, out_dir: Path) -> dict:
    try:
        request = Request(
            probe["url"], headers={"User-Agent": "nakama-test-article-qa/1.0"}
        )
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", "replace")
            status = getattr(response, "status", 200)
        missing = [
            fragment
            for fragment in probe["required_substrings"]
            if fragment not in body
        ]
        result = "PASS" if status == 200 and not missing else "REPROBE_REQUIRED"
        receipt = {
            "probe_id": probe["id"],
            "url": probe["url"],
            "http_status": status,
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "missing_substrings": missing,
            "result": result,
        }
    except Exception as exc:
        receipt = {
            "probe_id": probe["id"],
            "url": probe["url"],
            "result": "DEGRADED_EXTERNAL_WITNESS",
            "error": f"{type(exc).__name__}: {exc}",
        }
    write_json(out_dir / f"http-{probe['id']}.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcporter", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--network-manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    network = json.loads((ROOT / args.network_manifest).read_text(encoding="utf-8"))
    article_manifest = json.loads(
        (ROOT / network["article_manifest"]).read_text(encoding="utf-8")
    )
    graph_path = ROOT / article_manifest["graph"]

    providers = sorted(
        {network["wolfram"]["provider"]}
        | {probe["provider"] for probe in network.get("search_probes", [])}
    )
    inventories = {
        provider: inventory(args.mcporter, args.config, provider, out_dir)
        for provider in providers
    }

    wolfram_meta = network["wolfram"]
    if inventories[wolfram_meta["provider"]]["result"] == "PASS":
        formal = run_wolfram(
            args.mcporter,
            args.config,
            wolfram_meta["provider"],
            wolfram_meta["tool"],
            graph_path,
            article_manifest["roots"],
            article_manifest["conclusion"],
            out_dir,
        )
    else:
        formal = {"result": "DEGRADED_EXTERNAL_WITNESS"}
        write_json(out_dir / "wolfram-graph.json", formal)

    searches = []
    for probe in network.get("search_probes", []):
        if inventories[probe["provider"]]["result"] == "PASS":
            searches.append(
                run_search_probe(args.mcporter, args.config, probe, out_dir)
            )
        else:
            receipt = {
                "probe_id": probe["id"],
                "provider": probe["provider"],
                "result": "DEGRADED_EXTERNAL_WITNESS",
            }
            write_json(out_dir / f"searchm{probe['id']}.json", receipt)
            searches.append(receipt)

    http_receipts = [
        run_http_probe(probe, out_dir) for probe in network.get("http_probes", [])
    ]

    statuses = [
        formal["result"],
        *[item["result"] for item in searches],
        *[item["result"] for item in http_receipts],
    ]
    if "FAIL_ASSERTION" in statuses:
        overall = "FAIL_ASSERTION"
    elif all(status in {"PASS", "FOUND_EXPECTED_SOURCE"} for status in statuses):
        overall = "PASS"
    else:
        overall = "DEGRADED"

    summary = {
        "schema": "nakama.article-network-qa.receipt.v1",
        "overall": overall,
        "formal": formal["result"],
        "search": {item["probe_id"]: item["result"] for item in searches},
        "http": {item["probe_id"]: item["result"] for item in http_receipts},
        "notion_publication": "NOT_EXPOSED",
        "authority": "ADVISORY_ONLY",
    }
    write_json(out_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 1 if overall == "FAIL_ASSERTION" else 0


if __name__ == "__main__":
    raise SystemExit(main())
