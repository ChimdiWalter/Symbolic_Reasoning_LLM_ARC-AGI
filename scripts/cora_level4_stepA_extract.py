"""Level 4, Step A: blind failure-frontier extraction.

This is the mechanism. It reads the four sanitized inputs and nothing else,
it executes the blind runtime and nothing else, and it emits frontier records
plus their clustering. It does not propose an extension, does not open
E_transfer, and never learns a task identity.

WHAT A FOLD FAILURE IS. Exactly what the immutable verifier means by one:
induce on the other demonstrations, take the ranked winner the leave-one-out
gate would take, render it on the held-out input, and compare. A fold with no
discovered program fails too. Failure is NOT redefined as "no candidate
anywhere predicts the held-out pair", because Level 4 must diagnose the same
failure that blocks certification.

WHAT A FRONTIER IS. Among the terms that AROSE in that fold's goal-directed
derivation, those that type-check, execute on every training input of the
fold, are not a proper sub-term of another such term, and are of greatest
surface depth. All incomparable maxima are kept. Nothing is ranked by
closeness to the answer: a frontier is chosen by depth and execution, never
by how good its residual looks, because that would be hindsight.

TWO SIGNATURES, NOT ONE RESIDUAL. A frontier's result type is usually not the
goal type, so it cannot be differenced against the target at all. Each record
carries a value signature appropriate to what the term actually returns and,
independently, a signature of the demonstrated delta. A behavioural residual
is computed ONLY when the frontier's type is the goal type. No projection
onto the goal type is invented, since such a projection would smuggle in the
semantic bridge this stage exists to look for.

DISPATCH IS ON VALUES, NOT TYPE NAMES. The canonicalizers branch on the shape
of the runtime value (an array, a family of cell sets, one cell set, coloured
cells, a scalar), never on a type's name. The only type name this file knows
is the goal type, which it reads from the machine manifest.

FAILURE CLASSES are assigned once, by the frozen precedence in the manifest.
Strict precedence is coarse: a fold in which one continuation executed and
another could not be fitted is reported as the earlier class. The record
therefore also carries the raw diagnostic counts, so the precedence choice
costs ordering, never information.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V          # noqa: E402
from level4_blind_runtime import concept as C          # noqa: E402
from level4_blind_runtime import env as E              # noqa: E402
from level4_blind_runtime import stepA_trace_search as S  # noqa: E402

INPUTS = ROOT / "outputs" / "cora_breakthrough" / "level4_mechanism_inputs"
MANIFEST = INPUTS / "machine_manifest.json"
CONTRACT = INPUTS / "contract_redacted.json"
CONCEPTS = INPUTS / "concepts_redacted.json"
CORPUS = INPUTS / "invention_corpus.jsonl"
OUT = ROOT / "outputs" / "cora_breakthrough"


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_type(text: str):
    """Minimal parser for the recorded type texts."""
    text = text.strip().replace("=>", ",")
    if "[" not in text:
        return V.T(text)
    head, rest = text.split("[", 1)
    parts, depth, current = [], 0, ""
    for ch in rest[:-1]:
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        current += ch
    if current:
        parts.append(current)
    return V.T(head.strip(), *[parse_type(p) for p in parts])


def verify_inputs(manifest: dict, corpus_path: Path) -> dict:
    """Refuse to run on anything but the frozen bundle."""
    pinned = manifest["bundle_sha256"]
    checks, drift = {}, []
    files = {
        "blind_contract": CONTRACT,
        "concepts_redacted": CONCEPTS,
        "invention_corpus": CORPUS,
        "blind_runtime/__init__.py": ROOT / "level4_blind_runtime/__init__.py",
        "blind_runtime/concept.py": ROOT / "level4_blind_runtime/concept.py",
        "blind_runtime/env.py": ROOT / "level4_blind_runtime/env.py",
        "blind_runtime/runtime.py": ROOT / "level4_blind_runtime/runtime.py",
        "blind_runtime/search.py": ROOT / "level4_blind_runtime/search.py",
    }
    for key, path in files.items():
        if key not in pinned:
            continue
        # the manifest pins digest PREFIXES; compare at the pinned length
        got = sha256_file(path)[:len(pinned[key])]
        checks[key] = got == pinned[key]
        if not checks[key]:
            drift.append(key)
    return {"checks": checks, "drift": drift,
            "corpus_is_frozen": corpus_path.resolve() == CORPUS.resolve()}


def build_env(manifest: dict):
    """E_L4* = the eleven admitted productions plus the learned abstraction."""
    base = E.LanguageEnv(label=manifest["knowledge_state"]["label"])
    expected = set(manifest["knowledge_state"]["productions"])
    if set(base.base) != expected:
        raise SystemExit("ABORT: blind registry does not equal K_L4*")
    records = json.loads(CONCEPTS.read_text())
    for name in manifest["knowledge_state"]["abstractions"]:
        record = records[name]
        schema = V.from_json(record["schema"])
        slot_types = {k: parse_type(v)
                      for k, v in record["slot_types"].items()}
        concept = C.Concept(name=name, schema=schema, slot_types=slot_types,
                            provenance=(), source_hashes=(),
                            result_type=parse_type(record["result_type"]),
                            cost=record["cost"], status=record["status"])
        base = base.with_concept(concept, label=base.label)
    return base


# --------------------------------------------------------------------------
# static type reachability, used for the type_connectivity class
# --------------------------------------------------------------------------

def constructible_types(env) -> set:
    """Types some term can produce at all, from terminals upward."""
    known = set(V.TERMINAL_VALUES) | set(V.INDUCED_TYPES)
    changed = True
    while changed:
        changed = False
        for name in sorted(env.names):
            if all(str(a) in known for a in env.arg_types(name)):
                result = str(env.result_type(name))
                if result not in known:
                    known.add(result)
                    changed = True
    return known


def types_reaching(env, goal: str) -> set:
    """Types that can sit inside a term of the goal type."""
    known = constructible_types(env)
    reaching = {goal}
    changed = True
    while changed:
        changed = False
        for name in sorted(env.names):
            if str(env.result_type(name)) not in reaching:
                continue
            args = env.arg_types(name)
            for index, arg in enumerate(args):
                others = [str(a) for j, a in enumerate(args) if j != index]
                if not all(o in known for o in others):
                    continue
                if str(arg) not in reaching:
                    reaching.add(str(arg))
                    changed = True
    return reaching


# --------------------------------------------------------------------------
# canonical, normalised signatures
# --------------------------------------------------------------------------

def bucket_count(n: int) -> str:
    if n <= 3:
        return str(n)
    return "4-9" if n <= 9 else "10+"


def bucket_fraction(part: int, whole: int) -> str:
    if whole <= 0:
        return "undefined"
    if part == 0:
        return "0"
    if part == whole:
        return "100%"
    ratio = part / whole
    if ratio <= 0.1:
        return "<=10%"
    return "<=50%" if ratio <= 0.5 else "<100%"


def is_cells(value) -> bool:
    if not isinstance(value, (frozenset, set, tuple)) or not value:
        return False
    return all(isinstance(c, tuple) and len(c) == 2
               and all(isinstance(x, (int, np.integer)) for x in c)
               for c in value)


def is_coloured(value) -> bool:
    if not isinstance(value, tuple) or not value:
        return False
    return all(isinstance(p, tuple) and len(p) == 2 and is_cells(p[0])
               and isinstance(p[1], (int, np.integer, float)) for p in value)


def value_kind(value) -> str:
    if isinstance(value, np.ndarray) and value.ndim == 2:
        return "grid"
    if is_coloured(value):
        return "coloured"
    if is_cells(value):
        return "cells"
    if isinstance(value, tuple) and value and all(is_cells(v) for v in value):
        return "cellsets"
    if isinstance(value, (int, float, np.integer, np.floating)):
        return "scalar"
    return "opaque"


def cells_features(cells) -> dict:
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    height = max(rows) - min(rows) + 1
    width = max(cols) - min(cols) + 1
    return {"area_class": bucket_count(len(cells)),
            "is_rect": len(cells) == height * width,
            "is_square": height == width}


def value_features(value, grid) -> dict:
    """Position-, palette- and grid-size-invariant description of a value."""
    kind = value_kind(value)
    if kind == "grid":
        colours = {int(x) for x in np.unique(value)}
        return {"kind": kind,
                "shape_equals_input": value.shape == grid.shape,
                "palette_size_class": bucket_count(len(colours)),
                "differs_from_input": not (value.shape == grid.shape
                                           and np.array_equal(value, grid))}
    if kind == "cellsets":
        union, overlap = set(), False
        shapes, areas, single = set(), set(), True
        for cells in value:
            if union & set(cells):
                overlap = True
            union |= set(cells)
            r0 = min(r for r, _ in cells)
            c0 = min(c for _, c in cells)
            shapes.add(tuple(sorted((r - r0, c - c0) for r, c in cells)))
            areas.add(len(cells))
            if len({int(grid[r, c]) for r, c in cells}) != 1:
                single = False
        return {"kind": kind,
                "cardinality_class": bucket_count(len(value)),
                "disjoint": not overlap,
                "covers_grid": len(union) == grid.size,
                "uniform_shape": len(shapes) == 1,
                "uniform_area": len(areas) == 1,
                "all_single_colour": single}
    if kind == "cells":
        features = cells_features(value)
        features["kind"] = kind
        features["single_colour"] = len(
            {int(grid[r, c]) for r, c in value}) == 1
        return features
    if kind == "coloured":
        colours = {int(colour) for _, colour in value}
        return {"kind": kind,
                "cardinality_class": bucket_count(len(value)),
                "distinct_colours_class": bucket_count(len(colours)),
                "all_same_colour": len(colours) == 1}
    if kind == "scalar":
        return {"kind": kind}
    return {"kind": "opaque"}


def aggregate(per_input: list) -> dict:
    """One feature map for the fold: a constant value, or VARIES."""
    if not per_input:
        return {}
    keys = sorted(set().union(*[set(f) for f in per_input]))
    out = {}
    for key in keys:
        values = [f.get(key) for f in per_input]
        first = values[0]
        out[key] = first if all(v == first for v in values) else "VARIES"
    return out


def delta_features(grid_in, grid_out) -> dict:
    """The demonstrated transformation, described independently of any term."""
    palette_in = {int(x) for x in np.unique(grid_in)}
    palette_out = {int(x) for x in np.unique(grid_out)}
    if palette_out == palette_in:
        relation = "same"
    elif palette_out < palette_in:
        relation = "subset"
    elif palette_out > palette_in:
        relation = "superset"
    else:
        relation = "other"
    features = {"colours_introduced": bool(palette_out - palette_in),
                "colours_removed": bool(palette_in - palette_out),
                "palette_relation": relation}
    if grid_in.shape == grid_out.shape:
        features["shape_relation"] = "same"
        changed = {(r, c) for r in range(grid_in.shape[0])
                   for c in range(grid_in.shape[1])
                   if int(grid_in[r, c]) != int(grid_out[r, c])}
        components = V._components(changed) if changed else []
        uniform = all(len({int(grid_out[r, c]) for r, c in comp}) == 1
                      for comp in components)
        features["changed_fraction_class"] = bucket_fraction(
            len(changed), grid_in.size)
        features["changed_component_count_class"] = bucket_count(
            len(components))
        features["changed_components_uniform_colour"] = uniform
    else:
        smaller = (grid_out.shape[0] <= grid_in.shape[0]
                   and grid_out.shape[1] <= grid_in.shape[1])
        larger = (grid_out.shape[0] >= grid_in.shape[0]
                  and grid_out.shape[1] >= grid_in.shape[1])
        features["shape_relation"] = ("smaller" if smaller else
                                      "larger" if larger else "other")
        features["changed_fraction_class"] = "NOT_APPLICABLE"
        features["changed_component_count_class"] = "NOT_APPLICABLE"
        features["changed_components_uniform_colour"] = "NOT_APPLICABLE"
    return features


def residual_features(rendered, grid_in, grid_out) -> dict:
    """Only ever called when the frontier's type IS the goal type."""
    if not isinstance(rendered, np.ndarray) or rendered.ndim != 2:
        return {"shape_match": False, "comparable": False}
    if rendered.shape != grid_out.shape:
        return {"shape_match": False, "comparable": False}
    wrong = {(r, c) for r in range(grid_out.shape[0])
             for c in range(grid_out.shape[1])
             if int(rendered[r, c]) != int(grid_out[r, c])}
    goal_changed = set()
    if grid_in.shape == grid_out.shape:
        goal_changed = {(r, c) for r in range(grid_out.shape[0])
                        for c in range(grid_out.shape[1])
                        if int(grid_in[r, c]) != int(grid_out[r, c])}
    components = V._components(wrong) if wrong else []
    return {"shape_match": True, "comparable": True,
            "exact": not wrong,
            "wrong_fraction_class": bucket_fraction(len(wrong),
                                                    grid_out.size),
            "wrong_component_count_class": bucket_count(len(components)),
            "wrong_cells_within_goal_delta": bool(goal_changed)
            and wrong <= goal_changed,
            "correct_outside_goal_delta": bool(goal_changed)
            and not (wrong - goal_changed)}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


