"""Item-2 v1.7: the generic ConstructiveExtensionCompiler.

Turns a legal semantic extension from the constructive grammar (a meta-AST
block schema with free induced slots) into a canonical executable production
that can be installed, temporarily, into the same reasoner: the real ARC
engine's CORA expression phase, under the K* configuration of
records/ITEM2_V17_COMPILER_DESIGN.md.

Nothing here knows a task, a label, a target, an expected output or a named
ARC family. The input schema is closed (unknown keys are rejected), the
production is named by its content, elaboration is ordinary substitution
into kernel meta-AST semantics (`meta_ast.instantiate` / `meta_ast.evaluate`),
and installation is a context-scoped overlay that is verified to leave no
residue. Acceptance stays with the engine's unchanged re-induction gate.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile

from cora_arc2026 import v14_loc as L
from cora_arc2026 import v15_sel as _S          # puts the frozen tti root on the path

COMPILER_VERSION = "1.7.0"
FORMAT_INPUT = "cora-extension-input/1"
FORMAT_PRODUCTION = "cora-compiled-production/1"
LIMITS = {"max_blocks": 4, "max_selects_per_block": 3, "max_nodes": 64,
          "max_serialized_bytes": 65536}
INPUT_KEYS = frozenset({"format", "schema", "declared_types", "provenance",
                        "source_sha256", "compiler_version", "k_identity"})
PROVENANCE_KEYS = frozenset({"producer_sha256", "evidence_sha256"})
DECLARED_TYPES = {"input": "Grid", "output": "Grid"}
INDUCED_TYPE = "Map[FeatureValue,Colour]"
SLOT_NAME = re.compile(r"^\?[A-Za-z0-9_]{1,32}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

#: the K* configuration, fixed text hashed into the K identity
KSTAR_RULES = (
    "K*-1 expression slice: induce_computed_candidates is called with deadline=None, "
    "so the CORA expression phase receives its declared ARC_META_BUDGET_S slice per call",
    "K*-2 fitting law: the Map[FeatureValue,Colour] learner delegates one-block one-Select "
    "ASTs to the engine's own learner and every other shape to the frozen occurrence-scoped fitter",
    "K*-3 overlay: installed productions are appended to the expression phase's concept list",
)
KSTAR_ENV = {"ARC_META_INDUCTION": "1", "ARC_META_BUDGET_S": "8"}

FAILURE_CLASSES = (
    "MALFORMED_INPUT", "VERSION_MISMATCH", "K_IDENTITY_MISMATCH", "SOURCE_HASH_MISMATCH",
    "DECLARED_TYPE_MISMATCH", "UNPARSABLE_SCHEMA", "UNTYPEABLE", "UNKNOWN_TERMINAL",
    "LITERAL_INDUCED_SLOT", "DUPLICATE_SLOT", "LIMIT_EXCEEDED", "TAMPERED_PRODUCTION",
    "OVERLAY_CONFLICT", "RESTORATION_FAILURE", "KSTAR_NOT_ACTIVE",
)


class CompileError(Exception):
    """A rejected input or production; `code` is one of FAILURE_CLASSES."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


# --------------------------------------------------------------------------
# frozen dependencies
# --------------------------------------------------------------------------

def _meta():
    from geocat_arc.object_reasoning import meta_ast as M
    from geocat_arc.object_reasoning import meta_induction as MI
    return M, MI


def _sf():
    from cora_tti import scoped_slot_fitting as SF
    return SF


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compiler_sha256() -> str:
    with open(__file__, "rb") as handle:
        return _sha(handle.read())


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode()


_K_IDENTITY = None


def k_identity() -> str:
    """Identity of the frozen reasoner K*: the engine source tree, the
    occurrence-scoped fitter, the K* rules and the K* environment."""
    global _K_IDENTITY
    if _K_IDENTITY is None:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _K_IDENTITY = _sha(canonical_json({
            "geocat_arc_tree": L.tree_digest(os.path.join(here, "geocat_arc")),
            "fitter": _sf().fitter_identity(),
            "kstar_rules": list(KSTAR_RULES), "kstar_env": KSTAR_ENV}))
    return _K_IDENTITY


