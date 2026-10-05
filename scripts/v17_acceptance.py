"""Item-2 v1.7 compiler acceptance test (protocol section 14, as amended by
erratum 01). Run once, after the freeze and the one review, through
scripts/run_v17_acceptance.sh. Refuses on any freeze or environment problem,
and refuses to start a second time.

Fixtures: seed 830,000,000 + 100k, families in the frozen order, the first
6 tasks that pass the frozen filter (>= 2 blocks; 8 demonstrations; exact
scoped fit on the 7 training pairs; no exact single-block K fit; scoped
leave-one-out re-derivation of every training pair). The filter reads the
schema and the 7 training pairs only, never the held-out pair or the engine.
For each task: compile twice, reload, witness separation, paired ablation
with the held-out pair, a supplementary K* arm at 3x budget, adaptive
leave-one-out with recompilation in every fold.

Writes logs/v17/acceptance_start.json at start, one line per finished task
to outputs/tti/v17_acceptance_rows.jsonl, then
outputs/tti/v17_acceptance_report.json and the marker
logs/V17_ACCEPTANCE_DONE.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import traceback

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v15_sel as S                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402

MANIFEST = os.path.join(HERE, "outputs", "tti", "constructive_extension_compiler_v17_manifest.json")
OUT = os.path.join(HERE, "outputs", "tti", "v17_acceptance_report.json")
ROWS = os.path.join(HERE, "outputs", "tti", "v17_acceptance_rows.jsonl")
START = os.path.join(HERE, "logs", "v17", "acceptance_start.json")
MARKER = os.path.join(HERE, "logs", "V17_ACCEPTANCE_DONE")
SEED_BASE = 830_000_000
N_TASKS = 6
MAX_TRIES = 2000
BASELINE_3X_BUDGET_S = 24.0


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def freeze_problems():
    with open(MANIFEST) as handle:
        man = json.load(handle)
    p = []
    with open(MANIFEST + ".sha256") as handle:
        if handle.read().split()[0] != sha(MANIFEST):
            p.append("manifest")
    if sha(os.path.join(HERE, man["protocol_doc"])) != man["protocol_doc_sha256"]:
        p.append("protocol")
    for rel, d in man["implementation_sha256"].items():
        if sha(os.path.join(HERE, rel)) != d:
            p.append(rel)
    for name, root in L.dependency_roots(HERE).items():
        if L.tree_digest(root) != man["dependency_tree_sha256"][name]:
            p.append(f"dependency:{name}")
    for path, d in man["external_file_sha256"].items():
        if not os.path.exists(path) or sha(path) != d:
            p.append(f"external:{os.path.basename(path)}")
    if L.runtime_versions() != man["runtime_versions"]:
        p.append("runtime_versions")
    if X.k_identity() != man["k_identity"]:
        p.append("k_identity")
    return p, man


def conditions_now() -> dict:
    return {"environment": L.environment_snapshot(),
            "hash_randomization": sys.flags.hash_randomization,
            "threads": {v: os.environ.get(v) for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
                                                       "MKL_NUM_THREADS")},
            "loadavg": [round(x, 2) for x in os.getloadavg()], "cpus": os.cpu_count()}


def fixtures():
    """The frozen filter. Reads the schema and the 7 training pairs only."""
    import numpy as np
    from cora_tti import constructive_dataset as CD
    from cora_tti import scoped_slot_fitting as SF
    M, MI = X._meta()
    out = []
    for k in range(MAX_TRIES):
        seed = SEED_BASE + 100 * k
        fam = S.FAMILIES[k % len(S.FAMILIES)]
        schema = CD.sample_target(seed, S.G.parse_family(fam))
        if sum(1 for st in schema[1] if st[0] == "Paint") < 2:
            continue
        gs = [seed * 97 + i for i in range(30)]
        concrete = CD.instantiate_tables(schema, [CD.generate_grid(s) for s in gs[:6]])
        if concrete is None:
            continue
        pairs, _ = CD.render_demonstrations(concrete, gs, min_demos=6)
        if len(pairs) < 8:
            continue
        train, held = pairs[:7], pairs[7]
        f, _ = SF.fit_induced_occurrences(schema, train)
        if f is None or SF.base_search_with_scoped_fitter(train)["exact"]:
            continue
        ok = True
        for i in range(len(train)):
            sub = [p for j, p in enumerate(train) if j != i]
            g, _ = SF.fit_induced_occurrences(schema, sub)
            o = None if g is None else M.evaluate(g, train[i][0], MI.descriptors)
            if o is None or not np.array_equal(o, train[i][1]):
                ok = False
                break
        if not ok:
            continue
        out.append({"seed": seed, "family": fam, "schema": schema, "train": train, "held": held})
        if len(out) >= N_TASKS:
            break
    return out


def fresh_process_sha(schema_json):
    code = ("import sys,json,hashlib; sys.path.insert(0, %r); "
            "from cora_arc2026 import v17_compiler as X; M,_=X._meta(); "
            "ast=M.ast_from_json(json.loads(sys.argv[1])); "
            "print(hashlib.sha256(X.serialize(X.compile_extension(X.make_input(ast)))).hexdigest())" % HERE)
    env = dict(os.environ, PYTHONPATH=L.TTI_ROOT, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", code, json.dumps(schema_json)],
                         capture_output=True, text=True, env=env, timeout=900)
    return out.stdout.strip().splitlines()[-1] if out.stdout.strip() else None


def _as_dict(program):
    if isinstance(program, dict):
        return program
    if isinstance(program, str):
        return json.loads(program)
    return program.to_dict()


def names_in(program) -> set:
    """Every concept name anywhere in a program tree (any wrapper)."""
    found = set()

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("concept"), str):
                found.add(node["concept"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    if program is not None:
        walk(_as_dict(program))
    return found


def top_level(program) -> dict:
    d = _as_dict(program)
    while d.get("program_class") == "framed":
        d = d["inner"]
    return d


def direct_outputs(program, grids):
    """Execute an attributed winner by kernel semantics outside the engine:
    the engine's own dihedral helpers for frames, then meta_ast.evaluate."""
    import numpy as np
    from geocat_arc.object_reasoning.growth import _dihedral_inverse, _dihedral_transform
    M, MI = X._meta()
    d = _as_dict(program)
    frames = []
    while d.get("program_class") == "framed":
        frames.append((int(d["frame"][0]), bool(d["frame"][1])))
        d = d["inner"]
    ast = M.ast_from_json(d["ast"])
    outs = []
    for g in grids:
        a = np.asarray(g)
        for k, flip in frames:
            a = _dihedral_transform(a, k, flip)
        o = M.evaluate(ast, a, MI.descriptors)
        if o is not None:
            for k, flip in reversed(frames):
                o = _dihedral_inverse(o, k, flip)
        outs.append(o)
    return outs


