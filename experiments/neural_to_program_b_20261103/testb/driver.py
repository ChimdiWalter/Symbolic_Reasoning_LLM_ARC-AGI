"""Test B inference driver (PROTOCOL.md sections 5 and 6). Standard library only. It never opens an answer file:
the answer guard (common.install_answer_guard) is installed before anything is read, and refuses the pinned answers
path, any file whose name contains "solutions", hard links to them, and any subprocess naming them.

    python -I driver.py check-inputs   verify every pinned non-answer input, the construction code and its data;
                                       build the assignment in memory and print its denominators; writes nothing
    python -I driver.py run            needs runs/GO_B (exact lines); one use: runs/RUN_CLAIM.json (O_EXCL)
    python -I driver.py close          only after a forced interruption of `run`: finalize the arms from their
                                       durable records and receipts, write the completeness record (INCOMPLETE when
                                       any primary arm is unfinished) and the output freeze

Run sequence: GO_B -> code freeze -> pins -> driver lock -> RUN_CLAIM -> ASSIGNMENT.json -> arms in the assigned
order (primary, development, pool) -> COMPLETENESS.json -> OUTPUTS_FREEZE.json. Each arm runs in its own guard
process (arm_guard.py) and worker (arm_worker.py). Before each arm the whole-run guard checks that the arm's full
100 CPU-s limit still fits under 10 CPU-h (driver CPU + every child receipt + the upper bound of any receipt that
could not be recovered); otherwise the run stops there and every later arm is unfinished.
"""
import dataclasses
import fcntl
import json
import os
import resource
import subprocess
import sys
import time

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import assign as A              # noqa: E402
from testb import common as C              # noqa: E402
from testb import labels as LB             # noqa: E402

GO_B_KEYS = ("protocol_sha256", "protocol_freeze_sha256", "code_freeze_sha256")
GUARD = os.path.join(C.EXP, "testb", "arm_guard.py")
PRODUCTION_ROLES = {
    "eval_challenges": "outputs/score_first/data/arc-agi_evaluation_challenges.json",
    "cora_only_submission": "outputs/score_first/runs/op2_rehearsal_v1/submission.json",
    "cora_only_score": "kaggle/score_first_2026/configs/results/op2_rehearsal_v1/score.json",
    "eval_attempts": "outputs/score_first/runs/h_rehearsal_v1/submission_A.json",
    "dev_challenges": "outputs/score_first/runs/h_entry_v1/guarded_run_21d1b5c4a63d45d4a7aa2491a81d04cd/"
                      "challenges_used.json",
    "training_challenges": "<ARC data folder>/arc-agi_training_challenges.json",
}


@dataclasses.dataclass
class Config:
    """Production values are the defaults; the command line cannot change them. Tests build their own Config."""
    repo: str = C.REPO
    protocol: str = os.path.join(C.EXP, "PROTOCOL.md")
    protocol_freeze: str = os.path.join(C.EXP, "PROTOCOL_FREEZE.json")
    code_freeze: str = os.path.join(C.EXP, "CODE_FREEZE.json")
    runs: str = os.path.join(C.EXP, "runs")
    roles: dict = dataclasses.field(default_factory=lambda: dict(PRODUCTION_ROLES))
    arm_cpu_s: int = 100
    arm_wall_s: float = 400.0
    run_cpu_s: float = 36000.0
    python: str = C.PY_WORKER
    worker: str = os.path.join(C.EXP, "testb", "arm_worker.py")
    poll_s: float = 0.05
    recovery_wait_s: float = 60.0

    @property
    def run_dir(self):
        return os.path.join(self.runs, "run")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _cpu(ru):
    return ru.ru_utime + ru.ru_stime


def blocked_paths(cfg):
    """The scorer-only answers path(s), from the protocol freeze's key names only (the file is never opened)."""
    return sorted(C.load_json(cfg.protocol_freeze)["answers_scorer_only"])


# ---------------------------------------------------------------- verification (read-only, no answers)

