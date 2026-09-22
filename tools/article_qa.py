from __future__ import annotations

import json
import re
import sys
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "qa" / "articles"

EDGE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*-->\s*([A-Za-z][A-Za-z0-9_]*)")
MERMAID_BLOCK = re.compile(r"```mermaid\n(?P<body>.*?)\n```", re.DOTALL)
MARKDOWN_URL = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")


class QAFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise QAFailure(message)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_graph(text: str) -> tuple[set[str], dict[str, set[str]]]:
    nodes: set[str] = set()
    adjacency: dict[str, set[str]] = {}
    for line in text.splitlines():
        match = EDGE.match(line)
        if not match:
            continue
        source, target = match.groups()
        nodes.update((source, target))
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set())
    if not nodes:
        fail("argument graph has no directed edges")
    return nodes, adjacency


def assert_dag(nodes: set[str], adjacency: dict[str, set[str]]) -> None:
    indegree = {node: 0 for node in nodes}
    for targets in adjacency.values():
        for target in targets:
            indegree[target] += 1
    queue = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    seen = 0
    while queue:
        node = queue.popleft()
        seen += 1
        for target in sorted(adjacency[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if seen != len(nodes):
        fail("argument graph contains a directed cycle")


def assert_weakly_connected(nodes: set[str], adjacency: dict[str, set[str]]) -> None:
    undirected = {node: set() for node in nodes}
    for source, targets in adjacency.items():
        for target in targets:
            undirected[source].add(target)
            undirected[target].add(source)
    start = next(iter(nodes))
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in undirected[node]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    if seen != nodes:
        missing = ", ".join(sorted(nodes - seen))
        fail(f"argument graph has disconnected nodes: {missing}")


def reachable(adjacency: dict[str, set[str]], start: str, target: str) -> bool:
    queue = deque([start])
    seen = {start}
    while queue:
        node = queue.popleft()
        if node == target:
            return True
        for neighbor in adjacency.get(node, set()):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return False


def source_hosts(article: str) -> set[str]:
    hosts = set()
    for url in MARKDOWN_URL.findall(article):
        host = urlparse(url).hostname
        if host:
            hosts.add(host.lower())
    return hosts


def verify_source_bindings(article: str, article_rel: str, binding_path: Path) -> int:
    contract = load_manifest(binding_path)
    if contract.get("schema") != "nakama.article-source-bindings.v1":
        fail(f"unsupported source-binding schema: {binding_path.relative_to(ROOT)}")
    if contract.get("article") != article_rel:
        fail(
            f"source-binding contract targets another article: {binding_path.relative_to(ROOT)}"
        )
    bindings = contract.get("bindings")
    if not isinstance(bindings, list) or not bindings:
        fail(
            f"source-binding contract has no bindings: {binding_path.relative_to(ROOT)}"
        )
    seen_ids: set[str] = set()
    for binding in bindings:
        binding_id = binding.get("id")
        label = binding.get("label")
        url = binding.get("url")
        if not all(
            isinstance(value, str) and value for value in (binding_id, label, url)
        ):
            fail(f"invalid source binding in {binding_path.relative_to(ROOT)}")
        if binding_id in seen_ids:
            fail(f"duplicate source-binding id: {binding_id}")
        seen_ids.add(binding_id)
        expected = f"[{label}]({url})"
        if expected not in article:
            fail(f"source binding mismatch: {binding_id} expected {expected}")
    return len(bindings)


def verify_manifest(path: Path) -> None:
    manifest = load_manifest(path)
    article_path = ROOT / manifest["article"]
    graph_path = ROOT / manifest["graph"]
    if not article_path.is_file():
        fail(f"missing article: {article_path.relative_to(ROOT)}")
    if not graph_path.is_file():
        fail(f"missing graph: {graph_path.relative_to(ROOT)}")

    article = article_path.read_text(encoding="utf-8")
    graph = graph_path.read_text(encoding="utf-8").strip()

    evidence_rel = manifest.get("evidence_receipt")
    if evidence_rel is not None:
        evidence_path = ROOT / evidence_rel
        if not evidence_path.is_file():
            fail(f"missing evidence receipt: {evidence_rel}")
        evidence = evidence_path.read_text(encoding="utf-8")
        if f"Article: {manifest['article']}" not in evidence:
            fail(f"evidence receipt does not bind article: {evidence_rel}")

    h1 = [line for line in article.splitlines() if line.startswith("# ")]
    if len(h1) != 1:
        fail(
            f"{article_path.name}: expected exactly one level-1 title, found {len(h1)}"
        )

    for heading in manifest.get("required_headings", []):
        if heading not in article:
            fail(f"{article_path.name}: missing required heading: {heading}")

    for marker in manifest.get("required_markers", []):
        if marker not in article:
            fail(f"{article_path.name}: missing epistemic marker: {marker}")

    hosts = source_hosts(article)
    for expected in manifest.get("required_source_urls", []):
        if expected not in article:
            fail(f"{article_path.name}: missing source URL: {expected}")

    source_binding_count = 0
    source_bindings_rel = manifest.get("source_bindings")
    if source_bindings_rel is not None:
        source_bindings_path = ROOT / source_bindings_rel
        if not source_bindings_path.is_file():
            fail(f"missing source-binding contract: {source_bindings_rel}")
        source_binding_count = verify_source_bindings(
            article, manifest["article"], source_bindings_path
        )

    blocks = MERMAID_BLOCK.findall(article)
    if len(blocks) != 1:
        fail(f"{article_path.name}: expected exactly one Mermaid argument graph")
    if blocks[0].strip() != graph:
        fail(f"{article_path.name}: embedded Mermaid graph differs from QA artifact")

    nodes, adjacency = parse_graph(graph)
    conclusion = manifest["conclusion"]
    if conclusion not in nodes:
        fail(f"argument graph missing conclusion node: {conclusion}")

    assert_dag(nodes, adjacency)
    assert_weakly_connected(nodes, adjacency)

    for root in manifest["roots"]:
        if root not in nodes:
            fail(f"argument graph missing evidence root: {root}")
        if not reachable(adjacency, root, conclusion):
            fail(f"evidence root {root} cannot reach conclusion {conclusion}")

    print(
        "ARTICLE_QA_PASS",
        path.name,
        f"nodes={len(nodes)}",
        f"edges={sum(len(v) for v in adjacency.values())}",
        f"sources={len(hosts)}",
        f"bindings={source_binding_count}",
    )


def main() -> int:
    manifests = sorted(MANIFEST_DIR.glob("*.json"))
    if not manifests:
        print("ARTICLE_QA_UNKNOWN no manifests", file=sys.stderr)
        return 2
    try:
        for manifest in manifests:
            verify_manifest(manifest)
    except (QAFailure, KeyError, json.JSONDecodeError) as exc:
        print(f"ARTICLE_QA_FAIL {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