def direct_agrees(program, train, held, engine_heldout_exact) -> bool:
    """The attributed program reproduces every training output of its run
    and agrees with the engine on held-out exactness."""
    import numpy as np
    outs = direct_outputs(program, [p[0] for p in train] + [held[0]])
    train_ok = all(o is not None and np.array_equal(o, np.asarray(p[1])) for o, p in zip(outs, train))
    held_ok = outs[-1] is not None and np.array_equal(outs[-1], np.asarray(held[1]))
    return bool(train_ok and held_ok == bool(engine_heldout_exact))


def audit_with_e(program, accepted, uses, prod, train, held, engine_heldout_exact) -> dict:
    """Attribution audit of a K* + {e} run. A top-level computed pattern
    carrying e's name that fails the structure test is a label anomaly; e
    nested inside another wrapper is recorded and not credited."""
    if not accepted:
        return {"direct_agrees": None, "label_anomaly": False, "nested_use": False}
    top = top_level(program)
    anomaly = (top.get("program_class") == "computed_pattern" and top.get("concept") == prod["name"]
               and not uses)
    nested = prod["name"] in names_in(program) and top.get("concept") != prod["name"]
    agrees = direct_agrees(program, train, held, engine_heldout_exact) if uses else None
    return {"direct_agrees": agrees, "label_anomaly": bool(anomaly), "nested_use": bool(nested)}