# --------------------------------------------------------------------------
# terms
# --------------------------------------------------------------------------

def term_key(ast, env) -> str:
    return canonical(E.to_json(ast, env))


def skeleton(ast, env):
    """The term with every induced-slot value replaced by a wildcard.

    A candidate and its slot-fitted form differ only in those positions, so
    skeletons let a fitted term be recognised as the same continuation.
    """
    if not env.is_ast(ast):
        return ast
    name, args = ast
    declared = env.arg_types(name)
    out = []
    for index, arg in enumerate(args):
        if env.is_ast(arg):
            out.append(skeleton(arg, env))
        elif index < len(declared) and str(declared[index]) in V.INDUCED_TYPES:
            out.append("?SLOT")
        elif isinstance(arg, str) and arg.startswith("?"):
            out.append("?SLOT")
        else:
            out.append(arg)
    return (name, tuple(out))


def subterms(ast, env) -> set:
    out = set()

    def walk(node):
        if not env.is_ast(node):
            return
        out.add(term_key(node, env))
        for arg in node[1]:
            walk(arg)

    walk(ast)
    return out


def evaluate_on(ast, env, grids):
    """Every value the term takes on the fold's training inputs, or None."""
    core = E.expand(ast, env)
    if core is None:
        return None
    values = []
    for grid in grids:
        try:
            value = V._eval(core, V.Ctx(grid))
        except Exception:
            return None
        if value is None:
            return None
        values.append(value)
    return values


