"""The per-task policy for arms A-E (protocol sections 2-4, Amendment 1).

  python -m cora_fhr.measure --corpus c4_dev [--arms A,B,C,D,E] [--workers 4] [--keys k1,k2]
      -> outputs/cora_fhr/rows_<corpus>.jsonl   (solver side: no answer is read here)

The reasoner is harness.object_layer.run_object_task, the sealed v23 object layer:
- the frozen library and learned verbs (cora_pilot.native.prepare_object_dir);
- the sealed flags;
- the 90 s budget and 7 frames at 45 s.

As in the failure funnel, every native deadline runs on this worker's process CPU time
(cora_funnel.run.cpu_clock), and the harness cap is a CPU-time timer with a wall-clock hang guard.

Arms:
- A frozen;
- B matched search (budgets x f_B);
- C failure-blind (native views, nearest-object attribution);
- D shuffled (the donor task's authentic instances);
- E authentic (native's own memorized growth).

C, D and E construct, select the canonical-first proposal, check for a tie (Amendment 1), install it into
the unchanged engine, require native acceptance and use of the extension, and run the adaptive
leave-one-out. Every fold rebuilds the evidence and the extension from its own demonstrations.
A construction arm commits only where A has no certified answer; otherwise it commits A's output.
"""
import argparse
import contextlib
import json
import multiprocessing as mp
import os
import signal
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_funnel import run as FR                                     # noqa: E402  (sealed flags, CPU clock)

OUT = os.path.join(HERE, "outputs", "cora_fhr")
BUDGET_S, FRAME_S = 90.0, 45.0
EXTRACT_CAP_S = 450
F_B_PROVISIONAL = 3.0                     # development only; the frozen f_B is set from the development run


class _Cap(BaseException):
    """BaseException, as harness._HardTimeout: native code is full of `except Exception`."""


def _raise(signum, frame):                                            # noqa: ARG001
    raise _Cap()