# --------------------------------------------------------------------------
# the typing law
# --------------------------------------------------------------------------

def _is_slot(value) -> bool:
    return isinstance(value, str) and value.startswith("?")


def parse_blocks(ast):
    """[(partition, (predicates...), feature, slot)] or CompileError.

    The grammar: Compose over one or more blocks; a block is Partition(p),
    zero or more Select(q), Map(Key(f), Lookup(s)), Paint(). p, q and f are
    vocabulary terminals or free slots; s must be a free slot."""
    M, _ = _meta()
    if not (isinstance(ast, tuple) and len(ast) == 2 and ast[0] == "Compose"):
        raise CompileError("UNTYPEABLE", "root is not Compose")
    stages = list(ast[1])
    if not stages:
        raise CompileError("UNTYPEABLE", "no blocks")
    blocks, i = [], 0
    while i < len(stages):
        st = stages[i]
        if not (isinstance(st, tuple) and len(st) == 2 and st[0] == "Partition" and len(st[1]) == 1):
            raise CompileError("UNTYPEABLE", f"stage {i} is not Partition(p)")
        partition = st[1][0]
        i += 1
        preds = []
        while i < len(stages) and isinstance(stages[i], tuple) and stages[i][0] == "Select":
            if len(stages[i]) != 2 or len(stages[i][1]) != 1:
                raise CompileError("UNTYPEABLE", f"stage {i} malformed Select")
            preds.append(stages[i][1][0])
            i += 1
        if i >= len(stages) or not (isinstance(stages[i], tuple) and stages[i][0] == "Map"
                                    and len(stages[i]) == 2 and len(stages[i][1]) == 2):
            raise CompileError("UNTYPEABLE", f"block at stage {i} lacks Map(Key, Lookup)")
        key, lookup = stages[i][1]
        if not (isinstance(key, tuple) and key[0] == "Key" and len(key[1]) == 1
                and isinstance(lookup, tuple) and lookup[0] == "Lookup" and len(lookup[1]) == 1):
            raise CompileError("UNTYPEABLE", f"stage {i} Map is not Map(Key(f), Lookup(s))")
        feature, slot = key[1][0], lookup[1][0]
        i += 1
        if i >= len(stages) or not (isinstance(stages[i], tuple) and stages[i][0] == "Paint"
                                    and len(stages[i]) == 2 and len(stages[i][1]) == 0):
            raise CompileError("UNTYPEABLE", f"block lacks Paint() at stage {i}")
        i += 1
        if not _is_slot(slot):
            raise CompileError("LITERAL_INDUCED_SLOT", "a Lookup is bound to a literal table")
        for value, vocab, kind in ((partition, M.PARTITIONS, "partition"),
                                   (feature, M.KEY_FEATURES, "feature")):
            if not _is_slot(value) and value not in vocab:
                raise CompileError("UNKNOWN_TERMINAL", f"{kind} {value!r}")
        for q in preds:
            if not _is_slot(q) and q not in M.PREDICATES:
                raise CompileError("UNKNOWN_TERMINAL", f"predicate {q!r}")
        if len(preds) > LIMITS["max_selects_per_block"]:
            raise CompileError("LIMIT_EXCEEDED", "too many Select stages in a block")
        blocks.append((partition, tuple(preds), feature, slot))
    if len(blocks) > LIMITS["max_blocks"]:
        raise CompileError("LIMIT_EXCEEDED", "too many blocks")
    return blocks


OPS = ("Compose", "Partition", "Select", "Key", "Lookup", "Map", "Paint")


def _is_node(value) -> bool:
    return isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str) \
        and value[0] in OPS and isinstance(value[1], tuple)


def _slots_in_order(ast) -> list:
    """Free slots, depth first, left to right, through meta-AST nodes only."""
    out = []

    def walk(node):
        if _is_slot(node):
            out.append(node)
        elif _is_node(node):
            for arg in node[1]:
                walk(arg)
    walk(ast)
    return out


