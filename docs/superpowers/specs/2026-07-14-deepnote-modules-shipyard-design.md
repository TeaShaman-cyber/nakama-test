# Deepnote Modules for Palace Shipyard — Design

**Date:** 2026-07-14
**Status:** Approved design; implementation not started

## Purpose

Turn the stable, reusable parts of Palace Shipyard into Deepnote Modules so notebooks can consume trusted functions and compact status outputs without copying implementation code or loading large snapshots into ChatGPT.

This expedition covers only Deepnote Modules. Integrations, scheduling, data apps, AutoMem feature expansion, and new memory backends remain separate research-queue items.

## Success Criteria

The first module experiment is successful when:

1. one source notebook exposes a small, explicit export surface;
2. one consumer notebook imports and executes that surface with parameters;
3. the source and consumer produce the same verified result for a fixed fixture;
4. failures are returned as compact structured output;
5. the experiment stays within Shipyard Focus Guard C+ v0.2;
6. publishing the source notebook as a module is documented as a manual UI gate if the connector cannot perform it.

## Architecture

```text
canonical Python package in project storage
              ↓
source notebook adapter
              ↓
Deepnote Module export
              ↓
consumer notebook
              ↓
compact JSON result + Flight Recorder event
```

The canonical implementation remains normal Python files under project storage or Git. A Deepnote Module is an adapter and distribution surface, not the source of truth. This prevents module propagation from silently replacing versioned code.

## First Module Boundary

The first module is intentionally narrow: `Shipyard Core Diagnostics`.

It exports two functions:

```python
shipyard_status(root: str) -> dict
validate_compact_result(result: dict) -> dict
```

`shipyard_status` reads non-secret project-local state and returns only:

- component presence;
- schema/version identifiers;
- test summary when available;
- persistence marker;
- active warnings;
- one recommended next action.

`validate_compact_result` checks the output contract without mutating project state.

The first module does not export AutoMem mutation, Git operations, credentials, arbitrary shell execution, scheduler control, or integration access.

## Module Contract

Every exported result follows this shape:

```json
{
  "status": "success|warning|error",
  "module": "shipyard-core-diagnostics",
  "version": "0.1.0",
  "artifact": "string",
  "checks": {
    "passed": 0,
    "failed": 0
  },
  "warnings": [],
  "next": "string|null"
}
```

The result must be JSON-serializable, contain no credential values, and target less than 8 KB of UTF-8 output.

## Source Notebook

The source notebook contains:

1. a short contract description;
2. input blocks only for safe parameters;
3. one import block that loads the canonical Python package;
4. one exported function block per public function;
5. one verification block that runs fixed fixtures;
6. one compact commissioning result.

Functions import their own dependencies or receive them explicitly because imported Deepnote functions execute in the consuming notebook context.

## Consumer Notebook

The consumer notebook:

1. imports only the required module exports;
2. supplies an explicit project root parameter;
3. calls `shipyard_status`;
4. validates the returned contract;
5. compares the result with the direct canonical-package call;
6. emits one compact JSON summary.

No consumer depends on source-notebook globals, hidden variables, or source integrations.

## Data and State Rules

- Canonical state remains in project-local SQLite, JSONL, and versioned Python files.
- Modules may read state but the first module is read-only.
- Module output is a rebuildable view, never canonical memory.
- Raw logs remain in Deepnote/Git; ChatGPT receives only compact summaries.
- No secrets, environment-variable values, OAuth material, or credential-bearing URLs may enter outputs.

## Failure Handling

Expected failures become structured results where possible:

- missing project path;
- missing manifest;
- unsupported schema version;
- malformed compact result;
- output larger than the configured budget.

Unexpected exceptions fail the notebook run so Deepnote snapshots preserve evidence. The compact result includes only exception type and a sanitized message, never a full environment dump.

## Verification Strategy

Implementation follows RED → GREEN → cold-run verification:

1. write contract tests against absent module adapters;
2. confirm the expected failure;
3. implement the minimum adapter functions;
4. run unit tests against fixed temporary fixtures;
5. publish the source notebook manually as a Module if no connector action exists;
6. execute a separate consumer notebook;
7. compare module output with the direct canonical-package output;
8. repeat from a cold run;
9. record the result in Flight Recorder.

## Resource Guard

One module expedition ends at the first of:

- one verified artifact;
- eight normal tool calls;
- three Deepnote runs;
- one large inline snapshot;
- discovery of a new independent subsystem.

Up to three extra tool calls are allowed only to finish an already-started verification. One active run is allowed at a time. The target notebook stdout is at most 8 KB.

Every checkpoint reports:

```text
FOUND
BUILT
VERIFIED
COST
FAILED
PARKED
NEXT
```

## Manual UI Gate

The current connector can create and run notebooks but exposes no action for `Publish as a module` or selecting exported blocks. If that remains true during implementation, the source notebook will be prepared completely and execution will pause at one explicit human action:

```text
Open source notebook → Create module → Publish as a module → mark named blocks as exports
```

The consumer verification begins only after that gate is confirmed.

## Research Queue — Not Part of This Spec

- reusable AutoMem read/write module;
- integration-backed modules;
- scheduled module consumers;
- Deepnote Agent use of the module library;
- data apps and dashboards;
- module version migration and rollback;
- cross-project module impact analysis.

## Identity Invariant

The module layer may change how trusted functions are distributed, but it must not change where canonical code and durable memory live.

> Do not move the source of truth into the convenience layer.