def run_task(n, t, M):
    load0 = [round(x, 2) for x in os.getloadavg()]
    row = {"seed": t["seed"], "family": t["family"],
           "blocks": sum(1 for st in t["schema"][1] if st[0] == "Paint")}
    p1 = X.compile_extension(X.make_input(t["schema"]))
    p2 = X.compile_extension(X.make_input(t["schema"]))
    b = X.serialize(p1)
    row["name"] = p1["name"]
    s1 = b == X.serialize(p2) and X.load(b) == p1
    if n == 0:
        row["fresh_process_identical"] = (fresh_process_sha(M.ast_to_json(t["schema"]))
                                          == hashlib.sha256(b).hexdigest())
        s1 = s1 and row["fresh_process_identical"]
    row["S1_compiles_deterministic_reload"] = bool(s1)
    row["witness"] = X.witness_separation(p1, t["train"])

    ab = X.paired_ablation(t["train"], p1, heldout=t["held"])
    row["ablation"] = {"verdict": ab["verdict"], "with_uses": ab["with_uses_extension"],
                       "with": ab["with"], "without": ab["without"]}
    residue = int(p1["name"] in names_in(ab["without"]["program"]))
    audits = [audit_with_e(ab["with"]["program"], ab["with"]["accepted"], ab["with_uses_extension"],
                           p1, t["train"], t["held"], ab["with"].get("heldout_exact"))]
    row["ablation"]["audit"] = audits[0]

    base3 = X.run_reasoner(t["train"], (), budget_s=BASELINE_3X_BUDGET_S)
    residue += int(p1["name"] in names_in(base3["program"]))
    row["baseline_3x"] = {"budget_s": BASELINE_3X_BUDGET_S, "accepted": base3["accepted"],
                          "heldout_exact": X.predict_exact(base3, *t["held"]),
                          "seconds": base3["seconds"], "program": base3["program"],
                          "engine_dir_removed": base3["engine_dir_removed"]}

    runs = []

    def solve(pairs, prods):
        r = X.run_reasoner(pairs, prods)
        runs.append(r)
        return r
    loo = X.adaptive_loo(t["train"], lambda fold, s=t["schema"]: X.compile_extension(X.make_input(s)),
                         solve=solve)
    for f, r in zip([f for f in loo["folds"] if f.get("status") == "RUN"], runs):
        i = f["fold"]
        fold = [t["train"][j] for j in range(len(t["train"])) if j != i]
        f["audit"] = audit_with_e(r["program"], r["accepted"], f["uses_extension"], p1, fold,
                                  t["train"][i], f["heldout_exact"])
        f["seconds"], f["program"] = r["seconds"], r["program"]
        audits.append(f["audit"])
    row["adaptive_loo"] = {"passed": loo["passed"], "folds": loo["folds"]}
    row["attribution"] = {"residue": residue,
                          "direct_disagreements": sum(1 for a in audits if a["direct_agrees"] is False),
                          "label_anomalies": sum(1 for a in audits if a["label_anomaly"]),
                          "nested_uses": sum(1 for a in audits if a["nested_use"])}
    row["loadavg"] = {"start": load0, "end": [round(x, 2) for x in os.getloadavg()]}
    return row


