"""Phase 2 scoring and analysis (refused without the GO), on Athe after the kernels' outputs are downloaded.
Writes RESULTS.json and REPORT.md into the ARC-AGI-2 kernel's folder (PROTOCOL.md sections 6 and 7, amendments 1 to 3).

    python -I run.py report A_DIR B_DIR C_DIR        the downloaded folders of kernels A, B and C

Order of operations, fail-closed:
1. The GO is checked (ngb.gate). Each of the three folders' OUTPUT_MANIFEST.json is verified (every listed file has
   its digest; no unlisted file, the report's own two outputs excepted) and its STAGES.json must carry this GO's
   sha256, the same primary and the status "complete". Kernel C's packaged copies of A's and B's held rows must equal
   A's and B's files byte for byte. The held rows are read from A (ConceptARC, Mini-ARC) and B (1D-ARC), the
   ARC-AGI-2 rows from C.
2. Every expected row is collected and validated BEFORE any solution file is opened: for every benchmark and every
   one of the ten held arms, and for every one of the seven ARC-AGI-2 arms, exactly one row per task (a duplicate is
   INVALID, a missing one INCOMPLETE) with: bench, task and arm fields matching; this GO's digest; the frozen G0
   digest; the frozen library digests; the frozen registry digest of that benchmark and arm
   (`feasibility/object_registries.json`); at most two attempts; every attempt one grid per test input, each grid a
   rectangle of 1 to 30 rows and columns of integers 0 to 9; `fit` true exactly when attempts are present. A row whose
   stop is "arm_error" or "no_donor" is INVALID (a defect of the run, not an outcome). A static row whose child was
   killed by a signal must have exactly one retry row (run alone after the stage), which replaces it; the static
   children's other failure rows (child_timeout, child_failed, child_unreadable, child_error) are pre-registered
   no-answer outcomes, counted and reported. A run that is not complete and valid is reported as INCOMPLETE or INVALID
   with the lists, and nothing is scored (exit 2).
3. Scoring is exclusive: immediately before the first solution file is opened, a claim `SCORING_<GO digest>` is
   written (under runs/; under checks/kaggle_rehearsal/ in rehearsal mode), and scoring is refused when the claim or
   the completion marker `SCORED_<GO digest>` already exists. Only then are the solutions opened and the comparisons
   computed. The primary uses its raw exact p. The Holm family is the pre-registered list of thirteen secondaries,
   always complete: every secondary's decision uses its Holm-adjusted p (adjusted p < 0.05 and the clustered interval
   off zero), computed before any decision text. S4's decision is worded as which arm makes more wrong answers.
"""
import os
import sys

from ngb import env as E, gate as GT, score as SC, held as HB, phase2 as P2
from ngrow import data as DT, analysis as AN

ARMS = ("G0", "lib", "shuf", "static_lib", "obj", "obj_shuf", "static_obj", "construct", "construct_shuf",
        "static_construct")
ARC2_ARMS = ("G0", "lib", "obj", "construct", "static_lib", "static_obj", "static_construct")
NUMBER = {"G0": "arm 1", "lib": "arm 2", "shuf": "arm 3", "static_lib": "arm 4a", "obj": "arm 5", "obj_shuf": "arm 6",
          "static_obj": "arm 4b", "construct": "arm 7", "construct_shuf": "arm 8", "static_construct": "arm 4c"}
NAMES = {"G0": "G0 alone", "lib": "G0 plus the promoted library", "shuf": "G0 plus a shuffled library",
         "static_lib": "matched static search (library allowance)", "obj": "object-level growth, reuse",
         "obj_shuf": "reuse with a shuffled object registry", "static_obj": "matched static search (object allowance)",
         "construct": "task-local object construction", "construct_shuf": "construction with donor demonstrations",
         "static_construct": "matched static search (construction allowance)"}