# --------------------------------------------------------------------------
# one fold
# --------------------------------------------------------------------------

def run_fold(pairs, held, env, goal_type, reaching, execution_cap):
    """Search on the other demonstrations, judge the fold, trace the terms."""
    subset = [p for i, p in enumerate(pairs) if i != held]
    observer = S.TraceObserver()
    S.set_observer(observer)
    try:
        results, stats = S.search(subset, env=env)
    finally:
        S.set_observer(None)

    grid_in, grid_out = pairs[held]
    predicted = None
    if results:
        predicted = E.evaluate(results[0][0], grid_in, env)
    passed = predicted is not None and np.array_equal(predicted, grid_out)
    fold = {"failed": not passed,
            "no_program": not results,
            "truncations": sorted(observer.truncations),
            "stats": stats.as_dict()}
    if passed:
        return fold, []

    # -- candidate outcomes, strongest per candidate ----------------------
    rank = {"typecheck_failed": 0, "typed": 1, "slot_fit_failed": 2,
            "slot_fit_ok": 3, "executed_not_exact": 4, "exact": 5}
    outcomes = {}
    for ast, outcome in observer.candidates:
        key = canonical(skeleton(ast, env))
        if key not in outcomes or rank[outcome] > rank[outcomes[key]]:
            outcomes[key] = outcome

    # -- the terms that arose, deduplicated, type-correct ------------------
    #    A term with an unfilled induced slot cannot take a value: the
    #    interpreter returns None the moment it meets a slot argument, and the
    #    contextual productions raise on one. Such terms are therefore
    #    non-executing by construction and are excluded WITHOUT spending an
    #    execution test, so the cap bounds real work instead of being consumed
    #    by terms whose answer is already known. The gate script checks this
    #    implication rather than assuming it. Slot-fitted complete terms are
    #    traced separately and are not excluded here.
    candidates, unfilled = {}, 0
    for _, _, ast in observer.terms:
        key = term_key(ast, env)
        if key in candidates:
            continue
        if E.type_of(ast, env) is None:
            continue
        if E.free_slots(ast, env):
            unfilled += 1
            continue
        candidates[key] = ast

    training = [grid_in for grid_in, _ in subset]
    by_depth = {}
    for key, ast in candidates.items():
        by_depth.setdefault(E.surface_depth(ast, env), []).append((key, ast))

    executing, tested, capped = [], 0, False
    for depth in sorted(by_depth, reverse=True):
        for key, ast in sorted(by_depth[depth]):
            if tested >= execution_cap:
                capped = True
                break
            tested += 1
            values = evaluate_on(ast, env, training)
            if values is not None:
                executing.append((key, ast, values))
        if executing or capped:
            break

    # -- maximality: explicit, though equal depth already implies it -------
    contained = set()
    for _, ast, _ in executing:
        contained |= (subterms(ast, env) - {term_key(ast, env)})
    frontiers = [row for row in executing if row[0] not in contained]

    fold["execution_tests"] = tested
    fold["execution_cap_reached"] = capped
    fold["frontiers"] = len(frontiers)

    # -- the demonstrated delta, independent of any term -------------------
    per_pair = [delta_features(a, b) for a, b in subset]
    goal_delta = aggregate(per_pair)
    repeated = all(canonical(f) == canonical(per_pair[0]) for f in per_pair)

    records = []
    for key, ast, values in frontiers:
        frontier_type = str(E.type_of(ast, env))
        skeleton_key = canonical(skeleton(ast, env))
        matched = [outcome for candidate_key, outcome in outcomes.items()
                   if _continues(candidate_key, skeleton_key)]

        if fold["truncations"]:
            failure_class = "budget"
        elif frontier_type not in reaching:
            failure_class = "type_connectivity"
        elif not matched or set(matched) <= {"typecheck_failed"}:
            failure_class = "routing"
        elif "slot_fit_failed" in matched:
            failure_class = "slot_learning"
        else:
            failure_class = "semantic"

        if frontier_type == goal_type:
            residual = aggregate([residual_features(value, a, b)
                                  for value, (a, b) in zip(values, subset)])
        else:
            residual = "NOT_DEFINED"

        records.append({
            "fold_index": held,
            "frontier_ast": E.to_json(ast, env),
            "frontier_type": frontier_type,
            "goal_type": goal_type,
            "frontier_surface_depth": E.surface_depth(ast, env),
            "frontier_value_signature": aggregate(
                [value_features(value, grid)
                 for value, grid in zip(values, training)]),
            "goal_delta_signature": goal_delta,
            "behavioural_residual": residual,
            "repeated_structure": repeated,
            "failure_class": failure_class,
            "diagnostics": {
                "continuations_considered": len(matched),
                "slot_fit_failures": matched.count("slot_fit_failed"),
                "slot_fits_ok": matched.count("slot_fit_ok"),
                "executed_not_exact": matched.count("executed_not_exact"),
                "exact": matched.count("exact"),
                "fold_truncations": fold["truncations"],
                "terms_arose": len(candidates),
                "terms_with_unfilled_slots": unfilled,
                "execution_tests": tested,
                "execution_cap_reached": capped,
            },
        })
    return fold, records


