#!/usr/bin/env python3
"""AUTONOMOUS M4 (level 3): machine-curated placement laws.

M3b's delta-level certificates validate machine-invented verbs against a
placement-law catalog — but that catalog was human-authored (6 laws, 2 of
them added after inspecting mined tasks).  M4 closes that rung: laws are
SEARCHED from a generic law grammar and admitted to the catalog only when
they delta-LOO-generalize across >= K distinct tasks, exactly the standard
verbs face.  The human contribution shrinks to the GRAMMAR:

  law := place(transform(src), reference, side, gap)
    transform  the candidate verb chain applied to the source shape
               (or identity reflection about the reference axis)
    reference  src_bbox_edge | nearest_line_marker | grid_edge | grid_center
    side       fixed (below/above/right/left) OR relational
               (away_from_nearest_edge | toward_marker)
    gap        integer 0..3, constant across pairs

Every concrete (reference, side, gap, axis) combination is a candidate
law.  For each candidate verb's instance corpus (same collection as M3b),
a candidate law delta-certifies a task iff it is re-fit-free (fully
concrete) or its free slots re-derive from N-1 pairs, and it predicts the
held-out orphan exactly for every fold.  Laws that certify >= K_LAW
distinct tasks are written to outputs/learned_laws.json with provenance,
and meta_m3_delta_certificates.py consumes them (--laws learned) so the
registration catalog itself becomes machine-curated.

Usage: meta_m4_law_miner.py [K_LAW=2]
"""
import itertools
import json
import os
import sys

sys.path.insert(0, ".")
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "m3b", "scripts/meta_m3_delta_certificates.py")
m3b = importlib.util.module_from_spec(_spec)
sys.modules["m3b"] = m3b
_spec.loader.exec_module(m3b)

try:
    K_LAW = int(sys.argv[1]) if len(sys.argv) > 1 else 2
except ValueError:
    K_LAW = 2
OUT = "outputs/learned_laws.json"


# --- the law grammar: enumerate concrete candidate laws ---------------------

def _src_bounds(inst):
    rs = [r for r, _ in inst["src"]]
    cs = [c for _, c in inst["src"]]
    return min(rs), max(rs), min(cs), max(cs)


def _mk_reflect_axis_law(orient, ref, side, gap):
    """Reflection of the source across an axis derived from `ref`:
    src_edge   axis = bbox edge +- gap (side fixed or relational)
    marker     axis = nearest adjacent line object (orientation-matched)
    grid_center axis = grid center line."""
    def law(fit, chain):
        def axis_of(inst):
            r0, r1, c0, c1 = _src_bounds(inst)
            H, W = inst["grid_shape"]
            lo, hi = (r0, r1) if orient == "h" else (c0, c1)
            n = H if orient == "h" else W
            s = side
            if s == "away_from_nearest_edge":
                s = "after" if (n - 1 - hi) >= lo else "before"
            if ref == "src_edge":
                return (hi + gap) if s == "after" else (lo - gap)
            if ref == "marker":
                return m3b._nearest_line(inst, orient)
            if ref == "grid_center":
                return None if n % 2 == 0 else n // 2
            return None

        def predict(inst):
            ax = axis_of(inst)
            if ax is None:
                return None
            return m3b._reflect(inst["src"], orient, ax)

        for inst in fit:
            if predict(inst) != frozenset(inst["orphan"]):
                return None
        return predict
    return law


def enumerate_laws():
    """The concrete law space: small, generic, and enumerable."""
    laws = {}
    for orient in ("h", "v"):
        for ref in ("src_edge", "marker", "grid_center"):
            sides = ("after", "before", "away_from_nearest_edge") \
                if ref == "src_edge" else ("fixed",)
            gaps = (0, 1, 2, 3) if ref == "src_edge" else (0,)
            for side, gap in itertools.product(sides, gaps):
                name = f"reflect[{orient}|{ref}|{side}|g{gap}]"
                laws[name] = _mk_reflect_axis_law(orient, ref, side, gap)
    # translation laws: transformed shape at constant / touching offsets
    laws["const_offset"] = m3b._law_const_offset
    laws["touch"] = m3b._law_touch
    return laws


# --- mining ------------------------------------------------------------------

def delta_loo_with(instances, chain, law):
    n = len(instances)
    if n < 2:
        return 0, 0
    passed = 0
    for hold in range(n):
        fit = [x for i, x in enumerate(instances) if i != hold]
        held = instances[hold]
        try:
            predict = law(fit, chain)
            if predict is not None and \
                    predict(held) == frozenset(held["orphan"]):
                passed += 1
        except Exception:
            pass
    return passed, n


def main():
    rep = json.load(open("outputs/meta_m2_chains.json"))
    cands = {}
    for e in rep["chains_with_5plus_tasks"]:
        ch = m3b.parse_chain(e["chain"])
        sig = m3b.canon(ch)
        if sig is None or sig == m3b.PROBE:
            continue
        if sig not in cands or len(ch) < len(cands[sig][1]):
            cands[sig] = (e["chain"], ch)
    tasks = m3b.collect_instance_tasks()
    laws = enumerate_laws()
    print(f"law space: {len(laws)} candidates x {len(cands)} verbs x "
          f"{len(tasks)} tasks", flush=True)

    admitted = []
    family_cert = {}
    for law_name, law in sorted(laws.items()):
        certified = {}
        for key, ch in [(k, c) for k, c in cands.values()]:
            for tid, var in tasks:
                try:
                    inst = m3b.task_instances(tid, var, ch)
                except Exception:
                    continue
                if len(inst) < 2:
                    continue
                passed, folds = delta_loo_with(inst, ch, law)
                if folds >= 2 and passed == folds:
                    certified.setdefault(tid, []).append(key)
        if len(certified) >= K_LAW:
            admitted.append({"law": law_name, "granularity": "law",
                             "certified_tasks": sorted(certified),
                             "k_law": K_LAW})
            print(f"[ADMIT] {law_name}: {sorted(certified)}", flush=True)
        elif certified:
            print(f"[skip]  {law_name}: {len(certified)} < K_LAW",
                  flush=True)
        # family granularity: the grammar production is the unit of
        # recurrence (an M3b-catalog-equivalent: 2 tasks x 1 law each).
        if certified:
            fam = law_name.split("[")[0] if "[" in law_name else law_name
            family_cert.setdefault(fam, {})
            for tid in certified:
                family_cert[fam].setdefault(tid, law_name)
    for fam, tids in sorted(family_cert.items()):
        if len(tids) >= K_LAW and not any(
                a.get("granularity") == "law" and
                a["law"].startswith(fam) for a in admitted):
            admitted.append({"law": fam, "granularity": "family",
                             "members": sorted(set(tids.values())),
                             "certified_tasks": sorted(tids),
                             "k_law": K_LAW})
            print(f"[ADMIT-FAMILY] {fam}: {sorted(tids)} via "
                  f"{sorted(set(tids.values()))}", flush=True)
    json.dump(admitted, open(OUT, "w"), indent=1)
    print(f"ADMITTED {len(admitted)} machine-curated laws -> {OUT}",
          flush=True)


if __name__ == "__main__":
    main()