SECONDARIES = (("S0_library_vs_G0", "lib", "G0", "held"),
               ("S1_library_vs_matched_static", "lib", "static_lib", "held"),
               ("S2_library_vs_shuffled_library", "lib", "shuf", "held"),
               ("S3_reuse_vs_shuffled_registry", "obj", "obj_shuf", "held"),
               ("S4_wrong_answers_library_vs_matched_static", "lib", "static_lib", "wrong"),
               ("S5_concept_arc_library_vs_G0", "lib", "G0", "concept_arc"),
               ("S5_mini_arc_library_vs_G0", "lib", "G0", "mini_arc"),
               ("S5_1d_arc_library_vs_G0", "lib", "G0", "1d_arc"),
               ("S6_arc_agi_2_library_vs_matched_static", "lib", "static_lib", "arc2"),
               ("S7_arc_agi_2_reuse_vs_matched_static", "obj", "static_obj", "arc2"),
               ("S8_construction_vs_matched_static", "construct", "static_construct", "held"),
               ("S9_construction_vs_donor_demonstrations", "construct", "construct_shuf", "held"),
               ("S10_arc_agi_2_construction_vs_matched_static", "construct", "static_construct", "arc2"))
ALPHA = 0.05
FAILURE_STOPS = ("child_timeout", "child_error", "child_failed", "child_unreadable", "child_killed")
DEFECT_STOPS = ("arm_error", "no_donor")
OWN_OUTPUTS = ("RESULTS.json", "REPORT.md")
REGISTRIES = os.path.join(E.STUDY, "feasibility", "object_registries.json")
MARKER_DIR = os.path.join(E.STUDY, "checks", "kaggle_rehearsal") if E.REHEARSAL else os.path.join(E.STUDY, "runs")
HELD_FROM = {"concept_arc": "A", "mini_arc": "A", "1d_arc": "B"}


class RunRefused(RuntimeError):
    pass


def valid_grid(g):
    return isinstance(g, (list, tuple)) and 1 <= len(g) <= 30 and all(isinstance(r, (list, tuple)) for r in g) \
        and 1 <= len(g[0]) <= 30 and all(len(r) == len(g[0]) for r in g) \
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)


def valid_preds(preds, n_test):
    """At most two attempts, each one grid per test input, each a valid grid."""
    if not isinstance(preds, (list, tuple)) or not 1 <= len(preds) <= 2:
        return False
    return all(isinstance(att, (list, tuple)) and len(att) == n_test and all(valid_grid(g) for g in att)
               for att in preds)


def verify_run(run_dir, go_sha, primary):
    """Manifest and stage identity of one run folder."""
    man_path = os.path.join(run_dir, "OUTPUT_MANIFEST.json")
    st_path = os.path.join(run_dir, "STAGES.json")
    if not os.path.exists(man_path) or not os.path.exists(st_path):
        raise RunRefused(f"{run_dir}: OUTPUT_MANIFEST.json or STAGES.json missing")
    man = E.load(man_path)
    bad = [rel for rel, h in man.items()
           if not os.path.exists(os.path.join(run_dir, rel)) or E.sha_file(os.path.join(run_dir, rel)) != h]
    extra = [rel for rel in P2.manifest(run_dir) if rel not in man and rel not in OWN_OUTPUTS]
    if bad or extra:
        raise RunRefused(f"{run_dir}: manifest mismatch (changed or missing {bad[:5]}; unlisted {extra[:5]})")
    st = E.load(st_path)
    if st.get("go_sha256") != go_sha:
        raise RunRefused(f"{run_dir}: STAGES.json carries another GO ({st.get('go_sha256')})")
    if st.get("primary") != primary:
        raise RunRefused(f"{run_dir}: STAGES.json carries another primary ({st.get('primary')})")
    if st.get("status") != "complete":
        raise RunRefused(f"{run_dir}: run status is {st.get('status')!r}, not complete")
    return st


