# Deepnote Modules Shipyard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and commission the read-only `Shipyard Core Diagnostics` Deepnote Module, proving that a consumer notebook receives the same compact result as the canonical versioned Python package.

**Architecture:** The canonical implementation lives in the connected Git repository under `src/shipyard_core_diagnostics`. A source notebook exposes two thin function adapters as Deepnote Module exports. A separate consumer notebook imports those exports, compares them with direct package calls, validates the compact contract, and records commissioning evidence in the existing Flight Recorder.

**Tech Stack:** Python 3.13, standard library `json`, `pathlib`, `re`, and `unittest`; Deepnote notebooks and Modules; connected Git repository `nakama_test`; existing Palace Shipyard SQLite and Flight Recorder.

## Global Constraints

- This plan covers only Deepnote Modules.
- The first module is read-only and exports exactly `shipyard_status(root: str) -> dict` and `validate_compact_result(result: dict) -> dict`.
- Canonical code remains in normal versioned Python files; the Deepnote Module is an adapter and distribution surface.
- Module output is JSON-serializable, contains no credential values, and is smaller than 8 KB encoded as UTF-8.
- The module does not export AutoMem mutation, Git operations, credentials, arbitrary shell execution, scheduler control, or integration access.
- Raw logs remain in Deepnote or Git; ChatGPT receives compact summaries only.
- One active Deepnote run is allowed at a time.
- Publishing the source notebook and selecting exported blocks are explicit manual UI gates when no connector action exists.
- Implementation follows RED → GREEN → source-notebook verification → manual publish gate → consumer equivalence verification → cold-run verification.

---

## File Map

- `src/shipyard_core_diagnostics/__init__.py` — public package surface.
- `src/shipyard_core_diagnostics/contract.py` — compact-result validation and secret-pattern rejection.
- `src/shipyard_core_diagnostics/status.py` — read-only Palace Shipyard state inspection.
- `tests/test_shipyard_core_diagnostics.py` — contract and status behavior tests.
- `docs/deepnote/shipyard-core-diagnostics-module.md` — notebook names, exported names, manual publish instructions, and commissioning evidence.
- Deepnote notebook `Shipyard Core Diagnostics Module` — source module adapter and direct verification.
- Deepnote notebook `Shipyard Core Diagnostics Consumer` — imported-module equivalence and cold-run verification.

### Task 1: Compact Result Contract

**Files:**
- Create: `src/shipyard_core_diagnostics/__init__.py`
- Create: `src/shipyard_core_diagnostics/contract.py`
- Create: `tests/test_shipyard_core_diagnostics.py`

**Interfaces:**
- Produces: `validate_compact_result(result: dict) -> dict`
- Produces constants: `MODULE_NAME = "shipyard-core-diagnostics"`, `MODULE_VERSION = "0.1.0"`, `MAX_OUTPUT_BYTES = 8192`
- Validation success result: `{"valid": True, "errors": [], "bytes": int}`
- Validation failure result: `{"valid": False, "errors": list[str], "bytes": int}`

- [ ] **Step 1: Write the failing contract tests**

Create `tests/test_shipyard_core_diagnostics.py` with:

```python
import unittest

from shipyard_core_diagnostics import validate_compact_result


class CompactResultContractTests(unittest.TestCase):
    def valid_result(self) -> dict:
        return {
            "status": "success",
            "module": "shipyard-core-diagnostics",
            "version": "0.1.0",
            "artifact": "/datasets/_deepnote_work/shipyard",
            "checks": {"passed": 4, "failed": 0},
            "warnings": [],
            "next": None,
        }

    def test_accepts_valid_compact_result(self):
        validation = validate_compact_result(self.valid_result())
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["errors"], [])
        self.assertGreater(validation["bytes"], 0)

    def test_rejects_wrong_module_and_secret_bearing_value(self):
        result = self.valid_result()
        result["module"] = "other-module"
        result["warnings"] = ["https://user:password@example.invalid/path"]
        validation = validate_compact_result(result)
        self.assertFalse(validation["valid"])
        self.assertIn("module must equal shipyard-core-diagnostics", validation["errors"])
        self.assertIn("result contains credential-like material", validation["errors"])

    def test_rejects_oversized_result(self):
        result = self.valid_result()
        result["warnings"] = ["x" * 9000]
        validation = validate_compact_result(result)
        self.assertFalse(validation["valid"])
        self.assertIn("result exceeds 8192 UTF-8 bytes", validation["errors"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONPATH=src python -m unittest tests/test_shipyard_core_diagnostics.py -v
```

