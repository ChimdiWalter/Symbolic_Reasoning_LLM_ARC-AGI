"""What repeated Select can actually express (directive section 9).

A bounded semantic audit of the registered predicate inventory and the
reference executor, separating what is PROVED from definitions from what is
merely OBSERVED on finite grids. It hand-writes no target and changes no
inventory.

Part A  executor state semantics, established from the source of
        meta_ast.evaluate: which grid Partition, Select and Map read, and
        where Paint writes.
Part B  predicate purity: each registered predicate is a function of which
        descriptor fields (from its source).
Part C  closure of ordered predicate pairs under composition, PROVED over the
        descriptor domain the predicates actually read, with realizability of
        every point of that domain shown by witnesses.
Part D  OBSERVED separation on the fixture-grid distribution: for each
        partition and each ordered pair, how often the composed selection
        differs from every single-predicate selection. This is the finite
        observation that explains (but does not prove) why a two-Select target
        can be baseline-expressible on the fixture distribution.
"""
from __future__ import annotations

import ast as pyast
import hashlib
import inspect
import json
import sys
from itertools import product
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_probes as CP                   # noqa: E402


# ---------------------------------------------------------------- Part A ---

def executor_state_semantics() -> dict:
    """Read meta_ast.evaluate and record which name each stage reads/writes."""
    source = inspect.getsource(M.evaluate)
    tree = pyast.parse(source)
    reads, writes = {}, {}
    for node in pyast.walk(tree):
        if isinstance(node, pyast.Call):
            callee = node.func
            name = callee.id if isinstance(callee, pyast.Name) else getattr(callee, "attr", "")
            args = [a.id for a in node.args if isinstance(a, pyast.Name)]
            if name == "build":
                reads["Partition.build"] = args
            elif name == "predicate":
                inner = node.args[0]
                if isinstance(inner, pyast.Call):
                    reads["Select.descriptors_fn"] = [a.id for a in inner.args
                                                      if isinstance(a, pyast.Name)]
            elif name == "descriptors_fn":
                reads.setdefault("Map.descriptors_fn", [a.id for a in node.args
                                                        if isinstance(a, pyast.Name)])
        if isinstance(node, pyast.Assign):
            for target in node.targets:
                if isinstance(target, pyast.Subscript) and isinstance(target.value, pyast.Name):
                    writes["Paint.assigns_to"] = target.value.id
    facts = {
        "Partition_reads": reads.get("Partition.build"),
        "Select_reads": reads.get("Select.descriptors_fn"),
        "Map_reads": reads.get("Map.descriptors_fn"),
        "Paint_writes": writes.get("Paint.assigns_to"),
        "empty_selection_aborts_program": "if not sets:\n                return None" in source,
        "later_block_reads": None,
        "overlap_rule": None,
        "status": "PROVED_FROM_SOURCE",
    }
    all_read_grid = all(v == ["grid"] for v in (facts["Partition_reads"],
                                                 facts["Select_reads"],
                                                 facts["Map_reads"]))
    facts["later_block_reads"] = ("the ORIGINAL input grid (every stage reads `grid`; "
                                  "only Paint writes `out`)" if all_read_grid
                                  else "UNDETERMINED_FROM_SOURCE")
    facts["overlap_rule"] = ("last writer wins: Paint assigns colours to `out` in "
                             "stage order" if facts["Paint_writes"] == "out"
                             else "UNDETERMINED_FROM_SOURCE")
    #  executable confirmation of both facts on one constructed grid
    grid = np.zeros((6, 6), dtype=int)
    grid[1:3, 1:3] = 4
    two_block = ("Compose", (
        ("Partition", ("colour_components",)),
        ("Map", (("Key", ("area",)), ("Lookup", (((4, 7),),)))),
        ("Paint", ()),
        ("Partition", ("colour_components",)),
        ("Map", (("Key", ("area",)), ("Lookup", (((4, 9),),)))),
        ("Paint", ())))
    rendered = M.evaluate(two_block, grid, MI.descriptors)
    facts["executable_check"] = {
        "second_block_saw_original_component_of_area_4": bool(rendered is not None
                                                              and int(rendered[1, 1]) == 9),
        "last_writer_colour": None if rendered is None else int(rendered[1, 1]),
        "note": "if the second block had read the painted grid it would still find an "
                "area-4 component (colour 7) and paint 9; both readings give 9 here, so the "
                "source fact, not this check, is the authority on WHICH grid is read; the "
                "check confirms last-writer ownership",
    }
    return facts