def verify_pins(cfg):
    """Every pinned non-answer input and the construction code match the protocol freeze. Returns the paths the
    assignment reads."""
    fr = C.load_json(cfg.protocol_freeze)
    bad = []

    def check(path, want):
        p = C.absp(path, cfg.repo)
        try:
            got = C.sha_file(p)
        except OSError as e:
            bad.append(f"{path}: unreadable ({e.__class__.__name__})")
            return
        if got != want:
            bad.append(f"{path}: sha256 {got[:12]} != pinned {want[:12]}")

    for path, want in fr["protocol"].items():
        check(path, want)
    for path, want in {**fr["inputs_sha256"], **fr["development_inputs_sha256"]}.items():
        check(path, want)
    for key in ("neural_pools", "development_pools"):
        pin = fr[key]
        folder = C.absp(pin["folder"], cfg.repo)
        present = sorted(n for n in os.listdir(folder) if n.endswith(".json"))
        if present != sorted(pin["files_sha256"]):
            bad.append(f"{pin['folder']}: file set differs from the pinned {len(pin['files_sha256'])} files")
        for name, want in pin["files_sha256"].items():
            check(os.path.join(pin["folder"], name), want)
        if C.sha_text(json.dumps(pin["files_sha256"], sort_keys=True)) != pin["combined_sha256"]:
            bad.append(f"{key}: combined digest does not match its files")
    for path, want in fr["construction_code_sha256"].items():
        check(path, want)
    pinned = {**fr["inputs_sha256"], **fr["development_inputs_sha256"]}
    for role, path in cfg.roles.items():
        if path not in pinned:
            bad.append(f"role {role}: {path} is not a pinned input")
    if bad:
        raise SystemExit("pinned inputs do not verify:\n  " + "\n  ".join(bad))
    r = {k: C.absp(v, cfg.repo) for k, v in cfg.roles.items()}
    r["cora_only_submission_rel"] = cfg.roles["cora_only_submission"]
    r["eval_pools"] = C.absp(fr["neural_pools"]["folder"], cfg.repo)
    r["dev_pools"] = C.absp(fr["development_pools"]["folder"], cfg.repo)
    return r


def verify_code_freeze(cfg):
    cf = C.load_json(cfg.code_freeze)
    bad = [p for p, want in {**cf["files"], **cf["construction_data"]}.items()
           if not os.path.exists(C.absp(p, cfg.repo)) or C.sha_file(C.absp(p, cfg.repo)) != want]
    if cf["protocol_sha256"] != C.sha_file(cfg.protocol) or \
            cf["protocol_freeze_sha256"] != C.sha_file(cfg.protocol_freeze):
        bad.append("protocol or protocol freeze differs from the code freeze's")
    if bad:
        raise SystemExit("code freeze does not verify: " + ", ".join(bad))
    return cf


def verify_go_b(cfg):
    path = os.path.join(cfg.runs, "GO_B")
    if not os.path.exists(path):
        raise SystemExit("no runs/GO_B: the run is not released")
    go = C.read_go(path, GO_B_KEYS)
    want = {"protocol_sha256": C.sha_file(cfg.protocol), "protocol_freeze_sha256": C.sha_file(cfg.protocol_freeze),
            "code_freeze_sha256": C.sha_file(cfg.code_freeze)}
    for k in GO_B_KEYS:
        if go[k] != want[k]:
            raise SystemExit(f"GO_B {k} does not match the current file")
    return dict(go, go_b_sha256=C.sha_file(path))


def check_selected(cfg, core):
    sel = C.load_json(cfg.protocol_freeze)["selected"]
    p, d, s = core["primary"]["denominators"], core["development"]["denominators"], core["subgroup"]
    sg = sel["subgroup_cora_only_fails_or_abstains"]
    got = {"primary": (p["tasks"], p["units"]), "development": (d["tasks"], d["units"]),
           "subgroup": (len(s["tasks"]), len(s["outputs"])), "excluded": core["cora_only_correct"]}
    want = {"primary": (sel["primary"]["tasks"], sel["primary"]["outputs"]),
            "development": (sel["development_training"]["tasks"], sel["development_training"]["outputs"]),
            "subgroup": (sg["tasks"], sg["outputs"]), "excluded": sorted(sg["excluded_correct_outputs"])}
    if got != want:
        raise SystemExit(f"selected sets differ from the protocol freeze: {got} != {want}")


