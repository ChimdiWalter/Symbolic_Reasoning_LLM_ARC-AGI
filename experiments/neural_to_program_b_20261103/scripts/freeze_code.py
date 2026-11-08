"""Write CODE_FREEZE.json for Test B (PROTOCOL.md section 6). Refuses once any GO or run claim exists.

    python3 -I scripts/freeze_code.py

It checks the reviewed protocol and protocol freeze digests, the 38 construction-code files, the passing test log,
and the pinned non-answer inputs (driver check-inputs, which builds the assignment in memory and writes nothing),
then hashes every Test B source, test, launcher and test record.
"""
import glob
import os
import re
import sys
import time

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import common as C              # noqa: E402
from testb import driver as DR             # noqa: E402

REVIEWED = {"protocol_sha256": "f5d06798ae9be46acbd74d2523b892fbe1a45ff9d888ae05290529867ddefb88",
            "protocol_freeze_sha256": "81d58a1e3a5a3b3be9bf17f2bbea8ed6042279fa1a311789ba04550c802960b6"}
CORPUS = "experiments/architecture_sweep_20261026/a2/out/corpus.json"
CONDITIONS = {
    "1 within-donor output-index tie-break": "C1TieBreak (6 tests)",
    "2 exact hash-to-seed conversion": "C2Seed (4 tests)",
    "3 transitive release chain: outputs to GO_B, the full code and the assignment": "C3Chain (20 tests)",
    "4 child-inclusive CPU limit, receipts and recovery on forced interruption":
        "C4Guards (7 tests, including the two-child case), C4ProductionWorker (1 test), C4Recovery (6 tests)",
    "repaired point 1, no-fit label, flags and closest program": "test_r1_* (3 tests), RealWorker, RealWorkerClosest",
    "repaired point 2, random fallback": "test_r2_* (2 tests), test_c2_*",
    "repaired point 3, same-shape shuffled cohort": "test_r3_*, test_c1_*",
    "repaired point 4, child-inclusive CPU guards and INCOMPLETE": "C4Guards, C4Recovery",
    "repaired point 5, score gate": "test_r5_* (2 tests), test_c3_scorer_refuses_*",
    "repaired point 6, ARC task-level scoring": "test_r6_* (3 tests)",
    "answer blindness of the inference processes": "AnswerBlindness (6 tests)",
    "frozen construction code on synthetic tasks": "RealWorker, RealWorkerRetry, RealWorkerClosest"}
RULES = [
    "Donor order: other tasks of the same set by sha256('donor:' + task id). Rule 1: first task with an attempt-1 "
    "grid of the unit's shape, lowest such output index. Rule 2: first task with a pool candidate of that shape, "
    "lowest output index, then lowest pool position. Otherwise unmatched (no shuffled arm).",
    "Seed: int.from_bytes(sha256(UTF-8 text).digest(), 'big') (= int(hexdigest, 16)); random.Random(seed); text "
    "'random:' + task id + ':' + decimal output index; palette = sorted distinct colours of attempt 1; one draw = a "
    "whole grid, row by row, rng.choice(palette); at most 100 draws; fallback top-left (c + 1) mod 10.",
    "Run order: sha256('taskB:' + task id) for the evaluation and the development sets; then the pool stage in pool "
    "order (each valid candidate that differs from attempt 1 and from earlier candidates of its output).",
    "Per-arm guard: a guard process per arm; the worker under RLIMIT_CPU soft 100 CPU-s (SIGXCPU ends it) and hard "
    "101 CPU-s; PR_SET_PDEATHSIG ties the worker to its guard (SIGKILL) and the guard to the driver (SIGTERM); 400 s "
    "wall backstop; own process group; core dumps off. CPU_GUARD covers SIGXCPU, a hard-limit SIGKILL and the wall "
    "backstop (recorded as trigger), with the label NO_FIT_IN_BOUNDED_PROPOSAL and cpu_limit_stop.",
    "Child-inclusive limit: the worker runs under RLIMIT_NPROC 0 (soft and hard), set by the guard before exec and "
    "again by the worker before any import, so the kernel refuses every process and thread it tries to create "
    "(subprocess, os.fork, posix_spawn, os.system, multiprocessing, libc calls through ctypes) and the limit cannot "
    "be raised; an audit hook refuses the audited creation events with a clear error; the worker also sets one BLAS "
    "thread itself. The worker is the arm's only process, so RLIMIT_CPU bounds all of the arm's compute.",
    "Closest right-shaped program: every search of an arm (base and retries) runs with track_partial=True at the "
    "base budget; the record gives each search's best non-fitting right-shaped program and the arm's best over all "
    "of them (most correct cells, the earliest search on a tie); a guard-stopped arm gives it over the searches it "
    "finished.",
    "Receipt: getrusage(RUSAGE_CHILDREN) delta around the guard in the driver (guard plus reaped worker), "
    "cross-checked with os.wait4; the guard's own receipt (worker getrusage(RUSAGE_CHILDREN) plus guard CPU) "
    "recovers it when the driver died; with no receipt at all, the hard limit plus 1 s is charged as an upper bound.",
    "Unfinished (makes a primary run INCOMPLETE): NOT_STARTED, INTERRUPTED, KILLED (any other signal), WORKER_ERROR "
    "(non-zero exit, missing or invalid result, or a process left behind).",
    "Whole-run guard: an arm starts only if its full 100 CPU-s limit fits under 10 CPU-h counting driver CPU, every "
    "reaped child and every unrecovered upper bound; otherwise the run stops there.",
    "GO_B lines: protocol_sha256, protocol_freeze_sha256, code_freeze_sha256. GO_SCORE lines: "
    "outputs_freeze_sha256, scorer_sha256 (equal to its CODE_FREEZE entry), output_chain_review_sha256; the review "
    "must contain the line 'TEST_B_OUTPUT_CHAIN_REVIEW: PASS' and the outputs-freeze sha256.",
    "CORA-only correct outputs: the score-record result whose file is the pinned CORA-only submission.",
    "Bootstrap: tasks in sorted id order, numpy.random.default_rng(0), 10,000 resamples, one integers() draw per "
    "resample shared by every statistic, percentile 2.5 and 97.5; Holm adjusted p <= 0.05."]