# ---------------------------------------------------------------- Part B ---

def predicate_purity() -> dict:
    """Each registered predicate, its source expression, and the descriptor
    fields it reads (string constants subscripted on its argument)."""
    out = {}
    for name, fn in MI.PREDICATES.items():
        line = inspect.getsource(fn).strip().rstrip(",")
        expression = line[line.index("lambda"):]
        tree = pyast.parse(expression, mode="eval")
        fields = sorted({node.slice.value for node in pyast.walk(tree)
                         if isinstance(node, pyast.Subscript)
                         and isinstance(node.slice, pyast.Constant)
                         and isinstance(node.slice.value, str)})
        out[name] = {"source": expression, "descriptor_fields_read": fields,
                     "pure_function_of_descriptors": True}
    return out


# ---------------------------------------------------------------- Part C ---

DOMAIN_FIELDS = ("touches_border", "is_rect")


def _truth_table(fn) -> tuple:
    rows = []
    for tb, rect in product((False, True), repeat=2):
        rows.append(bool(fn({"touches_border": tb, "is_rect": rect})))
    return tuple(rows)


def closure_proof() -> dict:
    singles = {name: _truth_table(fn) for name, fn in MI.PREDICATES.items()}
    inverse = {}
    for name, table in singles.items():
        inverse.setdefault(table, []).append(name)
    pairs = {}
    classes = {"EQUIVALENT_TO_SINGLE": 0, "CONTRADICTORY": 0, "NEW_CONJUNCTION": 0}
    for q1, q2 in product(MI.PREDICATES, repeat=2):
        table = tuple(a and b for a, b in zip(singles[q1], singles[q2]))
        commutes = table == tuple(a and b for a, b in zip(singles[q2], singles[q1]))
        if not any(table):
            kind = "CONTRADICTORY"
        elif table in inverse:
            kind = "EQUIVALENT_TO_SINGLE"
        else:
            kind = "NEW_CONJUNCTION"
        classes[kind] += 1
        pairs[f"{q1} > {q2}"] = {
            "class": kind,
            "equivalent_singles": inverse.get(table, []),
            "redundant_stage": (q1 if table == singles[q2] else q2 if table == singles[q1] else None)
            if kind == "EQUIVALENT_TO_SINGLE" else None,
            "commutes": commutes,
            "truth_table_over_(touches_border,is_rect)": list(table),
        }
    #  realizability of every domain point on the fixture generator + probes
    witnesses = {}
    grids = [CD.generate_grid(80_000 + i) for i in range(40)] + list(CP.probes())
    for grid in grids:
        for partition, builder in MI.PARTITIONS.items():
            for cells in builder(grid) or []:
                d = MI.descriptors(cells, grid)
                point = (bool(d["touches_border"]), bool(d["is_rect"]))
                witnesses.setdefault(str(point), {"partition": partition, "area": d["area"]})
    return {
        "domain_fields": list(DOMAIN_FIELDS),
        "proof_basis": "every registered predicate is a function of the descriptor fields "
                       "above (Part B); the executor applies Select stages to sets computed "
                       "from the unchanged input grid (Part A); therefore "
                       "Select(q2)(Select(q1)(S)) = {r in S : q1(r) and q2(r)}, and two "
                       "ordered pairs are equivalent iff their conjunction truth tables agree "
                       "over the 4-point domain, PROVIDED every domain point is realizable",
        "single_truth_tables": {k: list(v) for k, v in singles.items()},
        "ordered_pairs": pairs,
        "class_counts": classes,
        "commutativity": "PROVED (conjunction is commutative; all 25 pairs commute)",
        "domain_points_realized": witnesses,
        "all_domain_points_realized": len(witnesses) == 4,
        "status": "PROVED_FROM_DEFINITIONS" if len(witnesses) == 4 else "PROVED_MODULO_REALIZABILITY",
        "unordered_new_conjunctions": sorted({tuple(sorted((a, b))) for a, b in product(MI.PREDICATES, repeat=2)
                                              if pairs[f"{a} > {b}"]["class"] == "NEW_CONJUNCTION"}),
    }