def _continues(candidate_key: str, frontier_key: str) -> bool:
    """Is the frontier this candidate, or a sub-term of it?

    Both are canonical serializations of skeletons, and a sub-term's
    serialization is a substring of its parent's. String containment is exact
    here because the serialization is deterministic and fully bracketed.
    """
    return frontier_key in candidate_key


# --------------------------------------------------------------------------
# one corpus record
# --------------------------------------------------------------------------

_STATE = {}


def _init_worker(manifest):
    env = build_env(manifest)
    _STATE["env"] = env
    _STATE["goal"] = manifest["goal_type"]
    _STATE["reaching"] = types_reaching(env, manifest["goal_type"])
    _STATE["cap"] = manifest["frontier"]["execution_test_cap"]


def process_record(record):
    env = _STATE["env"]
    pairs = [(np.array(d["input"]), np.array(d["output"]))
             for d in record["demonstrations"]]
    token = record["source_token"]
    folds, records = [], []
    started = time.monotonic()
    for held in range(len(pairs)):
        fold, found = run_fold(pairs, held, env, _STATE["goal"],
                               _STATE["reaching"], _STATE["cap"])
        folds.append(fold)
        for row in found:
            row["source_token"] = token
            records.append(row)
    return {"source_token": token,
            "demonstrations": len(pairs),
            "folds": len(folds),
            "failed_folds": sum(1 for f in folds if f["failed"]),
            "truncated_folds": sum(1 for f in folds if f["truncations"]),
            "frontier_records": records,
            "seconds": round(time.monotonic() - started, 2)}