def collect(run_dir, sub, arm, bench, expected, go_sha, frozen):
    """Validated {task: row} for one arm. expected: {task: number of test inputs}; frozen: the expected
    provenance {g0, library (digest or dict), registry}. Returns (rows, problems)."""
    d = os.path.join(run_dir, sub)
    rows, problems = {}, []
    files = sorted(p for p in os.listdir(d) if p == f"{arm}.jsonl" or p.startswith(f"{arm}.shard")) \
        if os.path.isdir(d) else []
    retry = HB.read_rows(os.path.join(d, f"{arm}.retry.jsonl")) if os.path.isdir(d) else []
    for p in files:
        for r in HB.read_rows(os.path.join(d, p)):
            t = r.get("task")
            tag = f"{bench}/{arm}/{t}"
            if t in rows:
                problems.append(f"INVALID duplicate row {tag} ({p})")
                continue
            if t not in expected:
                problems.append(f"INVALID unexpected task {tag}")
                continue
            if r.get("bench") != bench or r.get("arm") != arm:
                problems.append(f"INVALID provenance {tag}: bench or arm field differs")
                continue
            if r.get("go_sha256") != go_sha:
                problems.append(f"INVALID provenance {tag}: GO digest differs")
                continue
            if r.get("g0_sha256") != frozen["g0"]:
                problems.append(f"INVALID provenance {tag}: G0 digest differs")
                continue
            if r.get("library_sha256") != frozen["library"]:
                problems.append(f"INVALID provenance {tag}: library digest differs")
                continue
            if frozen["registry"] is not None and r.get("registry_sha256") != frozen["registry"]:
                problems.append(f"INVALID provenance {tag}: registry digest differs from the frozen one")
                continue
            if not all(k in r for k in HB.ROW_KEYS):
                problems.append(f"INVALID row {tag}: fields missing")
                continue
            if r.get("stop") in DEFECT_STOPS:
                problems.append(f"INVALID row {tag}: stop {r.get('stop')} is a defect of the run")
                continue
            fit, preds = r.get("fit"), r.get("preds")
            if fit is True and not valid_preds(preds, expected[t]):
                problems.append(f"INVALID row {tag}: fit without valid attempts (at most two, one valid grid per "
                                f"test input)")
                continue
            if fit is not True and preds not in (None, []):
                problems.append(f"INVALID row {tag}: attempts without a fit")
                continue
            if fit not in (True, False):
                problems.append(f"INVALID row {tag}: fit is neither true nor false")
                continue
            rows[t] = r
    retried = {}
    for r in retry:
        t = r.get("task")
        tag = f"{bench}/{arm}/{t}"
        if arm not in HB.STATIC:
            problems.append(f"INVALID retry row {tag}: only static arms are retried")
        elif t in retried:
            problems.append(f"INVALID duplicate retry row {tag}")
        elif t not in rows or rows[t].get("stop") != "child_killed":
            problems.append(f"INVALID retry row {tag}: its original row is not a killed child")
        elif r.get("go_sha256") != go_sha or r.get("bench") != bench or r.get("arm") != arm:
            problems.append(f"INVALID retry row {tag}: provenance differs")
        elif r.get("fit") is True and not valid_preds(r.get("preds"), expected[t]):
            problems.append(f"INVALID retry row {tag}: fit without valid attempts")
        else:
            retried[t] = r
    for t, r in list(rows.items()):
        if r.get("stop") == "child_killed":
            if t in retried:
                rows[t] = dict(retried[t], killed_then_retried=True)
            else:
                problems.append(f"INCOMPLETE killed child without its retry {bench}/{arm}/{t}")
    for t in expected:
        if t not in rows:
            problems.append(f"INCOMPLETE missing row {bench}/{arm}/{t}")
    return rows, problems


def decide(c, p, alpha=ALPHA):
    a, b = c["_a"], c["_b"]
    if c[f"tasks_only_{a}"] == c[f"tasks_only_{b}"]:
        return "tie"
    lo, hi = c["family_cluster_ci95"]
    if p < alpha and lo > 0:
        return f"{a} beats {b}"
    if p < alpha and hi < 0:
        return f"{b} beats {a}"
    return "inconclusive"


