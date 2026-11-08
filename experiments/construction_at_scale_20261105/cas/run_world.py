"""Phase 2 runner for one world (system side, then evaluator side). Every method is S1's frozen code.

    python -m cas.run_world controller WORLD_DIR            CORA's failure analysis on every system task
    python -m cas.run_world spec WORLD_DIR                  S-hole, S-demo, S-shuffled: motivating tasks x 3 seeds
    python -m cas.run_world enum WORLD_DIR SEED             S-enum, one seed (seeds run as separate processes)
    python -m cas.run_world c7m WORLD_DIR M|E WORKERS [MAX] matched static search on motivating (M) or excluded (E) tasks
    python -m cas.run_world c7m_one WORLD_DIR M|E TASK CAP [MEM_GB]   one matched search (memory-limited child)
    python -m cas.run_world c7m_rerun WORLD_DIR             memory failures run once more, alone, with 20 GB
    python -m cas.run_world commit WORLD_DIR                the committed predictions of every unit, before any label
    python -m cas.run_world evaluate WORLD_DIR              scoring, reuse and transfer, agreement, kind, contract

`cas.env.use_world` points S1's folder constants at WORLD_DIR, so the frozen functions read that world's grammar
(evaluator_only/REMOVED.json), its system tasks and its controller records, and write only there. Every command
first verifies the world's task files against its manifest and the configuration (verify_world) and, at the end,
records which project modules it executed, with their digests (cas.env.pin_record).

What is S1's code, unchanged (experiments/capability_growth_20261027/cgrow/):
- controller: cgrow.controller.analyze on every system task under the world's G0 (S1's experiment.prep loop; the
  neural prompt jobs that prep also wrote are not needed, as no neural method runs);
- motivating tasks: s1.motivating (partition M and decision INVENT_NEW_OPERATION); donors: S1's rule (the same-slot
  M task of the next family of the same world), guarded here against a family with no motivating task;
- gates: s1.Gates (novelty 200,000 executions on 12 probe pairs; retry at the base budget; regression on every
  previously solved task; validation on the other unsolved tasks in hash order; cached and charged), through the
  subclass AccountedGates below, which changes one charge (the regression check's);
- arms: s1.spec_candidates and s1.run_spec_unit (S-hole: all stored sketches; S-demo: the identity sketch only;
  S-shuffled: the donor's sketches; at most 3 retries), s1.run_enum_unit (S-enum: seed order, 60 charged CPU-s),
  with schema.seeded_order(seed); S1's loop order (seed, task, arm) without its neural method S1F;
- matched static search: S.run(G0, demonstrations, queries, budget=10**9, cpu_cap=...) in a child process limited
  in address space (testib_rest.c7m_one), on motivating tasks and on excluded tasks;
- scoring: evaluate.correct on the unit's committed outputs (at most two per query, committed_outputs below);
  structure scores as s1.evaluate (excluded-task fits with G0 plus the structure at the base budget; agreement with
  each removed reference; kind by a 1M-execution G0 search; the CAST contract checker); reuse and transfer by one
  base search per excluded task with the grown grammar (two committed outputs).
Differences from S1, stated in PROTOCOL.md: S-enum seeds run as three processes, each with its own copy of the gate
cache made after the specification arms (S1 ran one process); the matched search also runs on excluded tasks; the
two machine-dependent CPU stops (S-enum 60 charged CPU-s, matched search 150 CPU-s) are multiplied by the kernel's
measured speed factor CAS_CPU_SCALE (cas/bench.py), so that they mean S1's reference CPU-seconds; a motivating
task's matched search gets at least S-hole's complete charged CPU on it; the regression check is charged the stored
CPU of its retries (AccountedGates); the committed predictions are frozen (commit) before scoring (evaluate).
"""
import hashlib
import json
import os
import pickle
import resource
import shutil
import subprocess
import sys
import time

from cas import env as E
from cgrow import experiment as X, controller as CT, search as S, schema as SG, s1, evaluate as EV   # noqa: E402
from cgrow import lang0 as L0, episode as EP, testib_rest as TR                                      # noqa: E402

SEEDS = (0, 1, 2)
SPEC_ARMS = ("S-hole", "S-demo", "S-shuffled")
GROWTH_ARMS = SPEC_ARMS + ("S-enum",)
C7M_CPU = TR.C7M_CPU          # 150 CPU-s, as S1 (reference CPU-seconds)
C7M_MEM_GB = 8                # address-space limit of one matched-search child (S1 used 12 GB with one child at a time)
C7M_RERUN_MEM_GB = 20         # a search stopped by memory is run once more, alone, with this limit (c7m_rerun)
ENUM_CPU = s1.ENUM_CPU        # 60 charged CPU-s per S-enum unit, as S1 (reference CPU-seconds)
#: machine factor from cas/bench.py (kernel median under concurrency / Athe reference, clipped to [1, 3]); 1 when not set
CPU_SCALE = float(os.environ.get("CAS_CPU_SCALE", "1"))
C7M_GUARD_FACTOR = 6          # a child that exceeds 6 x its cap plus 60 s of wall time is killed: a failure, not a budget


def _runs(P, *parts):
    return os.path.join(P.RUNS, *parts)


def _save_json(path, obj):
    tmp = path + ".tmp"
    with E.open_write(tmp) as f:
        json.dump(obj, f, default=list)
    os.replace(tmp, path)


def _sha_json(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=list).encode()).hexdigest()


