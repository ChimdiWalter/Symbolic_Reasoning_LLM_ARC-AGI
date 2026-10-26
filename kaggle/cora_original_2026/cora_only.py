#!/usr/bin/env python3
"""CORA-ONLY-G3: an ARC Prize 2026 (ARC-AGI-2) Kaggle entry produced only by CORA's own engine. See CONFIG.md.

Pipeline: the sealed native CORA v23 harness (exactly as kaggle/native_v1 runs it), then ncv2-g3 search on every task
in isolated child processes with hard CPU limits, then a fixed attempt policy over CORA-owned sources:
NATIVE_CERTIFIED > NATIVE_CLAIMED_ON_CERTIFIED_TASK > G3_FIT_1 > NATIVE_CLAIMED > G3_FIT_2 > NATIVE_PARTIAL >
FALLBACK (the test input). No NVARC code,
checkpoint or prediction, no pretrained model, no network: `audit_modules` refuses to write a submission if any
forbidden module was imported.

Modes (environment K_MODE):
- "submit" (default): the competition's test file; writes /kaggle/working/submission.json.
- "dev": the public ARC-AGI-2 evaluation challenges. The solver never sees their solutions; `score_dev` (a separate
  notebook cell, run after every prediction is written) reads them. Its result is "exposed public evaluation,
  development evidence, not a competition score".
Other overrides (local emulation): K_INPUT, K_SRC, K_COMP, K_WORK, K_WORKERS, K_NATIVE_BUDGET_S, K_DEADLINE_S,
K_TASK_LIMIT, K_VARIANTS (comma list; the first variant writes submission.json), K_SKIP_NATIVE,
K_FORCE_NATIVE_FAIL (emulation of a harness failure).
"""
import hashlib
import json
import os
import py_compile
import shutil
import signal
import subprocess
import sys
import time

# one thread per numeric library, set before numpy is imported: the search children are forked from this process,
# and forking while library thread pools exist can deadlock; every child is single-threaded anyway
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

LABEL, VERSION = "CORA-ONLY-G3", "cora_original_2026_v1"
#: the sealed v23 chain flags and object-layer assets (identical to kaggle/native_v1/notebook.py)
CHAIN_FLAGS = {"ARC_DIHEDRAL_FRAMES": "45", "ARC_GENERATIVE": "1", "ARC_PATTERN_DERIVE": "1",
               "ARC_VARIANT_BUDGET": "1", "ARC_RAY_EXT": "1"}
ASSETS = {"library.json": "cdacd018da0bd9a3fa460c23beeff89fd5b0c5a85d70ecca276fe212df13ce03",
          "learned_verbs.json": "b1f07ba5f4337cf450b9c13cc142937c1c56b0dcc10e1796e6fcdb39fe2b585c"}
#: search variants (CONFIG.md): G3 is CORA-ONLY-G3; C1 and C2 are the pre-written development changes
VARIANTS = {"G3": {"search": "g3", "budget": 3000, "soft_cpu": 120, "hard_cpu": 300, "wall": 600},
            "C1": {"search": "g3", "budget": 10000, "soft_cpu": 300, "hard_cpu": 600, "wall": 1200},
            "C2": {"search": "g4", "budget": 3000, "soft_cpu": 120, "hard_cpu": 300, "wall": 600},
            # G5: rule-language version 5 (cora_neural_v2g5), a development variant; never the default
            "G5": {"search": "g5", "budget": 3000, "soft_cpu": 120, "hard_cpu": 300, "wall": 600}}
POLICIES = {"precision": ("NATIVE_CERTIFIED", "NATIVE_CLAIMED_ON_CERTIFIED_TASK", "G3_FIT_1", "NATIVE_CLAIMED",
                          "G3_FIT_2", "NATIVE_PARTIAL", "FALLBACK"),
            "search_first": ("NATIVE_CERTIFIED", "NATIVE_CLAIMED_ON_CERTIFIED_TASK", "G3_FIT_1", "G3_FIT_2",
                          "NATIVE_CLAIMED", "NATIVE_PARTIAL", "FALLBACK")}