def s4_words(decision):
    """S4 compares wrong answers per task (library minus matched static): say which arm makes more wrong answers."""
    return {"w_a beats w_b": "the library makes more wrong answers than matched static search",
            "w_b beats w_a": "matched static search makes more wrong answers than the library"}.get(decision, decision)


def compare(rows, a, b):
    rows = [r for r in rows if r.get(a) is not None and r.get(b) is not None]
    if not rows:
        raise RunRefused(f"comparison {a} vs {b} has no rows")
    c = AN.compare(rows, a, b)
    c["_a"], c["_b"] = a, b
    c["decision_raw"] = c.pop("decision")
    return c


def totals(rows, arm):
    n = sum(r["n_outputs"] for r in rows)
    c = sum(r[arm] for r in rows)
    a = sum(r[arm + "_answered"] for r in rows)
    return {"tasks": len(rows), "outputs": n, "correct": c, "answered": a, "precision": round(c / a, 4) if a else None,
            "precision_wilson95": AN.wilson(c, a), "accuracy_wilson95": AN.wilson(c, n),
            "failure_rows": sum(1 for r in rows if r.get(arm + "_stop") in FAILURE_STOPS)}


def wrong_rows(tab, a, b):
    return [dict(r, w_a=r[a + "_wrong"], w_b=r[b + "_wrong"]) for r in tab]


def copies_match(c_dir, src_dirs):
    """Kernel C's packaged copies of A's and B's held rows must equal A's and B's files byte for byte."""
    problems = []
    held_c = os.path.join(c_dir, "held")
    if not os.path.isdir(held_c):
        return problems
    for d, _, files in os.walk(held_c):
        for f in files:
            rel = os.path.relpath(os.path.join(d, f), c_dir)
            b = rel.split(os.sep)[1]
            src = src_dirs.get(HELD_FROM.get(b))
            if src is None or src == c_dir:
                continue
            orig = os.path.join(src, rel)
            if not os.path.exists(orig) or E.sha_file(orig) != E.sha_file(os.path.join(d, f)):
                problems.append(f"INVALID kernel C's copy {rel} differs from kernel {HELD_FROM[b]}'s file")
    return problems