def check_inputs(cfg):
    C.install_answer_guard(blocked_paths(cfg))
    paths = verify_pins(cfg)
    core = A.build(paths)
    check_selected(cfg, core)
    out = {"pins": "all pinned non-answer inputs and the construction code verify",
           "primary": core["primary"]["denominators"], "development": core["development"]["denominators"],
           "subgroup": {"tasks": len(core["subgroup"]["tasks"]), "outputs": len(core["subgroup"]["outputs"])},
           "pool_units": len(core["pool"]["units"]), "pool_skipped": len(core["pool"]["skipped"]),
           "planned_arms": {st: sum(a["stage"] == st for a in core["plan"]) for st in ("primary", "development",
                                                                                         "pool")},
           "attempt_mismatch_tasks": core["attempt_mismatch_tasks"]}
    print(json.dumps(out, indent=1))
    return out


# ---------------------------------------------------------------- arms

def arm_paths(rd, key):
    b = os.path.join(rd, "arms", key)
    return {x: f"{b}.{x}.json" for x in ("input", "started", "result", "receipt", "progress")} | \
        {"record": f"{b}.json", "lock": f"{b}.lock", "log": f"{b}.log"}


def child_env(cfg):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "HOME": os.environ.get("HOME", "/"),
           "TESTB_BLOCKED": os.pathsep.join(blocked_paths(cfg))}
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[k] = "1"
    return env


def _load(p):
    try:
        return C.load_json(p)
    except (OSError, ValueError):
        return None


def classify(cfg, receipt, result, arm_key):
    """(outcome, guard_trigger) from the guard's receipt and the worker's result."""
    if receipt is None:
        return "KILLED", None
    if receipt.get("status") == "driver_gone_before_start":
        return "INTERRUPTED", None
    trig = receipt.get("trigger")
    if trig and trig.startswith("interrupted"):
        return "INTERRUPTED", None
    if trig == "wall_backstop":
        return LB.CPU_GUARD, "wall_backstop"
    if receipt.get("signal") == "SIGXCPU":
        return LB.CPU_GUARD, "rlimit_cpu"
    if receipt.get("signal") == "SIGKILL" and receipt.get("cpu_s", 0) >= cfg.arm_cpu_s:
        return LB.CPU_GUARD, "rlimit_cpu_hard"
    if receipt.get("signal"):
        return "KILLED", None
    if receipt.get("stragglers"):
        return "WORKER_ERROR", None
    if receipt.get("exit_code") != 0 or result is None or result.get("arm") != arm_key or \
            result.get("outcome") not in LB.FIT | {LB.NO_FIT}:
        return "WORKER_ERROR", None
    return result["outcome"], None