@contextlib.contextmanager
def cpu_cap(seconds):
    signal.signal(signal.SIGPROF, _raise)
    signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_PROF, float(seconds))
    signal.alarm(int(8 * seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
        signal.alarm(0)


def _grid(x):
    if x is None:
        return None
    try:
        a = np.asarray(x, dtype=int)
    except (TypeError, ValueError):
        return None
    return a.tolist() if a.ndim == 2 and a.size else None


def object_run(task_id, train, tests, engine_dir, ext=None, budget_s=BUDGET_S):
    """One sealed object-layer run with `ext` installed (or nothing). Returns (record, program JSON or None)."""
    import geocat_arc.object_reasoning.engine as E
    from cora_fhr import bridge as BR
    from cora_reach.measure import clear_engine_caches, psha
    from harness.object_layer import run_object_task
    os.environ["ARC_DIHEDRAL_FRAMES"] = str(int(FRAME_S * budget_s / BUDGET_S))
    out = {"installed": ext["name"] if ext else None, "budget_s": budget_s, "accepted": False, "program_sha": None,
           "predictions": [None] * len(tests), "timeout": False, "error": None}
    seen, orig = [], E.ObjectReasoningEngine.solve

    def solve(self, tid, pairs):
        r = orig(self, tid, pairs)
        seen.append(r)
        return r
    program = None
    clear_engine_caches()
    c0, t0 = time.process_time(), time.time()
    E.ObjectReasoningEngine.solve = solve
    try:
        with contextlib.ExitStack() as stack:
            if ext is not None:
                stack.enter_context(BR.installed(ext))
            task = {"train": [{"input": np.asarray(a).tolist(), "output": np.asarray(b).tolist()} for a, b in train],
                    "test": [{"input": np.asarray(t).tolist()} for t in tests]}
            cap = budget_s + 15 + 7 * int(os.environ["ARC_DIHEDRAL_FRAMES"]) + 30
            try:
                with cpu_cap(cap):
                    res = run_object_task(task_id, task, None, out_dir=engine_dir, budget_s=budget_s)
            except _Cap:
                res = {"solved": False, "error": "hard_cap"}
                out["timeout"] = True
            sol = seen[-1].solution if seen else None
            accepted = bool(res.get("solved")) and sol is not None
            program = sol.program_json if accepted else None
            out.update(accepted=accepted, program_sha=psha(program), error=res.get("error"),
                       failure_stage=res.get("failure_stage"))
            if accepted:
                preds = res.get("predictions") or []
                out["predictions"] = [_grid(preds[i]) if i < len(preds) else None for i in range(len(tests))]
            if ext is not None:
                out["uses"] = bool(accepted and BR.uses(program, ext))
    finally:
        E.ObjectReasoningEngine.solve = orig
        os.environ["ARC_DIHEDRAL_FRAMES"] = str(int(FRAME_S))
    if ext is not None:
        out["restored"] = BR.restored()
    out["cpu_s"] = round(time.process_time() - c0, 2)
    out["wall_s"] = round(time.time() - t0, 2)
    return out, program


def authentic_raw(train, engine_dir):
    from cora_fhr import construct as CS
    try:
        with cpu_cap(EXTRACT_CAP_S):
            return CS.authentic_records(train, engine_dir, BUDGET_S), None
    except _Cap:
        return [], "extract_cap"


def groups_for(arm, train, dirs, donor_raw):
    from cora_fhr import construct as CS
    if arm == "E":
        raw, why = authentic_raw(train, dirs["extract"])
        return CS.group_reach_records(raw), why
    if arm == "C":
        g, why = CS.blind_groups(train)
        return g, why
    if arm == "D":
        return CS.group_reach_records(donor_raw or []), None
    if arm == "C2":                                                    # C' (proposed Amendment 2)
        try:
            with cpu_cap(EXTRACT_CAP_S):
                raw = CS.native_all_records(train, dirs["extract"], BUDGET_S)
        except _Cap:
            return {}, "extract_cap"
        return CS.group_reach_records(raw), None
    raise ValueError(arm)


def ambiguous(prop, groups, inputs, preds=None):
    """Amendment 1 item 2 (tie abstention). Among the fitting expressions of the selected one's complexity
    class, any that adds different cells to an object the committed prediction grows is a tie the
    demonstrations do not resolve. The objects come from native's segmentation of the unlabelled input in the
    selected view. An object is "grown" when the prediction changes a cell of the selected operator's
    footprint. With preds=None every object counts. Reads inputs and CORA's own prediction only."""
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import SegmentationVariant, cell_colors_of
    from geocat_arc.perception.grid import Grid
    from cora_fhr import ggrow as GG
    insts = [(O, A, G) for O, A, G, _d, _c in groups[prop["view"]][:64]]
    first = GG.from_str(prop["ext"]["expr"])
    same = [e for e in GG.expressions() if e[0] == first[0]]
    ctx = [GG.Ctx(O, G) for O, _A, G in insts]
    fits = [e for e in same if all(GG.evaluate(e, x) == set(A) for x, (_O, A, _G) in zip(ctx, insts))]
    view = SegmentationVariant(prop["view"])
    for k, t in enumerate(inputs):
        ta = np.asarray(t, dtype=int)
        changed = None
        if preds is not None and preds[k] is not None and np.asarray(preds[k]).shape == ta.shape:
            pa = np.asarray(preds[k], dtype=int)
            changed = {(int(r), int(c)) for r, c in zip(*np.nonzero(pa != ta))}
        g = Grid(ta)
        for o in S.segment(g, view, S.background_for(g, view)):
            cc = cell_colors_of(o)
            if not cc:
                continue
            x = GG.Ctx(cc, ta)
            ref = GG.evaluate(first, x)
            if changed is not None and not (ref & changed):
                continue                                              # an object the prediction does not grow
            if any(GG.evaluate(e, x) != ref for e in fits):
                return True, len(fits)
    return False, len(fits)


def construct_and_check(arm, key, train, inputs, dirs, donor_raw):
    """Evidence -> proposals -> selection -> tie check. Returns (record, ext or None)."""
    from cora_fhr import construct as CS
    rec = {"arm": arm}
    t0 = time.process_time()
    groups, why = groups_for(arm, train, dirs, donor_raw)
    rec["evidence"] = {"views": {v: len(x) for v, x in groups.items()}, "why_empty": why}
    prop = CS.propose(groups)
    rec["proposals"] = [{k: v for k, v in p.items() if k != "ext"} | {"name": p["ext"]["name"], "expr": p["ext"]["expr"]}
                        for p in prop["proposals"]]
    rec["construct_cpu_s"] = round(time.process_time() - t0, 2)
    if not prop["proposals"]:
        rec["outcome"] = "NO_PROPOSAL"
        return rec, None
    sel = prop["proposals"][0]
    rec["selected"] = {"name": sel["ext"]["name"], "pretty": sel["pretty"], "view": sel["view"],
                       "novelty": sel["novelty"]}
    rec["_sel"], rec["_groups"] = sel, groups                          # for the tie check; stripped before writing
    return rec, sel["ext"]


def tie_check(rec, inputs, preds):
    tie, n_same = ambiguous(rec.pop("_sel"), rec.pop("_groups"), inputs, preds)
    rec["selected"]["same_class_fitting"] = n_same
    return tie


FOLD_GATE = os.environ.get("CORA_FHR_FOLD_GATE", "native")      # "native" = the frozen nested semantics


@contextlib.contextmanager
def fold_semantics():
    """Frozen semantics ("native"): a fold succeeds only if native ACCEPTS on the fold's demonstrations, which
    nests native's own LOO inside the adaptive LOO. The development what-if ("ungated", proposed as Amendment 2;
    never used for a counted result without the user's decision) instead takes native's train-perfect program
    on the fold's demonstrations (OBJECT_GATE_OFF, native's own E2 switch). Native's own LOO folds use the same
    ungated search."""
    if FOLD_GATE != "ungated":
        yield
        return
    prev = os.environ.get("OBJECT_GATE_OFF")
    os.environ["OBJECT_GATE_OFF"] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("OBJECT_GATE_OFF", None)
        else:
            os.environ["OBJECT_GATE_OFF"] = prev


def loo(arm, key, train, full_ext, dirs, donor_raw):
    folds = []
    for i in range(len(train)):
        rest = [p for j, p in enumerate(train) if j != i]
        a, b = train[i]
        f, ext = construct_and_check(arm, f"{key}_fold{i}", rest, [a], dirs, donor_raw)
        f.update(fold=i, same_as_full=bool(ext and full_ext and ext["name"] == full_ext["name"]))
        if ext is None:
            f["class"] = f.get("outcome")
            folds.append(f)
            continue
        with fold_semantics():
            run, _p = object_run(f"{key}_loo{i}", rest, [a], dirs["loo"], ext=ext)
        f["fold_gate"] = FOLD_GATE
        tie = bool(run["accepted"] and run.get("uses") and tie_check(f, [a], run["predictions"]))
        f.pop("_sel", None), f.pop("_groups", None)
        exact = bool(run["accepted"] and run["predictions"][0] is not None and run["predictions"][0] == np.asarray(b).tolist())
        f.update(accepted=run["accepted"], uses=run.get("uses"), heldout_exact=exact, restored=run.get("restored"),
                 cpu_s=run["cpu_s"], tie=tie)
        f["class"] = "SUCCESS" if (run["accepted"] and run.get("uses") and exact and not tie) else \
            ("ABSTAIN_TIE" if tie else "LOO_FAILURE")
        folds.append(f)
    return folds


def run_task(key, view, arms, dirs, donor_raw, f_b):
    train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in view["train"]]
    tests = [np.asarray(p["input"], dtype=int) for p in view["test"]]
    row = {"key": key, "arms": {}}
    a_rec, _ = object_run(key, train, tests, dirs["A"])
    row["arms"]["A"] = {"committed": a_rec["predictions"] if a_rec["accepted"] else None, "certified": a_rec["accepted"],
                        "run": a_rec, "cpu_s": a_rec["cpu_s"]}
    if "B" in arms:
        b_rec, _ = object_run(key, train, tests, dirs["B"], budget_s=BUDGET_S * f_b)
        row["arms"]["B"] = {"committed": b_rec["predictions"] if b_rec["accepted"] else None, "certified": b_rec["accepted"],
                            "run": b_rec, "f_B": f_b, "cpu_s": b_rec["cpu_s"]}
    for arm in [x for x in ("C", "C2", "D", "E") if x in arms]:
        c0 = time.process_time()
        rec, ext = construct_and_check(arm, key, train, tests, dirs, donor_raw)
        commit, certified_by = (a_rec["predictions"], "A") if a_rec["accepted"] else (None, None)
        if ext is not None:
            top, _p = object_run(key, train, tests, dirs[arm], ext=ext)
            rec["top"] = top
            if not (top["accepted"] and top.get("uses")):
                rec.pop("_sel", None), rec.pop("_groups", None)
                rec["outcome"] = "ENGINE_REJECTION" if not top["accepted"] else "ROUTING_FAILURE"
            elif tie_check(rec, tests, top["predictions"]):
                rec["outcome"] = "ABSTAIN_TIE"
            else:
                rec["folds"] = loo(arm, key, train, ext, dirs, donor_raw)
                if all(f["class"] == "SUCCESS" for f in rec["folds"]):
                    rec["outcome"] = "CERTIFIED_WITH_EXTENSION"
                    if not a_rec["accepted"]:                           # the common commit rule (Amendment 1)
                        commit, certified_by = top["predictions"], f"{arm}+extension"
                else:
                    rec["outcome"] = "LOO_FAILURE"
        rec.update(committed=commit, certified_by=certified_by, cpu_s=round(time.process_time() - c0, 2))
        row["arms"][arm] = rec
    return row


def load_corpus(name):
    if name in ("c4_dev", "c4_dev_v2"):
        from cora_fhr.corpus_c4 import solver_view
        d = json.load(open(os.path.join(OUT, "c4_dev.json" if name == "c4_dev" else "c4_dev_v2.json")))
        return sorted((k, solver_view(t)) for k, t in d["tasks"].items())
    if name == "dev60":
        return FR.load("dev60")
    raise ValueError(name)


def job(args):
    key, view, arms, donor_key, donor_view, f_b = args
    if os.nice(0) < FR.NICE:
        os.nice(FR.NICE - os.nice(0))
    FR.cpu_clock()
    from cora_pilot import native as N
    base = os.path.join(OUT, "engines", key)
    dirs = {a: N.prepare_object_dir(os.path.join(base, a)) for a in ("A", "B", "C", "C2", "D", "E", "extract", "loo")}
    donor_raw = None
    if "D" in arms and donor_view is not None:
        dtrain = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in donor_view["train"]]
        donor_raw, _ = authentic_raw(dtrain, N.prepare_object_dir(os.path.join(base, "donor")))
    t0, c0 = time.time(), time.process_time()
    row = run_task(key, view, arms, dirs, donor_raw, f_b)
    row.update(donor=donor_key, wall_s=round(time.time() - t0, 1), cpu_s=round(time.process_time() - c0, 1))
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, choices=("c4_dev", "c4_dev_v2", "dev60"))
    ap.add_argument("--arms", default="A,B,C,D,E")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--keys", default="")
    ap.add_argument("--f_b", type=float, default=F_B_PROVISIONAL)
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    arms = tuple(a.arms.split(","))
    items = load_corpus(a.corpus)
    keys = [k for k, _ in items]
    view = dict(items)
    want = set(a.keys.split(",")) if a.keys else None
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"rows_{a.corpus}{a.tag}.jsonl")
    done = {json.loads(l)["key"] for l in open(path)} if os.path.exists(path) else set()
    todo = []
    for i, k in enumerate(keys):
        if k in done or (want is not None and k not in want):
            continue
        donor = keys[(i + 1) % len(keys)]                              # the next key in sorted order, cyclic
        todo.append((k, view[k], arms, donor, view[donor], a.f_b))
    print(f"{a.corpus}: {len(todo)} to run, arms {arms}", flush=True)
    t0 = time.time()
    with mp.get_context("fork").Pool(a.workers, maxtasksperchild=1) as pool, open(path, "a") as fh:
        for i, row in enumerate(pool.imap_unordered(job, todo), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            brief = {arm: (r.get("outcome") or ("certified" if r.get("certified") else "-")) for arm, r in row["arms"].items()}
            print(f"[{i}/{len(todo)}] {row['key']} {brief} cpu={row['cpu_s']}s elapsed={time.time() - t0:.0f}s", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