def main(a_dir, b_dir, c_dir):
    go_sha = GT.require_go()
    prim_name = GT.primary()
    claim = os.path.join(MARKER_DIR, f"SCORING_{go_sha}")
    marker = os.path.join(MARKER_DIR, f"SCORED_{go_sha}")
    if os.path.exists(claim) or os.path.exists(marker):
        raise RunRefused(f"scoring under this GO was already claimed ({claim} or {marker}); scoring is exclusive")
    dirs = {"A": os.path.abspath(a_dir), "B": os.path.abspath(b_dir), "C": os.path.abspath(c_dir)}
    run_dir, arc2_dir = dirs["C"], dirs["C"]
    rel = os.path.relpath(E.STUDY, E.REPO)
    reg = E.load(REGISTRIES)
    status = {"go_sha256": go_sha, "primary_rule_applied": prim_name, "problems": [], "kernels": dirs}
    for k, d in sorted(set((k, d) for k, d in dirs.items())):
        try:
            verify_run(d, go_sha, prim_name)
        except RunRefused as e:
            status["problems"].append(f"INVALID kernel {k}: {e}")
    status["problems"] += copies_match(dirs["C"], {"A": dirs["A"], "B": dirs["B"]})
    # rows, before any solution file is opened
    held_rows, n_test = {}, {}
    for b in DT.BENCHMARKS:
        tasks = DT.tasks(b)
        n_test[b] = {t: len(tasks[t]["test_inputs"]) for _, _, t in DT.half("held", (b,))}
        lib_hash = GT.frozen_hash(f"{rel}/feasibility/library/{b}/library.json")
        src_dir = dirs[HELD_FROM[b]]
        for a in ARMS:
            frozen = {"g0": reg["g0_sha256"], "library": lib_hash, "registry": reg["benchmarks"][b][a]["digest"]}
            rows, problems = collect(src_dir, os.path.join("held", b), a, b, n_test[b], go_sha, frozen)
            status["problems"] += problems
            held_rows[(b, a)] = rows
    from ngb import arc2 as A2
    tasks2 = A2.challenges()
    n_test2 = {t: len(v["test_inputs"]) for t, v in tasks2.items()}
    lib_dict = {b: GT.frozen_hash(f"{rel}/feasibility/library/{b}/library.json") for b in DT.BENCHMARKS}
    arc2_rows = {}
    for a in ARC2_ARMS:
        frozen = {"g0": reg["g0_sha256"], "library": lib_dict, "registry": reg["arc2"][a]["digest"]}
        rows, problems = collect(arc2_dir, "arc2", a, "arc_agi_2_eval", n_test2, go_sha, frozen)
        status["problems"] += problems
        arc2_rows[a] = rows
    if status["problems"]:
        status["status"] = "INVALID" if any(p.startswith("INVALID") for p in status["problems"]) else "INCOMPLETE"
        E.dump(os.path.join(run_dir, "RESULTS.json"), status)
        with E.open_write(os.path.join(run_dir, "REPORT.md")) as f:
            f.write(f"# Study B: run {status['status']}; nothing scored\n\n" +
                    "\n".join(f"- {p}" for p in status["problems"]) + "\n")
        print(f"{status['status']}: {len(status['problems'])} problems; nothing scored")
        raise SystemExit(2)
    with E.open_write(claim) as f:                 # the exclusive claim, before the first solution file opens
        f.write(f"claimed for {dirs}\n")
    killed = {f"{b}/{a}": sum(1 for r in held_rows[(b, a)].values() if r.get("killed_then_retried"))
              for b in DT.BENCHMARKS for a in HB.STATIC}
    # scoring (every arm complete and valid)
    tab = []
    for b in DT.BENCHMARKS:
        ids = [t for _, _, t in DT.half("held", (b,))]
        fam = {t: f for _, f, t in DT.half("held", (b,))}
        sol = SC.solutions(b, ids)
        for t in ids:
            g = held_rows[(b, "G0")][t]
            pf = g.get("partial_fit")
            r = {"bench": b, "family": fam[t], "task": t, "cluster": fam[t] if b != "mini_arc" else t,
                 "n_outputs": len(sol[t]), "localisable": not g["fit"] and bool(pf) and pf["cells_correct"] >= 1}
            for a in ARMS:
                row = held_rows[(b, a)][t]
                sc = SC.score_row(row["preds"] if row["fit"] else None, sol[t])
                r[a], r[a + "_answered"], r[a + "_wrong"] = sc["correct"], sc["answered"], sc["answered"] - sc["correct"]
                r[a + "_stop"] = row.get("stop")
            tab.append(r)
    sol2 = SC.arc2_solutions()
    a2 = []
    for t in sorted(sol2):
        r = {"bench": "arc_agi_2_eval", "task": t, "cluster": t, "n_outputs": len(sol2[t])}
        for a in ARC2_ARMS:
            row = arc2_rows[a][t]
            sc = SC.score_row(row["preds"] if row["fit"] else None, sol2[t])
            r[a], r[a + "_answered"], r[a + "_stop"] = sc["correct"], sc["answered"], row.get("stop")
        a2.append(r)
    res = {"status": "complete", "go_sha256": go_sha, "primary_rule_applied": prim_name,
           "totals": {a: totals(tab, a) for a in ARMS},
           "totals_by_benchmark": {b: {a: totals([r for r in tab if r["bench"] == b], a) for a in ARMS}
                                   for b in DT.BENCHMARKS},
           "localisable_stratum": sum(r["localisable"] for r in tab),
           "static_children_killed_then_retried": killed,
           "arc_agi_2": {"totals": {a: totals(a2, a) for a in ARC2_ARMS},
                         "exposure": "used in earlier development and gates of the project, and touched by the first "
                                     "dry run of this study (95 tasks' inputs, no solution opened); not a fresh test"}}
    prim = compare(tab, "obj", "static_obj") if prim_name == "arm5_vs_arm4" else compare(tab, "lib", "G0")
    prim["decision"] = decide(prim, prim["exact_mcnemar_p"])
    res["primary"] = prim
    sec = {}
    for name, x, y, pop in SECONDARIES:
        if pop == "held":
            sec[name] = compare(tab, x, y)
        elif pop == "wrong":
            sec[name] = compare(wrong_rows(tab, x, y), "w_a", "w_b")
        elif pop == "arc2":
            sec[name] = compare(a2, x, y)
        else:
            sec[name] = compare([r for r in tab if r["bench"] == pop], x, y)
    adj = AN.holm({k: v["exact_mcnemar_p"] for k, v in sec.items()})
    for k, v in sec.items():
        v["holm_p"] = adj[k]
        v["decision"] = decide(v, adj[k])            # the decision rule applied to the adjusted p
        if k.startswith("S4_"):
            v["decision"] = s4_words(v["decision"])
    res["secondary"] = sec
    res["holm_family_size"] = len(sec)
    desc = {f"{x}_vs_{y}": compare(tab, x, y) for x, y in
            (("static_lib", "G0"), ("obj", "G0"), ("shuf", "G0"), ("lib", "obj"), ("obj_shuf", "G0"), ("static_obj", "G0"),
             ("construct", "G0"), ("construct", "obj"), ("construct_shuf", "G0"), ("static_construct", "G0"))}
    loc = [r for r in tab if r["localisable"]]
    desc["localisable_stratum"] = {f"{x}_vs_{y}": compare(loc, x, y) for x, y in
                                   (("lib", "G0"), ("lib", "static_lib"), ("obj", "static_obj"),
                                    ("construct", "static_construct"))} if loc else {}
    desc["by_family"] = {}
    for x, y in (("lib", "G0"), ("obj", "G0"), ("obj", "static_obj"), ("construct", "G0")):
        desc["by_family"][f"{x}_vs_{y}"] = {
            f"{b}/{f}": compare([r for r in tab if r["bench"] == b and r["family"] == f], x, y)
            for b in DT.BENCHMARKS for f in sorted({r["family"] for r in tab if r["bench"] == b})}

    def mark(d):
        for v in d.values():
            if isinstance(v, dict) and "exact_mcnemar_p" in v:
                v["decision"] = "descriptive (no decision weight)"
            elif isinstance(v, dict):
                mark(v)
    mark(desc)
    res["descriptive"] = desc
    E.dump(os.path.join(run_dir, "RESULTS.json"), res)
    L = ["# Library-transfer and object-growth test (study B): results (written by ngb/report.py)", "",
         f"Status: complete. Primary rule applied (from the GO): {prim_name}. Held tasks: {len(tab)}; localisable "
         f"G0 failures: {res['localisable_stratum']}. Holm family: {len(sec)} secondaries.", "",
         "| arm | correct outputs | answered | precision | failure rows |", "|---|---|---|---|---|"]
    for a in ARMS:
        q = res["totals"][a]
        L.append(f"| {NUMBER[a]}: {NAMES[a]} | {q['correct']} | {q['answered']} | {q['precision']} | {q['failure_rows']} |")
    L += ["", f"**Primary ({prim['_a']} vs {prim['_b']}): {prim['decision']}**; exact p = {prim['exact_mcnemar_p']}, "
          f"total difference {prim['sum_difference']}, family-clustered 95% interval {prim['family_cluster_ci95']}.",
          "", "Secondary (decisions at the Holm-adjusted p):", ""]
    for k, v in sec.items():
        L.append(f"- {k}: {v['decision']}; raw p = {v['exact_mcnemar_p']}, Holm p = {v['holm_p']}, difference "
                 f"{v['sum_difference']}, interval {v['family_cluster_ci95']}")
    with E.open_write(os.path.join(run_dir, "REPORT.md")) as f:
        f.write("\n".join(L) + "\n")
    with E.open_write(marker) as f:
        f.write(f"scored {run_dir} and {arc2_dir}\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:])
