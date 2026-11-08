"""Synthetic adversarial tests for the Test B code (PROTOCOL.md revision 3, review conditions of
INDEPENDENT_PROTOCOL_REVIEW_V3.md). Synthetic tasks and answers only: no real ARC task, pool or answer file is read,
no GO_B of the real experiment is written and nothing is run on real data.

    python3 -I tests/test_adversarial.py

Review conditions:   C1 within-donor output tie-break          (test_c1_*)
                     C2 exact hash-to-seed conversion           (test_c2_*)
                     C3 transitive release chain                 (test_c3_*)
                     C4 child-inclusive CPU limit, receipts and recovery   (test_c4_*)
Repaired points:     R1 no-fit label, flags and closest program, R2 random fallback, R3 same-shape cohort,
                     R4 CPU guards (the C4 tests), R5 score gate, R6 ARC task-level scoring   (test_r*_*)
Answer blindness:    test_a_*
The frozen construction code on synthetic tasks (base search, typed holes, menu retries): test_real_worker_*
"""
import dataclasses
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(TESTS)
sys.path.insert(0, EXP)
sys.path.insert(0, TESTS)
from testb import assign as A              # noqa: E402
from testb import common as C              # noqa: E402
from testb import driver as DR             # noqa: E402
from testb import labels as LB             # noqa: E402
from testb import release_check as RC      # noqa: E402
from testb import scorer as SC             # noqa: E402
import world as W                          # noqa: E402

PY = C.PY_WORKER
RUN_DRIVER = os.path.join(TESTS, "run_driver.py")
RUN_SCORER = os.path.join(TESTS, "run_scorer.py")
g, flip = W.g, W.flip
SEED_TEXT = "random:0934a4d8:0"
SEED_INT = 73825735554927910844995363245002404091095741964115045262572528393141788037109
GOLDEN_GRID = [[2, 3, 4], [3, 2, 3]]          # first draw for attempt 1 [[1, 2, 3], [4, 5, 6]] of 0934a4d8 output 0
SCRATCH = []


def tmp():
    d = tempfile.mkdtemp(prefix="testb_t_")
    SCRATCH.append(d)
    return d


def driver(w, cmd, log=None, timeout=600):
    return subprocess.run([PY, "-I", RUN_DRIVER, w.cfg_json(), cmd] + ([log] if log else []), capture_output=True,
                          text=True, timeout=timeout)


def scorer(w, review, log):
    return subprocess.run([PY, "-I", RUN_SCORER, w.cfg_json(), review, log], capture_output=True, text=True,
                          timeout=600)


def comp(w):
    return C.load_json(os.path.join(w.cfg.run_dir, "COMPLETENESS.json"))


def records(w):
    core = C.load_json(os.path.join(w.cfg.run_dir, "ASSIGNMENT.json"))["core"]
    return {a["arm"]: DR.arm_status(w.cfg.run_dir, a)[1] for a in core["plan"]}


def procs_with(*needles, exclude=()):
    out = []
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cl = f.read()
            except OSError:
                continue
            if all(n.encode() in cl for n in needles) and not any(x.encode() in cl for x in exclude):
                out.append(int(pid))
    return out


def wait_until(pred, timeout, step=0.05):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        v = pred()
        if v:
            return v
        time.sleep(step)
    return pred()


def ch(n):
    return {"train": [], "test": [{"input": [[0]]} for _ in range(n)]}


def basic_tasks():
    return {"fit00001": {"train": [(g(2, 2, 1), g(2, 2, 2))], "x": [g(2, 2, 3), g(3, 3, 3)],
                         "a1": [g(2, 2, 4), g(3, 3, 4)], "truth": [g(2, 2, 4), g(3, 3, 5)],
                         "pool": [[g(2, 2, 7)], []]},
            "fit00002": {"train": [(g(2, 2, 1), g(2, 2, 2))], "x": [g(2, 2, 5)], "a1": [g(2, 2, 6)],
                         "truth": [g(2, 2, 6)]},
            "nof00003": {"train": [(g(4, 1, 1), g(4, 1, 2))], "x": [g(4, 1, 1)], "a1": [g(4, 1, 2)],
                         "truth": [g(4, 1, 2)]}}


TEMPLATE = {}


def template():
    """One finished synthetic run, released for scoring; copied by every chain and score test."""
    if "w" not in TEMPLATE:
        w = make(basic_tasks(), correct=["fit00002:0"])
        W.release(w)
        r = driver(w, "run", os.path.join(w.root, "open_log.json"))
        assert r.returncode == 0, r.stderr
        W.release_score(w)
        TEMPLATE["w"] = w
    return TEMPLATE["w"]


def copy_of(w):
    return W.rebase(w, tmp())


def make(*a, **k):
    k.setdefault("root", tmp())
    return W.make(*a, **k)


# ============================================================ C1: within-donor output tie-break

class C1TieBreak(unittest.TestCase):
    def test_c1_rule1_lowest_output_index_of_the_first_hashed_donor(self):
        tasks = {"u0": ch(1), "dA": ch(3), "dB": ch(3)}
        attempts = {"u0": [g(2, 2, 1)], "dA": [g(3, 3, 1), g(2, 2, 4), g(2, 2, 5)],
                    "dB": [g(1, 1, 1), g(2, 2, 6), g(2, 2, 7)]}
        first = C.hashed_order("donor:", ["dA", "dB"])[0]
        u = next(x for x in A.build_set("eval", tasks, attempts, {})["units"] if x["task"] == "u0")
        self.assertEqual(u["shuffled_donor"], {"task": first, "output": 1, "source": "attempt_1", "candidate": None,
                                               "rule": 1})
        self.assertEqual(u["targets"]["shuffled"], attempts[first][1])

    def test_c1_rule2_lowest_output_then_lowest_candidate(self):
        tasks = {"u0": ch(1), "dA": ch(2), "dB": ch(2)}
        attempts = {"u0": [g(2, 3, 1)], "dA": [g(5, 5), g(6, 6)], "dB": [g(5, 5), g(6, 6)]}
        first, second = C.hashed_order("donor:", ["dA", "dB"])
        pools = {first: [[g(3, 3), g(2, 3, 8), g(2, 3, 9)], [g(2, 3, 7)]],
                 second: [[g(2, 3, 5)], []]}
        u = next(x for x in A.build_set("eval", tasks, attempts, pools)["units"] if x["task"] == "u0")
        self.assertEqual(u["shuffled_donor"], {"task": first, "output": 0, "source": "pool", "candidate": 1, "rule": 2})
        self.assertEqual(u["targets"]["shuffled"], g(2, 3, 8))

    def test_c1_rule1_beats_an_earlier_rule2_donor(self):
        tasks = {"u0": ch(1), "dA": ch(1), "dB": ch(1)}
        first, second = C.hashed_order("donor:", ["dA", "dB"])
        attempts = {"u0": [g(2, 2, 1)], first: [g(4, 4)], second: [g(2, 2, 3)]}
        pools = {first: [[g(2, 2, 9)]]}
        u = next(x for x in A.build_set("eval", tasks, attempts, pools)["units"] if x["task"] == "u0")
        self.assertEqual((u["shuffled_donor"]["task"], u["shuffled_donor"]["rule"]), (second, 1))

    def test_c1_donor_order_is_the_hash_order_not_names_or_insertion(self):
        ids = [f"t{i:02d}" for i in range(12)]
        hashed = C.hashed_order("donor:", ids)
        self.assertNotEqual(hashed, sorted(ids))
        tasks = {t: ch(1) for t in ids}
        attempts = {t: [g(2, 2, i % 10)] for i, t in enumerate(ids)}
        a = A.build_set("eval", tasks, attempts, {})
        for u in a["units"]:
            self.assertEqual(u["shuffled_donor"]["task"], next(t for t in hashed if t != u["task"]))
        rev = A.build_set("eval", dict(reversed(list(tasks.items()))), dict(reversed(list(attempts.items()))), {})
        self.assertEqual(C.canon(a), C.canon(rev))

    def test_c1_a_unit_is_never_its_own_donor(self):
        tasks = {"u0": ch(2), "dA": ch(1)}
        attempts = {"u0": [g(2, 2, 1), g(2, 2, 2)], "dA": [g(3, 3)]}
        units = A.build_set("eval", tasks, attempts, {"u0": [[g(2, 2, 5)], []]})["units"]
        self.assertTrue(all(u["shuffled_donor"] is None for u in units if u["task"] == "u0"))

    def test_c1_same_assignment_in_separate_processes(self):
        code = ("import sys,json;sys.path.insert(0,sys.argv[1]);from testb import assign as A, common as C\n"
                "ids=[f'q{i}' for i in range(30)];t={i:{'train':[],'test':[{'input':[[0]]}]*2} for i in ids}\n"
                "a={i:[[[k%10]*(1+k%3)]*(1+k%2) for k in (n,n+1)] for n,i in enumerate(ids)}\n"
                "print(C.sha_text(C.canon(A.build_set('eval',t,a,{}))))")
        outs = {subprocess.run([PY, "-I", "-c", code, EXP], capture_output=True, text=True).stdout for _ in range(3)}
        self.assertEqual(len(outs), 1)
        self.assertEqual(len(outs.pop().strip()), 64)