# ------------------------------------------------------------------ custody of the world's files
def verify_world(wd):
    """The world's task files against its manifest, and its removed set and families against the configuration.
    Refuses on any difference. A phase 1 check world (S1's own, marked phase1_check in its manifest) is verified
    against its manifest only."""
    man_path = os.path.join(wd, "partitions", "PARTITIONS_MANIFEST.json")
    if not os.path.exists(man_path):
        raise RuntimeError(f"no PARTITIONS_MANIFEST.json in {wd}: the world is not verifiable")
    man = E.load(man_path)
    for rel, key in (("partitions/TASKS_SYSTEM.json", "tasks_system_sha256"),
                     ("evaluator_only/TASKS_EVAL.json", "tasks_eval_sha256"),
                     ("evaluator_only/REMOVED.json", "removed_sha256")):
        if E.sha256(os.path.join(wd, rel)) != man.get(key):
            raise RuntimeError(f"{rel} differs from its manifest digest in {wd}")
    rem = E.load(os.path.join(wd, "evaluator_only", "REMOVED.json"))
    if man.get("phase1_check"):
        return man
    cfg = E.load(os.path.join(E.STUDY, "config", "STUDY_CONFIG.json"))
    w = man.get("world")
    if w not in cfg["worlds"]:
        raise RuntimeError(f"world {w!r} is not in the configuration")
    if list(rem["removed"]) != list(cfg["worlds"][w]["removed"]) or \
            list(rem["families"]) != list(cfg["worlds"][w]["families"]):
        raise RuntimeError(f"REMOVED.json of {w} differs from the configuration")
    return man


# ------------------------------------------------------------------ S1's gates with complete charging
class AccountedGates(s1.Gates):
    """S1's gates with one accounting change. S1 charged the regression check with the process time of its loop, so
    retries served from the cache were charged nothing (a check with two cached 15 s retries charged 0.001 s). Here
    the regression check is charged the stored CPU of its retries over the regression set, whether computed now or
    taken from the cache; the loop time is kept beside it. Every other charge is S1's. S1's files are untouched."""

    def regression(self, sid):
        reg = super().regression(sid)
        charged = sum(float((self.c["retry"].get((sid, t)) or {}).get("cpu_s") or 0.0) for t in self.solved)
        return dict(reg, cpu_s=round(charged, 3), loop_cpu_s=reg["cpu_s"])


def donors_safe(ev):
    """S1's donor rule (cgrow/s1.py donors): the same-slot motivating task of the next family in name order, in the
    same world. Guarded: a family with no motivating task is skipped, and when no other family has one the task has
    no donor (its S-shuffled unit is recorded as not applicable, never substituted)."""
    fams = sorted({t["family"] for t in ev.values() if t["family"]})
    mts = {f: sorted([i for i, t in ev.items() if t["family"] == f and t["partition"] == "M"],
                     key=lambda i: (ev[i]["template"], X.h(i))) for f in fams}
    have = [f for f in fams if mts[f]]
    out = {}
    for fi, f in enumerate(have):
        others = have[fi + 1:] + have[:fi]
        for slot, tid in enumerate(mts[f]):
            out[tid] = mts[others[0]][slot % len(mts[others[0]])] if others else None
    return out