Expected: non-zero exit with `ModuleNotFoundError: No module named 'shipyard_core_diagnostics'`.

- [ ] **Step 3: Implement the minimal contract validator**

Create `src/shipyard_core_diagnostics/contract.py` with:

```python
from __future__ import annotations

import json
import re
from typing import Any

MODULE_NAME = "shipyard-core-diagnostics"
MODULE_VERSION = "0.1.0"
MAX_OUTPUT_BYTES = 8192
_REQUIRED_KEYS = {"status", "module", "version", "artifact", "checks", "warnings", "next"}
_SECRET_PATTERN = re.compile(
    r"(?i)(?:password|passwd|secret|token|api[_-]?key|authorization|"
    r"https?://[^/@\s]+:[^/@\s]+@)"
)


def _contains_secret_like_material(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_SECRET_PATTERN.search(value))
    if isinstance(value, dict):
        return any(
            _contains_secret_like_material(key) or _contains_secret_like_material(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_like_material(item) for item in value)
    return False


def validate_compact_result(result: dict) -> dict:
    errors: list[str] = []
    if not isinstance(result, dict):
        return {"valid": False, "errors": ["result must be a dict"], "bytes": 0}

    missing = sorted(_REQUIRED_KEYS - set(result))
    if missing:
        errors.append(f"missing keys: {missing}")
    if result.get("status") not in {"success", "warning", "error"}:
        errors.append("status must be success, warning, or error")
    if result.get("module") != MODULE_NAME:
        errors.append(f"module must equal {MODULE_NAME}")
    if result.get("version") != MODULE_VERSION:
        errors.append(f"version must equal {MODULE_VERSION}")
    checks = result.get("checks")
    if not isinstance(checks, dict) or set(checks) != {"passed", "failed"}:
        errors.append("checks must contain exactly passed and failed")
    elif not all(isinstance(checks[key], int) and checks[key] >= 0 for key in checks):
        errors.append("check counts must be non-negative integers")
    if not isinstance(result.get("warnings"), list):
        errors.append("warnings must be a list")
    if result.get("next") is not None and not isinstance(result.get("next"), str):
        errors.append("next must be a string or null")

    try:
        encoded = json.dumps(result, ensure_ascii=True, sort_keys=True).encode("utf-8")
    except (TypeError, ValueError):
        encoded = b""
        errors.append("result must be JSON-serializable")
    if len(encoded) > MAX_OUTPUT_BYTES:
        errors.append(f"result exceeds {MAX_OUTPUT_BYTES} UTF-8 bytes")
    if _contains_secret_like_material(result):
        errors.append("result contains credential-like material")

    return {"valid": not errors, "errors": errors, "bytes": len(encoded)}
```

Create `src/shipyard_core_diagnostics/__init__.py` with:

```python
from .contract import (
    MAX_OUTPUT_BYTES,
    MODULE_NAME,
    MODULE_VERSION,
    validate_compact_result,
)

__all__ = [
    "MAX_OUTPUT_BYTES",
    "MODULE_NAME",
    "MODULE_VERSION",
    "validate_compact_result",
]
```

- [ ] **Step 4: Run the contract tests and verify GREEN**

Run:

```bash
PYTHONPATH=src python -m unittest tests/test_shipyard_core_diagnostics.py -v
```

Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 5: Commit the contract**

```bash
git add src/shipyard_core_diagnostics tests/test_shipyard_core_diagnostics.py
git diff --cached --check
git commit -m "feat: add shipyard diagnostics contract"
```

### Task 2: Read-Only Shipyard Status Collector

**Files:**
- Create: `src/shipyard_core_diagnostics/status.py`
- Modify: `src/shipyard_core_diagnostics/__init__.py`
- Modify: `tests/test_shipyard_core_diagnostics.py`

**Interfaces:**
- Consumes: `validate_compact_result(result: dict) -> dict`
- Produces: `shipyard_status(root: str) -> dict`
- Reads only: `data/manifest.json`, `data/persistence_probe.json`, and paths declared under `manifest["components"]`

- [ ] **Step 1: Add failing status tests**

Add these imports and test class to `tests/test_shipyard_core_diagnostics.py`:

