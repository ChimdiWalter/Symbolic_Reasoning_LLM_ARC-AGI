"""Item-2 v1.7 compiler acceptance test (protocol section 14). Run once,
after the freeze and the one review. Refuses to run on any freeze problem.

Fixtures: seed 830,000,000 + 100k, families in the frozen order, the first
6 tasks that pass the frozen filter (>= 2 blocks; 8 demonstrations; exact
scoped fit on the 7 training pairs; no exact single-block K fit; scoped
leave-one-out re-derivation of every training pair). The filter reads the
schema and the 7 training pairs only, never the held-out pair or the engine.
For each task: compile twice, reload, witness separation, paired ablation
with the held-out pair, adaptive leave-one-out with recompilation in every
fold. Writes outputs/tti/v17_acceptance_report.json and the marker
logs/V17_ACCEPTANCE_DONE.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v15_sel as S                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402

MANIFEST = os.path.join(HERE, "outputs", "tti", "constructive_extension_compiler_v17_manifest.json")
OUT = os.path.join(HERE, "outputs", "tti", "v17_acceptance_report.json")
SEED_BASE = 830_000_000
N_TASKS = 6
MAX_TRIES = 2000


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
    if L.runtime_versions() != man["runtime_versions"]:
        p.append("runtime_versions")
    if X.k_identity() != man["k_identity"]:
        p.append("k_identity")
    return p, man


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


def carries_name(program, prod) -> bool:
    if program is None:
        return False
    d = _as_dict(program)
    while d.get("program_class") == "framed":
        d = d["inner"]
    return d.get("concept") == prod["name"]


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


def run_task(n, t, M):
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
    row["ablation"] = {"verdict": ab["verdict"], "with_accepted": ab["with"]["accepted"],
                       "with_uses": ab["with_uses_extension"],
                       "with_heldout_exact": ab["with"].get("heldout_exact"),
                       "without_accepted": ab["without"]["accepted"],
                       "without_heldout_exact": ab["without"].get("heldout_exact"),
                       "with_program": ab["with"]["program"]}
    residue = int(ab["without"]["accepted"] and carries_name(ab["without"]["program"], p1))
    direct_bad = 0
    if ab["with_uses_extension"]:
        row["ablation"]["direct_agrees"] = direct_agrees(ab["with"]["program"], t["train"], t["held"],
                                                         ab["with"].get("heldout_exact"))
        direct_bad += int(not row["ablation"]["direct_agrees"])

    runs = []

    def solve(pairs, prods):
        r = X.run_reasoner(pairs, prods)
        runs.append(r)
        return r
    loo = X.adaptive_loo(t["train"], lambda fold, s=t["schema"]: X.compile_extension(X.make_input(s)),
                         solve=solve)
    for f, r in zip([f for f in loo["folds"] if f.get("status") == "RUN"], runs):
        if f["uses_extension"]:
            i = f["fold"]
            fold = [t["train"][j] for j in range(len(t["train"])) if j != i]
            f["direct_agrees"] = direct_agrees(r["program"], fold, t["train"][i], f["heldout_exact"])
            direct_bad += int(not f["direct_agrees"])
    row["adaptive_loo"] = {"passed": loo["passed"], "folds": loo["folds"]}
    row["attribution"] = {"residue": residue, "direct_disagreements": direct_bad}
    return row


def main():
    problems, man = freeze_problems()
    if problems:
        raise SystemExit(f"freeze problems, refusing: {problems}")
    M, _ = X._meta()
    started = time.time()
    tasks = fixtures()
    rows, restoration_failures = [], 0
    if len(tasks) < N_TASKS:
        outcome, s = "NO_VERDICT_FIXTURE_SHORTFALL", {}
    else:
        snap0 = X.state_snapshot()
        for n, t in enumerate(tasks):
            try:
                rows.append(run_task(n, t, M))
            except X.CompileError as exc:
                rows.append({"seed": t["seed"], "family": t["family"], "error": exc.code,
                             "detail": exc.detail})
                restoration_failures += int(exc.code == "RESTORATION_FAILURE")
        snap1 = X.state_snapshot()
        ok = [r for r in rows if "error" not in r]
        complete = len(ok) == N_TASKS
        s = {"S1": complete and all(r["S1_compiles_deterministic_reload"] for r in ok),
             "S2": restoration_failures == 0 and snap0 == snap1,
             "S3": complete and all(r["attribution"]["residue"] == 0
                                    and r["attribution"]["direct_disagreements"] == 0 for r in ok),
             "S4": sum(1 for r in ok if r["ablation"]["verdict"] == "EXTENSION_NECESSARY_AND_USED"
                       and r["ablation"]["with_heldout_exact"]) >= 5,
             "S5": sum(1 for r in ok if r["adaptive_loo"]["passed"]) >= 5,
             "S6": complete and all(r["witness"]["status"] == "SEPARATED" for r in ok)}
        if not (s["S1"] and s["S2"] and s["S3"] and s["S6"]):
            outcome = "COMPILER_DEFECTIVE"
        elif not (s["S4"] and s["S5"]):
            outcome = "COMPILER_INTEGRATION_INCOMPLETE"
        else:
            outcome = "COMPILER_ACCEPTED"
    report = {"outcome": outcome, "conditions": s, "tasks": rows, "n_fixtures": len(tasks),
              "seed_base": SEED_BASE, "manifest_sha256": sha(MANIFEST), "k_identity": X.k_identity(),
              "seconds": round(time.time() - started, 1)}
    with open(OUT, "w") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    with open(os.path.join(HERE, "logs", "V17_ACCEPTANCE_DONE"), "w") as handle:
        handle.write(outcome + "\n")
    print(json.dumps({"outcome": outcome, "conditions": s, "seconds": report["seconds"]}))


if __name__ == "__main__":
    main()