# ============================================================ C2: exact hash-to-seed conversion

class C2Seed(unittest.TestCase):
    def test_c2_seed_is_the_full_digest_as_one_big_endian_integer(self):
        for text in (SEED_TEXT, "random:abc:10", "random:été:3"):
            d = hashlib.sha256(text.encode("utf-8"))
            self.assertEqual(C.seed_of(text), int(d.hexdigest(), 16))
            self.assertEqual(C.seed_of(text), int.from_bytes(d.digest(), "big"))
        self.assertEqual(C.seed_of(SEED_TEXT), SEED_INT)

    def test_c2_random_target_equals_an_independent_reimplementation(self):
        def independent(task, j, a1):
            rng = random.Random(int(hashlib.sha256(f"random:{task}:{j}".encode("utf-8")).hexdigest(), 16))
            pal = sorted({v for r in a1 for v in r})
            for _ in range(100):
                gr = [[rng.choice(pal) for _ in r] for r in a1]
                if gr != a1:
                    return gr
            out = [list(r) for r in a1]
            out[0][0] = (out[0][0] + 1) % 10
            return out
        cases = [("0934a4d8", 0, [[1, 2, 3], [4, 5, 6]]), ("abc", 10, [[0, 9], [9, 0]]), ("t", 1, g(5, 7, 3)),
                 ("u", 2, [[1, 1, 1, 2]])]
        for task, j, a1 in cases:
            self.assertEqual(A.random_target(task, j, a1)[0], independent(task, j, a1))
        self.assertEqual(A.random_target("0934a4d8", 0, [[1, 2, 3], [4, 5, 6]])[0], GOLDEN_GRID)

    def test_c2_other_seed_forms_give_other_grids(self):
        d = hashlib.sha256(SEED_TEXT.encode("utf-8"))
        pal = [1, 2, 3, 4, 5, 6]
        for seed in (d.hexdigest(), d.digest(), SEED_INT & 0xFFFFFFFF, SEED_TEXT):
            r = random.Random(seed)
            self.assertNotEqual([[r.choice(pal) for _ in range(3)] for _ in range(2)], GOLDEN_GRID)

    def test_c2_output_index_is_plain_decimal_text(self):
        a1 = [[1, 2], [3, 4]]
        r = random.Random(C.seed_of("random:abc:10"))
        want = [[r.choice([1, 2, 3, 4]) for _ in range(2)] for _ in range(2)]
        self.assertEqual(A.random_target("abc", 10, a1)[0], want)
        r2 = random.Random(C.seed_of("random:abc:010"))
        self.assertNotEqual([[r2.choice([1, 2, 3, 4]) for _ in range(2)] for _ in range(2)], want)


# ============================================================ C3: transitive release chain