```python
import json
import tempfile
from pathlib import Path

from shipyard_core_diagnostics import shipyard_status


class ShipyardStatusTests(unittest.TestCase):
    def test_reports_success_for_complete_fixture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "data").mkdir()
            (root / "flight_recorder").mkdir()
            (root / "mempalace").mkdir()
            (root / "flight_recorder" / "recorder.py").write_text("# fixture\n")
            (root / "mempalace" / "store.py").write_text("# fixture\n")
            (root / "data" / "manifest.json").write_text(
                json.dumps({
                    "name": "Palace Shipyard",
                    "version": "0.1",
                    "components": {
                        "flight_recorder": "flight_recorder/recorder.py",
                        "mempalace": "mempalace/store.py",
                    },
                })
            )
            (root / "data" / "persistence_probe.json").write_text(
                json.dumps({"probe": "palace-shipyard-persistence-v1", "run_count": 7})
            )

            result = shipyard_status(str(root))
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["checks"], {"passed": 4, "failed": 0})
            self.assertEqual(result["warnings"], [])
            self.assertIsNone(result["next"])

    def test_reports_structured_error_for_missing_root(self):
        result = shipyard_status("/path/that/does/not/exist")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["checks"], {"passed": 0, "failed": 1})
        self.assertEqual(result["warnings"], ["project root does not exist"])
        self.assertEqual(result["next"], "restore or correct the Palace Shipyard root")
```

- [ ] **Step 2: Run the status tests and verify RED**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_shipyard_core_diagnostics.ShipyardStatusTests -v
```

Expected: import failure stating that `shipyard_status` is not exported.

- [ ] **Step 3: Implement the status collector**

Create `src/shipyard_core_diagnostics/status.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contract import MODULE_NAME, MODULE_VERSION, validate_compact_result


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def shipyard_status(root: str) -> dict:
    root_path = Path(root)
    if not root_path.is_dir():
        return {
            "status": "error",
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "artifact": str(root_path),
            "checks": {"passed": 0, "failed": 1},
            "warnings": ["project root does not exist"],
            "next": "restore or correct the Palace Shipyard root",
        }

    passed = 0
    failed = 0
    warnings: list[str] = []
    manifest = _read_json(root_path / "data" / "manifest.json")
    if manifest is None:
        failed += 1
        warnings.append("data/manifest.json is missing or malformed")
        components: dict[str, str] = {}
    else:
        passed += 1
        raw_components = manifest.get("components", {})
        components = raw_components if isinstance(raw_components, dict) else {}

    persistence = _read_json(root_path / "data" / "persistence_probe.json")
    if persistence is None:
        failed += 1
        warnings.append("data/persistence_probe.json is missing or malformed")
    else:
        passed += 1

    for name, relative_path in sorted(components.items()):
        if isinstance(relative_path, str) and (root_path / relative_path).is_file():
            passed += 1
        else:
            failed += 1
            warnings.append(f"component missing: {name}")

    status = "success" if failed == 0 else "warning"
    result = {
        "status": status,
        "module": MODULE_NAME,
        "version": MODULE_VERSION,
        "artifact": str(root_path),
        "checks": {"passed": passed, "failed": failed},
        "warnings": warnings,
        "next": None if failed == 0 else "repair missing or malformed Palace Shipyard state",
    }
    validation = validate_compact_result(result)
    if not validation["valid"]:
        return {
            "status": "error",
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "artifact": str(root_path),
            "checks": {"passed": passed, "failed": failed + 1},
            "warnings": ["compact result validation failed", *validation["errors"]],
            "next": "repair the diagnostics result contract",
        }
    return result
```

Replace `src/shipyard_core_diagnostics/__init__.py` with:

```python
from .contract import (
    MAX_OUTPUT_BYTES,
    MODULE_NAME,
    MODULE_VERSION,
    validate_compact_result,
)
from .status import shipyard_status

__all__ = [
    "MAX_OUTPUT_BYTES",
    "MODULE_NAME",
    "MODULE_VERSION",
    "shipyard_status",
    "validate_compact_result",
]
```

- [ ] **Step 4: Run the complete package tests and verify GREEN**

Run:

```bash
PYTHONPATH=src python -m unittest tests/test_shipyard_core_diagnostics.py -v
```

Expected: `Ran 5 tests` and `OK`.

- [ ] **Step 5: Commit the status collector**

```bash
git add src/shipyard_core_diagnostics tests/test_shipyard_core_diagnostics.py
git diff --cached --check
git commit -m "feat: add read-only shipyard diagnostics"
```

### Task 3: Prepare and Verify the Source Module Notebook

**Files:**
- Create Deepnote notebook: `Shipyard Core Diagnostics Module`
- Create: `docs/deepnote/shipyard-core-diagnostics-module.md`

**Interfaces:**
- Consumes: versioned package at `/datasets/_deepnote_work/nakama_test/src/shipyard_core_diagnostics`
- Produces module export name: `shipyard_status_export`
- Produces module export name: `validate_compact_result_export`
- Source notebook parameter: `shipyard_root`, default `/datasets/_deepnote_work/shipyard`

- [ ] **Step 1: Create the source notebook and safe input block**

Create notebook `Shipyard Core Diagnostics Module` in project `Palace Lab`. Add an `input-text` block with content `/datasets/_deepnote_work/shipyard` and metadata:

```json
{
  "deepnote_variable_name": "shipyard_root",
  "deepnote_variable_value": "/datasets/_deepnote_work/shipyard",
  "display_name": "Palace Shipyard root"
}
```

- [ ] **Step 2: Add the package import and direct verification block**

Add this code block:

```python
import json
import sys
from pathlib import Path