def main():
    cfg = DR.Config()
    for p in ("GO_B", "RUN_CLAIM.json", "GO_SCORE", "SCORE_CLAIM.json"):
        if os.path.exists(os.path.join(cfg.runs, p)):
            raise SystemExit(f"runs/{p} exists: the code freeze must come before any GO or run")
    now = {"protocol_sha256": C.sha_file(cfg.protocol), "protocol_freeze_sha256": C.sha_file(cfg.protocol_freeze)}
    if now != REVIEWED:
        raise SystemExit(f"protocol digests differ from the reviewed ones: {now}")
    with open(os.path.join(EXP, "tests", "TEST_LOG.txt")) as f:
        log = f.read()
    ran = re.search(r"^Ran (\d+) tests? in ", log, re.M)
    if not ran or not re.search(r"^OK\s*$", log, re.M) or "FAILED" in log:
        raise SystemExit("tests/TEST_LOG.txt does not record a passing run")
    check = DR.check_inputs(cfg)          # verifies every pinned non-answer input and the 38 construction-code files
    rel = lambda p: os.path.relpath(p, C.REPO)
    files = sorted(glob.glob(os.path.join(EXP, "testb", "*.py")) + glob.glob(os.path.join(EXP, "tests", "*.py"))
                   + [os.path.join(EXP, "tests", n) for n in ("TEST_LOG.txt", "BENCH_ARM_COST.json")]
                   + [os.path.join(EXP, "scripts", n) for n in ("launch_testb.sh", "freeze_code.py")])
    fr = C.load_json(cfg.protocol_freeze)
    out = {"schema": "TESTB_CODE_FREEZE_V1", "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           **now, "protocol_review": "INDEPENDENT_PROTOCOL_REVIEW_V3.md sha256 "
                                     "426ad0ad78e973e2344ef348eb496b7316e7cd59d2ef7c7a4b5f51530b6b6381 "
                                     "(PASS_TEXT_ONLY)",
           "supersedes": {
               "code_freeze_sha256": "862d6a7a424524f7fada8eeb193c6a2ca14a9d0fced3ad0fd35297d92234901a",
               "review": "INDEPENDENT_EXACT_CODE_REVIEW_V1_20261103.md sha256 "
                         "2a80e9cb5300235c302298532ff8bef8f96bbfc78278ac1bf9abc5a6a7d5904b (HOLD)",
               "changes": ["blocking: the worker can create no process or thread (RLIMIT_NPROC 0 from the guard before "
                           "exec and from the worker before any import, plus an audit hook), so the 100 CPU-s "
                           "RLIMIT_CPU bounds the whole arm; two-child and every-route tests added",
                           "secondary: retries also run with track_partial=True and the arm's closest right-shaped "
                           "program is the best over all of its searches; a frozen-code witness where a retry "
                           "improves on the base search added"]},
           "files": {rel(p): C.sha_file(p) for p in files},
           "construction_data": {CORPUS: C.sha_file(os.path.join(C.REPO, CORPUS))},
           "construction_data_note": "read by lang0.build_g0 (the grammar's cost estimates); not among the 38 files "
                                     "pinned by the protocol freeze, so pinned here and checked before a run",
           "construction_code": f"{len(fr['construction_code_sha256'])} files pinned in PROTOCOL_FREEZE.json "
                                f"(commit {fr['construction_code_commit']}); all verified at this freeze",
           "roles": {"inference": ["testb/common.py", "testb/assign.py", "testb/labels.py", "testb/arm_worker.py",
                                   "testb/arm_guard.py", "testb/driver.py"],
                     "release_check": "testb/release_check.py",
                     "scorer": "experiments/neural_to_program_b_20261103/testb/scorer.py",
                     "launcher": "scripts/launch_testb.sh"},
           "environment": {"python": f"{C.PY_WORKER} -I (Python {sys.version.split()[0]})",
                           "blas_threads": 1, "cpu": "scripts/with_cpu_slot.sh (nice 19, ionice idle), one slot"},
           "limits": {"arm_cpu_s": cfg.arm_cpu_s, "arm_wall_s": cfg.arm_wall_s, "run_cpu_s": cfg.run_cpu_s},
           "implementation_rules": RULES,
           "tests": {"suite": "experiments/neural_to_program_b_20261103/tests/test_adversarial.py",
                     "passed": int(ran.group(1)), "log": "experiments/neural_to_program_b_20261103/tests/TEST_LOG.txt",
                     "synthetic_only": True, "conditions": CONDITIONS},
           "check_inputs": check,
           "state": "no GO_B, no RUN_CLAIM, no Test B run, no answer file opened or hashed"}
    C.write_json_atomic(cfg.code_freeze, out)
    print("CODE_FREEZE.json sha256", C.sha_file(cfg.code_freeze))


if __name__ == "__main__":
    main()
