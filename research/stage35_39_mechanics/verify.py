"""Check selected historical hashes and replay fictional mechanics only."""
import hashlib
import importlib.util
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
manifest = json.loads((ROOT / "provenance.json").read_text(encoding="utf-8"))
for name, record in manifest["source_artifacts"].items():
    actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    if actual != record["sha256"]:
        raise AssertionError(f"artifact hash mismatch: {name}")

for group, filename, expected_count in (
    ("workflow", "workflow_fixture.py", 12),
    ("policy", "joint_policy.py", 9),
):
    spec = importlib.util.spec_from_file_location(group, ROOT / group / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[group] = module
    spec.loader.exec_module(module)
    fixture = json.loads((ROOT / group / "fixture.json").read_text(encoding="utf-8"))
    deadline = time.monotonic() + fixture["run_limit_seconds"]
    runs = [module.run_flow(mode, name, events, fixture, deadline)
            for name, events in fixture["workloads"].items()
            for mode in fixture["strategies"]]
    expected = json.loads((ROOT / group / "results" / "run-001.json").read_text(encoding="utf-8"))
    assert len(runs) == expected_count
    assert json.loads(json.dumps(runs)) == expected["runs"], group
    print(f"{group}: {len(runs)} fictional runs match recorded results")
