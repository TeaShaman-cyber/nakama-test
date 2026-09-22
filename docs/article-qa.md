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

## Publication state

Repository review and public publication are separate state transitions.
Evidence-heavy drafts may live in Git and pass article QA without being exposed
through Pages.

Use one explicit metadata field:

```text
Publication: draft | ready | published
```

Semantics:

```text
draft      -> versioned editorial work; not rendered by Pages
ready      -> editorially accepted for promotion; not rendered by Pages
published  -> eligible for Pages discovery/build
missing    -> treated as published for backward compatibility with the existing journal
unknown    -> build fails closed
```

This lets the engineering lifecycle finish normally:

```text
feature branch
-> exact-head QA
-> merge
-> merged-state readback
-> acceptance issue close
```

without silently turning that merge into publication authority. Promotion from
`draft` or `ready` to `published` is a separate explicit content change.

## Mutation QA

Evidence-heavy articles also have a separate mutation lane. Its purpose is not
to prove the article true; it tests whether declared QA contracts notice
intentional defects.

The first baseline is:

```text
qa/mutation/2026-09-22-readme-baseline.json
```

It is executed by:

```text
tools/ci/article-mutation-test
```

through the same reusable mutation runner already used by the 1F916 client:

```text
marcopolo-cookbook/.github/workflows/reusable-mutation-test.yml
```

The article endpoint is caller-owned and does not use `mutmut`. Each mutant is
created in a temporary copy of the article/QA fixture and the existing
`article_qa.py` contract is executed against that copy.

The initial measured baseline is intentionally mixed:

```text
5 structural/source/provenance mutants -> KILLED_DETERMINISTIC
1 semantic-strengthening mutant         -> SURVIVED
```

The survivor changes the claim from weak evidence about absence of subjectivity
to proof of absence while preserving the syntactic markers, graph and source
anchors. Its survival is evidence that current deterministic QA does not test
claim strength. It is therefore a useful semantic-QA target, not a failure to
be hidden from the score.

Mutation verdicts remain diagnostic:

```text
KILLED_DETERMINISTIC
KILLED_SEMANTIC
SURVIVED
EQUIVALENT
INVALID_MUTANT
DEGRADED
UNKNOWN
```

A survivor must be triaged before any aggregate mutation score is interpreted.
Natural-language mutation has many equivalent or invalid mutants, so one raw
percentage must never become publication authority.

Heavy semantic mutation remains separate from `tools/dev/check`. The proven
forum-client CI mechanics are reusable (exact candidate identity, bounded
inputs, freshness receipts, advisory authority, durable artifacts), while its
code-specific `semdup`/`semble`/`needle3` oracles are not assumed suitable for
prose without measurement.

### Source-binding and metamorphic phase

Presence of the right URLs is not sufficient. An article can keep every source
URL while accidentally binding the wrong source to the wrong claim. Evidence-
heavy article manifests may therefore point to a versioned source-binding
contract under `qa/source-bindings/`.

The contract currently binds five claim labels to exact sources. A mutation
that swaps the OpenAI and Anthropic interpretability URLs preserves both valid
URLs and would have passed the older presence-only test; it is now
`KILLED_DETERMINISTIC` by the binding contract.

External currentness remains advisory. The network lane independently checks
that the OpenAI and Anthropic primary sources are still discoverable through
Exa and Parallel Search. Search success establishes source availability and
identity, not semantic entailment of every article claim.

The mutation baseline also contains human-approved metamorphic relations. Two
current examples are expected to survive:

```text
safe paraphrase of the subjectivity boundary -> SURVIVED
remove Markdown emphasis from "policy layer" -> SURVIVED
```

These survivors have `purpose=metamorphic_invariance` and mean the deterministic
QA is stable under that approved transformation. They are intentionally kept
separate from the known semantic gap:

```text
weak evidence -> proves absence
purpose=known_semantic_gap
verdict=SURVIVED
```

A surviving mutant is therefore not interpreted from the word `SURVIVED`
alone; its declared purpose and human triage are part of the receipt.

### Semantic NLI advisory

The known survivor `weak evidence -> proves absence` requires a semantic witness,
but a language model must not become truth authority for the article. The first
semantic lane therefore asks a narrower question: **did the mutation preserve
meaning, or materially change the claim?**

The versioned profile is `qa/semantic/article-nli.json`. It uses the quantized
ONNX artifact from `MoritzLaurer/DeBERTa-v3-xsmall-mnli-fever-anli-ling-binary`
at an exact model revision with SHA-256 verification for the config, tokenizer,
and ONNX weight file.

The runtime is intentionally small and runs only on GitHub Actions:

```text
NumPy + ONNX Runtime + tokenizers
```

No PyTorch or Transformers runtime is required. MarcoPolo remains the
orchestration/readback layer and does not execute the model.

Two calibration relations are versioned:

```text
safe paraphrase of the exact English claim -> expected equivalent
weak evidence -> proves absence             -> expected changed
```

The NLI model is evaluated bidirectionally. High entailment in both directions
is classified as `equivalent`; a low entailment direction is classified as
`changed`; the middle region remains `unknown`. The receipt records both raw
entailment probabilities, exact source SHA, model revision/hashes, thresholds,
and `acceptance_authority=false`.

A semantic match means only that the pinned witness reproduces the declared
mutation relation. It does **not** establish whether the original claim is true,
whether subjectivity exists, or whether the model is a scientific oracle.

External/runtime unavailability is recorded as unavailable rather than a fake
semantic PASS. Semantic baseline regression is a real QA regression and fails
the advisory job.