class C3Chain(unittest.TestCase):
    def assertBroken(self, w, needle, go_score=True):
        review = os.path.join(w.root, "OUTPUT_CHAIN_REVIEW.md")
        bad = RC.check_chain(w.cfg, review=review, go_score=go_score)
        self.assertTrue(bad, "the chain should not verify")
        self.assertTrue(any(needle in b for b in bad), f"{needle!r} not in {bad}")

    def test_c3_clean_chain_verifies(self):
        w = copy_of(template())
        self.assertEqual(RC.check_chain(w.cfg, review=os.path.join(w.root, "OUTPUT_CHAIN_REVIEW.md"),
                                        go_score=True), [])
        self.assertEqual(RC.check_chain(w.cfg), [])

    def _edit_json(self, path, fn):
        d = C.load_json(path)
        fn(d)
        C.write_json_atomic(path, d)

    def _refreeze(self, w):
        """A consistent forgery downstream of an edit: re-hash the record files, the outputs freeze and GO_SCORE."""
        rd = w.cfg.run_dir
        core = C.load_json(os.path.join(rd, "ASSIGNMENT.json"))["core"]
        for arm in core["plan"]:
            ap = DR.arm_paths(rd, arm["arm"])
            if os.path.exists(ap["record"]):
                self._edit_json(ap["record"], lambda r: r.__setitem__("files_sha256", {
                    k: (C.sha_file(ap[k]) if os.path.exists(ap[k]) else None)
                    for k in ("input", "result", "receipt", "progress")}))
        DR.outputs_freeze(w.cfg, rd, C.load_json(os.path.join(w.cfg.runs, "RUN_CLAIM.json")))
        W.release_score(w)

    def test_c3_code_file_changed_after_go(self):
        w = copy_of(template())
        with open(os.path.join(w.cfg.repo, W.REL_EXP, "testb", "driver.py"), "a") as f:
            f.write("# edit\n")
        self.assertBroken(w, "frozen file changed")

    def test_c3_construction_code_or_data_changed(self):
        w = copy_of(template())
        with open(os.path.join(w.cfg.repo, "code_stub.py"), "a") as f:
            f.write("# edit\n")
        self.assertBroken(w, "construction code changed")
        w2 = copy_of(template())
        with open(os.path.join(w2.cfg.repo, "corpus_stub.json"), "w") as f:
            f.write('{"x": 1}\n')
        self.assertBroken(w2, "frozen file changed")

    def test_c3_protocol_changed(self):
        w = copy_of(template())
        with open(w.cfg.protocol, "a") as f:
            f.write("edit\n")
        self.assertBroken(w, "GO_B protocol_sha256 differs")

    def test_c3_go_b_replaced_or_malformed(self):
        for text in ("protocol_sha256 " + "0" * 64 + "\n", None, "  ", "UPPER"):
            w = copy_of(template())
            p = os.path.join(w.cfg.runs, "GO_B")
            with open(p) as f:
                orig = f.read()
            new = {None: orig + "extra 1\n", "  ": orig.replace(" ", "  ", 1),
                   "UPPER": orig.replace(orig.split()[1], orig.split()[1].upper())}.get(text, text)
            with open(p, "w") as f:
                f.write(new)
            self.assertTrue(RC.check_chain(w.cfg), new)

    def test_c3_code_freeze_replaced_and_go_b_rewritten(self):
        w = copy_of(template())
        self._edit_json(w.cfg.code_freeze, lambda d: d.__setitem__("note", "forged"))
        W.release(w)
        self.assertBroken(w, "OUTPUTS_FREEZE names a different GO_B")

    def test_c3_assignment_target_forged_consistently(self):
        w = copy_of(template())
        p = os.path.join(w.cfg.run_dir, "ASSIGNMENT.json")
        self._edit_json(p, lambda d: d["core"]["primary"]["units"][0]["targets"].__setitem__("random", g(2, 2, 9)))
        self._refreeze(w)
        self.assertBroken(w, "ASSIGNMENT differs from the assignment rebuilt")

    def test_c3_arm_outcome_forged_consistently(self):
        w = copy_of(template())
        rd = w.cfg.run_dir
        key = next(a for a, r in records(w).items() if r and r["outcome"] == LB.NO_FIT)
        self._edit_json(DR.arm_paths(rd, key)["record"], lambda r: r.__setitem__("outcome", "VERIFIED"))
        self._refreeze(w)
        self.assertBroken(w, "outcome does not follow")

    def test_c3_result_changed_after_review(self):
        w = copy_of(template())
        key = next(a for a, r in records(w).items() if r and r["outcome"] == "VERIFIED")
        self._edit_json(DR.arm_paths(w.cfg.run_dir, key)["result"], lambda r: r.__setitem__("program", "forged"))
        self.assertBroken(w, "run file changed")
        self.assertBroken(w, "result file differs from its record")

    def test_c3_outputs_freeze_reforged_but_review_and_go_score_old(self):
        w = copy_of(template())
        key = next(a for a, r in records(w).items() if r and r["outcome"] == "VERIFIED")
        self._edit_json(DR.arm_paths(w.cfg.run_dir, key)["result"], lambda r: r.__setitem__("program", "forged"))
        review = os.path.join(w.root, "OUTPUT_CHAIN_REVIEW.md")
        with open(review) as f:
            old_review = f.read()
        self._refreeze(w)                             # new outputs freeze and GO_SCORE, but keep the old review text
        with open(review, "w") as f:
            f.write(old_review)
        self.assertBroken(w, "review file does not match GO_SCORE")

    def test_c3_record_deleted_or_extra_file(self):
        w = copy_of(template())
        key = next(a for a, r in records(w).items() if r)
        os.remove(DR.arm_paths(w.cfg.run_dir, key)["record"])
        self.assertBroken(w, "COMPLETENESS")
        w2 = copy_of(template())
        with open(os.path.join(w2.cfg.run_dir, "arms", "eval.zz000000.0.neural.json"), "w") as f:
            f.write("{}\n")
        self.assertBroken(w2, "arm file outside the plan")

    def test_c3_completeness_forged_consistently(self):
        w = copy_of(template())
        p = os.path.join(w.cfg.run_dir, "COMPLETENESS.json")
        self._edit_json(p, lambda d: d["stages"]["primary"].__setitem__("finished_arms", 0))
        self._refreeze(w)
        self.assertBroken(w, "COMPLETENESS stages does not follow")

    def test_c3_worker_input_forged_consistently(self):
        w = copy_of(template())
        key = next(a for a, r in records(w).items() if r and r["stage"] == "primary")
        self._edit_json(DR.arm_paths(w.cfg.run_dir, key)["input"], lambda s: s.__setitem__("demos", []))
        self._refreeze(w)
        self.assertBroken(w, "worker input differs")

    def test_c3_arm_started_with_another_worker_or_limits(self):
        w = copy_of(template())
        key = next(a for a, r in records(w).items() if r)
        self._edit_json(DR.arm_paths(w.cfg.run_dir, key)["started"],
                        lambda d: d.__setitem__("worker", "/elsewhere/other_worker.py"))
        self._refreeze(w)
        self.assertBroken(w, "started with another worker, guard or limits")
        w2 = copy_of(template())
        cfg = DR.Config(**{**dataclasses.asdict(w2.cfg), "arm_cpu_s": 100})
        bad = RC.check_chain(cfg)
        self.assertTrue(any("limits" in b or "arm_cpu_limit_s" in b for b in bad), bad)

    def test_c3_run_claim_replaced(self):
        w = copy_of(template())
        p = os.path.join(w.cfg.runs, "RUN_CLAIM.json")
        os.chmod(p, 0o644)
        self._edit_json(p, lambda d: d.__setitem__("go_b_sha256", "0" * 64))
        self.assertBroken(w, "RUN_CLAIM does not bind")

    def test_c3_scorer_changed(self):
        w = copy_of(template())
        with open(os.path.join(w.cfg.repo, W.REL_EXP, "testb", "scorer.py"), "a") as f:
            f.write("# edit\n")
        self.assertBroken(w, "GO_SCORE scorer digest")

    def test_c3_review_without_pass_or_for_another_freeze(self):
        for text in ("Synthetic review.\nTEST_B_OUTPUT_CHAIN_REVIEW: HOLD\n",
                     "Synthetic review for " + "1" * 64 + ".\nTEST_B_OUTPUT_CHAIN_REVIEW: PASS\n"):
            w = copy_of(template())
            W.release_score(w, review_text=text)
            self.assertBroken(w, "lacks its PASS line")

    def test_c3_go_score_for_another_outputs_freeze(self):
        w = copy_of(template())
        p = os.path.join(w.cfg.runs, "GO_SCORE")
        with open(p) as f:
            lines = f.read().split("\n")
        lines[0] = "outputs_freeze_sha256 " + "2" * 64
        with open(p, "w") as f:
            f.write("\n".join(lines))
        self.assertBroken(w, "GO_SCORE names a different OUTPUTS_FREEZE")

    def test_c3_pinned_input_changed(self):
        w = copy_of(template())
        with open(os.path.join(w.cfg.repo, "outputs/submission_A.json"), "a") as f:
            f.write(" ")
        self.assertBroken(w, "pins")

    def test_c3_scorer_refuses_a_broken_chain_without_touching_answers(self):
        w = copy_of(template())
        with open(os.path.join(w.cfg.repo, W.REL_EXP, "testb", "assign.py"), "a") as f:
            f.write("# edit\n")
        log = os.path.join(w.root, "score_log.json")
        r = scorer(w, os.path.join(w.root, "OUTPUT_CHAIN_REVIEW.md"), log)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("release check failed", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(w.cfg.runs, "SCORE_CLAIM.json")))
        opens = [o for o in C.load_json(log)["opens"] if o["path"] == w.answers]
        self.assertEqual(opens, [])


# ============================================================ C4 and R4: child CPU receipts, guards, recovery

def guard_world():
    tasks = {}
    for i, kind in enumerate(("brn", "imp", "two", "twb", "crs", "str")):
        tasks[f"{kind}0000{i}"] = {"train": [(g(1, i + 1, 1), g(1, i + 1, 2))], "x": [g(1, i + 1, 3)],
                                   "a1": [g(1, i + 1, 4)], "truth": [g(1, i + 1, 4)]}
    return make(tasks, arm_cpu_s=1, arm_wall_s=30.0)