def _nodes(ast) -> int:
    if not _is_node(ast):
        return 0
    return 1 + sum(_nodes(a) for a in ast[1])


def type_check(ast) -> dict:
    """Slot -> type, from the frozen typed signatures, after the grammar
    check; every slot name occurs exactly once."""
    M, _ = _meta()
    parse_blocks(ast)
    slots = _slots_in_order(ast)
    for s in slots:
        if not SLOT_NAME.match(s):
            raise CompileError("UNTYPEABLE", f"bad slot name {s!r}")
    if len(slots) != len(set(slots)):
        raise CompileError("DUPLICATE_SLOT", "a slot name occurs twice")
    if _nodes(ast) > LIMITS["max_nodes"]:
        raise CompileError("LIMIT_EXCEEDED", "too many nodes")
    types = M.free_slot_types(ast)
    if set(types) != set(slots):
        raise CompileError("UNTYPEABLE", "a slot sits in an untyped position")
    allowed = set(M.ENUMERABLE_TYPES) | {INDUCED_TYPE}
    for s, t in types.items():
        if t not in allowed:
            raise CompileError("UNTYPEABLE", f"slot {s} has unsupported type {t}")
    if M.OP_SIGNATURES["Compose"][1] != DECLARED_TYPES["output"]:
        raise CompileError("UNTYPEABLE", "result type is not Grid")
    return types


def canonicalize(ast):
    """Slots renamed ?s0, ?s1, ... in first-encounter order."""
    M, _ = _meta()
    order = _slots_in_order(ast)
    mapping = {s: f"?s{i}" for i, s in enumerate(order)}
    return M.instantiate(ast, mapping), mapping


# --------------------------------------------------------------------------
# input and output contracts
# --------------------------------------------------------------------------

def schema_source_sha256(schema_json) -> str:
    return _sha(canonical_json(schema_json))


def make_input(schema_ast, producer_sha256="0" * 64, evidence_sha256="0" * 64) -> dict:
    """A well-formed compiler input for a schema (used by producers and tests)."""
    M, _ = _meta()
    sj = M.ast_to_json(schema_ast)
    return {"format": FORMAT_INPUT, "schema": sj, "declared_types": dict(DECLARED_TYPES),
            "provenance": {"producer_sha256": producer_sha256, "evidence_sha256": evidence_sha256},
            "source_sha256": schema_source_sha256(sj), "compiler_version": COMPILER_VERSION,
            "k_identity": k_identity()}


def validate_input(inp) -> None:
    if not isinstance(inp, dict) or set(inp) != INPUT_KEYS:
        raise CompileError("MALFORMED_INPUT", f"keys must be exactly {sorted(INPUT_KEYS)}")
    if inp["format"] != FORMAT_INPUT:
        raise CompileError("MALFORMED_INPUT", "format")
    if inp["compiler_version"] != COMPILER_VERSION:
        raise CompileError("VERSION_MISMATCH", str(inp["compiler_version"]))
    if inp["k_identity"] != k_identity():
        raise CompileError("K_IDENTITY_MISMATCH", "input is bound to a different K*")
    if inp["declared_types"] != DECLARED_TYPES:
        raise CompileError("DECLARED_TYPE_MISMATCH", str(inp["declared_types"]))
    prov = inp["provenance"]
    if not isinstance(prov, dict) or set(prov) != PROVENANCE_KEYS or \
            not all(isinstance(v, str) and HEX64.match(v) for v in prov.values()):
        raise CompileError("MALFORMED_INPUT", "provenance must be exactly two 64-hex digests")
    if not isinstance(inp["source_sha256"], str) or not HEX64.match(inp["source_sha256"]):
        raise CompileError("MALFORMED_INPUT", "source_sha256")
    if schema_source_sha256(inp["schema"]) != inp["source_sha256"]:
        raise CompileError("SOURCE_HASH_MISMATCH", "schema does not match its declared hash")