repo_src = Path("/datasets/_deepnote_work/nakama_test/src")
if str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))

from shipyard_core_diagnostics import shipyard_status, validate_compact_result

direct_result = shipyard_status(shipyard_root)
direct_validation = validate_compact_result(direct_result)
assert direct_validation["valid"], direct_validation
assert direct_validation["bytes"] < 8192
print(json.dumps({
    "status": "success",
    "artifact": "Shipyard Core Diagnostics Module source notebook",
    "result_status": direct_result["status"],
    "result_bytes": direct_validation["bytes"],
}, ensure_ascii=True, sort_keys=True))
```

- [ ] **Step 3: Add the two function export blocks**

Add one code block whose last value is the function object:

```python
def shipyard_status_export(root: str) -> dict:
    import sys
    from pathlib import Path

    repo_src = Path("/datasets/_deepnote_work/nakama_test/src")
    if str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))
    from shipyard_core_diagnostics import shipyard_status
    return shipyard_status(root)


shipyard_status_export
```

Add a second code block whose last value is the function object:

```python
def validate_compact_result_export(result: dict) -> dict:
    import sys
    from pathlib import Path

    repo_src = Path("/datasets/_deepnote_work/nakama_test/src")
    if str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))
    from shipyard_core_diagnostics import validate_compact_result
    return validate_compact_result(result)


validate_compact_result_export
```

- [ ] **Step 4: Run the source notebook and verify compact success**

Run the notebook with `shipyard_root=/datasets/_deepnote_work/shipyard`.

Expected compact stdout:

```json
{"artifact":"Shipyard Core Diagnostics Module source notebook","result_bytes":1,"result_status":"success","status":"success"}
```

The numeric `result_bytes` may differ; it must be greater than zero and less than 8192. The run must report zero failed blocks.

- [ ] **Step 5: Write source-notebook documentation and commit it**

Create `docs/deepnote/shipyard-core-diagnostics-module.md` with:

```markdown
# Shipyard Core Diagnostics Deepnote Module

Canonical package: `src/shipyard_core_diagnostics`

Source notebook: `Shipyard Core Diagnostics Module`

Safe parameter:
- `shipyard_root=/datasets/_deepnote_work/shipyard`

Named exports:
- `shipyard_status_export`
- `validate_compact_result_export`

The notebook is read-only. It does not expose Git operations, credentials, shell execution, scheduler control, integrations, or memory mutation.

## Manual publish gate

1. Open `Shipyard Core Diagnostics Module`.
2. Select **Create module**.
3. Select **Publish as a module**.
4. Mark the `shipyard_status_export` function block as an export with the same name.
5. Mark the `validate_compact_result_export` function block as an export with the same name.
6. Confirm that the module appears in the workspace Modules library.

Consumer verification must not begin until these six actions are confirmed.
```

Commit:

```bash
git add docs/deepnote/shipyard-core-diagnostics-module.md
git diff --cached --check
git commit -m "docs: prepare shipyard diagnostics module"
```

- [ ] **Step 6: Stop at the manual UI gate**

Report exactly:

```text
MANUAL ACTION REQUIRED
Open Shipyard Core Diagnostics Module, publish it as a module, and export the two named function blocks. Confirm when the module appears in the Modules library.
```

Do not create or run the consumer notebook before confirmation.

### Task 4: Consumer Equivalence and Cold-Run Commissioning

**Files:**
- Create Deepnote notebook: `Shipyard Core Diagnostics Consumer`
- Modify: `docs/deepnote/shipyard-core-diagnostics-module.md`
- Write project checkpoint: `/datasets/_deepnote_work/shipyard/data/checkpoints/deepnote_modules_latest.json`

**Interfaces:**
- Consumes imported function renamed to: `shipyard_status_module`
- Consumes imported function renamed to: `validate_compact_result_module`
- Produces commissioning result with fields: `status`, `equivalent`, `result_bytes`, `flight_event`

- [ ] **Step 1: Create the consumer notebook after manual confirmation**

Create `Shipyard Core Diagnostics Consumer`. Add a module block through the notebook footer, select `Shipyard Core Diagnostics Module`, import both exports, and rename them exactly:

```text
shipyard_status_export -> shipyard_status_module
validate_compact_result_export -> validate_compact_result_module
```

Add an `input-text` block named `shipyard_root` with default `/datasets/_deepnote_work/shipyard`.

- [ ] **Step 2: Add the equivalence and Flight Recorder verification block**

Add this code block:

```python
import json
import sys
from pathlib import Path