CERTIFIED = frozenset({"NATIVE_CERTIFIED"})
#: module-name fragments that must never be imported (NVARC, Qwen, any model runtime, the v1 learned guide)
FORBIDDEN = ("torch", "transformers", "unsloth", "vllm", "peft", "qwen", "nvarc", "accelerate", "safetensors",
             "cora_neural_v1.prior", "cora_neural_v1.pilot", "cora_neural_v1.evaluate", "cora_neural_v1.audit")
INPUT = os.environ.get("K_INPUT", "/kaggle/input")
WORK = os.environ.get("K_WORK", "/kaggle/working")
T0 = time.time()


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def tree_sha(root):
    """One digest over every staged solver file (path and content)."""
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(root)):
        dirs[:] = sorted(x for x in dirs if x not in ("__pycache__", "data"))
        for f in sorted(files):
            if not f.endswith(".pyc"):
                p = os.path.join(d, f)
                h.update(os.path.relpath(p, root).encode() + b"\0" + _sha(p).encode() + b"\n")
    return h.hexdigest()


def find_comp():
    if os.environ.get("K_COMP"):
        return os.environ["K_COMP"]
    for dirname, _dirs, files in os.walk(INPUT):
        if "geocat_arc" in dirname or any(f.endswith(".tar.gz") for f in files):
            continue
        names = [f.lower() for f in files]
        if any(f.endswith(".json") and "challenges" in f for f in names):
            return dirname
    raise SystemExit(f"no competition data dir found under {INPUT}")


def resolve_src():
    """The solver tree: a directory holding geocat_arc/ and cora_neural_v2g3/ (Kaggle may unpack the archive)."""
    k_src = os.environ.get("K_SRC")
    if k_src and os.path.isdir(os.path.join(k_src, "geocat_arc")):
        return k_src
    tar_path = None
    for dirname, dirs, files in os.walk(INPUT):
        if "geocat_arc" in dirs and "cora_neural_v2g3" in dirs:
            return dirname
        for f in files:
            if f.endswith(".tar.gz") and "cora" in f and tar_path is None:
                tar_path = os.path.join(dirname, f)
    if tar_path is None:
        raise SystemExit(f"solver dataset not found under {INPUT}")
    import tarfile
    dest = os.path.join(WORK, "src_extracted")
    if not os.path.isdir(os.path.join(dest, "geocat_arc")):
        tarfile.open(tar_path).extractall(dest)
    return dest


def compile_all(code):
    """py_compile every staged .py: a syntax problem on Kaggle's Python fails here, before any work."""
    bad = []
    for d, dirs, files in os.walk(code):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "data")]
        for f in files:
            if f.endswith(".py"):
                try:
                    py_compile.compile(os.path.join(d, f), doraise=True)
                except py_compile.PyCompileError as e:
                    bad.append(f"{os.path.relpath(os.path.join(d, f), code)}: {str(e)[:200]}")
    return bad


def audit_modules():
    """Names of imported modules that match a forbidden fragment (must be empty)."""
    return sorted(m for m in sys.modules if any(k in m.lower() for k in FORBIDDEN))


def stage_inputs(code, comp, mode):
    """Copy ONLY the challenges the solver may see into code/data/arc. The evaluation solutions are never staged:
    the harness gets an empty solutions file. Training challenges and solutions are training data (as native_v1)."""
    data = os.path.join(code, "data", "arc")
    os.makedirs(data, exist_ok=True)
    task_file = "arc-agi_evaluation_challenges.json" if mode == "dev" else "arc-agi_test_challenges.json"
    if not os.path.exists(os.path.join(comp, task_file)):
        names = sorted(n for n in os.listdir(comp) if n.endswith(".json") and "challenges" in n and "training" not in n)
        task_file = names[0]
    for name in ("arc-agi_training_challenges.json", "arc-agi_training_solutions.json"):
        if os.path.exists(os.path.join(comp, name)):
            shutil.copy(os.path.join(comp, name), data)
    challenges = json.load(open(os.path.join(comp, task_file)))
    limit = int(os.environ.get("K_TASK_LIMIT", "0"))
    if limit:
        challenges = {k: challenges[k] for k in list(challenges)[:limit]}
    json.dump(challenges, open(os.path.join(data, "arc-agi_evaluation_challenges.json"), "w"))
    json.dump({}, open(os.path.join(data, "arc-agi_evaluation_solutions.json"), "w"))
    return challenges, task_file, _sha(os.path.join(comp, task_file))