def finalize(cfg, rd, ctx, arm, driver_view=None):
    """Write the arm's final record from its durable files. driver_view: the driver's own receipt of the guard
    process (getrusage(RUSAGE_CHILDREN) delta and os.wait4), absent when recovering after an interruption."""
    p = arm_paths(rd, arm["arm"])
    receipt, result, progress, spec = _load(p["receipt"]), _load(p["result"]), _load(p["progress"]), _load(p["input"])
    outcome, trigger = classify(cfg, receipt, result, arm["arm"])
    if driver_view is not None and driver_view["guard_signal"] is None and receipt is not None:
        cpu = {"cpu_s": round(driver_view["cpu_s"], 6), "source": "driver getrusage(RUSAGE_CHILDREN) delta",
               "recovered": True}
    elif receipt is not None:
        cpu = {"cpu_s": round(receipt.get("cpu_s", 0.0) + receipt.get("guard_cpu_s", 0.0), 6),
               "source": "guard receipt (worker getrusage(RUSAGE_CHILDREN) + guard own CPU)", "recovered": True}
    else:
        cpu = {"cpu_s": None, "source": "not recoverable: the guard process was killed before its receipt",
               "recovered": False, "upper_bound_cpu_s": cfg.arm_cpu_s + 2}
    if driver_view is not None:
        cpu["driver_view"] = driver_view
    if receipt is not None:
        cpu["worker_cpu_s"] = receipt.get("cpu_s")
        cpu["worker_wait4_cpu_s"] = receipt.get("wait4_cpu_s")
        cpu["guard_cpu_s"] = receipt.get("guard_cpu_s")
    rec = {"arm": arm["arm"], "stage": arm["stage"], "unit": arm["unit"], "name": arm["name"], "outcome": outcome,
           "finished": outcome in LB.FINISHED, "receipt": cpu, "binding": ctx,
           "target_sha256": C.sha_text(C.canon(spec["target"])) if spec else None,
           "files_sha256": {k: (C.sha_file(p[k]) if os.path.exists(p[k]) else None)
                            for k in ("input", "result", "receipt", "progress")},
           "finalized_utc": now(), "finalized_by": "driver" if driver_view is not None else "close (recovery)"}
    if outcome == LB.CPU_GUARD:
        searches = (progress or {}).get("searches", [])
        rec["guard"] = {"trigger": trigger, "label": LB.NO_FIT, "searches_finished": searches,
                        "no_fit_flags": LB.no_fit_flags(searches, guard_stop=True),
                        "closest": LB.closest_of(searches, (progress or {}).get("cells_total"))
                        if progress else {"found": False}}
    C.write_json_atomic(p["record"], rec)
    return rec


def run_one(cfg, rd, ctx, spec, arm, used_before):
    p = arm_paths(rd, arm["arm"])
    C.write_json_atomic(p["input"], spec)
    C.write_json_atomic(p["started"], {"arm": arm["arm"], "utc": now(), "used_cpu_s_before": round(used_before, 6),
                                       "driver_cpu_s": round(_cpu(resource.getrusage(resource.RUSAGE_SELF)), 6),
                                       "python": cfg.python, "worker": cfg.worker, "guard": GUARD,
                                       "cpu_limit_s": cfg.arm_cpu_s, "wall_limit_s": cfg.arm_wall_s})
    g = {"arm": arm["arm"], "driver_pid": os.getpid(), "cpu_limit_s": cfg.arm_cpu_s, "wall_limit_s": cfg.arm_wall_s,
         "receipt": p["receipt"], "lock": p["lock"], "log": p["log"], "poll_s": cfg.poll_s,
         "cmd": [cfg.python, "-I", cfg.worker, p["input"], p["result"], p["progress"]]}
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    proc = subprocess.Popen([cfg.python, "-I", GUARD, json.dumps(g)], env=child_env(cfg), stdin=subprocess.DEVNULL,
                            close_fds=True)
    _, status, ru = os.wait4(proc.pid, 0)
    proc.returncode = os.waitstatus_to_exitcode(status)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    view = {"cpu_s": _cpu(after) - _cpu(before), "wait4_cpu_s": round(_cpu(ru), 6),
            "guard_exit_code": proc.returncode if proc.returncode >= 0 else None,
            "guard_signal": None if proc.returncode >= 0 else -proc.returncode}
    return finalize(cfg, rd, ctx, arm, view)


class Usage:
    """Whole-run CPU: the driver's own CPU, every reaped child, and the upper bound of unrecoverable receipts."""

    def __init__(self):
        self.unrecovered = 0.0

    def used(self):
        return (_cpu(resource.getrusage(resource.RUSAGE_SELF)) + _cpu(resource.getrusage(resource.RUSAGE_CHILDREN))
                + self.unrecovered)


# ---------------------------------------------------------------- completeness and output freeze