class C4Guards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = guard_world()
        W.release(cls.w)
        cls.r = driver(cls.w, "run")
        cls.recs = records(cls.w)
        cls.comp = comp(cls.w)

    def by(self, kind):
        return {k: r for k, r in self.recs.items() if k.split(".")[1].startswith(kind)}

    def test_c4_run_finishes_and_is_incomplete_with_every_task_counted(self):
        self.assertEqual(self.r.returncode, 0, self.r.stderr)
        self.assertEqual(self.comp["status"], "INCOMPLETE")
        p = self.comp["stages"]["primary"]
        self.assertEqual(p["assigned_tasks"], 6)
        self.assertEqual(sorted(p["unfinished_tasks"]), ["crs00004", "str00005"])

    def test_c4_rlimit_cpu_guard_receipt_and_flags(self):
        for k, r in self.by("brn").items():
            self.assertEqual((r["outcome"], r["guard"]["trigger"]), (LB.CPU_GUARD, "rlimit_cpu"))
            self.assertTrue(r["finished"])
            self.assertGreaterEqual(r["receipt"]["worker_cpu_s"], 0.95)
            self.assertLess(r["receipt"]["worker_cpu_s"], 1.6)
            self.assertGreaterEqual(r["receipt"]["cpu_s"], r["receipt"]["worker_cpu_s"])
            f = r["guard"]["no_fit_flags"]
            self.assertEqual((f["cpu_limit_stop"], f["complete_search"], f["execution_budget_stop"]),
                             (True, False, True))
            self.assertEqual(r["guard"]["label"], LB.NO_FIT)
            self.assertEqual(len(r["guard"]["searches_finished"]), 1)

    def test_c4_guard_covers_interpreter_start_and_imports(self):
        for k, r in self.by("imp").items():
            self.assertEqual((r["outcome"], r["guard"]["trigger"]), (LB.CPU_GUARD, "rlimit_cpu"))
            self.assertEqual(r["guard"]["searches_finished"], [])
            self.assertGreaterEqual(r["receipt"]["worker_cpu_s"], 0.95)

    def test_c4_two_children_are_refused_so_the_arm_limit_bounds_all_compute(self):
        """The exact-code review's case: under a 1 CPU-s arm limit, a worker tries to start two children of 0.7 CPU-s
        each (1.4 CPU-s in all) and every other route. The guard's RLIMIT_NPROC = 0 refuses all of them."""
        arms = self.by("two")
        self.assertEqual(len(arms), 3)
        for k, r in arms.items():
            self.assertIn(r["outcome"], ("VERIFIED", "REACHABLE"))
            res = C.load_json(DR.arm_paths(self.w.cfg.run_dir, k)["result"])
            self.assertEqual(len(res["child_attempts"]), 9)
            self.assertTrue(all(a["refused"] for a in res["child_attempts"]), res["child_attempts"])
            rc = r["receipt"]
            self.assertLess(rc["worker_cpu_s"], 0.6)
            self.assertLess(abs(rc["worker_cpu_s"] - rc["worker_wait4_cpu_s"]), 0.02)
            receipt = C.load_json(DR.arm_paths(self.w.cfg.run_dir, k)["receipt"])
            self.assertEqual(receipt["worker_rlimit_nproc"], [0, 0])

    def test_c4_two_refused_children_then_a_burn_stop_at_the_arm_limit(self):
        for k, r in self.by("twb").items():
            self.assertEqual((r["outcome"], r["guard"]["trigger"]), (LB.CPU_GUARD, "rlimit_cpu"))
            prog = C.load_json(DR.arm_paths(self.w.cfg.run_dir, k)["progress"])
            self.assertTrue(all(a["refused"] for a in prog["child_attempts"]))
            self.assertGreaterEqual(r["receipt"]["worker_cpu_s"], 0.95)
            self.assertLessEqual(r["receipt"]["worker_cpu_s"], 1.1)

    def test_c4_worker_error_and_straggler_are_unfinished(self):
        for k, r in self.by("crs").items():
            self.assertEqual((r["outcome"], r["finished"]), ("WORKER_ERROR", False))
        for k, r in self.by("str").items():
            self.assertEqual((r["outcome"], r["finished"]), ("WORKER_ERROR", False))
            rc = C.load_json(DR.arm_paths(self.w.cfg.run_dir, k)["receipt"])
            self.assertFalse(rc["stragglers"])                  # its creation was refused
            with open(DR.arm_paths(self.w.cfg.run_dir, k)["log"]) as f:
                self.assertIn("BlockingIOError", f.read())
        self.assertEqual(procs_with("time.sleep(3600)", "import time"), [])

    def test_c4_whole_run_cpu_accounts_every_receipt(self):
        cpu = self.comp["cpu"]
        total = sum(r["receipt"]["cpu_s"] for r in self.recs.values() if r and r["receipt"]["recovered"])
        self.assertAlmostEqual(cpu["arm_receipts_cpu_s"], round(total, 6), places=5)
        self.assertGreater(cpu["driver_cpu_s"], 0)
        self.assertEqual(len(self.comp["guard_stops"]), 9)
        self.assertEqual(RC.check_chain(self.w.cfg), [])


class C4ProductionWorker(unittest.TestCase):
    def test_c4_production_worker_refuses_every_process_and_thread_on_import(self):
        """Importing the production worker sets RLIMIT_NPROC = 0 (and one BLAS thread) before anything else; with no
        guard and an empty environment, no route can create a process or thread, and the limit cannot be raised."""
        code = r"""
import json, os, resource, sys
sys.path.insert(0, sys.argv[1])
import testb.arm_worker
import ctypes, multiprocessing, subprocess, threading
res = {"rlimit_nproc": list(resource.getrlimit(resource.RLIMIT_NPROC)), "blas": os.environ.get("OPENBLAS_NUM_THREADS")}
def t(name, f):
    try:
        f(); res[name] = "allowed"
    except (OSError, RuntimeError, ValueError) as e:
        res[name] = "refused " + e.__class__.__name__
t("subprocess", lambda: subprocess.run(["true"]))
t("os.fork", lambda: os.waitpid(os.fork(), 0))
t("posix_spawn", lambda: os.waitpid(os.posix_spawn("/bin/true", ["true"], {}), 0))
t("mp_spawn", lambda: multiprocessing.get_context("spawn").Process(target=int).start())
def lf():
    pid = ctypes.CDLL(None, use_errno=True).fork()
    if pid == 0:
        os._exit(0)
    if pid < 0:
        raise OSError(ctypes.get_errno(), "fork failed")
t("libc_fork", lf)
t("thread", lambda: threading.Thread(target=int).start())
t("raise_limit", lambda: resource.setrlimit(resource.RLIMIT_NPROC, (5, 5)))
import numpy
res["numpy"] = numpy.__version__
print(json.dumps(res))
"""
        r = subprocess.run([PY, "-I", "-c", code, EXP], capture_output=True, text=True, timeout=120,
                           env={"PATH": "/usr/bin:/bin"})
        res = json.loads(r.stdout)
        self.assertEqual((res.pop("rlimit_nproc"), res.pop("blas")), ([0, 0], "1"))
        self.assertTrue(res.pop("numpy"))
        self.assertTrue(all(v.startswith("refused") for v in res.values()), res)
        self.assertNotIn("blas_thread_init", r.stderr)