# ------------------------------------------------------------------ controller
def controller(wd):
    P = E.use_world(wd)
    g0b = X.G0Builder()
    sys_t = X.system_tasks()
    path = _runs(P, "prep_v4", "records.pkl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    recs = {}
    if os.path.exists(path):
        with open(path, "rb") as f:
            recs = pickle.load(f)
    for tid in sorted(sys_t):
        if tid in recs:
            continue
        t0 = time.process_time()
        recs[tid] = CT.analyze(X.as_task(sys_t[tid]), g0b())
        recs[tid]["analyze_cpu_s"] = round(time.process_time() - t0, 3)     # the whole diagnosis, sketches included
        E.check_write(path)
        with open(path + ".tmp", "wb") as f:
            pickle.dump(recs, f)
        os.replace(path + ".tmp", path)
        print(json.dumps({"task": tid, "status": recs[tid]["status"], "decision": recs[tid]["decision"]}), flush=True)
    summ = {t: {"status": r["status"], "decision": r["decision"], "base_level": r["base"]["level_complete"],
                "deeper_level": (r.get("probe_deeper_search") or {}).get("level_complete"),
                "cpu_s": r.get("cpu_s", r["base"]["cpu_s"]), "analyze_cpu_s": r.get("analyze_cpu_s")}
            for t, r in recs.items()}
    E.dump(_runs(P, "prep_v4", "controller_summary.json"), summ)


# ------------------------------------------------------------------ growth arms
def _diagnosis_cpu(P):
    """Actual CPU of the controller's diagnosis per task (base search, 4x probe, closest program, sketches)."""
    path = _runs(P, "prep_v4", "controller_summary.json")
    return {t: v.get("analyze_cpu_s") for t, v in E.load(path).items()} if os.path.exists(path) else {}


def _unit_loop(P, arms, seeds, gates_path, out_path):
    units = E.load(out_path) if os.path.exists(out_path) else {}
    ev, recs, tids = s1.motivating()
    dn = donors_safe(ev)
    diag = _diagnosis_cpu(P)
    G = AccountedGates(gates_path)
    for s in seeds:
        order = SG.seeded_order(s)
        for tid in tids:
            for arm in arms:
                key = f"{arm}|{tid}|{s}"
                if key in units:
                    continue
                t0 = time.process_time()
                rec = {"arm": arm, "task": tid, "seed": s}
                spec_cpu = 0.0
                if arm == "S-shuffled" and dn.get(tid) is None:
                    rec.update(not_applicable="no donor family with a motivating task", rows=[], retries=0,
                               cpu_s=0.0, promoted=None, n_candidates=0)
                    res = {"cpu_s": 0.0, "promoted": None, "retries": 0}
                elif arm == "S-enum":
                    res = s1.run_enum_unit(G, tid, order)
                    rec.update(res)
                    # S1's loop checks the cap before each candidate; a candidate started below it completes, and
                    # its whole charge counts (pre-declared, PROTOCOL.md section 5); the overshoot is recorded
                    rec["enum_cap_cpu_s"] = round(ENUM_CPU * CPU_SCALE, 3)
                    rec["enum_overshoot_cpu_s"] = round(max(0.0, res["cpu_s"] - ENUM_CPU * CPU_SCALE), 3)
                else:
                    sk = recs[tid]["sketches"]
                    if arm == "S-demo":
                        sk = [x for x in sk if x["form"] == "?(I)"]
                    elif arm == "S-shuffled":
                        sk = recs[dn[tid]]["sketches"]
                        rec["donor"] = dn[tid]
                    t1 = time.process_time()
                    cands = s1.spec_candidates(order, sk)              # specification enumeration (not cached)
                    spec_cpu = round(time.process_time() - t1, 3)
                    res = s1.run_spec_unit(G, tid, cands)
                    rec.update(res)
                # CPU accounting: logical charges (cached gate results charged at their first-computation CPU) and
                # the actual process CPU of this unit are kept apart; the charged total adds the task's diagnosis
                # and the specification enumeration, so it is the complete cost of growth on this unit
                rec["charged_gates_cpu_s"] = res["cpu_s"]
                rec["spec_enum_cpu_s"] = spec_cpu
                rec["diagnosis_cpu_s"] = diag.get(tid)
                rec["charged_total_cpu_s"] = round((diag.get(tid) or 0.0) + spec_cpu + res["cpu_s"], 3)
                rec["actual_cpu_s"] = round(time.process_time() - t0, 3)
                units[key] = rec
                _save_json(out_path, units)
                print(json.dumps({"unit": key, "promoted": res["promoted"], "retries": res["retries"],
                                  "charged_total_cpu_s": rec["charged_total_cpu_s"]}), flush=True)
    G.save(force=True)


def spec(wd):
    P = E.use_world(wd)
    d = _runs(P, "cas_arms")
    os.makedirs(d, exist_ok=True)
    _unit_loop(P, SPEC_ARMS, SEEDS, os.path.join(d, "gates_spec.pkl"), os.path.join(d, "units_spec.json"))


def enum(wd, seed):
    P = E.use_world(wd)
    s1.ENUM_CPU = ENUM_CPU * CPU_SCALE        # the module constant s1.run_enum_unit reads; the file is unchanged
    d = _runs(P, "cas_arms")
    gp = os.path.join(d, f"gates_enum_s{seed}.pkl")
    if not os.path.exists(gp) and os.path.exists(os.path.join(d, "gates_spec.pkl")):
        E.check_write(gp)
        shutil.copyfile(os.path.join(d, "gates_spec.pkl"), gp)
    _unit_loop(P, ("S-enum",), (int(seed),), gp, os.path.join(d, f"units_enum_s{seed}.json"))


# ------------------------------------------------------------------ matched static search
def _c7m_tasks(P, which):
    ev = X.eval_tasks()                                       # partition labels only; query outputs are not read here
    if which == "M":
        _, _, tids = s1.motivating()
        return tids
    return sorted(i for i, t in ev.items() if t["partition"] == "E")


def c7m_budget(P, which, tid):
    """Matched search CPU cap for one task, in this machine's seconds: 150 reference CPU-s times the machine factor,
    or S-hole's largest complete charged total on that task over its seeds when that is larger (motivating tasks
    only), so that matched static search never has less CPU than growth had."""
    cap = C7M_CPU * CPU_SCALE
    if which == "M":
        path = _runs(P, "cas_arms", "units_spec.json")
        units = E.load(path) if os.path.exists(path) else {}
        tot = [v.get("charged_total_cpu_s") for k, v in units.items() if k.startswith(f"S-hole|{tid}|")]
        if len(tot) < len(SEEDS) or any(x is None for x in tot):
            raise RuntimeError(f"S-hole units incomplete for {tid}: the matched search on motivating tasks runs after them")
        cap = max(cap, max(tot))
    return round(cap, 3)


def _vm_peak_kb():
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmPeak:"):
                    return int(line.split()[1])
    except OSError:
        return None
    return None


def c7m_one(wd, which, tid, cap, mem_gb=C7M_MEM_GB):
    P = E.use_world(wd)
    lim = int(float(mem_gb) * (1 << 30))
    resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    sys_t = X.system_tasks() if which == "M" else None
    if which == "M":
        t = X.as_task(sys_t[tid])                                        # system view: demonstrations and query inputs
    else:
        ev = X.eval_tasks()                                              # excluded tasks are evaluator-only files
        t = X.as_task(ev[tid])
    try:
        r = S.run(X.G0Builder()(), t["train"], t["test_inputs"], budget=10 ** 9, cpu_cap=float(cap))
        out = {k: r[k] for k in ("fit", "program", "level_complete", "stop", "calls", "cpu_s", "closure_capped")}
        out["preds"] = (r["preds"] or [])[:2]                            # the two committed predictions
    except MemoryError:
        out = {"fit": False, "memory_capped": True, "preds": []}
    out["mem_limit_gb"] = float(mem_gb)
    out["vm_peak_kb"] = _vm_peak_kb()                                    # the quantity the limit bounds
    out["rss_peak_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print("C7M_RESULT " + json.dumps(out, default=list), flush=True)


def c7m(wd, which, workers, max_tasks=None):
    P = E.use_world(wd)
    path = _runs(P, "cas_c7m", f"c7m_{which}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    res = E.load(path) if os.path.exists(path) else {}
    tids = _c7m_tasks(P, which)
    todo = [t for t in tids if t not in res]
    if max_tasks is not None:
        todo = todo[:int(max_tasks)]
    caps = {t: c7m_budget(P, which, t) for t in todo}
    running = []
    env = dict(os.environ)

    def finish(tid, p):
        try:
            out, err = p.communicate(timeout=C7M_GUARD_FACTOR * caps[tid] + 60)
            line = [x for x in out.splitlines() if x.startswith("C7M_RESULT ")]
            r = json.loads(line[-1][11:]) if line else {"fit": False, "child_failed": True, "rc": p.returncode,
                                                         "stderr": err[-300:], "preds": []}
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            r = {"fit": False, "timed_out": True, "preds": [], "note": "wall-time guard; counts as not recovered"}
        r["budget_cpu_s"] = caps[tid]
        r["budget_reference_cpu_s"] = round(caps[tid] / CPU_SCALE, 3)
        r["cpu_scale"] = CPU_SCALE
        if r.get("cpu_s"):
            r["executions_per_cpu_s"] = round(r.get("calls", 0) / r["cpu_s"], 1)
        res[tid] = r
        _save_json(path, res)
        print(json.dumps({"c7m": which, "task": tid, "fit": r.get("fit"), "stop": r.get("stop"),
                          "cpu_s": r.get("cpu_s"), "budget_cpu_s": caps[tid]}), flush=True)

    def start(tid, mem_gb=C7M_MEM_GB):
        return subprocess.Popen([sys.executable, "-m", "cas.run_world", "c7m_one", wd, which, tid, str(caps[tid]),
                                 str(mem_gb)], cwd=E.STUDY, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)

    while todo or running:
        while todo and len(running) < int(workers):
            tid = todo.pop(0)
            running.append((tid, start(tid)))
        tid, p = running.pop(0)
        finish(tid, p)
    return res


def _memory_failure(r):
    """A search stopped by memory: a MemoryError under the address-space limit, or a child killed by the operating
    system (return code -9, the out-of-memory killer)."""
    return bool(r.get("memory_capped") or (r.get("child_failed") and r.get("rc") == -9))


def c7m_rerun(wd):
    """Stop rule: every matched search stopped by memory is run once more, alone (the kernel runs this as its own
    stage, with no other process), with a 20 GB address-space limit; that result stands, and the first attempt is
    kept beside it. A search stopped by the wall-time guard is not rerun."""
    P = E.use_world(wd)
    env = dict(os.environ)
    for which in ("M", "E"):
        path = _runs(P, "cas_c7m", f"c7m_{which}.json")
        if not os.path.exists(path):
            continue
        res = E.load(path)
        ev = X.eval_tasks()
        for tid in sorted(t for t, r in res.items() if _memory_failure(r) and not r.get("rerun_alone")):
            cap = res[tid].get("budget_cpu_s") or c7m_budget(P, which, tid)
            p = subprocess.Popen([sys.executable, "-m", "cas.run_world", "c7m_one", wd, which, tid, str(cap),
                                  str(C7M_RERUN_MEM_GB)], cwd=E.STUDY, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
            try:
                out, err = p.communicate(timeout=C7M_GUARD_FACTOR * cap + 60)
                line = [x for x in out.splitlines() if x.startswith("C7M_RESULT ")]
                r = json.loads(line[-1][11:]) if line else {"fit": False, "child_failed": True, "rc": p.returncode,
                                                             "stderr": err[-300:], "preds": []}
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
                r = {"fit": False, "timed_out": True, "preds": [], "note": "wall-time guard; counts as not recovered"}
            first = res[tid]
            r.update(budget_cpu_s=cap, budget_reference_cpu_s=round(cap / CPU_SCALE, 3), cpu_scale=CPU_SCALE,
                     rerun_alone=True, rerun_mem_gb=C7M_RERUN_MEM_GB, first_attempt=first)
            if r.get("cpu_s"):
                r["executions_per_cpu_s"] = round(r.get("calls", 0) / r["cpu_s"], 1)
            res[tid] = r
            _save_json(path, res)
            print(json.dumps({"c7m_rerun": which, "task": tid, "fit": r.get("fit"), "vm_peak_kb": r.get("vm_peak_kb")}),
                  flush=True)


# ------------------------------------------------------------------ committed predictions (before any label)
def _units(P):
    d = _runs(P, "cas_arms")
    units = E.load(os.path.join(d, "units_spec.json"))
    for s in SEEDS:
        units.update(E.load(os.path.join(d, f"units_enum_s{s}.json")))
    return units


def committed_outputs(rows):
    """The label-blind commit of a growth unit: at most two query outputs, those of the retry of the structure the
    unit keeps. The promoted structure if there is one; otherwise the first quarantined structure in candidate
    order; a rolled-back structure commits nothing. Promotion and candidate order never see the query label.
    Returns (predictions or None, kind, structure)."""
    fits = [r for r in rows if r.get("fit")]
    for kind in ("promoted", "quarantined"):
        kept = [r for r in fits if r.get("promotion") == kind]
        if kept:
            return (kept[0].get("preds") or [])[:2], kind, kept[0].get("sid")
    return None, None, None


def commit(wd):
    """System side, before any query label is read: the committed predictions of every growth unit (at most two per
    query), of every matched search, and of the reuse, transfer and per-structure searches on the excluded tasks
    (two predictions each, from the grown grammars built from label-blind promotion metadata), after a
    completeness check. Missing work (an arm, a seed, a task, a matched
    search) makes the world INCOMPLETE: it is listed in runs/cas_commit/INCOMPLETE.json and nothing is written in
    its place. Writes runs/cas_commit/COMMITTED_PREDICTIONS.json and its sha256 (COMMITTED_SHA256)."""
    P = E.use_world(wd)
    ev = X.eval_tasks()                                       # partition and family labels only
    _, _, tids = s1.motivating()
    e_ids = sorted(i for i, t in ev.items() if t["partition"] == "E")
    d = _runs(P, "cas_commit")
    os.makedirs(d, exist_ok=True)
    units = _units(P)
    c7m_m = E.load(_runs(P, "cas_c7m", "c7m_M.json")) if os.path.exists(_runs(P, "cas_c7m", "c7m_M.json")) else {}
    c7m_e = E.load(_runs(P, "cas_c7m", "c7m_E.json")) if os.path.exists(_runs(P, "cas_c7m", "c7m_E.json")) else {}
    missing, doc = [], {"world": os.path.basename(os.path.realpath(wd)), "units": {}, "c7m": {}, "rule":
                        "promoted structure's retry, else the first quarantined structure's retry, else nothing; "
                        "at most two predictions per query; matched search: the two predictions of its search"}
    for tid in tids:
        for s in SEEDS:
            for arm in GROWTH_ARMS:
                key = f"{arm}|{tid}|{s}"
                r = units.get(key)
                if r is None:
                    missing.append(key)
                    continue
                if r.get("not_applicable"):
                    doc["units"][key] = {"not_applicable": r["not_applicable"]}
                    continue
                preds, kind, sid = committed_outputs(r["rows"])
                doc["units"][key] = {"preds": preds, "kind": kind, "structure": sid}
        c = c7m_m.get(tid)
        if c is None:
            missing.append(f"C7m|M|{tid}")
        else:
            doc["c7m"][f"M|{tid}"] = {"preds": (c.get("preds") or [])[:2], "fit": bool(c.get("fit")), "stop": c.get("stop"),
                                      "failed": bool(c.get("timed_out") or c.get("child_failed") or c.get("memory_capped")),
                                      "budget_cpu_s": c.get("budget_cpu_s"), "cpu_s": c.get("cpu_s")}
    for t in e_ids:
        c = c7m_e.get(t)
        if c is None:
            missing.append(f"C7m|E|{t}")
        else:
            doc["c7m"][f"E|{t}"] = {"preds": (c.get("preds") or [])[:2], "fit": bool(c.get("fit")), "stop": c.get("stop"),
                                    "failed": bool(c.get("timed_out") or c.get("child_failed") or c.get("memory_capped")),
                                    "budget_cpu_s": c.get("budget_cpu_s"), "cpu_s": c.get("cpu_s")}
    if missing:
        E.dump(os.path.join(d, "INCOMPLETE.json"), {"missing": missing, "note": "absent work is never substituted"})
        raise SystemExit("INCOMPLETE: " + ", ".join(missing[:20]) + (" ..." if len(missing) > 20 else ""))
    # grown grammars from label-blind promotion metadata (a structure counts for a family when S-hole promoted it
    # on one of the family's motivating tasks in at least 2 of 3 seeds), then the reuse, transfer and
    # per-structure searches on the excluded tasks (demonstrations and query inputs only), their two predictions
    # persisted here and scored later by evaluate
    G = AccountedGates(_runs(P, "cas_arms", "gates_spec.pkl"))
    grown, promoted = {}, set()
    for tid in tids:
        cnt = {}
        for s in SEEDS:
            sid = units[f"S-hole|{tid}|{s}"].get("promoted")
            if sid:
                cnt[sid] = cnt.get(sid, 0) + 1
        for sid, n in cnt.items():
            if n >= 2:
                grown.setdefault(ev[tid]["family"], set()).add(sid)
        for s in SEEDS:
            for arm in GROWTH_ARMS:
                sid = units[f"{arm}|{tid}|{s}"].get("promoted")
                if sid:
                    promoted.add(sid)
    grown = {f: sorted(v) for f, v in grown.items()}
    doc["grown_by_family"] = grown
    doc["grown"] = {}
    gs_path = os.path.join(d, "grown_search_cache.json")
    gs = E.load(gs_path) if os.path.exists(gs_path) else {}

    def search(key, sids, t):
        if key not in gs:
            if not sids:
                gs[key] = {"structures": [], "fit": False, "preds": [], "program": None, "cpu_s": 0.0}
            else:
                tk = X.as_task(ev[t])                                   # demonstrations and query inputs only
                rr = S.run(grown_grammar(G, sids), tk["train"], tk["test_inputs"])
                gs[key] = {"structures": list(sids), "fit": bool(rr["fit"]), "preds": (rr["preds"] or [])[:2],
                           "program": rr["program"], "cpu_s": rr["cpu_s"]}
            _save_json(gs_path, gs)
        return gs[key]

    for t in e_ids:
        f = ev[t]["family"]
        own = grown.get(f, [])
        other = sorted({sid for g_, ss in grown.items() if g_ != f for sid in ss})
        doc["grown"][f"reuse|{t}"] = search(f"reuse|{t}", own, t)
        doc["grown"][f"transfer|{t}"] = search(f"transfer|{t}", other, t)
        for sid in sorted(promoted):
            doc["grown"][f"struct|{sid}|{t}"] = search(f"struct|{sid}|{t}", [sid], t)
        print(json.dumps({"committed_excluded": t, "reuse_structures": len(own), "transfer_structures": len(other)}),
              flush=True)
    G.save(force=True)
    doc["sha256_of_content"] = _sha_json({"units": doc["units"], "c7m": doc["c7m"], "grown": doc["grown"]})
    path = os.path.join(d, "COMMITTED_PREDICTIONS.json")
    with E.open_write(path) as f:
        json.dump(doc, f, sort_keys=True, default=list)
    with E.open_write(os.path.join(d, "COMMITTED_SHA256")) as f:
        f.write(E.sha256(path) + "\n")
    print(json.dumps({"committed_units": len(doc["units"]), "committed_c7m": len(doc["c7m"]),
                      "committed_grown": len(doc["grown"]), "sha256": E.sha256(path)}), flush=True)


# ------------------------------------------------------------------ evaluator side
def grown_grammar(G, sids):
    """G0 plus every structure in sids (the language after growth for one family, or for the other families)."""
    g = G.g0b()
    for sid in sids:
        st = G.st[sid]
        L0.add_production(g, "f:sig_" + sid.replace(":", "_"), G.fn(st), 1 if st.param else 0)
    return g


def evaluate(wd):
    """Evaluator side, after commit: each committed prediction against the query output; reach (descriptive);
    matched-search outcomes with their budgets; the scores of every promoted structure; the reuse and transfer
    searches with the grown grammars (two committed outputs each); CPU accounting."""
    P = E.use_world(wd)
    ev, recs, tids = s1.motivating()
    rem = X.load_json(os.path.join(P.EVALUATOR_DIR, "REMOVED.json"))
    units = _units(P)
    cpath = _runs(P, "cas_commit", "COMMITTED_PREDICTIONS.json")
    with open(os.path.join(_runs(P, "cas_commit"), "COMMITTED_SHA256"), encoding="utf-8") as f:
        want = f.read().strip()
    if E.sha256(cpath) != want:
        raise RuntimeError("COMMITTED_PREDICTIONS.json differs from its recorded sha256")
    com = E.load(cpath)
    c7m_m = E.load(_runs(P, "cas_c7m", "c7m_M.json"))
    c7m_e = E.load(_runs(P, "cas_c7m", "c7m_E.json"))
    G = AccountedGates(_runs(P, "cas_arms", "gates_spec.pkl"))
    e_ids = sorted(i for i, t in ev.items() if t["partition"] == "E")
    diag = _diagnosis_cpu(P)
    out_units = []
    for tid in tids:
        outs = ev[tid]["test_outputs"]
        u = {"task": tid, "family": ev[tid]["family"], "template": ev[tid]["template"], "op": ev[tid]["op"],
             "params": ev[tid]["params"], "source": ev[tid]["source"], "seeds": {}}
        for s in SEEDS:
            arms = {}
            for arm in GROWTH_ARMS:
                key = f"{arm}|{tid}|{s}"
                r, c = units[key], com["units"][key]
                if c.get("not_applicable"):
                    arms[arm] = {"not_applicable": c["not_applicable"], "recovered": None, "reach": None}
                    continue
                parts = (r.get("diagnosis_cpu_s") if r.get("diagnosis_cpu_s") is not None else diag.get(tid) or 0.0,
                         r.get("spec_enum_cpu_s") or 0.0, r.get("charged_gates_cpu_s", r.get("cpu_s")) or 0.0)
                arms[arm] = {"recovered": bool(c["preds"]) and EV.correct(c["preds"], outs),
                             "committed_kind": c["kind"], "committed_structure": c["structure"],
                             "reach": any(row.get("fit") and EV.correct(row.get("preds"), outs) for row in r["rows"]),
                             "fitting_candidates": sum(bool(row.get("fit")) for row in r["rows"]),
                             "promoted": r["promoted"], "retries": r["retries"],
                             "diagnosis_cpu_s": parts[0], "spec_enum_cpu_s": parts[1], "charged_gates_cpu_s": parts[2],
                             "charged_total_cpu_s": round(sum(parts), 3), "actual_cpu_s": r.get("actual_cpu_s"),
                             "n_candidates": r.get("n_candidates"), "structures_tried": r.get("structures_tried")}
            u["seeds"][str(s)] = arms
        c, cm = com["c7m"][f"M|{tid}"], c7m_m[tid]
        u["C7m"] = {"recovered": bool(c["preds"]) and EV.correct(c["preds"], outs) and not c["failed"],
                    "failed": c["failed"], "stop": cm.get("stop"), "level": cm.get("level_complete"),
                    "cpu_s": cm.get("cpu_s"), "calls": cm.get("calls"), "executions_per_cpu_s": cm.get("executions_per_cpu_s"),
                    "budget_cpu_s": cm.get("budget_cpu_s"), "budget_reference_cpu_s": cm.get("budget_reference_cpu_s")}
        out_units.append(u)
    # structures S-hole promoted for each family under the majority criterion (promoted on one of the family's
    # motivating tasks in at least 2 of 3 seeds): the grown grammar of that family
    grown = {}
    for u in out_units:
        cnt = {}
        for s in SEEDS:
            sid = u["seeds"].get(str(s), {}).get("S-hole", {}).get("promoted")
            if sid:
                cnt[sid] = cnt.get(sid, 0) + 1
        for sid, n in cnt.items():
            if n >= 2:
                grown.setdefault(u["family"], set()).add(sid)
    grown = {f: sorted(v) for f, v in grown.items()}
    promoted = sorted({a.get("promoted") for u in out_units for arms in u["seeds"].values() for a in arms.values()
                       if a.get("promoted")})
    cache_path = _runs(P, "cas_eval", "struct_scores.json")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    sc = E.load(cache_path) if os.path.exists(cache_path) else {}
    fams = list(rem["families"])
    for sid in promoted:
        if sid in sc:
            continue
        st = G.st[sid]
        e_res = {}
        for t in e_ids:
            g_ = com["grown"][f"struct|{sid}|{t}"]                     # the committed per-structure predictions
            e_res[t] = bool(g_["fit"]) and EV.correct(g_["preds"], ev[t]["test_outputs"])
        best_f, agree = None, {}
        for f in fams:
            ref = L0.reference_fn(f)
            grids = [EV.g(a) for t in e_ids if ev[t]["family"] == f for a, _ in ev[t]["train"]] + list(EV.REF_PROBES)
            plist = sorted({tuple(ev[t]["params"]) for t in e_ids if ev[t]["family"] == f})
            tab = {}
            for p in plist:
                ths = [p] if st.param and len(p) == 1 else ([()] if not st.param else [])
                for th in ths:
                    ok = tot = 0
                    for x in grids:
                        try:
                            w = ref(x, *p)
                        except Exception:                                # noqa: BLE001
                            w = None
                        v = st(x, *th)
                        if w is None and v is None:
                            continue
                        tot += 1
                        ok += w == v
                    tab[str(list(p))] = round(ok / tot, 4) if tot else None
            if tab and max(v or 0 for v in tab.values()) > max([v or 0 for v in agree.values()] or [-1]):
                best_f, agree = f, tab
        wit = []
        for th in st.thetas()[:2]:
            pairs = [(x, st(x, *th)) for x in EP.SIG_PROBES[:12]]
            pairs = [(x, y) for x, y in pairs if y is not None]
            if len(pairs) < 4:
                continue
            r = S.run(G.g0b(), pairs[:-1], [pairs[-1][0]], budget=EV.KIND_BUDGET, cpu_cap=30.0, want=1)
            wit.append(bool(r["fit"] and r["preds"] and r["preds"][0][0] == pairs[-1][1]))
        sc[sid] = {"family_best": best_f, "agreement": agree, "e_results": e_res,
                   "kind": "macro" if wit and all(wit) else ("expansion" if wit else "undetermined"),
                   "cast": s1._cast_verdict(st)}
        _save_json(cache_path, sc)
        print(json.dumps({"structure": sid, "family_best": best_f, "e_correct": sum(e_res.values()),
                          "kind": sc[sid]["kind"], "cast": sc[sid]["cast"]}), flush=True)
    # reuse and transfer: the committed two predictions of one base search per excluded task with the grown
    # grammar (made and saved by the commit stage), scored here
    if grown != com.get("grown_by_family", {}):
        raise RuntimeError("the grown grammars differ between the commit stage and the evaluation")

    def scored(key, t):
        g_ = com["grown"][key]
        return dict(g_, recovered=bool(g_["fit"]) and EV.correct(g_["preds"], ev[t]["test_outputs"]))

    e_tasks = {}
    for t in e_ids:
        f = ev[t]["family"]
        own = grown.get(f, [])
        other = sorted({sid for g_, ss in grown.items() if g_ != f for sid in ss})
        c, ce = com["c7m"][f"E|{t}"], c7m_e[t]
        e_tasks[t] = {"family": f, "template": ev[t]["template"], "source": ev[t]["source"],
                      "C7m": {"recovered": bool(c["preds"]) and EV.correct(c["preds"], ev[t]["test_outputs"]) and not c["failed"],
                              "failed": c["failed"], "stop": ce.get("stop"), "budget_cpu_s": ce.get("budget_cpu_s")},
                      "reuse": scored(f"reuse|{t}", t),
                      "transfer": scored(f"transfer|{t}", t),
                      "reach_reuse": any(sc.get(sid, {}).get("e_results", {}).get(t) for sid in own),
                      "reach_transfer": any(sc.get(sid, {}).get("e_results", {}).get(t) for sid in other)}
        print(json.dumps({"excluded": t, "family": f, "reuse": e_tasks[t]["reuse"]["recovered"],
                          "transfer": e_tasks[t]["transfer"]["recovered"]}), flush=True)
    _save_json(cache_path, sc)                       # written even when no structure was promoted (then empty)
    G.save(force=True)
    # CPU accounting per arm: logical charged totals against actual process CPU; stage CPU from the kernel driver
    acct = {}
    for arm in GROWTH_ARMS:
        rows = [a[arm] for u in out_units for a in u["seeds"].values() if arm in a and a[arm].get("recovered") is not None]
        if rows:
            acct[arm] = {"units": len(rows),
                         "mean_charged_total_cpu_s": round(sum(r["charged_total_cpu_s"] for r in rows) / len(rows), 2),
                         "mean_charged_gates_cpu_s": round(sum(r["charged_gates_cpu_s"] for r in rows) / len(rows), 2),
                         "mean_diagnosis_cpu_s": round(sum(r["diagnosis_cpu_s"] for r in rows) / len(rows), 2),
                         "mean_spec_enum_cpu_s": round(sum(r["spec_enum_cpu_s"] for r in rows) / len(rows), 3),
                         "mean_actual_cpu_s": round(sum(r["actual_cpu_s"] or 0 for r in rows) / len(rows), 2),
                         "max_charged_total_cpu_s": round(max(r["charged_total_cpu_s"] for r in rows), 2)}
    en = [units[f"S-enum|{tid}|{s}"] for tid in tids for s in SEEDS]
    over = [u.get("enum_overshoot_cpu_s") for u in en if u.get("enum_overshoot_cpu_s") is not None]
    pos = [o for o in over if o > 0]
    acct["S-enum_overshoot"] = {"units_with_record": len(over), "units_with_overshoot": len(pos),
                                "mean_over_overshooting_units_cpu_s": round(sum(pos) / len(pos), 2) if pos else None,
                                "mean_over_all_recorded_units_cpu_s": round(sum(over) / len(over), 2) if over else None,
                                "max_cpu_s": round(max(over), 2) if over else None,
                                "cap_cpu_s": en[0].get("enum_cap_cpu_s") if en else None}
    acct["C7m_memory"] = {w_: {"failures_first_attempt": sum(_memory_failure(v.get("first_attempt", v)) for v in d.values()),
                                "rerun_alone": sum(bool(v.get("rerun_alone")) for v in d.values()),
                                "still_failed": sum(bool(v.get("memory_capped") or v.get("child_failed")) for v in d.values()),
                                "max_vm_peak_kb": max([v.get("vm_peak_kb") or 0 for v in d.values()] or [0])}
                          for w_, d in (("M", c7m_m), ("E", c7m_e))}
    acct["C7m_M"] = {"tasks": len(c7m_m), "mean_cpu_s": round(sum(v.get("cpu_s") or 0 for v in c7m_m.values()) / max(1, len(c7m_m)), 2),
                     "failed": sum(bool(v.get("timed_out") or v.get("child_failed") or v.get("memory_capped")) for v in c7m_m.values()),
                     "tasks_with_budget_above_150_reference": sum((v.get("budget_reference_cpu_s") or 0) > C7M_CPU + 1e-9
                                                                   for v in c7m_m.values()),
                     "executions_per_cpu_s": sorted(v.get("executions_per_cpu_s") for v in c7m_m.values()
                                                    if v.get("executions_per_cpu_s"))}
    acct["C7m_E"] = {"tasks": len(c7m_e),
                     "failed": sum(bool(v.get("timed_out") or v.get("child_failed") or v.get("memory_capped")) for v in c7m_e.values())}
    stages_path = _runs(P, "STAGES.json")
    stg = E.load(stages_path) if os.path.exists(stages_path) else {}
    acct["stages"] = stg.get("stages")
    acct["cpu_scale"] = stg.get("cpu_scale", CPU_SCALE)
    acct["bench"] = {k: stg.get(k) for k in ("bench_reference_cpu_s", "bench_concurrency", "bench_median_cpu_s")}
    world = {"world": os.path.basename(os.path.realpath(wd)), "removed": rem["removed"], "families": fams,
             "committed_sha256": want, "units": out_units, "e_tasks": e_tasks, "structures": sc,
             "grown_by_family": grown, "cpu_accounting": acct,
             "controller": {t: {"partition": ev[t]["partition"], "family": ev[t]["family"],
                                "decision": recs[t]["decision"], "analyze_cpu_s": recs[t].get("analyze_cpu_s")}
                            for t in recs}}
    E.dump(_runs(P, "cas_eval", "world_results.json"), world)


if __name__ == "__main__":
    cmd, wd = sys.argv[1], sys.argv[2]
    verify_world(wd)
    if cmd == "controller":
        controller(wd)
    elif cmd == "spec":
        spec(wd)
    elif cmd == "enum":
        enum(wd, sys.argv[3])
    elif cmd == "c7m":
        c7m(wd, sys.argv[3], sys.argv[4], *(sys.argv[5:6]))
    elif cmd == "c7m_one":
        c7m_one(wd, sys.argv[3], sys.argv[4], sys.argv[5], *(sys.argv[6:7]))
    elif cmd == "c7m_rerun":
        c7m_rerun(wd)
    elif cmd == "commit":
        commit(wd)
    elif cmd == "evaluate":
        evaluate(wd)
    else:
        raise SystemExit(f"unknown command {cmd}")
    if cmd != "c7m_one":
        E.pin_record(os.path.join(wd, "runs", "module_pins", cmd + ("_" + sys.argv[3] if cmd in ("enum", "c7m") else "") + ".json"))
