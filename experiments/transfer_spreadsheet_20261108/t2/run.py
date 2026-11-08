"""Run the arms on development tasks or, after GO, once on the held tasks.

Usage:
  python3 -I t2/run.py <study> dev <out_dir> [--only id1,id2] [--salt S] [--budget B] [--curve]
  python3 -I t2/run.py <study> held               (needs runs/GO_T2; writes runs/held/; one run only)

Arms, per task and per base budget B (training examples chosen by the salted hash order, grow.split_examples):
  static        the static language, (1 + max_candidates) x B executions;
  grown         base search at B; on failure: failure description, pieces, a search again at B per candidate (at
                most max_candidates), leave-one-out acceptance;
  shuffled      as grown, but the pieces are built from another task's failure description (the next failing task
                in run order, cyclically), with leave-one-out over that task's pairs;
  classical     bottom-up enumeration with observational equivalence over the static language plus every piece of
                the structure space, (1 + max_candidates) x B executions (reference, not a gate);
  grown_no_loo  the grown arm's first fitting candidate, without the acceptance rule (secondary).
Recovered: the arm's program reproduces every held check of the task exactly.
Passes: the primary base budget first, then the curve budgets in the configured order. A pass starts only while the
run's CPU time is below secondary_start_cpu_s; any pass stops when the run's CPU time exceeds run_cpu_cap_s (its
remaining tasks are reported as not run).
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from t2 import dsl, grow, pieces as P, stats  # noqa: E402

DEV_SALT = "transfer-spreadsheet-20261108|dev-examples"
ARMS = ("static", "grown", "shuffled", "classical", "grown_no_loo")
FROZEN = ("t2/__init__.py", "t2/sl_parse.py", "t2/prepare.py", "t2/dsl.py", "t2/pieces.py", "t2/grow.py",
          "t2/stats.py", "t2/run.py", "t2/freeze.py", "config/CONFIG.json", "split/DEV_SPLIT.json",
          "DATA_MANIFEST.md", "data/SOURCE_FILES_SHA256.json", "data/prepared/tasks.json", "launch/run_held.sh",
          "PROTOCOL.md")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def pt():
    return time.process_time()


def outcome(program, lang, task, checks):
    if program is None:
        return {"answered": False, "recovered": False, "program": None}
    preds = grow.predict(program, lang, [task["examples"][i][0] for i in checks])
    right = [p == task["examples"][i][1] for p, i in zip(preds, checks)]
    return {"answered": True, "recovered": all(right), "checks_right": sum(right), "checks": len(right),
            "program": dsl.show(program)}


def run_task(task, salt, cfg, B):
    train, checks = grow.split_examples(task, salt)
    view = grow.view_of(task, train)
    D = P.delims(task["str_consts"])
    M, cap = cfg["max_candidates"], cfg["search_cpu_cap"]
    rec = {"id": task["id"], "k_train": len(train), "n_checks": len(checks), "base_budget": B}
    t0 = pt()
    base = dsl.search(view, dsl.Language(), B, cap, cfg["max_size"], keep_bank=True)
    base_cpu = pt() - t0
    rec["base"] = {k: base[k] for k in ("fit", "calls", "stop", "size")}
    base_lang = dsl.Language()
    # static
    if base["fit"]:
        s_prog, s_info, static_cpu = base["program"], {"calls": base["calls"], "stop": base["stop"]}, base_cpu
    else:
        t1 = pt()
        deep = dsl.search(view, base_lang, (1 + M) * B, (1 + M) * cap, cfg["max_size"])
        static_cpu = pt() - t1
        s_prog, s_info = deep["program"], {"calls": deep["calls"], "stop": deep["stop"]}
    rec["static"] = dict(outcome(s_prog, base_lang, task, checks), **s_info)
    # grown
    state = {"failed": not base["fit"], "view": view, "D": D, "cands": None, "build_cpu": 0.0, "base_cpu": base_cpu}
    if base["fit"]:
        rec["grown"] = dict(outcome(base["program"], base_lang, task, checks), path="base_fit")
        rec["grown_no_loo"] = rec["grown"]
        grown_cpu = base_cpu
    else:
        t1 = pt()
        sk = grow.failure_description(view, base["bank"], cfg["n_partial"])
        cands = grow.candidates(view, sk, D, cfg["per_hole"], cfg["max_candidates"])
        state["cands"], state["build_cpu"] = cands, pt() - t1
        t2 = pt()
        acc, first, rows, calls, _ = grow.try_candidates(view, cands, D, cfg, B)
        grown_cpu = base_cpu + state["build_cpu"] + (pt() - t2)
        rec["grown"] = dict(outcome(acc["program"] if acc else None, acc["lang"] if acc else None, task, checks),
                            path="constructed" if acc else "no_accepted_piece", candidates=rows,
                            n_candidates=len(cands), sketches=[s["form"] for s in sk], retry_calls=calls)
        rec["grown_no_loo"] = dict(outcome(first["program"] if first else None, first["lang"] if first else None,
                                           task, checks), path="first_fit" if first else "no_fit")
    # classical comparator
    t1 = pt()
    full = dsl.Language(pieces=[(P.name_of(pc), P.fn_of(pc)) for pc in P.all_pieces(D)])
    c = dsl.search(view, full, (1 + M) * B, (1 + M) * cap, cfg["max_size"])
    classical_cpu = pt() - t1
    rec["classical"] = dict(outcome(c["program"], full, task, checks), calls=c["calls"], stop=c["stop"])
    rec["cpu_s"] = {"base": round(base_cpu, 4), "static": round(static_cpu, 4), "grown": round(grown_cpu, 4),
                    "classical": round(classical_cpu, 4)}
    return rec, state, checks


def run_pass(tasks, salt, cfg, B, t_start):
    recs, states, checks_of, stopped = [], {}, {}, None
    for t in tasks:
        if pt() - t_start > cfg["run_cpu_cap_s"]:
            stopped = f"run CPU cap reached before task {len(recs) + 1} of {len(tasks)}"
            break
        rec, st, checks = run_task(t, salt, cfg, B)
        recs.append(rec)
        states[t["id"]], checks_of[t["id"]] = st, checks
    failing = [r["id"] for r in recs if states[r["id"]]["failed"]]
    byid = {t["id"]: t for t in tasks}
    for r in recs:
        st = states[r["id"]]
        if not st["failed"]:
            r["shuffled"] = dict(r["grown"], path="base_fit")
            r["cpu_s"]["shuffled"] = r["cpu_s"]["base"]
            continue
        if len(failing) < 2:
            r["shuffled"] = {"answered": False, "recovered": False, "program": None, "path": "no_donor"}
            r["cpu_s"]["shuffled"] = r["cpu_s"]["base"]
            continue
        donor = failing[(failing.index(r["id"]) + 1) % len(failing)]
        ds = states[donor]
        t1 = pt()
        acc, first, rows, calls, _ = grow.try_candidates(st["view"], ds["cands"], ds["D"], cfg, B)
        r["cpu_s"]["shuffled"] = round(st["base_cpu"] + ds["build_cpu"] + (pt() - t1), 4)
        r["shuffled"] = dict(outcome(acc["program"] if acc else None, acc["lang"] if acc else None,
                                     byid[r["id"]], checks_of[r["id"]]),
                             path="constructed" if acc else "no_accepted_piece", donor=donor, candidates=rows,
                             retry_calls=calls)
    return recs, stopped


def loo_cost(recs):
    lost = [r["id"] for r in recs if r["grown_no_loo"]["recovered"] and not r["grown"]["recovered"]]
    prevented = [r["id"] for r in recs if r["grown_no_loo"]["answered"] and not r["grown_no_loo"]["recovered"]
                 and (r["grown"]["recovered"] or not r["grown"]["answered"])]
    return {"lost_right_answers": lost, "prevented_wrong_answers": prevented,
            "net_recoveries_grown_minus_no_loo": sum(int(r["grown"]["recovered"]) for r in recs)
            - sum(int(r["grown_no_loo"]["recovered"]) for r in recs)}


def summarize(recs, stopped, n_planned, B):
    col = {a: [int(r[a]["recovered"]) for r in recs] for a in ARMS}
    return {"base_budget": B, "n_tasks": len(recs),
            "n_planned": n_planned, "complete": len(recs) == n_planned, "stopped": stopped,
            "recovered": {a: sum(col[a]) for a in ARMS},
            "answered": {a: sum(int(r[a]["answered"]) for r in recs) for a in ARMS},
            "cpu_s": {a: round(sum(r["cpu_s"][a] for r in recs), 3) for a in ("static", "grown", "shuffled",
                                                                              "classical")},
            "base_fit": sum(int(r["base"]["fit"]) for r in recs),
            "cpu_cap_stops": sum(int(r["base"]["stop"] == "cpu_cap") + int(r["static"].get("stop") == "cpu_cap")
                                 + int(r["classical"].get("stop") == "cpu_cap") for r in recs),
            "grown_vs_shuffled": stats.compare("grown", col["grown"], "shuffled", col["shuffled"]),
            "grown_vs_static": stats.compare("grown", col["grown"], "static", col["static"]),
            "grown_vs_classical": stats.compare("grown", col["grown"], "classical", col["classical"]),
            "loo_cost": loo_cost(recs),
            "by_k": {str(k): dict({a: sum(c for c, r in zip(col[a], recs) if r["k_train"] == k) for a in ARMS},
                                  n=sum(1 for r in recs if r["k_train"] == k)) for k in (2, 3)}}


def check_go(study):
    go = os.path.join(study, "runs", "GO_T2")
    if not os.path.exists(go):
        raise SystemExit("no GO file")
    lines = dict(ln.strip().split("=", 1) for ln in open(go) if "=" in ln)
    if lines.get("protocol_sha256") != sha(os.path.join(study, "PROTOCOL.md")) or \
            lines.get("freeze_sha256") != sha(os.path.join(study, "FREEZE.json")):
        raise SystemExit("GO does not match PROTOCOL.md and FREEZE.json")
    salt = lines.get("salt", "")
    if len(salt) != 40 or any(ch not in "0123456789abcdef" for ch in salt):
        raise SystemExit("salt must be the 40-hex freeze commit hash")
    top = subprocess.run(["git", "-C", study, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                         check=True).stdout.strip()
    rel = os.path.relpath(os.path.join(study, "FREEZE.json"), top)
    blob = subprocess.run(["git", "-C", top, "show", f"{salt}:{rel}"], capture_output=True, check=True).stdout
    if hashlib.sha256(blob).hexdigest() != lines["freeze_sha256"]:
        raise SystemExit("the salt commit does not hold this FREEZE.json")
    frozen = json.load(open(os.path.join(study, "FREEZE.json")))["files_sha256"]
    for f, h in frozen.items():
        if sha(os.path.join(study, f)) != h:
            raise SystemExit(f"frozen file changed: {f}")
    return salt


def run(study, mode, out, only=None, dev_salt=None, budget=None, curve=False):
    cfg = json.load(open(os.path.join(study, "config", "CONFIG.json")))
    split = json.load(open(os.path.join(study, "split", "DEV_SPLIT.json")))
    tp = os.path.join(study, "data", "prepared", "tasks.json")
    if sha(tp) != split["tasks_json_sha256"]:
        raise SystemExit("tasks.json digest differs from the split record")
    budgets = [cfg["primary_base_budget"]] + (list(cfg["curve_base_budgets"]) if (mode == "held" or curve) else [])
    if mode == "dev":
        ids, salt = set(split["dev_tasks"]), (dev_salt or DEV_SALT)
        if budget:
            budgets = [int(budget)]
    elif mode == "held":
        salt = check_go(study)
        ids = set(split["held_pool_tasks"])
        out = os.path.join(study, "runs", "held")
        if os.path.exists(out):
            raise SystemExit("runs/held exists: the held run is one run only")
    else:
        raise SystemExit("mode must be dev or held")
    tasks = [t for t in json.load(open(tp))["tasks"] if t["id"] in ids]
    if only:
        tasks = [t for t in tasks if t["id"] in only]
    tasks.sort(key=lambda t: hashlib.sha256(f"{salt}|order|{t['id']}".encode()).hexdigest())
    os.makedirs(out, exist_ok=False if mode == "held" else True)
    status = os.path.join(out, "run.status")
    stamp = lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())  # noqa: E731
    with open(status, "w") as f:
        f.write(f"RUNNING {stamp()} mode={mode} tasks={len(tasks)} budgets={budgets} pid={os.getpid()}\n")
    try:
        t_start = pt()
        passes = {}
        for B in budgets:
            if passes and pt() - t_start > cfg["secondary_start_cpu_s"]:
                passes[str(B)] = {"base_budget": B, "skipped": "secondary_start_cpu_s reached"}
                continue
            recs, stopped = run_pass(tasks, salt, cfg, B, t_start)
            with open(os.path.join(out, f"records_B{B}.jsonl"), "w") as f:
                for r in recs:
                    f.write(json.dumps(r, sort_keys=True) + "\n")
            passes[str(B)] = summarize(recs, stopped, len(tasks), B)
            passes[str(B)]["static_budget"] = (1 + cfg["max_candidates"]) * B
            with open(status, "a") as f:
                f.write(f"PASS {stamp()} B={B} tasks={len(recs)} cpu_s={round(pt() - t_start, 1)}\n")
        primary_b = budgets[0]
        prim = passes[str(primary_b)]
        p1, p2 = prim["grown_vs_shuffled"], prim["grown_vs_static"]
        adj, rej = stats.holm([p1["mcnemar_exact_p"], p2["mcnemar_exact_p"]])
        primary = {"P1_grown_vs_shuffled": dict(p1, holm_p=adj[0],
                                                success=bool(rej[0] and p1["a_only"] > p1["b_only"])),
                   "P2_grown_vs_static": dict(p2, holm_p=adj[1],
                                              success=bool(rej[1] and p2["a_only"] > p2["b_only"])),
                   "complete": prim["complete"]}
        # budget curve: static at each budget against grown at the primary budget, paired by task
        prim_recs = {json.loads(ln)["id"]: json.loads(ln)
                     for ln in open(os.path.join(out, f"records_B{primary_b}.jsonl"))}
        curve_rows = []
        for B in sorted(int(b) for b in passes):
            ps = passes[str(B)]
            if "skipped" in ps:
                continue
            recs = [json.loads(ln) for ln in open(os.path.join(out, f"records_B{B}.jsonl"))]
            both = [r for r in recs if r["id"] in prim_recs]
            g = [int(prim_recs[r["id"]]["grown"]["recovered"]) for r in both]
            s = [int(r["static"]["recovered"]) for r in both]
            curve_rows.append({"base_budget": B, "static_budget": ps["static_budget"], "complete": ps["complete"],
                               "static": ps["recovered"]["static"], "grown_same_base": ps["recovered"]["grown"],
                               "shuffled_same_base": ps["recovered"]["shuffled"],
                               "classical": ps["recovered"]["classical"], "cpu_s": ps["cpu_s"],
                               "grown_primary_vs_this_static": stats.compare("grown_primary", g, "static", s)})
        catch = [row["base_budget"] for row in curve_rows if row["complete"]
                 and row["static"] >= prim["recovered"]["grown"]]
        summary = {"mode": mode, "label": "development" if mode == "dev" else "held",
                   "salt": salt, "budgets": budgets, "config": cfg, "n_tasks_planned": len(tasks),
                   "total_cpu_s": round(pt() - t_start, 2), "passes": passes, "primary": primary,
                   "curve": curve_rows,
                   "static_catches_up_at_base_budget": min(catch) if catch else None}
        with open(os.path.join(out, "summary.json"), "w") as f:
            json.dump(summary, f, indent=1, sort_keys=True)
        with open(status, "a") as f:
            f.write(f"DONE {stamp()} cpu_s={summary['total_cpu_s']}\n")
        return summary
    except BaseException as e:
        with open(status, "a") as f:
            f.write(f"FAILED {stamp()} {type(e).__name__}: {e}\n{traceback.format_exc()[-2000:]}\n")
        raise


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = {}
    for flag in ("--only", "--salt", "--budget"):
        if flag in a:
            i = a.index(flag)
            opt[flag] = a[i + 1]
            a = a[:i] + a[i + 2:]
    curve = "--curve" in a
    a = [x for x in a if x != "--curve"]
    only = set(opt["--only"].split(",")) if "--only" in opt else None
    if a[1] != "dev" and (opt or curve):
        raise SystemExit("--only, --salt, --budget and --curve are for development runs only")
    s = run(os.path.abspath(a[0]), a[1], os.path.abspath(a[2]) if len(a) > 2 else None, only, opt.get("--salt"),
            opt.get("--budget"), curve)
    prim = s["passes"][str(s["budgets"][0])]
    print(json.dumps({"label": s["label"], "total_cpu_s": s["total_cpu_s"],
                      "by_budget": {b: (p.get("recovered"), p.get("cpu_s")) for b, p in s["passes"].items()},
                      "catch_up": s["static_catches_up_at_base_budget"],
                      "P1": [s["primary"]["P1_grown_vs_shuffled"][k] for k in ("a_only", "b_only", "holm_p")],
                      "P2": [s["primary"]["P2_grown_vs_static"][k] for k in ("a_only", "b_only", "holm_p")],
                      "loo": prim["loo_cost"]["net_recoveries_grown_minus_no_loo"]}))