class C4Recovery(unittest.TestCase):
    def world(self, **kw):
        tasks = {"fit00001": {"train": [(g(2, 2, 1), g(2, 2, 2))], "x": [g(2, 2, 3)], "a1": [g(2, 2, 4)],
                              "truth": [g(2, 2, 4)]},
                 "slp00002": {"train": [(g(2, 2, 1), g(2, 2, 2))], "x": [g(2, 2, 3)], "a1": [g(2, 2, 5)],
                              "truth": [g(2, 2, 5)]}}
        w = make(tasks, arm_cpu_s=kw.get("arm_cpu_s", 2), arm_wall_s=kw.get("arm_wall_s", 60.0))
        W.release(w)
        return w

    def start(self, w, session=False):
        return subprocess.Popen([PY, "-I", RUN_DRIVER, w.cfg_json(), "run"], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=session)

    def sleeper(self, w):
        return procs_with(W.SYNTH_WORKER, os.path.join(w.cfg.run_dir, "arms"), "slp00002", exclude=("arm_guard.py",))

    def test_c4_driver_killed_mid_arm_receipt_recovered_and_incomplete(self):
        w = self.world()
        p = self.start(w)
        pids = wait_until(lambda: self.sleeper(w), 60)
        self.assertTrue(pids, "no in-flight arm to interrupt")
        time.sleep(0.5)
        os.kill(p.pid, signal.SIGKILL)
        p.wait()
        self.assertTrue(wait_until(lambda: not DR._alive_for(w.cfg.run_dir), 15), "orphan arm processes remain")
        r = driver(w, "close")
        self.assertEqual(r.returncode, 0, r.stderr)
        c = comp(w)
        self.assertEqual((c["status"], c["interrupted"], c["stop_reason"]), ("INCOMPLETE", True, "interrupted"))
        rec = c["recovery"]["recovered_arms"]
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["outcome"], "INTERRUPTED")
        self.assertTrue(rec[0]["receipt"]["recovered"])
        self.assertTrue(rec[0]["receipt"]["source"].startswith("guard receipt"))
        receipt = C.load_json(DR.arm_paths(w.cfg.run_dir, rec[0]["arm"])["receipt"])
        self.assertEqual(receipt["trigger"], "interrupted:SIGTERM")
        statuses = [u["status"] for u in c["stages"]["primary"]["unfinished"]]
        self.assertIn("INTERRUPTED", statuses)
        self.assertEqual(c["stages"]["primary"]["assigned_tasks"], 2)
        self.assertIn("slp00002", c["stages"]["primary"]["unfinished_tasks"])
        self.assertEqual(RC.check_chain(w.cfg), [])
        again = driver(w, "run")
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("RUN_CLAIM", again.stderr)
        self.assertIn("already closed", driver(w, "close").stderr)
        self.assertEqual(RC.check_chain(w.cfg), [])

    def test_c4_whole_tree_killed_receipt_bounded_and_incomplete(self):
        w = self.world()
        p = self.start(w, session=True)
        pids = wait_until(lambda: self.sleeper(w), 60)
        self.assertTrue(pids)
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
        self.assertTrue(wait_until(lambda: not DR._alive_for(w.cfg.run_dir), 15), "the worker outlived its guard")
        r = driver(w, "close")
        self.assertEqual(r.returncode, 0, r.stderr)
        c = comp(w)
        self.assertEqual(c["status"], "INCOMPLETE")
        rec = c["recovery"]["recovered_arms"]
        self.assertEqual([x["outcome"] for x in rec], ["KILLED"])
        self.assertFalse(rec[0]["receipt"]["recovered"])
        self.assertEqual(rec[0]["receipt"]["upper_bound_cpu_s"], w.cfg.arm_cpu_s + 2)
        self.assertEqual(c["cpu"]["unrecovered_upper_bound_cpu_s"], w.cfg.arm_cpu_s + 2)
        self.assertEqual(RC.check_chain(w.cfg), [])

    def test_c4_externally_killed_worker_is_unfinished(self):
        w = self.world()
        p = self.start(w)
        killed = set()
        t0 = time.monotonic()
        while p.poll() is None and time.monotonic() - t0 < 120:
            for pid in self.sleeper(w):
                if pid not in killed:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    killed.add(pid)
            time.sleep(0.05)
        self.assertEqual(p.wait(), 0)
        c = comp(w)
        self.assertEqual(c["status"], "INCOMPLETE")
        slp = {k: r for k, r in records(w).items() if ".slp00002." in k}
        self.assertTrue(slp and all(r["outcome"] == "KILLED" and not r["finished"] for r in slp.values()))
        self.assertTrue(all(r["receipt"]["recovered"] for r in slp.values()))

    def test_c4_wall_backstop_is_a_guard_stop(self):
        w = self.world(arm_wall_s=1.5)
        r = driver(w, "run")
        self.assertEqual(r.returncode, 0, r.stderr)
        slp = {k: v for k, v in records(w).items() if ".slp00002." in k}
        self.assertTrue(slp)
        for v in slp.values():
            self.assertEqual((v["outcome"], v["guard"]["trigger"]), (LB.CPU_GUARD, "wall_backstop"))
            self.assertTrue(v["guard"]["no_fit_flags"]["cpu_limit_stop"])
        self.assertEqual(comp(w)["status"], "COMPLETE")

    def test_c4_whole_run_guard_stops_before_an_arm_could_overrun(self):
        w = make({"brn00001": {"train": [(g(1, 1, 1), g(1, 1, 2))], "x": [g(1, 1, 3)], "a1": [g(1, 1, 4)],
                                 "truth": [g(1, 1, 4)]}}, arm_cpu_s=1, run_cpu_s=1.6)
        W.release(w)
        self.assertEqual(driver(w, "run").returncode, 0)
        c = comp(w)
        self.assertEqual((c["status"], c["stop_reason"]), ("INCOMPLETE", "whole_run_guard"))
        st = c["stages"]["primary"]
        self.assertGreaterEqual(st["finished_arms"], 1)
        self.assertTrue(any(u["status"] == "NOT_STARTED" for u in st["unfinished"]))
        self.assertEqual(st["assigned_tasks"], 1)
        self.assertLessEqual(c["cpu"]["arm_receipts_cpu_s"] + c["cpu"]["driver_cpu_s"], w.cfg.run_cpu_s)
        w0 = make({"fit00001": {"train": [(g(1, 1, 1), g(1, 1, 2))], "x": [g(1, 1, 3)], "a1": [g(1, 1, 4)],
                                  "truth": [g(1, 1, 4)]}}, arm_cpu_s=1, run_cpu_s=0.5)
        W.release(w0)
        self.assertEqual(driver(w0, "run").returncode, 0)
        c0 = comp(w0)
        self.assertEqual((c0["status"], c0["stages"]["primary"]["finished_arms"]), ("INCOMPLETE", 0))
        self.assertTrue(all(u["status"] == "NOT_STARTED" for u in c0["stages"]["primary"]["unfinished"]))

    def test_c4_unrecoverable_receipt_counts_its_upper_bound(self):
        w = make({"kgd00001": {"train": [(g(1, 1, 1), g(1, 1, 2))], "x": [g(1, 1, 3)], "a1": [g(1, 1, 4)],
                                 "truth": [g(1, 1, 4)]}}, arm_cpu_s=1, run_cpu_s=4.0)
        W.release(w)
        self.assertEqual(driver(w, "run").returncode, 0)
        c = comp(w)
        ran = [r for r in records(w).values() if r]
        self.assertEqual([r["outcome"] for r in ran], ["KILLED"])
        self.assertFalse(ran[0]["receipt"]["recovered"])
        self.assertEqual((c["stop_reason"], c["status"]), ("whole_run_guard", "INCOMPLETE"))
        self.assertEqual(c["cpu"]["unrecovered_upper_bound_cpu_s"], 3)


# ============================================================ R1, R2, R3, R5, R6