def compile_extension(inp) -> dict:
    """Input dict -> canonical production dict, or CompileError."""
    M, _ = _meta()
    validate_input(inp)
    try:
        ast = M.ast_from_json(inp["schema"])
    except Exception as exc:                                   # noqa: BLE001
        raise CompileError("UNPARSABLE_SCHEMA", type(exc).__name__)
    types = type_check(ast)
    canon, mapping = canonicalize(ast)
    ctypes = {mapping[s]: t for s, t in types.items()}
    order = [f"?s{i}" for i in range(len(mapping))]
    body = M.ast_to_json(canon)
    body_bytes = canonical_json(body)
    signature = {"input": DECLARED_TYPES["input"], "result": DECLARED_TYPES["output"],
                 "args": [[s, ctypes[s]] for s in order]}
    name = "cx_" + _sha(b"cora-cx|" + body_bytes + b"|" + canonical_json(signature))[:24]
    prod = {"format": FORMAT_PRODUCTION, "name": name, "signature": signature, "body": body,
            "induced_slots": [s for s in order if ctypes[s] == INDUCED_TYPE],
            "enumerable_slots": [s for s in order if ctypes[s] != INDUCED_TYPE],
            "blocks": len(parse_blocks(canon)), "source_sha256": _sha(body_bytes),
            "compiler_version": COMPILER_VERSION, "compiler_sha256": compiler_sha256(),
            "k_identity": inp["k_identity"]}
    if len(serialize(prod)) > LIMITS["max_serialized_bytes"]:
        raise CompileError("LIMIT_EXCEEDED", "serialized production too large")
    return prod


def serialize(prod) -> bytes:
    return canonical_json(prod)


def load(data: bytes) -> dict:
    """Reload a serialized production, recomputing every content-derived
    field; any disagreement is TAMPERED_PRODUCTION."""
    M, _ = _meta()
    try:
        prod = json.loads(data)
    except Exception as exc:                                   # noqa: BLE001
        raise CompileError("TAMPERED_PRODUCTION", type(exc).__name__)
    keys = {"format", "name", "signature", "body", "induced_slots", "enumerable_slots",
            "blocks", "source_sha256", "compiler_version", "compiler_sha256", "k_identity"}
    if not isinstance(prod, dict) or set(prod) != keys or prod["format"] != FORMAT_PRODUCTION:
        raise CompileError("TAMPERED_PRODUCTION", "fields")
    ast = M.ast_from_json(prod["body"])
    types = type_check(ast)
    canon, _ = canonicalize(ast)
    if canon != ast:
        raise CompileError("TAMPERED_PRODUCTION", "body is not canonical")
    body_bytes = canonical_json(prod["body"])
    order = [f"?s{i}" for i in range(len(types))]
    signature = {"input": "Grid", "result": "Grid", "args": [[s, types[s]] for s in order]}
    name = "cx_" + _sha(b"cora-cx|" + body_bytes + b"|" + canonical_json(signature))[:24]
    if prod["signature"] != signature or prod["name"] != name or \
            prod["source_sha256"] != _sha(body_bytes) or prod["blocks"] != len(parse_blocks(ast)):
        raise CompileError("TAMPERED_PRODUCTION", "content-derived field mismatch")
    if serialize(prod) != data:
        raise CompileError("TAMPERED_PRODUCTION", "not the canonical serialization")
    return prod


def elaborate(prod, bindings: dict):
    """Surface application to a core meta-AST by ordinary substitution."""
    M, _ = _meta()
    return M.instantiate(M.ast_from_json(prod["body"]), bindings)


class ConceptView:
    """What the expression phase's concept route reads: .name and .schema."""

    def __init__(self, prod):
        M, _ = _meta()
        self.name = prod["name"]
        self.schema = M.ast_from_json(prod["body"])

    def __repr__(self):
        return f"ConceptView({self.name})"


# --------------------------------------------------------------------------
# K* and the overlay
# --------------------------------------------------------------------------

_STATE = {"active": False, "orig_icc": None, "orig_learner": None, "env": None,
          "overlay": (), "installed": []}


def _shape_ops(ast) -> list:
    if not (isinstance(ast, tuple) and len(ast) == 2 and ast[0] == "Compose"):
        return []
    return [s[0] if isinstance(s, tuple) and len(s) == 2 else None for s in ast[1]]


