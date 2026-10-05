"""Exercise v17_acceptance.main() end to end with mocked fixtures and tasks.
No acceptance seed, no engine: freeze_problems, fixtures and run_task are
replaced; every output path points into a scratch directory."""
import copy
import json
import os
import shutil
import sys

R = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
SP = "/tmp/claude-100350790/-deltos/1a86a57b-d764-4f47-a834-c23a0c91436c/scratchpad/main_mock"
sys.path.insert(0, R)
sys.path.insert(0, R + "/scripts")
import v17_acceptance as A                                         # noqa: E402

txt = open(R + "/logs/v17/acceptance_dryrun_dev_erratum01.log").read()
TEMPLATE = json.loads(txt[txt.find("{\n"):txt.rfind("}") + 1])["row"]


def setup(name):
    d = os.path.join(SP, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    A.OUT, A.ROWS = os.path.join(d, "report.json"), os.path.join(d, "rows.jsonl")
    A.START, A.MARKER = os.path.join(d, "start.json"), os.path.join(d, "DONE")
    A.MANIFEST = os.path.join(d, "manifest.json")
    open(A.MANIFEST, "w").write("{}")
    A.freeze_problems = lambda: ([], {})
    return d


def run(name, n_fixtures, task_fn):
    setup(name)
    A.fixtures = lambda: [{"seed": 1000 + k, "family": "(1,0)", "schema": None, "train": None,
                           "held": None} for k in range(n_fixtures)]
    A.run_task = task_fn
    A.main()
    rep = json.load(open(A.OUT))
    rows = [json.loads(l) for l in open(A.ROWS)] if os.path.exists(A.ROWS) else []
    print(f"{name:22s} outcome={rep['outcome']} conditions={rep['conditions']} "
          f"supp={rep['supplementary']} rows={len(rows)} marker={open(A.MARKER).read().strip()}")
    return rep


def ok_task(n, t, M):
    r = copy.deepcopy(TEMPLATE)
    r["seed"] = t["seed"]
    return r


def unexpected_task(n, t, M):
    if n == 2:
        raise OSError("disk")
    return ok_task(n, t, M)


def restoration_task(n, t, M):
    if n == 1:
        raise A.X.CompileError("RESTORATION_FAILURE", "mock")
    return ok_task(n, t, M)


run("all_ok", 6, ok_task)
run("unexpected_error", 6, unexpected_task)
run("restoration_failure", 6, restoration_task)
run("fixture_shortfall", 4, ok_task)
# the run-once guard: a second start in the same directory must refuse
try:
    A.main()
    print("SECOND START NOT REFUSED")
except SystemExit as exc:
    print("second start refused:", str(exc)[:80])
# the environment refusal
os.environ["ARC_DIHEDRAL_FRAMES"] = "1"
setup("env_refusal")
try:
    A.main()
    print("ENVIRONMENT NOT REFUSED")
except SystemExit as exc:
    print("environment refused:", str(exc)[:80])
del os.environ["ARC_DIHEDRAL_FRAMES"]