class RepairedPoints(unittest.TestCase):
    def test_r1_no_fit_flags_truth_table(self):
        s = lambda stop, cap=False: {"stop": stop, "closure_capped": cap}
        self.assertEqual(LB.no_fit_flags([s("max_size"), s("max_size")]),
                         {"complete_search": True, "execution_budget_stop": False, "cpu_limit_stop": False,
                          "enumeration_capped": False})
        self.assertEqual(LB.no_fit_flags([s("max_size"), s("budget")])["complete_search"], False)
        self.assertEqual(LB.no_fit_flags([s("cpu_cap")])["cpu_limit_stop"], True)
        self.assertEqual(LB.no_fit_flags([s("max_size", True)]),
                         {"complete_search": False, "execution_budget_stop": False, "cpu_limit_stop": False,
                          "enumeration_capped": True})
        self.assertEqual(LB.no_fit_flags([s("max_size")], guard_stop=True)["complete_search"], False)
        self.assertEqual(LB.STOP_REASON["max_size"], None)

    def test_r1_no_fit_label_in_records_and_no_language_claim_anywhere(self):
        w = template()
        nof = {k: r for k, r in records(w).items() if r and ".nof00003." in k}
        self.assertTrue(nof)
        for k in nof:
            res = C.load_json(DR.arm_paths(w.cfg.run_dir, k)["result"])
            self.assertEqual(res["outcome"], LB.NO_FIT)
            self.assertEqual(set(res["no_fit_flags"]), {"complete_search", "execution_budget_stop", "cpu_limit_stop",
                                                        "enumeration_capped"})
        texts = []
        for root, _d, names in os.walk(os.path.join(w.cfg.repo, W.REL_EXP, "runs")):
            for n in names:
                with open(os.path.join(root, n), "rb") as f:
                    texts.append(f.read().decode("utf-8", "replace").lower())
        for src in ("labels.py", "arm_worker.py", "scorer.py"):
            with open(os.path.join(EXP, "testb", src)) as f:
                texts.append(f.read().lower())
        for t in texts:
            for bad in ("expressib", "inexpressible", "cannot express"):
                self.assertNotIn(bad, t)

    def test_r1_closest_program_is_the_best_over_base_and_retries(self):
        s = lambda name, c: {"search": name, "closest": None if c is None else {"program": name, "cells_correct": c}}
        got = LB.closest_of([s("base", 5), s("retry A", 9), s("retry B", 9), s("retry C", None)], 20)
        self.assertEqual((got["search"], got["cells_correct"], got["share_correct"]), ("retry A", 9, 0.45))
        self.assertEqual(LB.closest_of([s("base", 7), s("retry A", 7)], 10)["search"], "base")
        self.assertEqual(LB.closest_of([s("base", None)], 10), {"found": False, "cells_total": 10})

    def test_r2_one_colour_attempt_falls_back_and_terminates(self):
        for c in (0, 4, 9):
            gr, info = A.random_target("t", 0, g(3, 2, c))
            self.assertEqual(gr[0][0], (c + 1) % 10)
            self.assertEqual([v for r in gr for v in r][1:], [c] * 5)
            self.assertEqual(info, {"random_degenerate": True, "palette_size": 1, "random_draws": 100})
            self.assertTrue(C.grid_ok(gr))

    def test_r2_at_most_100_draws_even_if_every_draw_repeats_attempt_1(self):
        a1 = [[1, 2], [2, 1]]
        calls = []

        class Stub:
            def __init__(self):
                self.cells = [v for r in a1 for v in r]
                self.i = 0

            def choice(self, pal):
                calls.append(1)
                v = self.cells[self.i % 4]
                self.i += 1
                return v
        orig = C.rng_for
        C.rng_for = lambda text: Stub()
        try:
            gr, info = A.random_target("t", 0, a1)
        finally:
            C.rng_for = orig
        self.assertEqual(len(calls), 100 * 4)
        self.assertEqual((gr, info["random_degenerate"], info["palette_size"]), ([[2, 2], [2, 1]], True, 2))

    def test_r3_shuffled_is_same_shape_or_absent_and_fixed_before_any_arm(self):
        w = template()
        asg = C.load_json(os.path.join(w.cfg.run_dir, "ASSIGNMENT.json"))
        core = asg["core"]
        for u in core["primary"]["units"] + core["development"]["units"]:
            sh = u["targets"]["shuffled"]
            if sh is None:
                self.assertFalse(u["cohort"])
                self.assertNotIn(f"{u['unit']}.shuffled", {a["arm"] for a in core["plan"]})
            else:
                self.assertEqual(C.shape(sh), C.shape(u["targets"]["neural"]))
        d = core["primary"]["denominators"]
        self.assertEqual(d["units"], d["matched_rule_1"] + d["matched_rule_2"] + d["unmatched"])
        self.assertEqual((d["units"], d["unmatched"]), (4, 2))
        first = min(os.path.getmtime(os.path.join(w.cfg.run_dir, "arms", n))
                    for n in os.listdir(os.path.join(w.cfg.run_dir, "arms")) if n.endswith(".started.json"))
        self.assertLessEqual(os.path.getmtime(os.path.join(w.cfg.run_dir, "ASSIGNMENT.json")), first)
        sha = C.sha_file(os.path.join(w.cfg.run_dir, "ASSIGNMENT.json"))
        self.assertTrue(all(r["binding"]["assignment_sha256"] == sha for r in records(w).values() if r))

    def test_r5_score_gate_claim_before_answers_once_and_fail_closed(self):
        w = copy_of(template())
        review = os.path.join(w.root, "OUTPUT_CHAIN_REVIEW.md")
        os.rename(os.path.join(w.cfg.runs, "GO_SCORE"), os.path.join(w.root, "GO_SCORE.held"))
        log = os.path.join(w.root, "log0.json")
        r = scorer(w, review, log)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(w.cfg.runs, "SCORE_CLAIM.json")))
        self.assertEqual([o for o in C.load_json(log)["opens"] if o["path"] == w.answers], [])
        with open(os.path.join(w.root, "GO_SCORE.held")) as f:
            good = f.read()
        with open(os.path.join(w.cfg.runs, "GO_SCORE"), "w") as f:
            f.write(good.replace("\n", "\r\n"))
        self.assertNotEqual(scorer(w, review, log).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(w.cfg.runs, "SCORE_CLAIM.json")))
        with open(os.path.join(w.cfg.runs, "GO_SCORE"), "w") as f:
            f.write(good)
        log1 = os.path.join(w.root, "log1.json")
        r = scorer(w, review, log1)
        self.assertEqual(r.returncode, 0, r.stderr)
        lg = C.load_json(log1)
        opens = [o for o in lg["opens"] if o["path"] == w.answers]
        self.assertEqual(len(opens), 1)
        self.assertTrue(opens[0]["claim_existed"])
        self.assertEqual(lg["training_answers"], "refused")
        self.assertTrue(os.path.exists(os.path.join(w.cfg.runs, "score", "SCORE.json")))
        log2 = os.path.join(w.root, "log2.json")
        r = scorer(w, review, log2)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SCORE_CLAIM", r.stderr)
        self.assertEqual([o for o in C.load_json(log2)["opens"] if o["path"] == w.answers], [])

    def test_r5_tampered_answers_after_release_fail_closed_and_stay_claimed(self):
        w = make(basic_tasks(), correct=["fit00002:0"])
        W.release(w)
        self.assertEqual(driver(w, "run").returncode, 0)
        review = W.release_score(w)
        with open(w.answers, "a") as f:
            f.write(" ")
        log = os.path.join(w.root, "log.json")
        r = scorer(w, review, log)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not match its pinned sha256", r.stderr)
        self.assertTrue(os.path.exists(os.path.join(w.cfg.runs, "SCORE_CLAIM.json")))
        self.assertFalse(os.path.exists(os.path.join(w.cfg.runs, "score", "SCORE.json")))
        r2 = scorer(w, review, log)
        self.assertIn("SCORE_CLAIM", r2.stderr)

    def test_r6_task_correct_only_when_every_output_is(self):
        row = lambda vn, an, vs=None: {"v_neural": vn, "v_shuffled": vs, "v_random": False, "v_no_target": False,
                                       "a_neural": an, "a_cora": False}
        ind = SC.task_indicators({"two_one_wrong": [row(True, True), row(True, False)],
                                  "two_right": [row(True, True), row(True, True)],
                                  "one_unverified": [row(True, True), row(False, False)],
                                  "cohort_mixed": [row(True, False, True), row(False, False, None)],
                                  "no_cohort": [row(True, False)]})
        self.assertEqual(ind["two_one_wrong"]["A_neural"], False)
        self.assertEqual(ind["two_one_wrong"]["V_neural"], True)
        self.assertEqual(ind["two_right"]["A_neural"], True)
        self.assertEqual(ind["one_unverified"]["V_neural"], False)
        self.assertEqual((ind["cohort_mixed"]["V_neural_cohort"], ind["cohort_mixed"]["V_shuffled_cohort"]),
                         (True, True))
        self.assertEqual(ind["cohort_mixed"]["V_neural"], False)
        self.assertIsNone(ind["no_cohort"]["V_neural_cohort"])
        c1, c2, c3 = SC.contrasts(ind)
        self.assertEqual(c1["tasks"], 1)
        self.assertEqual(c2["tasks"], 5)

    def test_r6_exact_mcnemar_holm_underpowered_and_decision(self):
        self.assertAlmostEqual(SC.mcnemar_exact(6, 0), 2 / 64)
        self.assertAlmostEqual(SC.mcnemar_exact(5, 1), 2 * 7 / 64)
        self.assertEqual(SC.mcnemar_exact(0, 0), 1.0)
        self.assertEqual(SC.mcnemar_exact(3, 3), 1.0)
        self.assertEqual(SC.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
        mk = lambda b, c: dict(SC.contrast("C", {**{f"b{i}": (True, False) for i in range(b)},
                                                 **{f"c{i}": (False, True) for i in range(c)}}))
        c1, c2, c3 = mk(9, 0), mk(8, 0), mk(0, 0)
        for c, p in zip((c1, c2, c3), SC.holm([c1["p"], c2["p"], c3["p"]])):
            c["p_holm"], c["significant"] = p, p <= SC.ALPHA
        self.assertEqual(SC.decision("COMPLETE", c1, c2, c3)["primary"],
                         "neural guesses become verified programs more often than control targets")
        self.assertEqual(SC.decision("INCOMPLETE", c1, c2, c3)["primary"], "not shown")
        self.assertEqual(SC.decision("COMPLETE", c1, c2, c3)["C3"], "no difference shown")
        self.assertTrue(mk(3, 2)["underpowered"])
        self.assertFalse(mk(4, 2)["underpowered"])
        rev = mk(0, 9)
        rev["p_holm"], rev["significant"] = rev["p"], True
        self.assertEqual(SC.decision("COMPLETE", rev, c2, c3)["primary"], "not shown")

    def test_r6_scored_synthetic_run_follows_arc_task_scoring(self):
        w = copy_of(template())
        r = scorer(w, os.path.join(w.root, "OUTPUT_CHAIN_REVIEW.md"), os.path.join(w.root, "log.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        s = C.load_json(os.path.join(w.cfg.runs, "score", "SCORE.json"))
        p = s["primary"]
        self.assertEqual(p["outputs"]["verified_neural_correct"], 2)
        self.assertEqual(p["tasks"]["A_neural"], 1)
        self.assertEqual(p["tasks"]["V_neural"], 2)
        self.assertAlmostEqual(p["precision"]["precision_with_verification"], 2 / 3)
        self.assertAlmostEqual(p["precision"]["precision_guesses_alone"], 3 / 4)
        self.assertEqual(p["contrasts"][2]["neural_only"], 1)
        self.assertEqual(s["subgroup"]["assigned_tasks"], 2)
        self.assertEqual(s["pool_stage"]["units"], 1)
        self.assertNotIn("accuracy", json.dumps(s["development"]).replace("no accuracy", ""))


# ============================================================ answer blindness

class AnswerBlindness(unittest.TestCase):
    def test_a_guard_refuses_every_route_to_an_answer_file(self):
        d = tmp()
        blocked = os.path.join(d, "eval_answers_pinned.json")
        for name in ("eval_answers_pinned.json", "other_solutions.json", "normal.json"):
            with open(os.path.join(d, name), "w") as f:
                f.write("{}")
        os.symlink(blocked, os.path.join(d, "link.json"))
        os.link(blocked, os.path.join(d, "hard.json"))
        code = r"""
import json, os, pathlib, subprocess, sys
sys.path.insert(0, sys.argv[1])
from testb import common as C
blocked, d = sys.argv[2], sys.argv[3]
C.install_answer_guard([blocked])
res = {}
def t(name, f):
    try:
        f(); res[name] = "allowed"
    except PermissionError:
        res[name] = "refused"
t("open", lambda: open(blocked, "rb").close())
t("os_open", lambda: os.close(os.open(blocked, os.O_RDONLY)))
t("symlink", lambda: open(os.path.join(d, "link.json"), "rb").close())
t("hard_link", lambda: open(os.path.join(d, "hard.json"), "rb").close())
t("named", lambda: open(os.path.join(d, "other_solutions.json"), "rb").close())
t("write_named", lambda: open(os.path.join(d, "new_solutions.json"), "w").close())
t("pathlib", lambda: pathlib.Path(blocked).read_bytes())
t("subprocess", lambda: subprocess.run(["cat", blocked], capture_output=True))
t("shell", lambda: os.system("cat " + os.path.join(d, "other_solutions.json")))
t("normal", lambda: open(os.path.join(d, "normal.json"), "rb").close())
print(json.dumps(res))
"""
        r = subprocess.run([PY, "-I", "-c", code, EXP, blocked, d], capture_output=True, text=True)
        res = json.loads(r.stdout)
        self.assertEqual(res.pop("normal"), "allowed")
        self.assertEqual(set(res.values()), {"refused"}, res)

    def test_a_worker_and_guard_install_the_guard_on_import(self):
        d = tmp()
        blocked = os.path.join(d, "pinned.json")
        with open(blocked, "w") as f:
            f.write("{}")
        for mod in ("arm_worker", "arm_guard"):
            code = (f"import sys;sys.path.insert(0,sys.argv[1]);import testb.{mod}\n"
                    "try:\n open(sys.argv[2]).close();print('allowed')\nexcept PermissionError:\n print('refused')")
            env = {"PATH": "/usr/bin:/bin", "TESTB_BLOCKED": blocked}
            r = subprocess.run([PY, "-I", "-c", code, EXP, blocked], capture_output=True, text=True, env=env)
            self.assertEqual(r.stdout.strip(), "refused", (mod, r.stderr))

    def test_a_workers_in_a_run_cannot_read_answers(self):
        tasks = {"ans00001": {"train": [(g(1, 1, 1), g(1, 1, 2))], "x": [g(1, 1, 3)], "a1": [g(1, 1, 4)],
                              "truth": [g(1, 1, 4)]}}
        w = make(tasks)
        W.release(w)
        self.assertEqual(driver(w, "run").returncode, 0)
        for k, r in records(w).items():
            if r and ".ans00001." in k:
                res = C.load_json(DR.arm_paths(w.cfg.run_dir, k)["result"])
                self.assertTrue(res["answer_attempts"])
                self.assertTrue(all(a["refused"] for a in res["answer_attempts"]), res["answer_attempts"])

    def test_a_driver_never_opens_answers_even_when_they_are_unreadable(self):
        w = make(basic_tasks(), correct=["fit00002:0"])
        W.release(w)
        os.chmod(w.answers, 0)
        try:
            log = os.path.join(w.root, "open_log.json")
            r = driver(w, "run", log)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(C.load_json(log)["answer_open_attempts"], [])
            log2 = os.path.join(w.root, "open_log2.json")
            self.assertEqual(driver(w, "check-inputs", log2).returncode, 0)
            self.assertEqual(C.load_json(log2)["answer_open_attempts"], [])
        finally:
            os.chmod(w.answers, 0o644)

    def test_a_inference_sources_name_no_answer_file_and_never_import_the_scorer(self):
        import re
        pat = re.compile(r"[\w./-]*solutions[\w.-]*\.json", re.I)
        for src in ("common.py", "assign.py", "labels.py", "arm_worker.py", "arm_guard.py", "driver.py"):
            with open(os.path.join(EXP, "testb", src)) as f:
                text = f.read()
            self.assertEqual(pat.findall(text), [], src)
            self.assertNotRegex(text, r"import\s+[\w, ]*\b(scorer|release_check)\b|from testb import (scorer|"
                                      r"release_check)")

    def test_a_production_configuration_is_fixed(self):
        cfg = DR.Config()
        self.assertEqual((cfg.arm_cpu_s, cfg.arm_wall_s, cfg.run_cpu_s), (100, 400.0, 36000.0))
        self.assertEqual(cfg.worker, os.path.join(EXP, "testb", "arm_worker.py"))
        fr = C.load_json(cfg.protocol_freeze)
        pinned = {**fr["inputs_sha256"], **fr["development_inputs_sha256"]}
        self.assertTrue(all(p in pinned for p in cfg.roles.values()))
        self.assertEqual(DR.blocked_paths(cfg), ["<ARC data folder>/arc-agi_evaluation_solutions.json"])
        self.assertTrue(all(C.ANSWER_NAME.search(os.path.basename(p)) is None for p in cfg.roles.values()))


# ============================================================ the frozen construction code on synthetic tasks

class RealWorker(unittest.TestCase):
    def test_real_worker_runs_the_frozen_construction_code(self):
        demos = [(a, flip(a)) for a in ([[1, 2, 3], [4, 5, 6]], [[7, 8], [9, 1], [2, 3]], [[5, 0, 0, 1]])]
        x1, x2 = [[3, 1, 4], [1, 5, 9]], [[2, 2, 3], [4, 4, 5]]
        tasks = {"rw000001": {"train": demos, "x": [x1], "a1": [flip(x1)], "truth": [flip(x1)]},
                 "rw000002": {"train": demos, "x": [x2], "a1": [[[7, 7, 2], [0, 0, 0]]], "truth": [flip(x2)]}}
        w = make(tasks, worker="real", arm_cpu_s=100, arm_wall_s=400.0)
        W.release(w)
        r = driver(w, "run")
        self.assertEqual(r.returncode, 0, r.stderr)
        recs = records(w)
        self.assertEqual(comp(w)["status"], "COMPLETE")
        res = {k: C.load_json(DR.arm_paths(w.cfg.run_dir, k)["result"]) for k, v in recs.items() if v}
        n = res["eval.rw000001.0.neural"]
        self.assertEqual((n["outcome"], n["level"], n["prediction"]), ("VERIFIED", "base grammar", flip(x1)))
        self.assertTrue(n["prediction_equals_target"])
        self.assertEqual(res["eval.rw000001.0.no_target"]["outcome"], "REACHABLE")
        nofit = [v for v in res.values() if v["outcome"] == LB.NO_FIT]
        self.assertTrue(nofit)
        for v in nofit:
            self.assertEqual(set(v["no_fit_flags"]), {"complete_search", "execution_budget_stop", "cpu_limit_stop",
                                                      "enumeration_capped"})
            self.assertIsNotNone(v["holes"])
            self.assertIsInstance(v["n_hole_matching_operations"], int)
            self.assertLessEqual(len(v["tried_operations"]), 3)
            self.assertTrue(all(s["stop"] in LB.STOP_REASON for s in v["searches"]))
            self.assertIn("cells_total", v["closest"])
        for v in res.values():
            self.assertIsInstance(v["shape_relation"], str)
        self.assertTrue(all(v["receipt"]["cpu_s"] < 100 for v in recs.values() if v))
        self.assertEqual(RC.check_chain(w.cfg), [])


RETRY_TASK = {"demos": [[[[0, 2, 3, 3, 0], [0, 0, 1, 0, 0], [0, 1, 2, 0, 2], [2, 0, 0, 0, 0]],
                         [[0, 0, 0, 0, 0, 0, 2, 2], [2, 2, 0, 0, 1, 1, 0, 0], [3, 3, 1, 1, 2, 2, 0, 0],
                          [3, 3, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 2, 2, 0, 0]]],
                        [[[0, 0, 1, 2, 0], [0, 3, 0, 2, 0], [0, 3, 0, 0, 3], [0, 2, 0, 1, 0], [3, 3, 0, 2, 3]],
                         [[0, 0, 0, 0, 0, 0, 0, 0, 3, 3], [0, 0, 3, 3, 3, 3, 2, 2, 3, 3], [1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
                          [2, 2, 2, 2, 0, 0, 1, 1, 2, 2], [0, 0, 0, 0, 3, 3, 0, 0, 3, 3]]],
                        [[[2, 0, 1], [3, 2, 2], [1, 1, 0]], [[2, 2, 3, 3, 1, 1], [0, 0, 2, 2, 1, 1], [1, 1, 2, 2, 0, 0]]]],
              "x": [[1, 0, 3, 3, 1], [3, 3, 3, 0, 1], [0, 3, 0, 1, 1]],
              "target": [[1, 1, 3, 3, 0, 0], [0, 0, 3, 3, 3, 3], [3, 3, 3, 3, 0, 0], [3, 3, 0, 0, 1, 1],
                         [1, 1, 1, 1, 1, 1]]}


class RealWorkerRetry(unittest.TestCase):
    def test_real_worker_retry_path_adds_a_menu_operation(self):
        """A synthetic task made from one menu operation: the base search finds no fit, the typed holes match menu
        operations, and the third retry (the s1.M_RETRIES bound) fits with that operation added."""
        r, res, files = real_worker(RETRY_TASK, tmp())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((res["outcome"], res["level"]), ("VERIFIED", "base grammar + f:sig_MAP_same_spread_1"))
        self.assertEqual([t["sid"] for t in res["tried_operations"]],
                         ["MAP:same:spread:0", "MAP:spread:same:0", "MAP:same:spread:1"])
        self.assertEqual([s["fit"] for s in res["searches"]], [False, False, False, True])
        self.assertEqual(res["n_hole_matching_operations"], 3)
        self.assertEqual(res["prediction"], RETRY_TASK["target"])
        self.assertEqual(C.load_json(files[2])["searches"], res["searches"])


WITNESS_TASK = {"demos": [[[[3, 2, 2], [0, 0, 0], [1, 3, 0]], [[0, 0, 0]]],
                          [[[2, 0, 5, 2, 2], [3, 1, 5, 3, 5], [2, 1, 5, 3, 0]], [[3, 1, 3, 5]]],
                          [[[0, 2, 0, 3], [1, 3, 3, 1], [1, 1, 3, 5], [5, 3, 5, 3], [0, 5, 1, 0]],
                           [[1, 3, 3, 1], [1, 1, 3, 5], [5, 3, 5, 3]]]],
                "x": [[3, 5, 0, 5], [0, 5, 0, 0], [1, 1, 2, 0], [3, 0, 0, 0]],
                "target": [[0, 5, 0, 0], [1, 1, 2, 0]]}


def real_worker(task, d):
    spec = dict(task, arm="synthetic.neural", stage="primary", name="neural", unit="synthetic", task="synthetic",
                output=0)
    files = [os.path.join(d, n) for n in ("in.json", "out.json", "progress.json")]
    C.write_json_atomic(files[0], spec)
    r = subprocess.run([PY, "-I", os.path.join(EXP, "testb", "arm_worker.py")] + files, env=DR.child_env(DR.Config()),
                       capture_output=True, text=True, timeout=600)
    return r, (C.load_json(files[1]) if os.path.exists(files[1]) else None), files


class RealWorkerClosest(unittest.TestCase):
    def test_real_worker_closest_program_improved_by_a_retry(self):
        """Witness on the frozen construction code: the base search finds no right-shaped program, the retry with the
        hole-matching operation finds one with 26 correct cells (then a fit), and the record reports the retry's."""
        r, res, files = real_worker(WITNESS_TASK, tmp())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(res["searches"][0]["closest"])
        best = max(s["closest"]["cells_correct"] for s in res["searches"][1:] if s["closest"])
        self.assertEqual(best, 26)
        self.assertTrue(res["closest"]["found"])
        self.assertTrue(res["closest"]["search"].startswith("retry "))
        self.assertEqual(res["closest"]["cells_correct"], 26)
        self.assertEqual(res["closest"]["cells_total"], res["cells_total"])
        self.assertEqual(res["process_creation"]["rlimit_nproc"], [0, 0])


def tearDownModule():
    for d in SCRATCH:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