def arm_status(rd, arm):
    p = arm_paths(rd, arm["arm"])
    rec = _load(p["record"])
    if rec is not None:
        return rec["outcome"], rec
    return ("INTERRUPTED" if os.path.exists(p["started"]) else "NOT_STARTED"), None


def completeness(cfg, rd, core, stop_reason, interrupted, driver_cpu_s):
    stages = {}
    receipts, bound, guard_stops = 0.0, 0.0, []
    unit = A.unit_index(core)
    for arm in core["plan"]:
        st, rec = arm_status(rd, arm)
        s = stages.setdefault(arm["stage"], {"assigned_arms": 0, "finished_arms": 0, "unfinished": [],
                                             "assigned_tasks": set(), "unfinished_tasks": set()})
        s["assigned_arms"] += 1
        s["assigned_tasks"].add(unit[arm["unit"]]["task"])
        if st in LB.FINISHED:
            s["finished_arms"] += 1
        else:
            s["unfinished"].append({"arm": arm["arm"], "status": st})
            s["unfinished_tasks"].add(unit[arm["unit"]]["task"])
        if rec is not None:
            if rec["receipt"]["recovered"]:
                receipts += rec["receipt"]["cpu_s"]
            else:
                bound += rec["receipt"]["upper_bound_cpu_s"]
            if st == LB.CPU_GUARD:
                guard_stops.append({"arm": arm["arm"], "trigger": rec["guard"]["trigger"]})
    for st in ("primary", "development", "pool"):
        s = stages.setdefault(st, {"assigned_arms": 0, "finished_arms": 0, "unfinished": [], "assigned_tasks": set(),
                                   "unfinished_tasks": set()})
        s["complete"] = not s["unfinished"]
        s["assigned_tasks"], s["unfinished_tasks"] = len(s["assigned_tasks"]), sorted(s["unfinished_tasks"])
    status = "COMPLETE" if stages["primary"]["complete"] else "INCOMPLETE"
    return {"schema": "TESTB_COMPLETENESS_V1", "status": status,
            "rule": "INCOMPLETE when any assigned primary arm is unfinished; every assigned task stays in the "
                    "denominator; no full-population decision is made on an INCOMPLETE run",
            "stop_reason": stop_reason, "interrupted": interrupted, "stages": stages,
            "denominators": {"primary": core["primary"]["denominators"],
                             "development": core["development"]["denominators"],
                             "pool_units": len(core["pool"]["units"])},
            "guard_stops": guard_stops,
            "cpu": {"arm_receipts_cpu_s": round(receipts, 6), "unrecovered_upper_bound_cpu_s": bound,
                    "driver_cpu_s": round(driver_cpu_s, 6), "arm_cpu_limit_s": cfg.arm_cpu_s,
                    "arm_wall_limit_s": cfg.arm_wall_s, "run_cpu_limit_s": cfg.run_cpu_s}}


def outputs_freeze(cfg, rd, go):
    files = {}
    for root, _dirs, names in os.walk(rd):
        for n in names:
            fp = os.path.join(root, n)
            r = os.path.relpath(fp, rd)
            if r == "OUTPUTS_FREEZE.json" or n.endswith(".lock") or n.endswith(".tmp"):
                continue
            files[r] = C.sha_file(fp)
    comp = C.load_json(os.path.join(rd, "COMPLETENESS.json"))
    of = {"schema": "TESTB_OUTPUTS_FREEZE_V1", "utc": now(), "go_b_sha256": go["go_b_sha256"],
          "go_b": {k: go[k] for k in GO_B_KEYS}, "code_freeze_sha256": go["code_freeze_sha256"],
          "run_claim_sha256": C.sha_file(os.path.join(cfg.runs, "RUN_CLAIM.json")),
          "assignment_sha256": files["ASSIGNMENT.json"], "completeness_sha256": files["COMPLETENESS.json"],
          "status": comp["status"], "files_sha256": dict(sorted(files.items())),
          "answers": "never opened by the inference processes (audit-hook guard in the driver, guards and workers)"}
    C.write_json_atomic(os.path.join(rd, "OUTPUTS_FREEZE.json"), of)
    return of