def install_assets(code, out_dir):
    obj = os.path.join(out_dir, "object")
    os.makedirs(obj, exist_ok=True)
    for name, digest in ASSETS.items():
        src = os.path.join(code, name)
        if _sha(src) != digest:
            raise SystemExit(f"{name} sha256 {_sha(src)} != sealed {digest}")
        shutil.copy(src, os.path.join(obj, name))


def native_env(code):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARC_")}
    env["PYTHONPATH"] = code + ":" + os.path.join(code, "src")
    env.update(CHAIN_FLAGS)
    return env


def run_native(code, out_dir, budget_s, workers, man):
    """The NATIVE_BASELINE harness, as kaggle/native_v1/notebook.py runs it. Returns {task_id: progress row}."""
    install_assets(code, out_dir)
    cmd = [sys.executable, "scripts/run_unified_harness.py", "--split", "evaluation", "--workers", str(workers),
           "--out-dir", out_dir, "--run-id", "kaggle", "--emit-predictions", "--global-budget-s", str(budget_s)]
    if os.environ.get("K_FORCE_NATIVE_FAIL"):                 # emulation only: the harness fails at once
        cmd = [sys.executable, "-c", "raise SystemExit(3)"]
    t = time.time()
    proc = subprocess.Popen(cmd, env=native_env(code), cwd=code, start_new_session=True)
    try:
        man["native_returncode"] = proc.wait(timeout=budget_s + 600)
        man["native_status"] = "completed" if proc.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        man["native_returncode"], man["native_status"] = None, "killed_at_hard_limit"
    man["native_s"] = round(time.time() - t, 1)
    rows = {}
    progress = os.path.join(out_dir, "progress.jsonl")
    if os.path.exists(progress):
        for line in open(progress):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            rows[r.get("task_id")] = r
    return rows


def _as_task(t):
    return {"train": [(p["input"], p["output"]) for p in t["train"]], "test_inputs": [c["input"] for c in t["test"]]}


def _child(task, variant, path):
    """One task's search in its own process: a HARD CPU limit; the result is written atomically or not at all."""
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (variant["hard_cpu"], variant["hard_cpu"] + 5))
    c0 = time.process_time()
    try:
        if variant["search"] == "g4":
            from cora_neural_v2g4 import search as S
        elif variant["search"] == "g5":
            from cora_neural_v2g5 import search as S
        else:
            from cora_neural_v2g3 import search as S
        r = S.search(task, variant["budget"], cpu_cap_s=variant["soft_cpu"])
        out = {"status": "ok", "n_consistent": r["n_consistent"], "n_candidates": r["n_candidates"],
               "first_fit_at": r["first_fit_at"], "attempts_by_test": r["attempts_by_test"],
               "attempt_programs": r.get("attempt_programs", [])[:2], "predictions": r.get("predictions", [])[:50],
               "n_distinct_predictions": r.get("n_distinct_predictions")}
    except Exception as e:                                     # noqa: BLE001 (a task-level failure: no attempts)
        out = {"status": "error", "error": f"{type(e).__name__}: {str(e)[:300]}"}
    out["cpu_s"] = round(time.process_time() - c0, 2)
    json.dump(out, open(path + ".tmp", "w"))
    os.replace(path + ".tmp", path)


