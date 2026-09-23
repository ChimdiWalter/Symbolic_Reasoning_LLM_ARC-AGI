"""Near-solve memory, failure clustering, and library learning (Section 5).

Fixes the WAY_FORWARD Section-1 finding (memory contributed zero) by putting
this store ON the solve path: the engine writes NearSolveRecords during
solving, clusters feed operator invention, and promoted operators are handed
to inducer.InductionConfig.library on subsequent tasks.

Storage: JSON, append-only — one JSONL file per run plus a cumulative index
directory.  Library operators are typed sub-programs with free slots
(types.LibraryOperator); parameters are ALWAYS re-induced per task and pass
the same LOO gate.  Never lookup tables, never task-ID keyed.

Layering: this module imports ONLY types (plus stdlib).  Fragment holes are
manipulated in their SERIALIZED form ({"expr_class": "FreeSlotExpr", ...}
dicts) so no import of expressions.py is needed; deserialization through
types.Expr.from_dict lazily loads the node registry when a consumer needs
live Expr trees.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .types import LibraryOperator, NearSolveRecord, ObjectProgram

#: Fragment promotion threshold (Section 5.3): same fragment schema in >= 3
#: accepted programs.
PROMOTION_MIN_OCCURRENCES: int = 3

#: A failure cluster needs >= 3 member tasks to be an invention candidate.
CLUSTER_MIN_TASKS: int = 3

#: Retro-solve requirement for cluster-sourced fragments (Section 5.3).
CLUSTER_MIN_RETRO_SOLVES: int = 2

#: Budget cap: at most this many mined schemas per cluster are retro-tested
#: (each retro-solve is a full re-induction — Section 3.5 budget discipline).
MAX_INVENTION_CANDIDATES: int = 5

#: Canonical cumulative artifact locations (Requirements 4.2 / 5.x).
PACKAGE_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR: Path = PACKAGE_ROOT / "outputs" / "object_reasoning"
DEFAULT_NEAR_SOLVES_PATH: Path = DEFAULT_OUTPUT_DIR / "near_solves.jsonl"
DEFAULT_LIBRARY_PATH: Path = DEFAULT_OUTPUT_DIR / "library.json"


# ---------------------------------------------------------------------------
# Near-solve store
# ---------------------------------------------------------------------------

class NearSolveStore:
    """Append-only JSONL store of NearSolveRecords.

    ``path`` is the run-local .jsonl file; records are flushed on every
    append so background-interrupted runs lose nothing.  Reading tolerates
    truncated final lines.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: NearSolveRecord) -> None:
        """Serialize and append one record (implemented — mechanics fixed)."""
        import json
        with self.path.open("a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
            f.flush()

    def load_all(self) -> list[NearSolveRecord]:
        """All records in append order; skips unparseable trailing lines."""
        import json
        records: list[NearSolveRecord] = []
        if not self.path.exists():
            return records
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(NearSolveRecord.from_dict(json.loads(line)))
                except (ValueError, TypeError, KeyError):
                    continue
        return records

    def records_for_cluster(self, cluster: "FailureCluster") -> list[NearSolveRecord]:
        """The member records of a cluster (by task_id + timestamp identity)."""
        keys = set(cluster.member_keys)
        return [r for r in self.load_all() if (r.task_id, r.timestamp) in keys]


# ---------------------------------------------------------------------------
# Failure clustering (Section 5.2)
# ---------------------------------------------------------------------------

@dataclass
class FailureCluster:
    """A group of NearSolveRecords sharing a failure signature.

    ``signature`` = (failure_stage, sorted delta-histogram support, sorted
    residual delta types) — the Section-5.2 key.  ``cluster_id`` is a stable
    hash of the signature (NOT of task ids)."""
    cluster_id: str
    signature: tuple
    member_keys: list[tuple[str, str]] = field(default_factory=list)  # (task_id, timestamp)

    @property
    def n_tasks(self) -> int:
        return len({k[0] for k in self.member_keys})

    @property
    def is_invention_candidate(self) -> bool:
        return self.n_tasks >= CLUSTER_MIN_TASKS


def _failure_signature(record: NearSolveRecord) -> tuple:
    """(failure_stage, delta-histogram SUPPORT, residual delta types).

    Support = which delta types occurred (counts vary per task and would
    shatter clusters), residual types from residual.unexplained_deltas.
    Deterministic in record content only — no task ids."""
    histogram_support = tuple(sorted(
        k for k, v in (record.delta_histogram or {}).items() if v))
    residual = record.residual or {}
    residual_types = tuple(sorted({
        str(d.get("delta_type"))
        for d in residual.get("unexplained_deltas", [])
        if isinstance(d, dict) and d.get("delta_type") is not None}))
    return (str(record.failure_stage), histogram_support, residual_types)


def _cluster_id_of(signature: tuple) -> str:
    digest = hashlib.md5(
        json.dumps(signature, sort_keys=True).encode()).hexdigest()
    return f"fc_{digest[:10]}"


def cluster_failures(records: list[NearSolveRecord]) -> list[FailureCluster]:
    """Group records by (failure_stage, delta_histogram signature, residual
    delta types); returns clusters sorted by n_tasks desc.  Deterministic in
    record content only."""
    by_signature: dict[tuple, FailureCluster] = {}
    for record in records:
        sig = _failure_signature(record)
        cluster = by_signature.get(sig)
        if cluster is None:
            cluster = FailureCluster(cluster_id=_cluster_id_of(sig),
                                     signature=sig)
            by_signature[sig] = cluster
        key = (record.task_id, record.timestamp)
        if key not in cluster.member_keys:
            cluster.member_keys.append(key)
    return sorted(by_signature.values(),
                  key=lambda c: (-c.n_tasks, c.cluster_id))


# ---------------------------------------------------------------------------
# Fragment mining & promotion (Section 5.3)
# ---------------------------------------------------------------------------
#
# Fragments are mined on the SERIALIZED rule form (ObjectRule.to_dict()):
# induced constants are replaced by serialized FreeSlotExpr holes
# ({"expr_class": "FreeSlotExpr", "op": "free_slot", "args": [name, type]}),
# named slot_0, slot_1, ... in a deterministic traversal order (selector
# predicate first, then action params in sorted-name order, depth-first
# left-to-right).  Two rules share a schema iff the abstracted dicts are
# equal — the mining key.

#: Whole const nodes of these Expr classes become free slots of the given
#: ExprType.value (the "free color/axis/scalar slots" of Section 5.3).
_EXPR_CONST_SLOT_TYPES: dict[str, str] = {
    "ColorExpr": "color",
    "VecExpr": "vector",
    "ScalarExpr": "scalar",
}

#: Whole-node abstractions: the induced payload IS the node (color_map's
#: dict); the schema keeps only "an induced color-valued expression here".
_NODE_SLOT_TYPES: dict[tuple[str, str], str] = {
    ("ColorExpr", "color_map"): "color",
}

#: Literal (non-Expr) argument positions that are induced constants, keyed by
#: (expr_class, op) -> {arg_index: slot ExprType.value}.  Mirrors the frozen
#: expressions.py GRAMMAR tables (design decision 6: vocabulary is frozen).
_LITERAL_SLOT_SPECS: dict[tuple[str, str], dict[int, str]] = {
    ("RefExpr", "nearest_object_of_color"): {0: "color"},
    ("VecExpr", "vector_to_border"): {0: "direction"},
    ("VecExpr", "gap_closing_vector"): {1: "axis"},
    ("VecExpr", "scaled_unit"): {0: "direction"},
    ("RegionExpr", "grid_quadrant"): {0: "scalar"},
    ("RegionExpr", "separator_cell"): {0: "scalar", 1: "scalar"},
}

#: COLOR-kind features of the frozen PLANNED_FEATURES vocabulary — a test
#: value against these is a color slot (kept in sync by test_memory.py).
_COLOR_VALUED_FEATURES: frozenset[str] = frozenset({"color", "nearest_object_color"})


class _SlotAllocator:
    """Deterministic slot_0, slot_1, ... naming during one rule abstraction."""

    def __init__(self) -> None:
        self.slots: list[tuple[str, str]] = []

    def new(self, slot_type: str) -> dict:
        name = f"slot_{len(self.slots)}"
        self.slots.append((name, slot_type))
        return {"expr_class": "FreeSlotExpr", "op": "free_slot",
                "args": [name, slot_type]}


def _is_expr_dict(x: Any) -> bool:
    return isinstance(x, dict) and "expr_class" in x


def _test_value_slot_type(feature: Any, value: Any) -> str:
    """Slot type for an abstracted PredExpr test value."""
    if isinstance(feature, str) and feature in _COLOR_VALUED_FEATURES:
        return "color"
    if isinstance(value, (list, tuple)) or (isinstance(value, dict)
                                            and "__tuple__" in value):
        return "vector"
    return "scalar"


def _abstract_expr(d: dict, alloc: _SlotAllocator) -> dict:
    """Serialized Expr dict -> schema dict with induced constants slotted."""
    cls = d.get("expr_class")
    op = d.get("op")
    if cls == "FreeSlotExpr":
        # already a hole (program was built from a library fragment):
        # renumber for schema stability, keep the declared type.
        args = d.get("args", [None, "scalar"])
        return alloc.new(str(args[1]) if len(args) > 1 else "scalar")
    if (cls, op) in _NODE_SLOT_TYPES:
        return alloc.new(_NODE_SLOT_TYPES[(cls, op)])
    if op == "const" and cls in _EXPR_CONST_SLOT_TYPES:
        return alloc.new(_EXPR_CONST_SLOT_TYPES[cls])
    args = list(d.get("args", []))
    if cls == "PredExpr" and op == "test" and len(args) == 3:
        feature, cmp, value = args
        if _is_expr_dict(value):
            new_value: Any = _abstract_expr(value, alloc)
        elif isinstance(value, bool) or (isinstance(value, str)
                                         and value.startswith("@")):
            # boolean polarity and rank sentinels (@rank_min/@rank_max) are
            # structural, not induced constants — kept concrete.
            new_value = value
        else:
            new_value = alloc.new(_test_value_slot_type(feature, value))
        return {"expr_class": cls, "op": op, "args": [feature, cmp, new_value]}
    literal_spec = _LITERAL_SLOT_SPECS.get((cls, op), {})
    new_args: list[Any] = []
    for i, a in enumerate(args):
        if _is_expr_dict(a):
            new_args.append(_abstract_expr(a, alloc))
        elif i in literal_spec:
            new_args.append(alloc.new(literal_spec[i]))
        elif isinstance(a, dict) and "__tuple__" in a:
            new_args.append({"__tuple__": [
                _abstract_expr(x, alloc) if _is_expr_dict(x) else x
                for x in a["__tuple__"]]})
        else:
            new_args.append(a)
    return {"expr_class": cls, "op": op, "args": new_args}


def _abstract_rule_dict(rule_dict: dict) -> tuple[dict, list[tuple[str, str]]]:
    """Serialized ObjectRule dict -> (fragment schema dict, ordered slots).

    Traversal order (fixes slot numbering across programs): selector
    predicate first, then action params in sorted-name order."""
    alloc = _SlotAllocator()
    selector = rule_dict["selector"]
    action = rule_dict["action"]
    new_predicate = _abstract_expr(selector["predicate"], alloc)
    new_params = {name: _abstract_expr(action["params"][name], alloc)
                  for name in sorted(action.get("params", {}))}
    fragment = {
        "selector": {"predicate": new_predicate,
                     "literals": selector.get("literals", 0)},
        "action": {"delta_type": action["delta_type"],
                   "params": new_params,
                   "parameter_class": action.get("parameter_class", "constant")},
    }
    return fragment, alloc.slots


def _abstract_action_schema(rule_dict: dict) -> Optional[tuple[dict, list[tuple[str, str]]]]:
    """Serialized ObjectRule dict -> ACTION-SCHEMA fragment: the whole
    selector predicate becomes one free ``predicate`` slot (slot_0); the
    action is abstracted exactly as in _abstract_rule_dict.

    Second, coarser mining granularity (2026-07-05, after the 1000-scale
    promotion pass registered nothing): 42 accepted programs yielded 35
    full (selector, action) schemas with zero >=3 recurrence, but clear
    action families (10x crop_to/bbox_self, 9x recolor/induced_map, ...)
    separated ONLY by their per-task selector.  The selector slot is
    re-induced per task through the normal zero-conflict path at
    instantiation (inducer._try_library_operator) — the generalization of
    Section 5.3's "parameters are always re-induced per task" to the
    selector position.  Identity actions (parameterless keep) are never
    mined."""
    action = rule_dict["action"]
    if str(action.get("delta_type")) == "keep" and not action.get("params"):
        return None
    alloc = _SlotAllocator()
    hole = alloc.new("predicate")
    new_params = {name: _abstract_expr(action["params"][name], alloc)
                  for name in sorted(action.get("params", {}))}
    fragment = {
        "selector": {"predicate": hole, "literals": 0},
        "action": {"delta_type": action["delta_type"],
                   "params": new_params,
                   "parameter_class": action.get("parameter_class", "constant")},
    }
    return fragment, alloc.slots


def _fragments_with_slots(program: ObjectProgram) -> list[tuple[dict, list[tuple[str, str]]]]:
    """(fragment, slots) pairs per ObjectRule of the program: the full
    (selector, action) schema plus the coarser action schema (selector as a
    free predicate slot) when the action is non-trivial."""
    out: list[tuple[dict, list[tuple[str, str]]]] = []
    for rule in program.rules:
        rule_dict = rule.to_dict()
        out.append(_abstract_rule_dict(rule_dict))
        action_schema = _abstract_action_schema(rule_dict)
        if action_schema is not None:
            out.append(action_schema)
    return out


def _is_trivial_fragment(fragment: dict) -> bool:
    """(true-selector, parameterless keep) — the identity rule; never mined."""
    return (fragment["action"]["delta_type"] == "keep"
            and not fragment["action"]["params"]
            and fragment["selector"]["predicate"].get("op") == "true")


def _fragment_key(fragment: dict) -> str:
    """Canonical mining key: equal schemas <=> equal keys."""
    return json.dumps(fragment, sort_keys=True)


def _predicate_descriptor(d: dict) -> str:
    """Human-readable selector hint for auto-generated operator names."""
    op = d.get("op")
    if op == "true":
        return "all"
    if op == "test":
        return str(d["args"][0])
    if op == "and2":
        parts = [_predicate_descriptor(a) for a in d.get("args", [])
                 if _is_expr_dict(a)]
        return "_and_".join(parts) if parts else "and2"
    if op == "relation_exists":
        return str(d["args"][0])
    if op == "free_slot":
        return "slot"
    return str(op)


def _operator_name(fragment: dict) -> str:
    """Deterministic name, e.g. op_recolor_by_hole_count_3fa2c1: descriptive
    prefix (spec 5.3 style) + 6-hex schema hash for uniqueness/stability."""
    delta = str(fragment["action"]["delta_type"])
    descriptor = _predicate_descriptor(fragment["selector"]["predicate"])
    digest = hashlib.md5(_fragment_key(fragment).encode()).hexdigest()[:6]
    if descriptor == "all":
        return f"op_{delta}_all_{digest}"
    return f"op_{delta}_by_{descriptor}_{digest}"


def _operator_from_fragment(fragment: dict, slots: list[tuple[str, str]],
                            provenance: list[str]) -> LibraryOperator:
    return LibraryOperator(
        name=_operator_name(fragment),
        fragment=fragment,
        free_slots=[tuple(s) for s in slots],
        provenance=sorted(provenance),
        created_at=datetime.now(timezone.utc).isoformat(),
        loo_record={},
        falsification_record={},
    )


def fragment_schema_of(program: ObjectProgram) -> list[dict]:
    """Extract the (selector-expr schema, action, param-expr schema) fragments
    of a program: each ObjectRule serialized with its induced color/axis/
    scalar constants replaced by expressions.FreeSlotExpr holes.  Two rules
    from different programs share a schema iff these dicts are equal —
    the mining key for promotion."""
    return [fragment for fragment, _ in _fragments_with_slots(program)]


def promote_fragments(accepted_programs: dict[str, ObjectProgram],
                      min_occurrences: int = PROMOTION_MIN_OCCURRENCES,
                      ) -> list[LibraryOperator]:
    """Mine fragment schemas over accepted programs (keyed by task_id for
    provenance ONLY — never for applicability) and promote every schema
    appearing in >= min_occurrences distinct accepted programs to a
    LibraryOperator with auto-generated name (e.g.
    op_move_until_adjacent_by_color), free_slots listed, and provenance =
    contributing task_ids.  Does NOT register them — callers must first pass
    validate_operator (Section 5.4)."""
    mined: dict[str, dict] = {}
    for task_id in sorted(accepted_programs):
        program = accepted_programs[task_id]
        for fragment, slots in _fragments_with_slots(program):
            if _is_trivial_fragment(fragment):
                continue
            key = _fragment_key(fragment)
            entry = mined.setdefault(
                key, {"fragment": fragment, "slots": slots, "tasks": set()})
            entry["tasks"].add(task_id)
    operators = [
        _operator_from_fragment(entry["fragment"], entry["slots"],
                                sorted(entry["tasks"]))
        for entry in mined.values()
        if len(entry["tasks"]) >= min_occurrences
    ]
    return sorted(operators, key=lambda op: (-len(op.provenance), op.name))


def _rule_dict_from_explained(explained_rule: dict) -> Optional[dict]:
    """NearSolveRecord.explained_rules entry -> serialized ObjectRule dict
    (best effort; None when malformed)."""
    def count_literals(pred: Any) -> int:
        if not _is_expr_dict(pred):
            return 0
        op = pred.get("op")
        if op == "true":
            return 0
        if op in ("test", "relation_exists"):
            return 1
        return sum(count_literals(a) for a in pred.get("args", []))

    try:
        predicate = explained_rule["selector_expr"]
        delta_type = explained_rule["action"]
        params = dict(explained_rule.get("param_exprs") or {})
        if not _is_expr_dict(predicate):
            return None
        return {"selector": {"predicate": predicate,
                             "literals": count_literals(predicate)},
                "action": {"delta_type": str(delta_type), "params": params,
                           "parameter_class":
                               explained_rule.get("parameter_class", "constant")}}
    except (KeyError, TypeError):
        return None


def invent_from_cluster(cluster: FailureCluster, store: NearSolveStore,
                        retro_solve_fn: Optional[
                            Callable[[str, LibraryOperator], bool]] = None,
                        ) -> Optional[LibraryOperator]:
    """Mine the recurring (selector schema, action, param schema) fragment
    from a cluster's partial programs; candidate is returned only if it
    retro-solves >= CLUSTER_MIN_RETRO_SOLVES member tasks THROUGH THE NORMAL
    INDUCTION PATH (re-run inducer.induce_program with the candidate in
    config.library — no task-targeted shortcuts).  None otherwise.

    ``retro_solve_fn(task_id, candidate) -> bool`` is supplied by the ENGINE
    layer (which owns task data): it must re-run normal induction with the
    candidate operator added to config.library and report whether the task is
    now solved (accepted + LOO-perfect).  Without it the retro-solve gate
    cannot be evaluated, so None is returned (never an unvalidated operator).
    """
    if retro_solve_fn is None:
        return None
    records = store.records_for_cluster(cluster)
    if not records:
        return None

    mined: dict[str, dict] = {}
    for record in records:
        fragment_slot_pairs: list[tuple[dict, list[tuple[str, str]]]] = []
        if record.program_partial:
            # Stage-2 composed partials (2.2.4) nest per-part program
            # dicts; flatten and mine each part like any flat partial.
            stack = [record.program_partial]
            while stack:
                part = stack.pop()
                if not isinstance(part, dict):
                    continue
                if part.get("program_class") == "composed_partial":
                    stack.extend(p for p in (part.get("stage1"),
                                             part.get("rest")) if p)
                    continue
                try:
                    from .types import program_from_dict
                    fragment_slot_pairs.extend(
                        _fragments_with_slots(program_from_dict(part)))
                except Exception:
                    pass
        if not fragment_slot_pairs and record.explained_rules:
            for explained in record.explained_rules:
                rule_dict = _rule_dict_from_explained(explained)
                if rule_dict is not None:
                    fragment_slot_pairs.append(_abstract_rule_dict(rule_dict))
        for fragment, slots in fragment_slot_pairs:
            if _is_trivial_fragment(fragment):
                continue
            key = _fragment_key(fragment)
            entry = mined.setdefault(
                key, {"fragment": fragment, "slots": slots, "tasks": set()})
            entry["tasks"].add(record.task_id)
    if not mined:
        return None

    member_tasks = sorted({k[0] for k in cluster.member_keys})
    candidates = sorted(
        mined.values(),
        key=lambda e: (-len(e["tasks"]), _fragment_key(e["fragment"])))
    for entry in candidates[:MAX_INVENTION_CANDIDATES]:
        candidate = _operator_from_fragment(
            entry["fragment"], entry["slots"], sorted(entry["tasks"]))
        retro_solved: list[str] = []
        for task_id in member_tasks:
            try:
                if retro_solve_fn(task_id, candidate):
                    retro_solved.append(task_id)
            except Exception:
                continue
        if len(retro_solved) >= CLUSTER_MIN_RETRO_SOLVES:
            candidate.provenance = sorted(set(candidate.provenance)
                                          | set(retro_solved))
            candidate.loo_record = {
                "cluster_id": cluster.cluster_id,
                "retro_attempted": member_tasks,
                "retro_solved": retro_solved,
            }
            return candidate
    return None


def _concrete_color_constants(fragment: dict) -> list[str]:
    """Concrete color constants remaining in a fragment's expressions (used
    by the color-relabeling-invariance check).  Mined fragments have none by
    construction; hand-assembled operators may."""
    violations: list[str] = []

    def walk(d: Any, path: str) -> None:
        if isinstance(d, dict) and "__tuple__" in d:
            for i, x in enumerate(d["__tuple__"]):
                walk(x, f"{path}[{i}]")
            return
        if not _is_expr_dict(d):
            return
        cls, op = d.get("expr_class"), d.get("op")
        args = d.get("args", [])
        if cls == "ColorExpr" and op == "const":
            violations.append(f"{path}: ColorExpr const {args}")
        if (cls == "RefExpr" and op == "nearest_object_of_color"
                and args and not _is_expr_dict(args[0])):
            violations.append(f"{path}: nearest_object_of_color({args[0]})")
        if (cls == "PredExpr" and op == "test" and len(args) == 3
                and isinstance(args[0], str)
                and args[0] in _COLOR_VALUED_FEATURES
                and not isinstance(args[2], bool)
                and isinstance(args[2], int)):
            violations.append(f"{path}: test({args[0]}, {args[1]}, {args[2]})")
        for i, a in enumerate(args):
            walk(a, f"{path}.args[{i}]")

    walk(fragment.get("selector", {}).get("predicate", {}), "selector.predicate")
    for name, expr in (fragment.get("action", {}).get("params") or {}).items():
        walk(expr, f"action.params.{name}")
    return violations


def validate_operator(op: LibraryOperator,
                      reinduce_provenance_fn,
                      solved_probe_fns: list,
                      ) -> tuple[bool, dict]:
    """Counterexample survival (Section 5.4) before registration:
      (a) re-validation on all provenance tasks via full re-induction
          (``reinduce_provenance_fn(task_id) -> InductionResult`` supplied by
          the engine layer, which owns task data access);
      (b) applicability probes on 10 random already-solved tasks with ZERO
          regressions (a previously accepted program displaced by one that
          fails LOO = regression); each ``solved_probe_fns`` entry is a
          zero-argument callable returning True iff its already-solved task
          REMAINS solved when re-induced with ``op`` in the library;
      (c) color-relabeling invariance where the fragment claims color
          genericity (any free slot of type "color"): the fragment must carry
          no residual concrete color constants — abstracted fragments satisfy
          this by construction; hand-assembled ones are caught here.
    Returns (passed, falsification_record).  Failures block LIBRARY
    REGISTRATION ONLY — never an individual task solution that passed
    train+LOO (2026-06-15 lesson)."""
    provenance_results: dict[str, bool] = {}
    for task_id in op.provenance:
        try:
            result = reinduce_provenance_fn(task_id)
            provenance_results[task_id] = bool(
                result is not None and getattr(result, "accepted", False))
        except Exception:
            provenance_results[task_id] = False
    a_passed = bool(provenance_results) and all(provenance_results.values())

    probe_results: list[bool] = []
    for probe_fn in solved_probe_fns:
        try:
            probe_results.append(bool(probe_fn()))
        except Exception:
            probe_results.append(False)
    b_passed = all(probe_results)  # vacuously True with no solved tasks yet

    claims_color = any(slot_type == "color" for _, slot_type in op.free_slots)
    color_violations = _concrete_color_constants(op.fragment) if claims_color else []
    c_passed = not color_violations

    passed = a_passed and b_passed and c_passed
    falsification_record = {
        "operator": op.name,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provenance_revalidation": provenance_results,
        "provenance_passed": a_passed,
        "probes": {"total": len(probe_results),
                   "passed": sum(probe_results),
                   "regressions": len(probe_results) - sum(probe_results)},
        "probes_passed": b_passed,
        "color_invariance": {"claims_color_genericity": claims_color,
                             "violations": color_violations,
                             "passed": c_passed},
        "passed": passed,
    }
    return passed, falsification_record


# ---------------------------------------------------------------------------
# The library itself
# ---------------------------------------------------------------------------

class FragmentLibrary:
    """Persistent registry of validated LibraryOperators (JSON file).

    Operators are tried EARLY (before raw enumeration) by the inducer, but
    their parameters are always re-induced per task and pass the same LOO
    gate.  ``enabled=False`` is the Requirement 1.2 --no-library ablation.
    """

    def __init__(self, path: Path | str, enabled: bool = True):
        self.path = Path(path)
        self.enabled = enabled
        self._operators: dict[str, LibraryOperator] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        import json
        data = json.loads(self.path.read_text() or "{}")
        self._operators = {name: LibraryOperator.from_dict(d)
                           for name, d in data.items()}

    def save(self) -> None:
        import json
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {n: op.to_dict() for n, op in self._operators.items()}, indent=2))

    def register(self, op: LibraryOperator) -> None:
        """Add a VALIDATED operator (caller must have run validate_operator);
        duplicate names raise ValueError."""
        if op.name in self._operators:
            raise ValueError(f"operator already registered: {op.name}")
        self._operators[op.name] = op
        self.save()

    def operators(self) -> list[LibraryOperator]:
        """Registered operators for inducer.InductionConfig.library
        (empty when disabled — the ablation path)."""
        if not self.enabled:
            return []
        return list(self._operators.values())

    def __len__(self) -> int:
        return len(self._operators)


# ---------------------------------------------------------------------------
# Engine-facing hooks (library loading + try-library-first wiring)
# ---------------------------------------------------------------------------

def load_library(path: Path | str | None = None,
                 enabled: bool = True) -> FragmentLibrary:
    """Open the cumulative fragment library (DEFAULT_LIBRARY_PATH when
    ``path`` is None).  ``enabled=False`` is the --no-library ablation: the
    file is still readable but operators() yields nothing."""
    return FragmentLibrary(DEFAULT_LIBRARY_PATH if path is None else path,
                           enabled=enabled)


def try_library_first(library: FragmentLibrary, config):
    """Return a copy of an inducer.InductionConfig with the library's
    operators injected so promoted fragments are tried BEFORE raw enumeration
    (Section 5.3); free slots are still re-induced per task and the LOO gate
    is unchanged.  With a disabled library (--no-library) the copy has
    use_library=False and an empty operator list.

    ``config`` is duck-typed (any dataclass with ``library`` and
    ``use_library`` fields) to preserve the layering: memory never imports
    inducer.  The input config is not mutated."""
    operators = list(library.operators())
    return dataclasses.replace(config, library=operators,
                               use_library=bool(library.enabled))
