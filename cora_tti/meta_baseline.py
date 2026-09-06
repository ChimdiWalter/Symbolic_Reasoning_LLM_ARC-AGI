"""One explicitly identified baseline reasoner for the corrected census (v2c).

Directive section 6: the failure a proposer is trained on must be the failure
of the reasoner whose language the extension repairs. Protocol v2 evaluated
requirement 4 with the 200-schema scoped-fitter adapter but extracted its TFG
from the blind-runtime trace search, a different language with a different
fitter. This module removes that gap by making ONE configuration the single
authority for

    hypothesis generator   the complete single-block product of the frozen
                           terminals (set-equal to meta_induction.search's
                           space; see scripts/baseline_enumeration_identity.py)
    ordering               sorted partitions, sorted predicates, registered
                           key-feature order (differs from the actual search's
                           container order; declared, and irrelevant under a
                           fixed work limit with no deadline)
    slot fitter            scoped_slot_fitting.fit_outcome, strict options for
                           the success predicate, inspection options only for
                           the constraint-consistent comparison set
    evaluator              meta_ast.evaluate with meta_induction.descriptors
    budgets                a FIXED WORK LIMIT (all enumerated schemas); an
                           optional wall-clock limit exists only as an
                           operational safeguard and is recorded as truncation
    success predicate      EXACT_DEMONSTRATION_FIT on every demonstration
    trace observer         a per-schema structured outcome record, from which
                           the TFG is built

and by stamping the configuration digest on the trace AND on the TFG so a row
whose failure and TFG came from different configurations can be rejected.

Data-flow boundary (directive section 12): run_baseline receives demonstrations
and a configuration; tfg_from_trace receives demonstrations, the trace and the
configuration. Neither accepts, nor can be handed, a target schema, a concrete
table, a digest, a family label or generator metadata. Tests check the
signatures directly.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402
from cora_parent.tfg import ConcreteTFG, TFGEdge, TFGNode        # noqa: E402

MAX_FRONTIER_TERMS = 12
TRACE_BUILDER_VERSION = "tfg_from_trace:v1;frontier=constraint_consistent_by_cells_wrong_asc"


def _engine_hashes() -> dict:
    return {"meta_ast.py": hashlib.sha256(Path(M.__file__).read_bytes()).hexdigest(),
            "meta_induction.py": hashlib.sha256(Path(MI.__file__).read_bytes()).hexdigest()}


@dataclass(frozen=True)
class BaselineConfig:
    """Every scientific choice of the baseline reasoner, in one hashed record."""
    hypothesis_generator: str = "single_block_product"
    ordering: str = "sorted_partitions;sorted_predicates;registered_key_features"
    fitter: str = "cora_tti.scoped_slot_fitting.fit_outcome"
    strict_options: tuple = field(
        default_factory=lambda: tuple(sorted(SF.fitter_options(True).items())))
    inspection_options: tuple = field(
        default_factory=lambda: tuple(sorted(SF.fitter_options(False).items())))
    evaluator: str = "meta_ast.evaluate with meta_induction.descriptors"
    success_predicate: str = "EXACT_DEMONSTRATION_FIT on every demonstration"
    work_limit_schemas: int = 200
    wall_clock_limit_s: Optional[float] = None
    trace_observer: str = "per-schema structured outcome record"
    max_frontier_terms: int = MAX_FRONTIER_TERMS

    def to_json(self) -> dict:
        data = asdict(self)
        data["strict_options"] = [list(kv) for kv in self.strict_options]
        data["inspection_options"] = [list(kv) for kv in self.inspection_options]
        return data

    @classmethod
    def from_json(cls, data: dict) -> "BaselineConfig":
        data = dict(data)
        data["strict_options"] = tuple(tuple(kv) for kv in data["strict_options"])
        data["inspection_options"] = tuple(tuple(kv) for kv in data["inspection_options"])
        return cls(**data)

    def digest(self) -> str:
        """Configuration + fitter implementation + engine implementation."""
        payload = {"config": self.to_json(), "fitter_identity": SF.fitter_identity(),
                   "engine": _engine_hashes()}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def trace_config_digest(config: BaselineConfig) -> str:
    """Identity of the TFG builder applied to a trace of this configuration."""
    return hashlib.sha256(
        f"{config.digest()}|{TRACE_BUILDER_VERSION}|{config.max_frontier_terms}".encode()
    ).hexdigest()


def hypothesis_space(config: BaselineConfig) -> list:
    if config.hypothesis_generator != "single_block_product":
        raise ValueError(f"unknown hypothesis generator {config.hypothesis_generator!r}")
    if config.ordering != "sorted_partitions;sorted_predicates;registered_key_features":
        raise ValueError(f"unknown ordering {config.ordering!r}")
    return SF.baseline_single_block_schemas()


def _triple(schema) -> tuple:
    return (schema[1][0][1][0], schema[1][1][1][0], schema[1][2][1][0][1][0])


def _canonical(ast) -> str:
    return json.dumps(M.ast_to_json(ast), sort_keys=True)


def _evaluate(ast, grid):
    return M.evaluate(ast, np.asarray(grid), MI.descriptors)


def _palette(grid: np.ndarray) -> set:
    return set(int(v) for v in np.unique(grid))


def _mismatch_signature(program, pairs) -> dict:
    """HOW a constraint-consistent but inexact program differs from the
    demonstrations, on the first demonstration where it is defined."""
    for grid_in, grid_out in pairs:
        try:
            rendered = _evaluate(program, grid_in)
        except Exception as error:                                # noqa: BLE001
            return {"defined": False, "error": type(error).__name__}
        if rendered is None:
            continue
        if rendered.shape != grid_out.shape:
            return {"defined": True, "shape_matches": False}
        wrong = int(np.count_nonzero(rendered != grid_out))
        return {"defined": True, "shape_matches": True, "cells_wrong": wrong,
                "fraction_wrong": round(wrong / grid_out.size, 4),
                "palette_extra": len(_palette(rendered) - _palette(grid_out))}
    return {"defined": False}


@dataclass
class BaselineTrace:
    config_digest: str
    fitter_identity: str
    records: list
    exact: list                     # [(open_schema, program)]
    constraint_consistent: list     # [(open_schema, program, signature)] inspection only
    census: dict
    work_done: int
    enumerated_total: int           # size of the full hypothesis space
    truncated: bool                 # wall-clock cut OR work limit below the full space
    truncation_causes: list
    errors: int                     # schemas whose verdict is an EXECUTION_ERROR
    exhausted: int                  # schemas never judged because a limit fired
    inspection_errors: int          # errors in the inspection-only refit (not a verdict)
    seconds: float

    def complete(self) -> bool:
        """True only when every hypothesis in the declared space received a
        scientific verdict. A baseline that did not complete cannot support the
        statement "the baseline failed"."""
        return (not self.truncated and self.errors == 0 and self.exhausted == 0
                and self.work_done == self.enumerated_total)

    def incompleteness_reasons(self) -> list:
        reasons = []
        if self.work_done != self.enumerated_total:
            reasons.append(f"work_done {self.work_done} != enumerated {self.enumerated_total}")
        if self.truncated:
            reasons.extend(self.truncation_causes or ["truncated"])
        if self.errors:
            reasons.append(f"{self.errors} schema verdicts were EXECUTION_ERROR")
        if self.exhausted:
            reasons.append(f"{self.exhausted} schemas were never judged")
        return reasons

    def summary(self) -> dict:
        return {"config_digest": self.config_digest, "fitter_identity": self.fitter_identity,
                "work_done": self.work_done, "enumerated_total": self.enumerated_total,
                "truncated": self.truncated, "truncation_causes": list(self.truncation_causes),
                "errors": self.errors, "exhausted": self.exhausted,
                "inspection_errors": self.inspection_errors,
                "complete": self.complete(),
                "incompleteness_reasons": self.incompleteness_reasons(),
                "census": dict(sorted(self.census.items())),
                "exact": len(self.exact),
                "constraint_consistent": len(self.constraint_consistent),
                "seconds": round(self.seconds, 3)}


def run_baseline(pairs, config: BaselineConfig) -> BaselineTrace:
    """The baseline reasoner. Receives demonstrations and a configuration only."""
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in pairs]
    started = time.monotonic()
    deadline = (None if config.wall_clock_limit_s is None
                else started + float(config.wall_clock_limit_s))
    records, exact, consistent, census = [], [], [], {}
    truncated, work_done, causes = False, 0, []
    inspection_errors = 0
    full_space = hypothesis_space(config)
    space = full_space[:config.work_limit_schemas]
    if len(space) < len(full_space):
        #  a work limit below the declared space is itself a truncation and is
        #  never allowed to look like a complete search that found nothing
        truncated = True
        causes.append(f"work_limit_schemas={config.work_limit_schemas} "
                      f"< hypothesis space {len(full_space)}")
    for index, schema in enumerate(space):
        if deadline is not None and time.monotonic() > deadline:
            truncated = True
            causes.append("wall_clock_limit")
            for rest_index in range(index, len(space)):
                records.append({"index": rest_index, "triple": list(_triple(space[rest_index])),
                                "status": "RESOURCE_EXHAUSTED", "code": "wall_clock_limit",
                                "detail": ""})
                census["RESOURCE_EXHAUSTED"] = census.get("RESOURCE_EXHAUSTED", 0) + 1
            break
        work_done += 1
        strict = SF.fit_outcome(schema, pairs, require_exact_replay=True)
        record = {"index": index, "triple": list(_triple(schema)),
                  "status": strict["status"], "code": strict["code"],
                  "detail": strict["detail"]}
        if strict["status"] == "EXACT_DEMONSTRATION_FIT":
            exact.append((schema, strict["program"]))
        elif strict["status"] == "FIT_FAILURE" and strict["code"] == "final_execution_mismatch":
            #  bindings exist but do not replay exactly: inspection-only set. The
            #  STRICT verdict already stands; a failure of this inspection call is
            #  recorded as such and never overwrites the scientific verdict.
            loose = SF.fit_outcome(schema, pairs, require_exact_replay=False)
            if loose["status"] == "CONSTRAINT_CONSISTENT_BINDING":
                signature = _mismatch_signature(loose["program"], pairs)
                record["status"] = "CONSTRAINT_CONSISTENT_BINDING"
                record["code"] = None
                record["signature"] = signature
                consistent.append((schema, loose["program"], signature))
            elif loose["status"] in ("EXECUTION_ERROR", "RESOURCE_EXHAUSTED"):
                inspection_errors += 1
                record["inspection_status"] = loose["status"]
                record["inspection_code"] = loose["code"]
            else:
                record["status"] = loose["status"]
                record["code"] = loose["code"]
        census[record["status"]] = census.get(record["status"], 0) + 1
        records.append(record)
    #  the hypotheses that were never reached at all, if the space was cut
    for index in range(len(space), len(full_space)):
        records.append({"index": index, "triple": list(_triple(full_space[index])),
                        "status": "RESOURCE_EXHAUSTED", "code": "work_limit_schemas",
                        "detail": ""})
        census["RESOURCE_EXHAUSTED"] = census.get("RESOURCE_EXHAUSTED", 0) + 1
    return BaselineTrace(config_digest=config.digest(), fitter_identity=SF.fitter_identity(),
                         records=records, exact=exact, constraint_consistent=consistent,
                         census=census, work_done=work_done,
                         enumerated_total=len(full_space), truncated=truncated,
                         truncation_causes=causes,
                         errors=census.get("EXECUTION_ERROR", 0),
                         exhausted=census.get("RESOURCE_EXHAUSTED", 0),
                         inspection_errors=inspection_errors,
                         seconds=time.monotonic() - started)


def _demo_nodes(pairs) -> tuple:
    nodes, edges = [], []
    for index, (grid_in, grid_out) in enumerate(pairs):
        din = f"delta{index}"
        same_shape = grid_in.shape == grid_out.shape
        nodes.append(TFGNode(din, "delta_signature", "", {
            "same_shape": bool(same_shape),
            "shrinks": bool(grid_out.size < grid_in.size),
            "grows": bool(grid_out.size > grid_in.size)}))
        edges.append(TFGEdge(din, "blocks", "goal"))
        pin, pout = _palette(grid_in), _palette(grid_out)
        nodes.append(TFGNode(f"palette{index}", "palette_change", "", {
            "introduced": len(pout - pin), "removed": len(pin - pout),
            "n_in": len(pin), "n_out": len(pout)}))
        edges.append(TFGEdge(f"palette{index}", "observed_on", din))
        if same_shape:
            changed = int(np.count_nonzero(grid_in != grid_out))
            nodes.append(TFGNode(f"shape{index}", "shape_change", "", {
                "cells_changed": changed,
                "fraction_changed": round(changed / grid_in.size, 4)}))
            edges.append(TFGEdge(f"shape{index}", "observed_on", din))
    return nodes, edges


def tfg_from_trace(pairs, trace: BaselineTrace, config: BaselineConfig) -> ConcreteTFG:
    """The failure graph of THIS baseline's failure. Receives demonstrations,
    the trace and the configuration only; carries both configuration digests."""
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in pairs]
    nodes = [TFGNode("goal", "goal", "Grid")]
    edges = []
    demo_nodes, demo_edges = _demo_nodes(pairs)
    nodes += demo_nodes
    edges += demo_edges

    def frontier_key(item):
        schema, _program, signature = item
        wrong = signature.get("cells_wrong")
        return (0 if wrong is not None else 1, wrong if wrong is not None else 10 ** 9,
                _canonical(schema))

    seen, taken = set(), 0
    for schema, _program, signature in sorted(trace.constraint_consistent, key=frontier_key):
        if taken >= config.max_frontier_terms:
            break
        key = _canonical(schema)
        if key in seen:
            continue
        seen.add(key)
        node_id = f"frontier{taken}"
        nodes.append(TFGNode(node_id, "frontier_term", "Grid",
                             {"op": "Compose", "outcome": "CONSTRAINT_CONSISTENT_BINDING",
                              "surface_nodes": M.ast_nodes(schema), "ast": key}))
        edges.append(TFGEdge(node_id, "fails", "goal"))
        nodes.append(TFGNode(f"vsig{taken}", "value_signature", "", dict(signature)))
        edges.append(TFGEdge(f"vsig{taken}", "observed_on", node_id))
        taken += 1

    #  slot evidence: fit failures by code and by partition
    by_code: dict = {}
    by_partition: dict = {}
    for record in trace.records:
        if record["status"] == "FIT_FAILURE":
            by_code[record["code"]] = by_code.get(record["code"], 0) + 1
            partition = record["triple"][0]
            by_partition[partition] = by_partition.get(partition, 0) + 1
    for index, (code, count) in enumerate(sorted(by_code.items(), key=lambda kv: str(kv[0]))):
        node_id = f"slotcode{index}"
        nodes.append(TFGNode(node_id, "slot", "", {"code": str(code), "failures": count}))
        edges.append(TFGEdge(node_id, "fails", "goal"))
    for index, (partition, count) in enumerate(sorted(by_partition.items())):
        node_id = f"slotpart{index}"
        nodes.append(TFGNode(node_id, "slot", "", {"op": partition, "failures": count}))
        edges.append(TFGEdge(node_id, "fails", "goal"))

    for index, cause in enumerate(trace.truncation_causes or []):
        nodes.append(TFGNode(f"cause{index}", "cause", "", {"truncation": str(cause)}))
        edges.append(TFGEdge(f"cause{index}", "blocks", "goal"))

    nodes.append(TFGNode("search", "execution", "", {
        "typed": int(trace.work_done), "generated": int(trace.work_done),
        "rejected": int(trace.work_done - len(trace.exact)),
        "max_depth": 1, "semantic_classes": int(len(trace.exact)),
        "outcome_census": {k: trace.census[k] for k in sorted(trace.census)},
        "enumerated_total": int(trace.enumerated_total),
        "search_complete": bool(trace.complete()),
        "deadline_hit": bool(trace.truncated),
        "baseline_config": trace.config_digest,
        "trace_config": trace_config_digest(config)}))
    edges.append(TFGEdge("search", "fails", "goal"))
    return ConcreteTFG("Grid", "Grid", nodes, edges)


def tfg_configuration(tfg: ConcreteTFG) -> dict:
    """Read back the configuration digests a TFG carries (for the mismatch check)."""
    for node in tfg.nodes_of_kind("execution"):
        return {"baseline_config": node.attrs.get("baseline_config"),
                "trace_config": node.attrs.get("trace_config")}
    return {"baseline_config": None, "trace_config": None}
