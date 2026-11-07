"""Fictitious sequential mechanics. No embedding, native ANN or timing benchmark."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class Pending(Exception):
    pass


class Ledger:
    def __init__(self, totals, score_limit=1000):
        self.totals = totals
        self.used = Counter()
        self.limits = {"score_evals": score_limit}
        self.extensions = []

    def charge(self, **units):
        self.used["budget_checks"] += 1
        self.totals["budget_checks"] += 1
        for name, amount in units.items():
            if self.used[name] + amount > self.limits.get(name, float("inf")):
                self.used["budget_denials"] += 1
                self.totals["budget_denials"] += 1
                raise Pending(name)
        self.used.update(units)
        self.totals.update(units)

    def extend_scores(self, extra, reason):
        assert reason and extra > 0
        old = self.limits["score_evals"]
        self.limits["score_evals"] += extra
        self.extensions.append({"resource": "score_evals", "old": old, "new": old + extra, "reason": reason})


@dataclass(frozen=True)
class Doc:
    id: str
    group: str
    vector: tuple
    version: int = 1
    visible: bool = True
    deleted: bool = False

    @property
    def body(self):
        return f"fictional-{self.id}-v{self.version}"


class Store:
    def __init__(self, fixture, totals):
        self.docs = {d[0]: Doc(d[0], d[1], tuple(d[2])) for d in fixture["documents"]}
        self.epochs = {g: 1 for g in "ABC"}
        self.snapshot = 1
        self.totals = totals
        totals["initial_doc_inserts"] += len(self.docs)
        totals["initial_vector_payload_bytes"] += sum(len(struct.pack("<4q", *d.vector)) for d in self.docs.values())
        totals["initial_source_payload_bytes"] += sum(len(d.body.encode()) for d in self.docs.values())

    def token(self, dependency):
        kind, key = dependency.split(":", 1)
        return self.epochs[key] if kind == "g" else self.docs[key].version

    def mutate(self, event):
        op, key = event["op"], event["id"]
        if op == "insert":
            assert key not in self.docs
            doc = Doc(key, event["group"], tuple(event["vector"]))
        else:
            old = self.docs[key]
            values = {"version": old.version + 1}
            if op == "modify":
                values["vector"] = tuple(event["vector"])
            elif op == "delete":
                values["deleted"] = True
            elif op == "hide":
                values["visible"] = False
            else:
                raise ValueError(op)
            doc = replace(old, **values)
        self.docs[key] = doc
        self.epochs[doc.group] += 1
        self.snapshot += 1
        self.totals.update({"update_events": 1, "update_log_records": 1})
        if op in ("insert", "modify"):
            self.totals["update_vector_payload_bytes"] += len(struct.pack("<4q", *doc.vector))
            self.totals["update_source_payload_bytes"] += len(doc.body.encode())
        return {"d:" + key, "g:" + doc.group}


class Cache:
    def __init__(self, fixture, totals):
        self.entries = OrderedDict()
        self.size = 0
        self.max_entries = fixture["cache_entries"]
        self.max_bytes = fixture["cache_serialized_bytes"]
        self.peak_entries = self.peak_bytes = 0
        self.totals = totals

    def get(self, key, store, ledger):
        ledger.charge(cache_probes=1)
        if key not in self.entries:
            ledger.charge(cache_misses=1)
            return None
        value, deps, size = self.entries[key]
        for dep, version in deps.items():
            ledger.charge(cache_dependency_checks=1)
            if store.token(dep) != version:
                raise AssertionError("stale cache entry survived invalidation")
        ledger.charge(cache_hits=1, cache_return_value_bytes=len(encoded(value)))
        self.entries.move_to_end(key)
        return value

    def put(self, key, value, deps, ledger):
        size = len(encoded([key, value, deps]))
        ledger.charge(cache_writes=1, cache_write_payload_bytes=size)
        if size > self.max_bytes:
            ledger.charge(cache_admission_rejections=1)
            return
        assert key not in self.entries
        while self.entries and (len(self.entries) >= self.max_entries or self.size + size > self.max_bytes):
            _, (_, _, removed) = self.entries.popitem(last=False)
            self.size -= removed
            ledger.charge(cache_evictions=1, cache_evicted_payload_bytes=removed)
        self.entries[key] = value, deps, size
        self.size += size
        self.peak_entries = max(self.peak_entries, len(self.entries))
        self.peak_bytes = max(self.peak_bytes, self.size)
        assert len(self.entries) <= self.max_entries and self.size <= self.max_bytes

    def invalidate(self, changed):
        for key, (_, deps, size) in list(self.entries.items()):
            self.totals["invalidation_entry_checks"] += 1
            for dep in deps:
                self.totals["invalidation_dependency_checks"] += 1
                if dep in changed:
                    del self.entries[key]
                    self.size -= size
                    self.totals.update({"cache_invalidations": 1, "cache_invalidated_payload_bytes": size})
                    break


@dataclass
class Request:
    q: tuple
    scope: str
    module: str
    snapshot: int
    ledger: Ledger
    allowed: object = None
    cursor: int = 0
    scores: list = field(default_factory=list)
    ranked: object = None
    sources: list = field(default_factory=list)
    done: object = None
    nodes: set = field(default_factory=set)
    edges: set = field(default_factory=set)
    stack: list = field(default_factory=list)


class Engine:
    def __init__(self, mode, fixture):
        self.mode, self.fixture = mode, fixture
        self.totals = Counter()
        self.store = Store(fixture, self.totals)
        self.cache = Cache(fixture, self.totals)
        self.max_graph_reference_bytes = 0

    def artifact(self, req, kind, identity, deps, build):
        key = kind + ":" + encoded(identity).decode("utf-8")
        req.ledger.charge(provider_calls=1)
        if self.mode == "dag":
            if key not in req.nodes:
                req.nodes.add(key)
                req.ledger.charge(dag_node_allocations=1)
            if req.stack:
                edge = (req.stack[-1], key)
                if edge not in req.edges:
                    req.edges.add(edge)
                    req.ledger.charge(dag_edge_insertions=1)
            req.stack.append(key)
        try:
            if self.mode != "direct":
                hit = self.cache.get(key, self.store, req.ledger)
                if hit is not None:
                    return hit
            value = build()
            if self.mode != "direct":
                self.cache.put(key, value, deps, req.ledger)
            return value
        finally:
            if self.mode == "dag":
                req.stack.pop()

    def scope_ids(self, req):
        deps = {"g:" + g: self.store.epochs[g] for g in req.scope}
        def build():
            req.ledger.charge(scope_builds=1)
            found = []
            for key, doc in sorted(self.store.docs.items()):
                req.ledger.charge(scope_member_checks=1)
                if doc.group in req.scope and doc.visible and not doc.deleted:
                    found.append(key)
            return tuple(found)
        return self.artifact(req, "scope", [req.scope, list(deps.items())], deps, build)

    def score(self, req, key):
        doc = self.store.docs[key]
        req.ledger.charge(metadata_reads=1)
        assert doc.visible and not doc.deleted and doc.group in req.scope
        deps = {"d:" + key: doc.version}
        def prepare():
            payload = struct.pack("<4q", *doc.vector)
            req.ledger.charge(row_preparations=1, vector_return_payload_bytes=len(payload))
            return tuple(struct.unpack("<4q", payload))
        def compute():
            vector = self.artifact(req, "row", [key, doc.version], deps, prepare)
            req.ledger.charge(score_evals=1, integer_multiply_adds=len(req.q))
            return sum(a * b for a, b in zip(req.q, vector))
        namespace = req.module if self.mode == "modular" else "global"
        return self.artifact(req, "score", [namespace, req.q, key, doc.version], deps, compute)

    def rank(self, req):
        deps = {"g:" + g: self.store.epochs[g] for g in req.scope}
        namespace = req.module if self.mode == "modular" else "global"
        def build():
            if req.allowed is None:
                req.allowed = self.scope_ids(req)
            while req.cursor < len(req.allowed):
                key = req.allowed[req.cursor]
                score = self.score(req, key)
                req.scores.append((key, score, self.store.docs[key].version))
                req.cursor += 1
            req.ledger.charge(rank_builds=1, rank_input_items=len(req.scores))
            return tuple(sorted(req.scores, key=lambda item: (-item[1], item[0]))[:self.fixture["k"]])
        return self.artifact(req, "rank", [namespace, req.q, req.scope, list(deps.items()), self.fixture["k"]], deps, build)

    def source(self, req, item):
        key, _, version = item
        doc = self.store.docs[key]
        req.ledger.charge(source_validations=1, metadata_reads=1)
        assert doc.version == version and doc.visible and not doc.deleted and doc.group in req.scope
        def build():
            body = doc.body
            req.ledger.charge(source_fetches=1, source_return_payload_bytes=len(body.encode()))
            return body
        return self.artifact(req, "source", [key, version], {"d:" + key: version}, build)

    def execute(self, req):
        if req.done is not None:
            return req.done
        req.ledger.charge(snapshot_validations=1)
        if req.snapshot != self.store.snapshot:
            return {"status": "rejected", "reason": "request_snapshot_changed"}
        try:
            if req.ranked is None:
                req.ranked = self.rank(req)
            while len(req.sources) < len(req.ranked):
                req.sources.append(self.source(req, req.ranked[len(req.sources)]))
            output = {"status": "complete", "snapshot": req.snapshot, "items": req.ranked}
            req.ledger.charge(result_publications=1, published_payload_bytes=len(encoded(output)))
            req.done = output
            self.max_graph_reference_bytes = max(self.max_graph_reference_bytes, len(encoded([sorted(req.nodes), sorted(req.edges)])) if req.nodes else 0)
            return output
        except Pending as exc:
            return {"status": "pending", "resource": str(exc), "cursor": req.cursor}


def reference(store, event, fixture):
    q = fixture["queries"][event["q"]]
    scored = [(d.id, sum(a * b for a, b in zip(q, d.vector)), d.version)
              for d in store.docs.values() if d.group in event["scope"] and d.visible and not d.deleted]
    return {"status": "complete", "snapshot": store.snapshot,
            "items": tuple(sorted(scored, key=lambda item: (-item[1], item[0]))[:fixture["k"]])}, len(scored)


def run_flow(mode, name, events, fixture, deadline):
    engine = Engine(mode, fixture)
    records, oracle_scores = [], 0
    for index, event in enumerate(events):
        if time.monotonic() > deadline:
            raise TimeoutError("60 second mechanics run budget")
        if event["op"] != "query":
            changed = engine.store.mutate(event)
            engine.cache.invalidate(changed)
            records.append({"event": index, "op": event["op"], "snapshot": engine.store.snapshot})
            continue
        ledger = Ledger(engine.totals, event.get("score_limit", 1000))
        req = Request(tuple(fixture["queries"][event["q"]]), event["scope"], event["module"], engine.store.snapshot, ledger)
        output = engine.execute(req)
        first = output
        if "extend_scores" in event:
            assert output["status"] == "pending" and ledger.used["score_evals"] == 2
            old_ledger = req.ledger
            ledger.extend_scores(event["extend_scores"], "frozen cold-request continuation probe")
            output = engine.execute(req)
            assert req.ledger is old_ledger and ledger.used["score_evals"] == len(req.allowed)
        expected, count = reference(engine.store, event, fixture)
        oracle_scores += count
        assert output == expected, (mode, name, index, output, expected)
        before = ledger.used.copy()
        assert engine.execute(req) == output and ledger.used == before
        records.append({"event": index, "op": "query", "q": event["q"], "scope": event["scope"],
                        "module": event["module"], "snapshot": engine.store.snapshot, "output": output,
                        "first_status": first["status"], "paid": dict(ledger.used), "extensions": ledger.extensions,
                        "cache_entries": len(engine.cache.entries), "cache_payload_bytes": engine.cache.size})
    return {"strategy": mode, "workload": name, "events": records, "totals": dict(engine.totals),
            "peak_cache_entries": engine.cache.peak_entries, "peak_cache_serialized_bytes": engine.cache.peak_bytes,
            "peak_graph_reference_bytes": engine.max_graph_reference_bytes,
            "external_oracle_account": {"score_evals": oracle_scores, "integer_multiply_adds": 4 * oracle_scores,
                                        "excluded_from_strategy_decisions_and_totals": True}}


def main():
    base = Path(__file__).resolve().parents[1]
    fixture_path = base / "治理" / "fixture-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    protocol = json.loads((base / "治理" / "运行前冻结清单-v1.json").read_text(encoding="utf-8"))
    for item in protocol["run_inputs"]:
        assert hashlib.sha256((base / item["path"]).read_bytes()).hexdigest() == item["sha256"], item["path"]
    target = base / "结果" / "run-001.json"
    if target.exists():
        raise FileExistsError("refuse overwriting first complete mechanics run")
    deadline = time.monotonic() + fixture["run_limit_seconds"]
    runs = [run_flow(mode, name, events, fixture, deadline)
            for name, events in fixture["workloads"].items() for mode in fixture["strategies"]]
    probes = [run_flow(mode, "budget_probe", [fixture["budget_probe"]], fixture, deadline) for mode in fixture["strategies"]]
    # Same paid primitive kernels and LRU behavior: only the recorded DAG differs.
    excluded = {"dag_node_allocations", "dag_edge_insertions", "budget_checks"}
    equivalences = []
    for name in fixture["workloads"]:
        strong, dag = [next(r for r in runs if r["workload"] == name and r["strategy"] == m) for m in ("strong", "dag")]
        normal = lambda r: {k: v for k, v in r["totals"].items() if k not in excluded}
        assert normal(strong) == normal(dag)
        assert [e.get("output") for e in strong["events"]] == [e.get("output") for e in dag["events"]]
        equivalences.append({"workload": name, "all_non_DAG_paid_units_equal": True,
                             "cache_occupancy_equal": strong["peak_cache_serialized_bytes"] == dag["peak_cache_serialized_bytes"]})
    result = {"version": "workflow-run-v1", "kind": "fictitious_sequential_mechanics_not_performance",
              "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(), "runs": runs, "budget_probes": probes,
              "equivalence": equivalences, "checks": {"all_outputs_equal_reference": True, "budget_resume": True,
              "same_completed_request_no_extra_work": True, "cache_limits": True},
              "formal_semantic_metrics": None, "native_ANN_run": False, "physical_IO_measured": False,
              "concurrent_singleflight_or_batching_tested": False}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded(result) + b"\n")
    print(json.dumps({"output": str(target), "main_runs": len(runs), "budget_probes": len(probes), "checks": result["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