def append_row(row):
    with open(ROWS, "a") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main():
    for path in (OUT, ROWS, START, MARKER):
        if os.path.exists(path):
            raise SystemExit(f"refusing: {os.path.relpath(path, HERE)} exists; the acceptance test runs once")
    env_problems = X.kstar_environment_problems()
    if env_problems:
        raise SystemExit(f"environment problems, refusing: {env_problems}")
    problems, man = freeze_problems()
    if problems:
        raise SystemExit(f"freeze problems, refusing: {problems}")
    M, _ = X._meta()
    started = time.time()
    with open(START, "w") as handle:
        handle.write(json.dumps({"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "pid": os.getpid(), "manifest_sha256": sha(MANIFEST),
                                 "k_identity": X.k_identity(), **conditions_now()},
                                indent=1, sort_keys=True) + "\n")
    rows, restoration_failures, unexpected, s, tasks = [], 0, [], {}, []
    try:
        tasks = fixtures()
    except Exception:                                          # noqa: BLE001
        unexpected.append({"stage": "fixtures", "traceback": traceback.format_exc()})
    if not unexpected and len(tasks) < N_TASKS:
        outcome = "NO_VERDICT_FIXTURE_SHORTFALL"
    elif unexpected:
        outcome = "NO_VERDICT_RUN_ERROR"
    else:
        snap0 = X.state_snapshot()
        for n, t in enumerate(tasks):
            try:
                row = run_task(n, t, M)
            except X.CompileError as exc:
                row = {"seed": t["seed"], "family": t["family"], "error": exc.code, "detail": exc.detail}
                restoration_failures += int(exc.code == "RESTORATION_FAILURE")
            except Exception as exc:                           # noqa: BLE001
                row = {"seed": t["seed"], "family": t["family"], "error": "UNEXPECTED",
                       "exception": type(exc).__name__, "traceback": traceback.format_exc()}
                unexpected.append({"stage": f"task {n}", "exception": type(exc).__name__})
            rows.append(row)
            append_row(row)
        snap1 = X.state_snapshot()
        ok = [r for r in rows if "error" not in r]
        complete = len(ok) == N_TASKS
        s = {"S1": complete and all(r["S1_compiles_deterministic_reload"] for r in ok),
             "S2": restoration_failures == 0 and snap0 == snap1,
             "S3": complete and all(r["attribution"]["residue"] == 0
                                    and r["attribution"]["direct_disagreements"] == 0
                                    and r["attribution"]["label_anomalies"] == 0 for r in ok),
             "S4": sum(1 for r in ok if r["ablation"]["verdict"] == "EXTENSION_NECESSARY_AND_USED"
                       and r["ablation"]["with"].get("heldout_exact")) >= 5,
             "S5": sum(1 for r in ok if r["adaptive_loo"]["passed"]) >= 5,
             "S6": complete and all(r["witness"]["status"] == "SEPARATED" for r in ok)}
        if unexpected:
            outcome = "NO_VERDICT_RUN_ERROR"
        elif not (s["S1"] and s["S2"] and s["S3"] and s["S6"]):
            outcome = "COMPILER_DEFECTIVE"
        elif not (s["S4"] and s["S5"]):
            outcome = "COMPILER_INTEGRATION_INCOMPLETE"
        else:
            outcome = "COMPILER_ACCEPTED"
    supplementary = {
        "necessary_at_3x_baseline": sum(1 for r in rows if "error" not in r
                                        and r["ablation"]["verdict"] == "EXTENSION_NECESSARY_AND_USED"
                                        and not r["baseline_3x"]["accepted"]),
        "nested_uses": sum(r["attribution"]["nested_uses"] for r in rows if "error" not in r),
        "k_programs_fitted": [r["witness"].get("k_programs_fitted") for r in rows if "error" not in r]}
    report = {"outcome": outcome, "conditions": s, "supplementary": supplementary, "tasks": rows,
              "n_fixtures": len(tasks), "unexpected": unexpected, "seed_base": SEED_BASE,
              "manifest_sha256": sha(MANIFEST), "k_identity": X.k_identity(),
              "conditions_at_end": conditions_now(), "seconds": round(time.time() - started, 1)}
    with open(OUT, "w") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    with open(MARKER, "w") as handle:
        handle.write(outcome + "\n")
    print(json.dumps({"outcome": outcome, "conditions": s, "supplementary": supplementary,
                      "seconds": report["seconds"]}))


if __name__ == "__main__":
    main()