def kstar_learner_factory(orig):
    """K*-2: the engine's learner for its own shape, the frozen
    occurrence-scoped fitter for every other shape."""
    def kstar_feature_colour_map(ast, pairs, slot):
        if _shape_ops(ast) == ["Partition", "Select", "Map", "Paint"]:
            return orig(ast, pairs, slot)
        SF = _sf()
        fitted, _ev = SF.fit_induced_occurrences(ast, pairs)
        if fitted is None:
            return None
        for index, stage in enumerate(ast[1]):
            if stage[0] == "Map" and stage[1][1][0] == "Lookup" and stage[1][1][1][0] == slot:
                return fitted[1][index][1][1][1][0]
        return None
    kstar_feature_colour_map.__wrapped_original__ = orig
    return kstar_feature_colour_map


def state_snapshot() -> str:
    """Hash of everything an installation could leave behind: the expression
    phase entry point, the slot-learner registry, the meta vocabulary and
    signatures, every non-callable module value of the meta modules and of
    the fitter, the ARC_* environment and this module's overlay state."""
    M, MI = _meta()
    SF = _sf()

    def fn_id(f):
        code = getattr(f, "__code__", None)
        return [getattr(f, "__module__", None), getattr(f, "__qualname__", None),
                _sha(code.co_code) if code is not None else None]
    items = [["icc", fn_id(MI.induce_computed_candidates)],
             ["learners", sorted([k, fn_id(v)] for k, v in MI.SLOT_LEARNERS.items())],
             ["env", sorted((k, v) for k, v in os.environ.items() if k.startswith("ARC_"))],
             ["overlay", [c.name for c in _STATE["overlay"]]],
             ["active", _STATE["active"]]]
    for mod in (M, MI, SF):
        for k in sorted(vars(mod)):
            v = vars(mod)[k]
            if callable(v) or type(v).__name__ == "module" or k.startswith("__") or k == "SLOT_LEARNERS":
                continue
            items.append([mod.__name__, k, repr(v)])
    return _sha(json.dumps(items, default=str).encode())


@contextlib.contextmanager
def kstar():
    """Run the reasoner as K*. Restores every patched object and the
    environment on exit and verifies the restoration by snapshot."""
    M, MI = _meta()
    if _STATE["active"]:
        raise CompileError("OVERLAY_CONFLICT", "K* is already active")
    before = state_snapshot()
    orig_icc = MI.induce_computed_candidates
    orig_learner = MI.SLOT_LEARNERS[INDUCED_TYPE]
    env_before = {k: os.environ.get(k) for k in KSTAR_ENV}

    def kstar_induce_computed_candidates(train_pairs, deadline=None, concepts=(),
                                         concepts_only=False):
        #  K*-1 (deadline=None: the declared slice) and K*-3 (the overlay)
        return orig_icc(train_pairs, deadline=None,
                        concepts=tuple(concepts) + tuple(_STATE["overlay"]),
                        concepts_only=concepts_only)
    _STATE.update(active=True, orig_icc=orig_icc, orig_learner=orig_learner,
                  env=env_before, overlay=(), installed=[])
    MI.induce_computed_candidates = kstar_induce_computed_candidates
    MI.SLOT_LEARNERS[INDUCED_TYPE] = kstar_learner_factory(orig_learner)
    os.environ.update(KSTAR_ENV)
    try:
        yield
    finally:
        MI.induce_computed_candidates = orig_icc
        MI.SLOT_LEARNERS[INDUCED_TYPE] = orig_learner
        for k, v in env_before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _STATE.update(active=False, orig_icc=None, orig_learner=None, env=None,
                      overlay=(), installed=[])
        after = state_snapshot()
        if after != before:
            raise CompileError("RESTORATION_FAILURE", "K* left state behind")