def run_search(code, challenges, native_rows, vname, deadline, workers, out_dir):
    """Every task once, `workers` children at a time, uncertified tasks first; wall-clock kill per task and at the
    global deadline. Returns {task_id: result} (status ok / error / cpu_limit / timeout / not_reached)."""
    import multiprocessing as mp
    variant = VARIANTS[vname]
    if code not in sys.path:
        sys.path.insert(0, code)
    import cora_neural_v2g3.search                            # noqa: F401  (loaded once, inherited by every fork)
    if variant["search"] == "g4":
        import cora_neural_v2g4.search                        # noqa: F401
    if variant["search"] == "g5":
        import cora_neural_v2g5.search                        # noqa: F401
    ctx = mp.get_context("fork")
    d = os.path.join(out_dir, vname)
    os.makedirs(d, exist_ok=True)
    cert = {t for t, r in native_rows.items() if object_certified(r)}
    order = [t for t in challenges if t not in cert] + [t for t in challenges if t in cert]
    res, running = {}, {}
    while order or running:
        while order and len(running) < workers and time.time() < deadline:
            tid = order.pop(0)
            path = os.path.join(d, f"{tid}.json")
            p = ctx.Process(target=_child, args=(_as_task(challenges[tid]), variant, path))
            p.start()
            running[p] = (tid, path, time.time())
        if time.time() >= deadline:
            for tid in order:
                res[tid] = {"status": "not_reached"}
            order = []
        for p, (tid, path, t) in list(running.items()):
            over = time.time() - t > variant["wall"] or time.time() >= deadline + 60
            if p.is_alive() and not over:
                continue
            if p.is_alive():
                p.kill()
            p.join()
            del running[p]
            if os.path.exists(path):
                res[tid] = json.load(open(path))
            else:
                res[tid] = {"status": "timeout" if over else ("cpu_limit" if p.exitcode in (-24, -9) else "no_result"),
                            "exitcode": p.exitcode}
        time.sleep(0.1)
    return res