repo_src = Path("/datasets/_deepnote_work/nakama_test/src")
shipyard = Path("/datasets/_deepnote_work/shipyard")
if str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))
if str(shipyard) not in sys.path:
    sys.path.insert(0, str(shipyard))

from shipyard_core_diagnostics import (
    shipyard_status as shipyard_status_direct,
    validate_compact_result as validate_direct,
)
from flight_recorder.recorder import FlightRecorder

module_result = shipyard_status_module(shipyard_root)
direct_result = shipyard_status_direct(shipyard_root)
module_validation = validate_compact_result_module(module_result)
direct_validation = validate_direct(direct_result)

assert module_validation["valid"], module_validation
assert direct_validation["valid"], direct_validation
assert module_result == direct_result, {
    "module": module_result,
    "direct": direct_result,
}

recorder = FlightRecorder(
    db_path=shipyard / "data" / "palace_shipyard.sqlite3",
    jsonl_path=shipyard / "data" / "runtime_events.jsonl",
)
flight_event = recorder.record(
    namespace="DeepnoteModules",
    operation="shipyard_core_diagnostics_consumer",
    status="success",
    details={
        "module": "shipyard-core-diagnostics",
        "version": "0.1.0",
        "equivalent": True,
        "result_bytes": module_validation["bytes"],
    },
)

commissioning = {
    "status": "success",
    "equivalent": True,
    "result_bytes": module_validation["bytes"],
    "flight_event": flight_event,
}
print(json.dumps(commissioning, ensure_ascii=True, sort_keys=True))
```

- [ ] **Step 3: Run the consumer and verify first GREEN**

Run with `shipyard_root=/datasets/_deepnote_work/shipyard`.

Expected: zero failed blocks and compact stdout containing:

```json
{"equivalent":true,"flight_event":"non-empty UUID","result_bytes":1,"status":"success"}
```

The UUID and numeric byte count will differ.

- [ ] **Step 4: Run the consumer again as a cold run**

Start a new notebook run with the same input after the first run completes.

Expected: zero failed blocks, `equivalent=true`, a different non-empty `flight_event`, and `result_bytes` still below 8192.

- [ ] **Step 5: Record documentation evidence and commit**

Append to `docs/deepnote/shipyard-core-diagnostics-module.md`:

```markdown
## Commissioning evidence

- Source notebook direct verification: passed.
- Module published in workspace Modules library: confirmed manually.
- Consumer direct/module equivalence: passed.
- Independent cold run: passed.
- Flight Recorder namespace: `DeepnoteModules`.
- Compact output budget: below 8192 UTF-8 bytes.
```

Commit:

```bash
git add docs/deepnote/shipyard-core-diagnostics-module.md
git diff --cached --check
git commit -m "test: commission shipyard diagnostics module"
```

- [ ] **Step 6: Save the final checkpoint**

Write `/datasets/_deepnote_work/shipyard/data/checkpoints/deepnote_modules_latest.json` with:

```json
{
  "subsystem": "deepnote-modules",
  "status": "commissioned",
  "artifact": "Shipyard Core Diagnostics Module",
  "verified": {
    "package_tests": 5,
    "source_notebook": true,
    "module_published": true,
    "consumer_equivalent": true,
    "cold_run": true,
    "output_under_8192_bytes": true,
    "flight_recorder_event": true
  },
  "failed": [],
  "parked": [
    "AutoMem read-write module",
    "integration-backed modules",
    "scheduled module consumers",
    "Deepnote Agent module-library experiment"
  ],
  "next": "select the next parked Deepnote subsystem in a new Shipyard Focus Guard expedition"
}
```

- [ ] **Step 7: Run final repository and evidence verification**

Run:

```bash
PYTHONPATH=src python -m unittest tests/test_shipyard_core_diagnostics.py -v
git status --porcelain=v1
git log -4 --oneline
```

Expected:
- `Ran 5 tests` and `OK`;
- empty Git status output;
- four recent commits covering plan, contract, diagnostics, documentation, and commissioning as produced by the executed steps.