@contextlib.contextmanager
def install(*productions):
    """K* -> K* + {e,...} for the duration of the context, then exactly K*.
    Productions are reloaded from their canonical bytes first, so a mutated
    or forged object cannot be installed."""
    if not _STATE["active"]:
        raise CompileError("KSTAR_NOT_ACTIVE", "install() needs an active kstar()")
    if _STATE["overlay"]:
        raise CompileError("OVERLAY_CONFLICT", "an overlay is already installed")
    checked = []
    for prod in productions:
        p = load(serialize(prod))
        if p["k_identity"] != k_identity():
            raise CompileError("K_IDENTITY_MISMATCH", "production compiled for another K*")
        checked.append(p)
    names = [p["name"] for p in checked]
    if len(names) != len(set(names)):
        raise CompileError("OVERLAY_CONFLICT", "a production is installed twice")
    before = state_snapshot()
    record = {"installed": names, "snapshot_before": before}
    _STATE["overlay"] = tuple(ConceptView(p) for p in checked)
    _STATE["installed"] = names
    try:
        yield record
    finally:
        _STATE["overlay"] = ()
        _STATE["installed"] = []
        after = state_snapshot()
        record["snapshot_after"] = after
        if after != before:
            raise CompileError("RESTORATION_FAILURE", "the overlay left state behind")


# --------------------------------------------------------------------------
# attribution
# --------------------------------------------------------------------------

def _matches(body, ast, types) -> bool:
    """Does `ast` instantiate `body`? A slot matches a value of its type:
    an induced slot a table (tuple of key/colour pairs), an enumerable slot
    a member of its frozen vocabulary."""
    M, _ = _meta()
    if _is_slot(body):
        t = types.get(body)
        if t == INDUCED_TYPE:
            return isinstance(ast, tuple) and all(isinstance(kv, tuple) and len(kv) == 2 for kv in ast)
        return t in M.ENUMERABLE_TYPES and ast in M.slot_domain(t)
    if _is_node(body):
        if not (isinstance(ast, tuple) and len(ast) == 2 and ast[0] == body[0]
                and len(ast[1]) == len(body[1])):
            return False
        return all(_matches(b, a, types) for b, a in zip(body[1], ast[1]))
    return body == ast


def structurally_instantiates(program, prod) -> bool:
    M, _ = _meta()
    d = program if isinstance(program, dict) else program.to_dict()
    while d.get("program_class") == "framed":
        d = d["inner"]
    if d.get("program_class") != "computed_pattern":
        return False
    body = M.ast_from_json(prod["body"])
    return _matches(body, M.ast_from_json(d["ast"]), M.free_slot_types(body))


def uses_extension(program, prod) -> bool:
    """Exact audit: the winning program is a computed pattern carrying the
    production's name AND its AST instantiates the production's body."""
    d = program if isinstance(program, dict) else program.to_dict()
    while d.get("program_class") == "framed":
        d = d["inner"]
    return (d.get("program_class") == "computed_pattern" and d.get("concept") == prod["name"]
            and structurally_instantiates(d, prod))


# --------------------------------------------------------------------------
# running the same reasoner, ablation, adaptive leave-one-out
# --------------------------------------------------------------------------

def run_reasoner(train_pairs, productions=(), budget_s=8.0, workdir=None, task_id="task") -> dict:
    """One solve by the real engine under K* (+ the given productions), with
    a fresh engine directory and cleared memo caches."""
    import numpy as np
    from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
    from geocat_arc.object_reasoning.inducer import InductionConfig
    L.clear_engine_caches()
    d = tempfile.mkdtemp(prefix="v17run_", dir=workdir)
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in train_pairs]
    with kstar():
        if productions:
            with install(*productions):
                eng = ObjectReasoningEngine(d, use_library=True,
                                            config=InductionConfig(budget_s=float(budget_s)))
                res = eng.solve(task_id, pairs)
        else:
            eng = ObjectReasoningEngine(d, use_library=True,
                                        config=InductionConfig(budget_s=float(budget_s)))
            res = eng.solve(task_id, pairs)
    sol = res.solution
    return {"accepted": sol is not None, "program": sol.program_json if sol else None,
            "apply_fn": sol.apply_fn if sol else None, "engine_dir": d,
            "events": list(res.induction.events) if res.induction else []}