# --------------------------------------------------------------------------
# clustering
# --------------------------------------------------------------------------

def cluster(records, threshold: int) -> list:
    groups = {}
    for row in records:
        key = (row["frontier_type"], row["goal_type"],
               canonical(row["goal_delta_signature"]), row["failure_class"])
        groups.setdefault(key, []).append(row)
    out = []
    for key in sorted(groups):
        rows = groups[key]
        tokens = sorted({r["source_token"] for r in rows})
        out.append({
            "frontier_type": key[0],
            "goal_type": key[1],
            "goal_delta_signature": json.loads(key[2]),
            "failure_class": key[3],
            "records": len(rows),
            "distinct_source_tokens": len(tokens),
            "eligible": len(tokens) >= threshold,
        })
    out.sort(key=lambda c: (-c["distinct_source_tokens"], -c["records"],
                            c["frontier_type"], c["failure_class"]))
    return out


# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--tag", default="level4_stepA")
    parser.add_argument("--outdir", default=str(OUT))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    corpus_path = Path(args.corpus)
    integrity = verify_inputs(manifest, corpus_path)
    if integrity["drift"]:
        print(f"ABORT: frozen bundle drift in {integrity['drift']}")
        return 1

    records = [json.loads(line) for line in
               corpus_path.read_text().splitlines() if line.strip()]
    if args.limit:
        records = records[:args.limit]
    records.sort(key=lambda r: r["source_token"])

    goal = manifest["goal_type"]
    threshold = manifest["cluster_eligibility"]["distinct_source_tokens"]

    print(f"corpus records            {len(records)}")
    print(f"workers                   {args.workers}")
    print(f"corpus is the frozen one  {integrity['corpus_is_frozen']}")
    sys.stdout.flush()

    started = time.monotonic()
    results = []
    if args.workers > 1:
        context = mp.get_context("fork")
        with context.Pool(args.workers, initializer=_init_worker,
                          initargs=(manifest,)) as pool:
            for done, result in enumerate(
                    pool.imap_unordered(process_record, records, chunksize=1),
                    start=1):
                results.append(result)
                _progress(done, len(records), results, started)
    else:
        _init_worker(manifest)
        for done, record in enumerate(records, start=1):
            results.append(process_record(record))
            _progress(done, len(records), results, started)

    results.sort(key=lambda r: r["source_token"])
    frontier_records = []
    for result in results:
        for row in result["frontier_records"]:
            frontier_records.append(row)
    frontier_records.sort(key=lambda r: (r["source_token"], r["fold_index"],
                                         canonical(r["frontier_ast"])))

    clusters = cluster(frontier_records, threshold)

    outdir = Path(args.outdir)
    records_path = outdir / f"{args.tag}_frontier_records.jsonl"
    folds_path = outdir / f"{args.tag}_fold_summary.json"
    clusters_path = outdir / f"{args.tag}_clusters.json"

    records_path.write_text(
        "".join(canonical(row) + "\n" for row in frontier_records))
    folds_path.write_text(canonical({
        "stage": "Level 4 Step A: failure-frontier extraction",
        "corpus_is_frozen": integrity["corpus_is_frozen"],
        "corpus_sha256": sha256_file(corpus_path),
        "records": len(records),
        "folds": sum(r["folds"] for r in results),
        "failed_folds": sum(r["failed_folds"] for r in results),
        "truncated_folds": sum(r["truncated_folds"] for r in results),
        "frontier_records": len(frontier_records),
        "per_record": [{"source_token": r["source_token"],
                        "demonstrations": r["demonstrations"],
                        "folds": r["folds"],
                        "failed_folds": r["failed_folds"],
                        "truncated_folds": r["truncated_folds"],
                        "frontier_records": len(r["frontier_records"])}
                       for r in results],
    }))
    clusters_path.write_text(canonical({
        "cluster_key": ["frontier_type", "goal_type", "goal_delta_signature",
                        "failure_class"],
        "eligibility_threshold_distinct_source_tokens": threshold,
        "clusters": clusters,
    }))

    digest = hashlib.sha256()
    for path in (records_path, folds_path, clusters_path):
        digest.update(path.read_bytes())
    output_hash = digest.hexdigest()
    (outdir / f"{args.tag}_output_hash.txt").write_text(
        f"{output_hash}\n"
        f"{records_path.name} {sha256_file(records_path)}\n"
        f"{folds_path.name} {sha256_file(folds_path)}\n"
        f"{clusters_path.name} {sha256_file(clusters_path)}\n")

    print()
    print("STEP A COMPLETE")
    print(f"  records processed   {len(records)}")
    print(f"  folds               {sum(r['folds'] for r in results)}")
    print(f"  failed folds        {sum(r['failed_folds'] for r in results)}")
    print(f"  truncated folds     {sum(r['truncated_folds'] for r in results)}")
    print(f"  frontier records    {len(frontier_records)}")
    print(f"  clusters            {len(clusters)}")
    print(f"  eligible clusters   "
          f"{sum(1 for c in clusters if c['eligible'])}")
    print(f"  seconds             {round(time.monotonic() - started, 1)}")
    print()
    print("STEP A FROZEN")
    print(f"output hash = {output_hash}")
    return 0


def _progress(done, total, results, started):
    if done % 10 and done != total:
        return
    print(f"  {done}/{total} records  "
          f"folds {sum(r['folds'] for r in results)}  "
          f"failed {sum(r['failed_folds'] for r in results)}  "
          f"truncated {sum(r['truncated_folds'] for r in results)}  "
          f"frontiers {sum(len(r['frontier_records']) for r in results)}  "
          f"{round(time.monotonic() - started)}s")
    sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
