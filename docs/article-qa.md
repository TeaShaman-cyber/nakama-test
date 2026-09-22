# Article QA

Evidence-heavy essays in this repository are treated like small engineering
artifacts: prose still needs editorial judgment, but some failure modes are
mechanical enough to make reproducible.

The goal is not to turn an essay into a theorem. The goal is to stop claiming
more than a check actually observed.

## Three QA layers

### 1. Deterministic repository gate

`tools/dev/check` is the pre-review entrypoint. It runs the existing unit tests,
Ruff checks, a static-site build and the article-QA verifier.

For registered evidence-heavy articles the verifier can establish narrow
mechanical claims:

- the canonical article and argument-graph artifact both exist;
- the embedded Mermaid graph is byte-equivalent to the reviewed `.mmd` source;
- the graph is a directed acyclic graph and one weakly connected component;
- every declared evidence root has a directed path to the declared conclusion;
- required logical sections and epistemic markers remain present;
- required source domains have not silently disappeared from the Markdown;
- the ordinary blog build and internal-link validation still pass.

A green gate means only those properties passed.

### 2. External advisory review

Some useful checks are intentionally not CI dependencies:

- render the graph with Mermaid and inspect whether the visual hierarchy still
  communicates the intended argument;
- inspect the same directed graph with Wolfram or another independent graph
  implementation for topology, articulation points and reachability;
- re-open time-sensitive sources and authoritative documentation when freshness
  matters;
- search for counterevidence or missing primary sources when a logical branch
  looks under-supported.

If one of these routes is unavailable, its result is `UNKNOWN`, not `PASS`.
A Mermaid render or a graph-theory result does not establish that a premise is
true.

### 3. Human-authoritative review

Automation does not decide:

- whether a factual source actually supports the wording used;
- whether an inference is proportionate to the evidence;
- whether contested ontology has been presented as settled;
- whether FACT / INFERENCE / HYPOTHESIS / UNKNOWN boundaries are honest;
- whether tone, fairness, privacy and publication are acceptable.

Those are review and publication decisions, not lint rules.

## Argument graph convention

A registered article has a manifest under `qa/articles/` and a Mermaid source
under `qa/argument-graphs/`.

The graph is a dependency map:

```text
evidence / specimen
        ->
intermediate claim
        ->
meta-thesis
        ->
conclusion
```

An edge means “supports the next block in this editorial argument”. It does not
mean physical causation and does not replace source verification.

The first specimen is:

`journal/2026-09-22-readme-byl-velikolepen-sistema-ne-rabotala.md`

Its editorial review exposed an important pattern: privacy/data-flow and model
self-description are different claims. They meet only at the narrower bridge
that the observation pipeline itself is part of the system being reasoned
about. Encoding that distinction as a graph made the accidental prose-level
glue visible.

## Local pre-review

Run:

```text
./tools/dev/check
```

The default build goes to a temporary directory. CI may pass `public` as the
first argument when it needs a deployable Pages artifact.

For an evidence-heavy article, a useful review receipt has three independent
lines:

```text
MECHANICAL: PASS / FAIL
ADVISORY: PASS / DEGRADED / UNKNOWN
EDITORIAL: accepted / changes requested
```

Keeping those lines separate is the point of the workflow.

## Network advisory lane

The deterministic gate deliberately does not depend on network providers.
A separate GitHub Actions workflow, `Article network advisory`, can call public
MCP services through pinned `mcporter@0.13.8` and stores receipts as an artifact.

Current routes:

```text
GitHub Actions
  -> pinned mcporter
     -> Wolfram Cloud MCP
     -> Exa public MCP
     -> Parallel Search public MCP
  -> direct readback of official GitHub Docs source
  -> receipts/article-network/*
```

The lane has different failure semantics from the deterministic gate:

```text
formal external assertion disproved -> FAIL_ASSERTION
provider / transport unavailable    -> DEGRADED_EXTERNAL_WITNESS
search does not surface target      -> NO_SIGNAL
official docs wording/path changed  -> REPROBE_REQUIRED
```

Only `FAIL_ASSERTION` is a blocking exit from the witness adapter. The other
states are preserved as advisory evidence rather than relabeled as article
failure.

The current Notion connector does not expose a mutation for making a page
public. Human permission exists to use temporary public publication for
editorial QA if that capability becomes available later, but the current
runtime state is `NOT_EXPOSED`. Git remains the canonical CI source, so Notion
publication is not a dependency of the pipeline.