def predict_exact(run, grid_in, grid_out) -> bool:
    import numpy as np
    if not run["accepted"]:
        return False
    try:
        return bool(np.array_equal(run["apply_fn"](np.asarray(grid_in)), np.asarray(grid_out)))
    except Exception:                                          # noqa: BLE001
        return False


def paired_ablation(train_pairs, prod, heldout=None, budget_s=8.0, workdir=None, task_id="task") -> dict:
    """K* + {e} against K* on the same pairs, budget, environment and task
    id, each in a fresh engine directory."""
    a = run_reasoner(train_pairs, (prod,), budget_s, workdir, task_id)
    b = run_reasoner(train_pairs, (), budget_s, workdir, task_id)
    used = a["accepted"] and uses_extension(a["program"], prod)
    if used and not b["accepted"]:
        verdict = "EXTENSION_NECESSARY_AND_USED"
    elif used and b["accepted"]:
        verdict = "USED_BUT_BASELINE_ALSO_SOLVES"
    elif a["accepted"]:
        verdict = "SOLVED_WITHOUT_USING_EXTENSION"
    else:
        verdict = "NOT_SOLVED_WITH_EXTENSION"
    out = {"verdict": verdict, "with": {k: a[k] for k in ("accepted", "program", "events")},
           "without": {k: b[k] for k in ("accepted", "program", "events")},
           "with_uses_extension": used}
    if heldout is not None:
        out["with"]["heldout_exact"] = predict_exact(a, *heldout)
        out["without"]["heldout_exact"] = predict_exact(b, *heldout)
    return out


def adaptive_loo(train_pairs, propose_and_compile, solve=None) -> dict:
    """The L leg: for each held-out demonstration, start from K*, give the
    proposer only the remaining demonstrations, compile from scratch,
    install, solve and predict the held-out one. Nothing from the full-data
    run is passed in."""
    solve = solve or (lambda pairs, prods: run_reasoner(pairs, prods))
    folds = []
    for i in range(len(train_pairs)):
        fold = [train_pairs[j] for j in range(len(train_pairs)) if j != i]
        held = train_pairs[i]
        prod = propose_and_compile(list(fold))
        if prod is None:
            folds.append({"fold": i, "status": "NO_EXTENSION"})
            continue
        run = solve(fold, (prod,))
        folds.append({"fold": i, "status": "RUN", "production": prod["name"],
                      "accepted": run["accepted"],
                      "uses_extension": bool(run["accepted"] and uses_extension(run["program"], prod)),
                      "heldout_exact": predict_exact(run, *held)})
    passed = bool(folds) and all(f.get("status") == "RUN" and f["accepted"] and f["uses_extension"]
                                 and f["heldout_exact"] for f in folds)
    return {"folds": folds, "passed": passed}


def witness_separation(prod, pairs) -> dict:
    """Declared bounded witness test: is the fitted production behaviourally
    equal, on the frozen probe grids, to any single-block program of K's
    meta space fitted on the same pairs?"""
    import numpy as np
    from cora_tti import constructive_probes as CP
    M, MI = _meta()
    SF = _sf()
    if prod["enumerable_slots"]:
        return {"status": "UNSUPPORTED", "reason": "enumerable slots"}
    body = M.ast_from_json(prod["body"])
    fitted, ev = SF.fit_induced_occurrences(body, pairs)
    if fitted is None:
        return {"status": "DOES_NOT_FIT", "reason": ev.get("failure")}
    evaluate = (lambda ast, grid: M.evaluate(ast, np.asarray(grid), MI.descriptors))
    fp = CP.fingerprint(fitted, evaluate)
    base = SF.base_search_with_scoped_fitter(pairs)
    equal = 0
    for _schema, fitted_b in base["fitted_pairs"]:
        try:
            if CP.fingerprint(fitted_b, evaluate) == fp:
                equal += 1
        except Exception:                                      # noqa: BLE001
            continue
    return {"status": "SEPARATED" if equal == 0 else "EQUIVALENT_TO_K",
            "equivalent_k_programs": equal, "k_programs_fitted": len(base["fitted_pairs"]),
            "k_exact": base["exact"]}