def _status(cfg, **kw):
    """runs/run.status: progress for monitoring only (outside the run folder, so not part of the output freeze)."""
    C.write_json_atomic(os.path.join(cfg.runs, "run.status"), dict(kw, utc=now(), pid=os.getpid()))


def _driver_lock(rd):
    fd = os.open(os.path.join(rd, "DRIVER.lock"), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("another driver process holds this run")
    return fd


# ---------------------------------------------------------------- commands

def run(cfg):
    C.install_answer_guard(blocked_paths(cfg))
    go = verify_go_b(cfg)
    verify_code_freeze(cfg)
    paths = verify_pins(cfg)
    core = A.build(paths)                     # deterministic from the pinned inputs; built before the claim
    check_selected(cfg, core)
    rd = cfg.run_dir
    os.makedirs(os.path.join(rd, "arms"), exist_ok=True)
    lock = _driver_lock(rd)
    claim = os.path.join(cfg.runs, "RUN_CLAIM.json")
    try:
        C.exclusive_claim(claim, {"go_b_sha256": go["go_b_sha256"], **{k: go[k] for k in GO_B_KEYS}, "utc": now(),
                                  "pid": os.getpid(), "note": "one use; a second run is refused"})
    except FileExistsError:
        raise SystemExit("runs/RUN_CLAIM.json exists: GO_B is one use; after an interruption use `close`")
    ctx = {"go_b_sha256": go["go_b_sha256"], "code_freeze_sha256": go["code_freeze_sha256"],
           "run_claim_sha256": C.sha_file(claim)}
    C.write_json_atomic(os.path.join(rd, "ASSIGNMENT.json"), {"schema": "TESTB_ASSIGNMENT_V1", **ctx,
                                                              "written_utc": now(), "core": core})
    ctx["assignment_sha256"] = C.sha_file(os.path.join(rd, "ASSIGNMENT.json"))
    challenges = {"eval": C.load_json(paths["eval_challenges"]), "dev": C.load_json(paths["dev_challenges"])}
    usage, stop_reason = Usage(), None
    for i, arm in enumerate(core["plan"]):
        used = usage.used()
        if used + cfg.arm_cpu_s > cfg.run_cpu_s:
            stop_reason = "whole_run_guard"
            break
        _status(cfg, state="running", arm=arm["arm"], index=i, planned=len(core["plan"]), used_cpu_s=round(used, 1))
        rec = run_one(cfg, rd, ctx, A.arm_spec(core, challenges, arm), arm, used)
        if not rec["receipt"]["recovered"]:
            usage.unrecovered += rec["receipt"]["upper_bound_cpu_s"]
    comp = completeness(cfg, rd, core, stop_reason, False, _cpu(resource.getrusage(resource.RUSAGE_SELF)))
    C.write_json_atomic(os.path.join(rd, "COMPLETENESS.json"), comp)
    of = outputs_freeze(cfg, rd, go)
    os.close(lock)
    _status(cfg, state="finished", status=comp["status"], stop_reason=stop_reason,
            outputs_freeze_sha256=C.sha_file(os.path.join(rd, "OUTPUTS_FREEZE.json")))
    print(json.dumps({"status": comp["status"], "stop_reason": stop_reason,
                      "outputs_freeze_sha256": C.sha_file(os.path.join(rd, "OUTPUTS_FREEZE.json")),
                      "files": len(of["files_sha256"])}))
    return comp


def _alive_for(rd):
    """Processes still running this run's guards or workers (their command lines name this run's arm files)."""
    mark = os.path.join(rd, "arms") + os.sep
    out = []
    for pid in os.listdir("/proc"):
        if pid.isdigit() and int(pid) != os.getpid():
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    if mark.encode() in f.read():
                        out.append(int(pid))
            except OSError:
                pass
    return out


def close(cfg):
    """Recovery after a forced interruption of `run`. Never runs an arm."""
    C.install_answer_guard(blocked_paths(cfg))
    rd = cfg.run_dir
    if not os.path.exists(os.path.join(cfg.runs, "RUN_CLAIM.json")):
        raise SystemExit("no RUN_CLAIM: there is no run to close")
    if os.path.exists(os.path.join(rd, "OUTPUTS_FREEZE.json")):
        raise SystemExit("the run is already closed")
    lock = _driver_lock(rd)
    claim = C.load_json(os.path.join(cfg.runs, "RUN_CLAIM.json"))
    go = {k: claim[k] for k in GO_B_KEYS} | {"go_b_sha256": claim["go_b_sha256"]}
    if os.path.exists(os.path.join(rd, "COMPLETENESS.json")):     # interrupted after completeness: freeze only
        outputs_freeze(cfg, rd, go)
        os.close(lock)
        return C.load_json(os.path.join(rd, "COMPLETENESS.json"))
    t0 = time.monotonic()
    while _alive_for(rd) and time.monotonic() - t0 < cfg.recovery_wait_s:
        time.sleep(0.2)
    left = _alive_for(rd)
    if left:
        raise SystemExit(f"processes of this run are still alive: {left}")
    asg_path = os.path.join(rd, "ASSIGNMENT.json")
    if not os.path.exists(asg_path):                 # interrupted before the assignment was written: no arm ran
        paths = verify_pins(cfg)
        core = A.build(paths)
        C.write_json_atomic(asg_path, {"schema": "TESTB_ASSIGNMENT_V1", "go_b_sha256": go["go_b_sha256"],
                                       "code_freeze_sha256": go["code_freeze_sha256"],
                                       "run_claim_sha256": C.sha_file(os.path.join(cfg.runs, "RUN_CLAIM.json")),
                                       "written_utc": now(), "written_by": "close (recovery)", "core": core})
    asg = C.load_json(asg_path)
    core = asg["core"]
    ctx = {"go_b_sha256": asg["go_b_sha256"], "code_freeze_sha256": asg["code_freeze_sha256"],
           "run_claim_sha256": asg["run_claim_sha256"], "assignment_sha256": C.sha_file(asg_path)}
    recovered = []
    for arm in core["plan"]:
        p = arm_paths(rd, arm["arm"])
        if os.path.exists(p["started"]) and not os.path.exists(p["record"]):
            rec = finalize(cfg, rd, ctx, arm, None)
            recovered.append({"arm": arm["arm"], "outcome": rec["outcome"], "receipt": rec["receipt"]})
    last = [C.load_json(arm_paths(rd, a["arm"])["started"])["driver_cpu_s"] for a in core["plan"]
            if os.path.exists(arm_paths(rd, a["arm"])["started"])]
    comp = completeness(cfg, rd, core, "interrupted", True, max(last, default=0.0))
    comp["recovery"] = {"closed_utc": now(), "recovered_arms": recovered,
                        "driver_cpu_note": "driver CPU up to its last durable record; the driver runs no search"}
    C.write_json_atomic(os.path.join(rd, "COMPLETENESS.json"), comp)
    outputs_freeze(cfg, rd, go)
    os.close(lock)
    _status(cfg, state="closed after an interruption", status=comp["status"],
            outputs_freeze_sha256=C.sha_file(os.path.join(rd, "OUTPUTS_FREEZE.json")))
    print(json.dumps({"status": comp["status"], "recovered_arms": len(recovered),
                      "outputs_freeze_sha256": C.sha_file(os.path.join(rd, "OUTPUTS_FREEZE.json"))}))
    return comp


def main(argv):
    cmds = {"check-inputs": check_inputs, "run": run, "close": close}
    if len(argv) != 1 or argv[0] not in cmds:
        raise SystemExit(__doc__)
    cmds[argv[0]](Config())


if __name__ == "__main__":
    main(sys.argv[1:])