def _valid(g):
    return (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) for r in g)
            and 1 <= len(g[0]) <= 30 and all(len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


def object_certified(native_row):
    """The native object layer solved the task with a real leave-one-out certificate: train-perfect and
    leave-one-out-by-reinduction-perfect over at least two folds (a single demonstration gives no certificate)."""
    o = (native_row or {}).get("object") or {}
    return bool(o.get("solved")) and (o.get("loo_folds") or 0) >= 2 and o.get("loo_score") == 1.0


def native_label(native_row):
    """The source label of native's solving-layer render, or None when native rendered nothing."""
    src = ((native_row or {}).get("predictions") or {}).get("attempt_1_source")
    if src is None:
        return None
    if object_certified(native_row):
        return "NATIVE_CERTIFIED" if src == "object" else "NATIVE_CLAIMED_ON_CERTIFIED_TASK"
    return "NATIVE_CLAIMED"


def candidates(task, i, native_row, search_row):
    """{source label: grid or None} for test input i. Native's render is the first solved layer's (pipeline,
    geocat, then object). It is NATIVE_CERTIFIED only when it is the object layer's own certified render; a pipeline
    or geocat render on a task the object layer certified is NATIVE_CLAIMED_ON_CERTIFIED_TASK (never marked
    certified: the grid is not the object layer's); any other native render is NATIVE_CLAIMED."""
    p = (native_row or {}).get("predictions") or {}
    a1s, a2s = p.get("attempt_1"), p.get("attempt_2")
    a1 = a1s[i] if a1s and i < len(a1s) else None
    a2 = a2s[i] if a2s and i < len(a2s) else None
    lab = native_label(native_row)
    g = (search_row or {}).get("attempts_by_test") if (search_row or {}).get("status") == "ok" else None
    gi = g[i] if g and i < len(g) else []
    return {"NATIVE_CERTIFIED": a1 if lab == "NATIVE_CERTIFIED" else None,
            "NATIVE_CLAIMED_ON_CERTIFIED_TASK": a1 if lab == "NATIVE_CLAIMED_ON_CERTIFIED_TASK" else None,
            "NATIVE_CLAIMED": a1 if lab == "NATIVE_CLAIMED" else None,
            "NATIVE_PARTIAL": a2,
            "G3_FIT_1": gi[0] if len(gi) > 0 else None,
            "G3_FIT_2": gi[1] if len(gi) > 1 else None,
            "FALLBACK": task["test"][i]["input"]}


def merge(challenges, native_rows, search_rows, policy="precision"):
    """submission (dict) and provenance (per task: per test input, [source of attempt_1, source of attempt_2])."""
    sub, prov = {}, {}
    for tid, task in challenges.items():
        entries, pr = [], []
        for i in range(len(task["test"])):
            c = candidates(task, i, native_rows.get(tid), search_rows.get(tid))
            chosen = []
            for label in POLICIES[policy]:
                gr = c.get(label)
                if _valid(gr) and all(gr != x for x, _ in chosen):
                    chosen.append((gr, label))
                if len(chosen) == 2:
                    break
            if len(chosen) == 1:
                chosen.append(chosen[0])
            entries.append({"attempt_1": chosen[0][0], "attempt_2": chosen[1][0]})
            pr.append([{"source": lab, "certified": lab in CERTIFIED} for _, lab in chosen])
        sub[tid], prov[tid] = entries, pr
    return sub, prov


def validate(sub, challenges):
    """Schema problems (must be empty): ids, order, positions, both attempts, valid grids."""
    probs = []
    if list(sub) != list(challenges):
        probs.append("task ids or order differ from the input file")
    for tid, task in challenges.items():
        e = sub.get(tid)
        if not isinstance(e, list) or len(e) != len(task["test"]):
            probs.append(f"{tid}: {len(e) if isinstance(e, list) else 'no'} entries for {len(task['test'])} test inputs")
            continue
        for i, x in enumerate(e):
            if set(x) != {"attempt_1", "attempt_2"} or not (_valid(x["attempt_1"]) and _valid(x["attempt_2"])):
                probs.append(f"{tid}[{i}]: invalid entry")
    return probs


def main():
    mode = os.environ.get("K_MODE", "submit")
    vnames = [v for v in os.environ.get("K_VARIANTS", "G3").split(",") if v]
    workers = int(os.environ.get("K_WORKERS", str(os.cpu_count() or 4)))
    man = {"label": LABEL, "version": VERSION, "mode": mode, "variants": vnames, "python": sys.version.split()[0],
           "started_unix": round(T0, 1), "workers": workers}
    src, comp = resolve_src(), find_comp()
    code = os.path.join(WORK, "solver")
    shutil.rmtree(code, ignore_errors=True)
    shutil.copytree(src, code, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    man["solver_tree_sha256"] = tree_sha(code)
    man["compile_problems"] = compile_all(code)
    if man["compile_problems"]:
        print("COMPILE PROBLEMS:", man["compile_problems"][:5])
    challenges, task_file, task_sha = stage_inputs(code, comp, mode)
    man.update(task_file=task_file, task_file_sha256=task_sha, tasks=len(challenges),
               test_outputs=sum(len(t["test"]) for t in challenges.values()))
    print(f"{LABEL} {VERSION} | mode {mode} | {task_file}: {man['tasks']} tasks, {man['test_outputs']} test outputs |"
          f" python {man['python']} | variants {vnames}", flush=True)
    out_dir = os.path.join(WORK, "run")
    native_rows = {}
    if not os.environ.get("K_SKIP_NATIVE"):
        nb = int(os.environ.get("K_NATIVE_BUDGET_S", str(6 * 3600)))
        native_rows = run_native(code, out_dir, nb, workers, man)
        print(f"native: {man['native_status']} in {man['native_s']} s, rows {len(native_rows)}", flush=True)
    deadline = T0 + float(os.environ.get("K_DEADLINE_S", str(11.3 * 3600)))
    results = {}
    for k, vname in enumerate(vnames):
        t = time.time()
        # each later variant gets an equal share of the remaining time, so the first is never starved
        share = deadline if k == 0 and len(vnames) == 1 else t + (deadline - t) / (len(vnames) - k)
        results[vname] = run_search(code, challenges, native_rows, vname, share, workers, out_dir)
        st = {}
        for r in results[vname].values():
            st[r["status"]] = st.get(r["status"], 0) + 1
        cands = [r.get("n_candidates", 0) for r in results[vname].values()]
        man[f"search_{vname}"] = {"s": round(time.time() - t, 1), "status": st,
                                  "tasks_with_fit": sum(1 for r in results[vname].values() if r.get("n_consistent")),
                                  "max_candidates": max(cands, default=0), "budget": VARIANTS[vname]["budget"],
                                  "cpu_s_max": max((r.get("cpu_s", 0) for r in results[vname].values()), default=0)}
        print(f"search {vname}: {man[f'search_{vname}']}", flush=True)
    man["forbidden_modules"] = audit_modules()
    if man["forbidden_modules"]:
        raise SystemExit(f"forbidden modules imported: {man['forbidden_modules']}")
    for k, vname in enumerate(vnames or ["NATIVE_ONLY"]):
        sub, prov = merge(challenges, native_rows, results.get(vname, {}), "precision")
        probs = validate(sub, challenges)
        name = "submission.json" if k == 0 else f"submission_{vname}.json"
        json.dump(sub, open(os.path.join(WORK, name), "w"))
        json.dump(prov, open(os.path.join(WORK, f"attempt_provenance_{vname}.json"), "w"))
        counts = {}
        for tid in prov:
            for pair in prov[tid]:
                for j, a in enumerate(pair):
                    counts[f"attempt_{j + 1}:{a['source']}"] = counts.get(f"attempt_{j + 1}:{a['source']}", 0) + 1
        man[f"output_{vname}"] = {"file": name, "schema_problems": probs, "sha256": _sha(os.path.join(WORK, name)),
                                  "sources": counts}
        print(f"{name}: schema problems {len(probs)} | sources {counts}", flush=True)
    if os.path.exists(os.path.join(WORK, "attempt_provenance_G3.json")):
        shutil.copy(os.path.join(WORK, "attempt_provenance_G3.json"), os.path.join(WORK, "attempt_provenance.json"))
    json.dump({"native": native_rows, "search": results}, open(os.path.join(WORK, "cora_rows.json"), "w"))
    import resource
    man["peak_rss_mb"] = {"main": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
                          "largest_child": round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024, 1)}
    man["elapsed_s"] = round(time.time() - T0, 1)
    json.dump(man, open(os.path.join(WORK, "execution_manifest.json"), "w"), indent=1)
    print("done in", man["elapsed_s"], "s", flush=True)


def score_dev(policies=("precision", "search_first")):
    """DEV ONLY, a separate step after every prediction is written: score each variant and attempt policy on the
    public evaluation solutions. ARC-style: a task scores the share of its test outputs matched by either attempt;
    the score is the mean over tasks. Development evidence, not a competition score."""
    comp = find_comp()
    sol_path = os.path.join(comp, "arc-agi_evaluation_solutions.json")
    solutions = json.load(open(sol_path))
    rows = json.load(open(os.path.join(WORK, "cora_rows.json")))
    challenges = json.load(open(os.path.join(WORK, "solver", "data", "arc", "arc-agi_evaluation_challenges.json")))
    report = {"label": "exposed public evaluation, development evidence, not a competition score",
              "solutions_sha256": _sha(sol_path), "tasks": len(challenges)}
    for vname in list(rows["search"]) or ["NATIVE_ONLY"]:
        for pol in policies:
            sub, prov = merge(challenges, rows["native"], rows["search"].get(vname, {}), pol)
            task_scores, by_source, solved = [], {}, []
            for tid, task in challenges.items():
                ok = 0
                for i, e in enumerate(sub[tid]):
                    truth = solutions[tid][i]
                    hit = [j for j, a in enumerate((e["attempt_1"], e["attempt_2"])) if a == truth]
                    if hit:
                        ok += 1
                        src = prov[tid][i][hit[0]]["source"]
                        by_source[src] = by_source.get(src, 0) + 1
                task_scores.append(ok / len(task["test"]))
                if ok:
                    solved.append(tid)
            report[f"{vname}/{pol}"] = {"score_pct": round(100 * sum(task_scores) / len(task_scores), 3),
                                        "tasks_with_a_correct_output": len(solved), "correct_by_source": by_source,
                                        "solved": solved}
    # reference: native CORA alone (its certified, claimed and partial renders under the same policy)
    sub, prov = merge(challenges, rows["native"], {}, "precision")
    ok_tasks = [tid for tid, task in challenges.items()
                if any(any(a == solutions[tid][i] for a in (e["attempt_1"], e["attempt_2"])) for i, e in enumerate(sub[tid]))]
    scores = [sum(any(a == solutions[tid][i] for a in (e["attempt_1"], e["attempt_2"])) for i, e in enumerate(sub[tid]))
              / len(task["test"]) for tid, task in challenges.items()]
    report["NATIVE_ONLY"] = {"score_pct": round(100 * sum(scores) / len(scores), 3),
                             "tasks_with_a_correct_output": len(ok_tasks), "solved": ok_tasks}
    json.dump(report, open(os.path.join(WORK, "dev_score.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in report.items() if isinstance(v, dict)}, indent=1))
    return report


if __name__ == "__main__":
    main()