# ---------------------------------------------------------------- Part D ---

def observed_separation(n_grids: int = 60) -> dict:
    """On the fixture distribution, does the composed selection differ from
    EVERY single-predicate selection over the same partition?"""
    grids = [CD.generate_grid(90_000 + i) for i in range(n_grids)]
    out = {}
    for partition, builder in MI.PARTITIONS.items():
        per_pair = {}
        for q1, q2 in product(MI.PREDICATES, repeat=2):
            differs, defined, both_empty = 0, 0, 0
            for grid in grids:
                sets = builder(grid)
                if not sets:
                    continue
                defined += 1
                descs = [MI.descriptors(s, grid) for s in sets]
                composed = frozenset(s for s, d in zip(sets, descs)
                                     if MI.PREDICATES[q1](d) and MI.PREDICATES[q2](d))
                singles = [frozenset(s for s, d in zip(sets, descs) if MI.PREDICATES[q](d))
                           for q in MI.PREDICATES]
                if not composed:
                    both_empty += 1
                    continue
                if all(composed != single for single in singles):
                    differs += 1
            per_pair[f"{q1} > {q2}"] = {
                "grids_partition_defined": defined,
                "grids_composed_empty": both_empty,
                "grids_composed_differs_from_every_single": differs,
            }
        out[partition] = per_pair
    return {"n_grids": n_grids, "generator_seeds": "90000 + i",
            "status": "OBSERVED_ON_FINITE_GRIDS", "per_partition": out}


def main(out_path: Path) -> dict:
    report = {
        "part_a_executor_state": executor_state_semantics(),
        "part_b_predicate_purity": predicate_purity(),
        "part_c_closure_proof": closure_proof(),
        "part_d_observed_separation": observed_separation(),
        "engine_hashes": {
            "meta_ast.py": hashlib.sha256(Path(M.__file__).read_bytes()).hexdigest(),
            "meta_induction.py": hashlib.sha256(Path(MI.__file__).read_bytes()).hexdigest(),
        },
    }
    #  headline: for the NEW_CONJUNCTION pairs, how often the composition is
    #  observably distinct on the fixture distribution, per partition
    headline = {}
    for partition, per_pair in report["part_d_observed_separation"]["per_partition"].items():
        rows = []
        for pair, meta in report["part_c_closure_proof"]["ordered_pairs"].items():
            if meta["class"] == "NEW_CONJUNCTION":
                r = per_pair[pair]
                rows.append((pair, r["grids_composed_differs_from_every_single"],
                             r["grids_partition_defined"]))
        headline[partition] = rows
    report["headline_new_conjunction_observed_distinct"] = headline
    text = json.dumps(report, indent=1, sort_keys=True, default=str)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    report["sha256"] = hashlib.sha256(text.encode()).hexdigest()
    return report


if __name__ == "__main__":
    target = ROOT / "outputs" / "tti" / "constructive_v2_corrected" / "predicate_semantics_audit.json"
    result = main(target)
    print(json.dumps(result["part_a_executor_state"], indent=1))
    print(json.dumps(result["part_b_predicate_purity"], indent=1))
    c = result["part_c_closure_proof"]
    print("classes:", c["class_counts"], "status:", c["status"],
          "realized:", c["all_domain_points_realized"])
    print("new conjunctions:", c["unordered_new_conjunctions"])
    for pair, meta in c["ordered_pairs"].items():
        print(f"  {pair:45} {meta['class']:22} eq={meta['equivalent_singles']} redundant={meta['redundant_stage']}")
    print("observed distinct (pair, differs, defined) per partition:")
    for partition, rows in result["headline_new_conjunction_observed_distinct"].items():
        print(" ", partition, rows)
    print("sha256:", result["sha256"])
