"""Fictitious current-cohort policy mechanics; no embedding, ANN or timing claim."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Pending(Exception):
    pass


class Ledger:
    def __init__(self, totals, limits):
        self.used = Counter()
        self.totals = totals
        self.limits = dict(limits)
        self.extensions = []

    def charge(self, **units):
        self.used["budget_checks"] += 1
        self.totals["budget_checks"] += 1
        for name, count in units.items():
            if self.used[name] + count > self.limits.get(name, float("inf")):
                self.used["budget_denials"] += 1
                self.totals["budget_denials"] += 1
                raise Pending(name)
        self.used.update(units)
        self.totals.update(units)

    def extend(self, name, extra, reason):
        assert reason and extra > 0
        old = self.limits[name]
        self.limits[name] += extra
        self.extensions.append({"resource": name, "old": old, "new": self.limits[name], "reason": reason})


@dataclass(frozen=True)
class Doc:
    id: str
    vector: tuple
    version: int = 1
    visible: bool = True
    deleted: bool = False

    def payload(self):
        return {"id": self.id, "version": self.version, "vector": self.vector,
                "body": f"fictitious-{self.id}-v{self.version}"}


class Backend:
    def __init__(self, fixture, totals):
        self.docs = {key: Doc(key, tuple(vector)) for key, vector in fixture["documents"]}
        self.pages = {key: tuple(ids) for key, ids in fixture["pages"].items()}
        self.pages.update({"S" + key[1:]: (key,) for key in self.docs})
        self.snapshot = 1
        self.totals = totals
        totals["initial_objects"] += len(self.docs)
        totals["initial_record_encoded_bytes"] += len(encoded([d.payload() for d in self.docs.values()]))
        self.build_catalog()

    def response(self, action_id):
        return {"store": "fictitious-vector-store", "contract": "fixture_int4_ip_v1",
                "snapshot": self.snapshot, "rows": [self.docs[key].payload() for key in self.pages[action_id]]}

    def build_catalog(self):
        actions = []
        for key, ids in sorted(self.pages.items()):
            # Backend publication work, not a policy probe of alternative results.
            payload = encoded(self.response(key))
            self.totals["catalog_sizing_encodes"] += 1
            self.totals["catalog_sizing_encoded_bytes"] += len(payload)
            actions.append({"id": key, "coverage": [(d, self.docs[d].version) for d in ids],
                            "response_bytes": len(payload)})
        self.catalog = {"snapshot": self.snapshot, "actions": actions,
                        "objects": {key: {"version": d.version, "visible": d.visible, "deleted": d.deleted}
                                    for key, d in sorted(self.docs.items())}}
        self.catalog_wire = encoded(self.catalog)
        self.totals["catalog_publications"] += 1
        self.totals["catalog_metadata_encoded_bytes"] += len(self.catalog_wire)

    def mutate(self, changes):
        affected = set()
        for event in changes:
            old = self.docs[event["id"]]
            vector = tuple(event.get("vector", old.vector))
            visible = False if event["op"] == "hide" else old.visible
            deleted = event["op"] == "delete" or old.deleted
            self.docs[old.id] = Doc(old.id, vector, old.version + 1, visible, deleted)
            affected.add(old.id)
            self.totals["update_records"] += 1
            self.totals["update_record_encoded_bytes"] += len(encoded(self.docs[old.id].payload()))
        self.snapshot += 1
        self.totals["update_committed_events"] += 1
        self.build_catalog()
        return affected

    def fetch(self, action, ledger):
        ledger.charge(backend_fetch_calls=1, backend_response_bytes=action["response_bytes"])
        wire = encoded(self.response(action["id"]))
        assert len(wire) == action["response_bytes"], "advertised exact encoding contract mismatch"
        ledger.charge(backend_response_encodes=1, backend_response_decodes=1)
        value = json.loads(wire)
        assert value["snapshot"] == self.snapshot
        ledger.charge(decoded_rows=len(value["rows"]))
        return value["rows"]


class Cache:
    def __init__(self, fixture, totals):
        self.entries = OrderedDict()
        self.size = self.peak_entries = self.peak_bytes = 0
        self.max_entries = fixture["cache_entries"]
        self.max_bytes = fixture["cache_bytes"]
        self.totals = totals

    def get(self, key, metadata, ledger):
        ledger.charge(cache_probes=1)
        if key not in self.entries:
            ledger.charge(cache_misses=1)
            return None
        value, deps, _ = self.entries[key]
        for doc_id, version in deps.items():
            ledger.charge(cache_dependency_checks=1)
            assert metadata[doc_id]["version"] == version
        ledger.charge(cache_hits=1, cache_return_encoded_bytes=len(encoded(value)))
        self.entries.move_to_end(key)
        return value

    def put(self, key, value, deps, ledger):
        size = len(encoded([key, value, deps]))
        ledger.charge(cache_writes=1, cache_write_encoded_bytes=size)
        if key in self.entries:
            _, _, old_size = self.entries.pop(key)
            self.size -= old_size
        if size > self.max_bytes:
            ledger.charge(cache_rejections=1)
            return
        while self.entries and (len(self.entries) >= self.max_entries or self.size + size > self.max_bytes):
            _, (_, _, old_size) = self.entries.popitem(last=False)
            self.size -= old_size
            ledger.charge(cache_evictions=1, cache_evicted_encoded_bytes=old_size)
        self.entries[key] = (value, dict(deps), size)
        self.size += size
        self.peak_entries = max(self.peak_entries, len(self.entries))
        self.peak_bytes = max(self.peak_bytes, self.size)
        assert len(self.entries) <= self.max_entries and self.size <= self.max_bytes

    def invalidate(self, affected):
        for key, (_, deps, size) in list(self.entries.items()):
            self.totals["invalidation_entry_checks"] += 1
            if affected.intersection(deps):
                del self.entries[key]
                self.size -= size
                self.totals["cache_invalidations"] += 1
                self.totals["cache_invalidated_encoded_bytes"] += size


class Planner:
    """Receives only current metadata and demands, never vectors or future events."""
    def __init__(self, strategy, actions, ledger):
        self.strategy = strategy
        self.actions = actions
        self.ledger = ledger

    def clone(self, values):
        self.ledger.charge(planner_set_copies=1, planner_copied_materials=len(values))
        return set(values)

    def eligible(self, required):
        result = []
        for action in self.actions:
            self.ledger.charge(planner_evaluations=1, planner_coverage_checks=len(action["coverage"]))
            covered = required.intersection(tuple(pair) for pair in action["coverage"])
            if covered:
                result.append((action, covered))
        return result

    def greedy_pick(self, candidates):
        best = None
        for action, covered in candidates:
            self.ledger.charge(planner_ratio_comparisons=1)
            if best is None:
                best = action, covered
                continue
            old, old_covered = best
            left = action["response_bytes"] * len(old_covered)
            right = old["response_bytes"] * len(covered)
            if left < right or (left == right and action["id"] < old["id"]):
                best = action, covered
        assert best is not None
        return best

    def greedy_plan(self, required):
        remaining = self.clone(required)
        path, cost = [], 0
        while remaining:
            self.ledger.charge(planner_simulated_steps=1)
            action, covered = self.greedy_pick(self.eligible(remaining))
            path.append(action["id"])
            cost += action["response_bytes"]
            remaining.difference_update(covered)
        return cost, tuple(path)

    def prefix_plans(self, required, candidates):
        options = []
        for action, covered in candidates:
            self.ledger.charge(planner_prefix_simulations=1)
            remaining = self.clone(required)
            remaining.difference_update(covered)
            tail_cost, tail = self.greedy_plan(remaining)
            options.append((action["response_bytes"] + tail_cost, (action["id"],) + tail, action))
        return options

    def choose(self, required, per_request):
        if self.strategy == "per_request":
            target = next(items for items in per_request if items)
            candidates = self.eligible(target)
            options = self.prefix_plans(target, candidates)
            cost, path = self.greedy_plan(target)
            by_id = {a["id"]: a for a in self.actions}
            options.append((cost, path, by_id[path[0]]))
            singles = []
            single_cost = 0
            for doc_id, _ in sorted(target):
                self.ledger.charge(planner_single_route_items=1)
                action = by_id["S" + doc_id[1:]]
                singles.append(action["id"])
                single_cost += action["response_bytes"]
            options.append((single_cost, tuple(singles), by_id[singles[0]]))
            self.ledger.charge(planner_route_comparisons=len(options))
            best = min(options, key=lambda item: (item[0], item[1]))
            return best[2], {"kind": "local_complete_route", "predicted_completion_bytes": best[0], "path": best[1]}
        candidates = self.eligible(required)
        if self.strategy == "shared_greedy":
            action, _ = self.greedy_pick(candidates)
            return action, {"kind": "global_ratio"}
        assert self.strategy == "rollout"
        self.ledger.charge(planner_forced_choice_checks=1)
        if len(candidates) == len(required) and all(len(cov) == 1 for _, cov in candidates):
            distinct = {next(iter(cov)) for _, cov in candidates}
            if len(distinct) == len(required):
                action, _ = self.greedy_pick(candidates)
                return action, {"kind": "forced_actions_greedy"}
        options = self.prefix_plans(required, candidates)
        self.ledger.charge(planner_route_comparisons=len(options))
        best = min(options, key=lambda item: (item[0], item[2]["id"]))
        return best[2], {"kind": "one_step_rollout", "predicted_completion_bytes": best[0], "path": best[1]}


class Cohort:
    def __init__(self, event, fixture, totals):
        self.id = event["id"]
        self.requests = [{"name": name, "q": tuple(fixture["queries"][name]), "scope": tuple(scope)}
                         for name, scope in event["queries"]]
        limits = dict(fixture["default_limits"])
        limits["score_evals"] = event.get("score_limit", limits["score_evals"])
        self.ledger = Ledger(totals, limits)
        self.snapshot = None
        self.scores = {}
        self.ranks = {}
        self.actions = []
        self.done = None


class Engine:
    def __init__(self, strategy, fixture):
        self.strategy = strategy
        self.fixture = fixture
        self.totals = Counter()
        self.backend = Backend(fixture, self.totals)
        self.cache = Cache(fixture, self.totals)
        self.catalog = None
        self.active = None
        self.completed = []
        self.peak_request_state_bytes = 0

    def admit(self, event):
        assert self.active is None or self.active.done is not None
        self.active = Cohort(event, self.fixture, self.totals)
        self.totals["cohort_admissions"] += 1
        self.totals["request_admissions"] += len(self.active.requests)

    def synchronize(self, c):
        c.ledger.charge(catalog_version_checks=1)
        if self.catalog is None or self.catalog["snapshot"] != self.backend.snapshot:
            wire = self.backend.catalog_wire
            c.ledger.charge(catalog_fetches=1, catalog_return_bytes=len(wire), catalog_decodes=1)
            self.catalog = json.loads(wire)
        else:
            c.ledger.charge(catalog_memo_hits=1)
        if c.snapshot != self.catalog["snapshot"]:
            c.ledger.charge(cohort_snapshot_bindings=1)
            if c.snapshot is not None:
                c.ledger.charge(cohort_version_repairs=1)
            metadata = self.catalog["objects"]
            for key in list(c.scores):
                _, doc_id, version = key
                c.ledger.charge(request_prefix_dependency_checks=1)
                item = metadata[doc_id]
                if item["version"] != version or not item["visible"] or item["deleted"]:
                    del c.scores[key]
                    c.ledger.charge(request_prefix_invalidations=1)
            c.ranks.clear()
            c.done = None
            c.snapshot = self.catalog["snapshot"]

    def allowed(self, req, ledger):
        found = []
        for key in sorted(req["scope"]):
            ledger.charge(scope_metadata_checks=1)
            info = self.catalog["objects"][key]
            if info["visible"] and not info["deleted"]:
                found.append((key, info["version"]))
        return found

    def evaluate_available(self, c):
        missing_by_request = []
        metadata = self.catalog["objects"]
        for index, req in enumerate(c.requests):
            missing = set()
            for doc_id, version in self.allowed(req, c.ledger):
                working_key = (index, doc_id, version)
                if working_key in c.scores:
                    c.ledger.charge(request_prefix_hits=1)
                    continue
                score_key = "score:" + encoded([req["q"], doc_id, version]).decode()
                hit = self.cache.get(score_key, metadata, c.ledger)
                if hit is not None:
                    c.scores[working_key] = hit
                    c.ledger.charge(request_prefix_writes=1)
                    continue
                row = self.cache.get(f"row:{doc_id}:{version}", metadata, c.ledger)
                if row is None:
                    missing.add((doc_id, version))
                    continue
                c.ledger.charge(score_evals=1, integer_multiply_adds=len(req["q"]))
                value = sum(a * b for a, b in zip(req["q"], row["vector"]))
                c.scores[working_key] = value
                c.ledger.charge(request_prefix_writes=1)
                self.cache.put(score_key, value, {doc_id: version}, c.ledger)
            missing_by_request.append(missing)
        return missing_by_request

    def rank_and_sources(self, c):
        metadata = self.catalog["objects"]
        source_missing = []
        for index, req in enumerate(c.requests):
            allowed = self.allowed(req, c.ledger)
            if index not in c.ranks:
                key = "rank:" + encoded([req["q"], allowed, self.fixture["k"]]).decode()
                ranked = self.cache.get(key, metadata, c.ledger)
                if ranked is None:
                    c.ledger.charge(rank_builds=1, rank_input_items=len(allowed))
                    ranked = sorted([(doc_id, c.scores[(index, doc_id, version)], version)
                                     for doc_id, version in allowed], key=lambda it: (-it[1], it[0]))[:self.fixture["k"]]
                    self.cache.put(key, ranked, dict(allowed), c.ledger)
                c.ranks[index] = ranked
            missing = set()
            for doc_id, _, version in c.ranks[index]:
                row = self.cache.get(f"row:{doc_id}:{version}", metadata, c.ledger)
                if row is None:
                    missing.add((doc_id, version))
            source_missing.append(missing)
        return source_missing

    def publish(self, c):
        outputs = []
        metadata = self.catalog["objects"]
        for index, req in enumerate(c.requests):
            items = []
            for doc_id, score, version in c.ranks[index]:
                c.ledger.charge(source_validations=1)
                info = metadata[doc_id]
                assert info["version"] == version and info["visible"] and not info["deleted"] and doc_id in req["scope"]
                row = self.cache.get(f"row:{doc_id}:{version}", metadata, c.ledger)
                assert row is not None
                items.append({"id": doc_id, "score": score, "version": version, "body": row["body"]})
            outputs.append({"query": req["name"], "scope": req["scope"], "items": items})
        value = {"status": "complete", "snapshot": c.snapshot, "cohort": c.id, "requests": outputs}
        c.ledger.charge(cohort_publications=1, request_publications=len(outputs), publication_encoded_bytes=len(encoded(value)))
        c.done = value
        return value

    def drain(self):
        c = self.active
        assert c is not None
        try:
            self.synchronize(c)
            if c.done is not None:
                return c.done
            while True:
                missing_by_request = self.evaluate_available(c)
                required = set().union(*missing_by_request)
                if not required:
                    missing_by_request = self.rank_and_sources(c)
                    required = set().union(*missing_by_request)
                    if not required:
                        result = self.publish(c)
                        self.completed.append(copy.deepcopy(result))
                        return result
                # This fixture has an analytic <=44-entry working set bound;
                # lookahead never assumes an unmodeled payload cache or eviction.
                assert len(self.cache.entries) + len(required) + sum(len(r["scope"]) for r in c.requests) + len(c.requests) <= 64
                planner = Planner(self.strategy, self.catalog["actions"], c.ledger)
                action, why = planner.choose(required, missing_by_request)
                c.ledger.charge(action_decisions=1, current_required_materials_observed=len(required))
                rows = self.backend.fetch(action, c.ledger)
                for row in rows:
                    meta = self.catalog["objects"][row["id"]]
                    assert row["version"] == meta["version"]
                    self.cache.put(f"row:{row['id']}:{row['version']}", row, {row["id"]: row["version"]}, c.ledger)
                c.actions.append({"action": action["id"], "snapshot": c.snapshot,
                                  "response_bytes": action["response_bytes"], "required_before": sorted(required), "decision": why})
                self.peak_request_state_bytes = max(self.peak_request_state_bytes, len(encoded([sorted(c.scores.items()), c.actions])))
        except Pending as exc:
            return {"status": "pending", "resource": str(exc), "snapshot": c.snapshot, "cohort": c.id,
                    "already_paid_scores": c.ledger.used["score_evals"], "already_paid_response_bytes": c.ledger.used["backend_response_bytes"]}

    def mutate(self, event):
        affected = self.backend.mutate(event["changes"])
        self.cache.invalidate(affected)


def reference(engine, c):
    outputs = []
    count = 0
    for req in c.requests:
        rows = []
        for doc_id in req["scope"]:
            d = engine.backend.docs[doc_id]
            if d.visible and not d.deleted:
                rows.append((doc_id, sum(a * b for a, b in zip(req["q"], d.vector)), d.version))
                count += 1
        ranked = sorted(rows, key=lambda it: (-it[1], it[0]))[:engine.fixture["k"]]
        items = [{"id": key, "score": score, "version": version,
                  "body": engine.backend.docs[key].payload()["body"]} for key, score, version in ranked]
        outputs.append({"query": req["name"], "scope": req["scope"], "items": items})
    return {"status": "complete", "snapshot": engine.backend.snapshot, "cohort": c.id, "requests": outputs}, count


def run_flow(strategy, name, events, fixture, deadline):
    engine = Engine(strategy, fixture)
    records, oracle_count = [], 0
    for number, event in enumerate(events):
        if time.monotonic() > deadline:
            raise TimeoutError("mechanics 60 second run limit")
        op = event["op"]
        record = {"event": number, "op": op}
        if op == "admit":
            engine.admit(event)
            record["cohort"] = event["id"]
        elif op == "mutate":
            engine.mutate(event)
            record["snapshot"] = engine.backend.snapshot
        elif op == "extend":
            engine.active.ledger.extend(event["resource"], event["extra"], event["reason"])
            record["extensions"] = copy.deepcopy(engine.active.ledger.extensions)
        elif op == "drain":
            before = engine.active.ledger
            output = engine.drain()
            assert output["status"] == event["expect"], (strategy, name, number, output)
            assert engine.active.ledger is before
            if output["status"] == "complete":
                expected, scored = reference(engine, engine.active)
                oracle_count += scored
                assert encoded(output) == encoded(expected), (strategy, name, number, output, expected)
            record.update({"output": output, "paid": dict(engine.active.ledger.used),
                           "actions": copy.deepcopy(engine.active.actions), "extensions": copy.deepcopy(engine.active.ledger.extensions),
                           "cache_entries": len(engine.cache.entries), "cache_bytes": engine.cache.size})
        else:
            raise ValueError(op)
        records.append(record)
    return {"strategy": strategy, "workload": name, "records": records, "totals": dict(engine.totals),
            "peak_cache_entries": engine.cache.peak_entries, "peak_cache_encoded_bytes": engine.cache.peak_bytes,
            "peak_request_record_encoded_bytes": engine.peak_request_state_bytes,
            "completed_requests": sum(len(out["requests"]) for out in engine.completed),
            "external_oracle": {"score_evals": oracle_count, "integer_multiply_adds": 4 * oracle_count,
                                "excluded_from_decisions_and_strategy_totals": True}}


def main():
    base = Path(__file__).resolve().parents[1]
    permission = base / "治理" / "运行放行-v1.json"
    if not permission.exists():
        raise PermissionError("explicit root admission record required before running")
    admitted = json.loads(permission.read_text(encoding="utf-8"))
    assert admitted["run_authorized"] is True and admitted["decision_owner"] == "/root"
    manifest = json.loads((base / "治理" / "运行前冻结清单-v1.json").read_text(encoding="utf-8"))
    for item in manifest["inputs"]:
        assert hashlib.sha256((base / item["path"]).read_bytes()).hexdigest() == item["sha256"], item["path"]
    target = base / "结果" / "run-001.json"
    if target.exists():
        raise FileExistsError("refuse overwriting first completed run")
    fixture = json.loads((base / "治理" / "fixture-v1.json").read_text(encoding="utf-8"))
    deadline = time.monotonic() + fixture["run_limit_seconds"]
    runs = [run_flow(strategy, name, events, fixture, deadline)
            for name, events in fixture["workloads"].items() for strategy in fixture["strategies"]]
    output = {"version": "joint-policy-run-v1", "kind": "fictitious_current_cohort_logical_bytes_not_performance",
              "runs": runs, "formal_semantic_metrics": None, "native_ANN_run": False,
              "physical_IO_or_wall_latency_measured": False, "all_completed_outputs_match_reference": True}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded(output) + b"\n")
    print(json.dumps({"output": str(target), "runs": len(runs), "completed_requests": sum(r["completed_requests"] for r in runs)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
