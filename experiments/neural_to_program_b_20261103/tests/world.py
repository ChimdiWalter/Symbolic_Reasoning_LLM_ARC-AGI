"""Synthetic worlds for the Test B adversarial tests: a temporary repository with synthetic tasks, neural attempts and
pools, a CORA-only score record, development tasks, a synthetic answers file, a stand-in construction-code file,
copies of the Test B code, a protocol freeze and a code freeze. No real ARC task, pool or answer is read."""
import dataclasses
import glob
import json
import os
import shutil
import sys
import tempfile

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import common as C              # noqa: E402
from testb import driver as DR             # noqa: E402

REL_EXP = "experiments/neural_to_program_b_20261103"
SYNTH_WORKER = os.path.join(EXP, "tests", "synthetic_worker.py")
REAL_WORKER = os.path.join(EXP, "testb", "arm_worker.py")


def g(h, w, c=0):
    return [[c] * w for _ in range(h)]


def flip(x):
    return [list(reversed(r)) for r in x]


def _w(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


@dataclasses.dataclass
class World:
    root: str
    cfg: DR.Config
    answers: str
    training_answers: str

    def cfg_json(self):
        p = os.path.join(self.root, "config.json")
        _w(p, dataclasses.asdict(self.cfg))
        return p


def make(tasks, dev=None, correct=(), worker="synthetic", arm_cpu_s=2, arm_wall_s=20.0, run_cpu_s=36000.0,
         root=None):
    """tasks: {id: {"train": [(in, out)], "x": [test inputs], "truth": [answers], "a1": [attempt 1],
    "pool": [[extra candidates] per output] (optional)}}; dev: same without truth (no training answer exists)."""
    root = root or tempfile.mkdtemp(prefix="testb_synth_")
    repo, dl = os.path.join(root, "repo"), os.path.join(root, "Downloads")
    exp = os.path.join(repo, REL_EXP)
    os.makedirs(os.path.join(exp, "testb"))
    for f in glob.glob(os.path.join(EXP, "testb", "*.py")):
        shutil.copy2(f, os.path.join(exp, "testb"))
    dev = dev or {"fit0dev1": {"train": [([[1, 2]], [[2, 1]])], "x": [[[3, 4]]], "a1": [[[4, 3]]]}}

    def challenge(t):
        return {"train": [{"input": a, "output": b} for a, b in t["train"]], "test": [{"input": x} for x in t["x"]]}

    _w(os.path.join(repo, "outputs/eval_challenges.json"), {k: challenge(t) for k, t in tasks.items()})
    _w(os.path.join(repo, "outputs/submission_A.json"),
       {k: [{"attempt_1": a, "attempt_2": a} for a in t["a1"]] for k, t in tasks.items()})
    for k, t in tasks.items():
        pool = t.get("pool") or [[] for _ in t["x"]]
        _w(os.path.join(repo, "outputs/pools", f"{k}.json"),
           {"task": k, "outputs": [{"candidates": [{"grid": a, "votes": 9}] + [{"grid": c, "votes": 1} for c in p]}
                                   for a, p in zip(t["a1"], pool)],
            "selected": [{"attempt_1": a, "attempt_2": a} for a in t["a1"]], "error": None})
    _w(os.path.join(repo, "outputs/cora_submission.json"), {k: [] for k in tasks})
    _w(os.path.join(repo, "outputs/check.json"), {"ok": True})
    _w(os.path.join(repo, "outputs/score.json"),
       {"results": {"other": {"file": "outputs/other.json", "correct": []},
                    "cora": {"file": "outputs/cora_submission.json", "correct": sorted(correct)}}})
    _w(os.path.join(repo, "outputs/dev/challenges_used.json"), {k: challenge(t) for k, t in dev.items()})
    for k, t in dev.items():
        _w(os.path.join(repo, "outputs/dev/pools", f"{k}.json"),
           {"task": k, "outputs": [{"candidates": [{"grid": a, "votes": 9}]} for a in t["a1"]],
            "selected": [{"attempt_1": a, "attempt_2": a} for a in t["a1"]], "error": None})
    training = os.path.join(dl, "training_challenges.json")
    _w(training, {**{k: challenge(t) for k, t in dev.items()}, "zzzother": challenge(next(iter(dev.values())))})
    answers = os.path.join(dl, "synthetic_evaluation_solutions.json")
    _w(answers, {k: t["truth"] for k, t in tasks.items()})
    training_answers = os.path.join(dl, "synthetic_training_solutions.json")
    _w(training_answers, {k: [[[0]]] for k in dev})
    with open(os.path.join(repo, "code_stub.py"), "w") as f:
        f.write("# stand-in for one construction-code file\n")
    with open(os.path.join(repo, "corpus_stub.json"), "w") as f:
        f.write("{}\n")
    protocol = os.path.join(exp, "PROTOCOL.md")
    with open(protocol, "w") as f:
        f.write("synthetic protocol for the adversarial tests\n")

    def folder_pin(folder):
        fs = {os.path.basename(p): C.sha_file(p) for p in sorted(glob.glob(os.path.join(repo, folder, "*.json")))}
        return {"folder": folder, "files_sha256": fs, "combined_sha256": C.sha_text(json.dumps(fs, sort_keys=True))}

    ins = ["outputs/eval_challenges.json", "outputs/cora_submission.json", "outputs/score.json", "outputs/check.json",
           "outputs/submission_A.json"]
    n_out = {k: len(t["x"]) for k, t in tasks.items()}
    outs = {f"{k}:{j}" for k, n in n_out.items() for j in range(n)}
    sub = outs - set(correct)
    fr = {"protocol": {f"{REL_EXP}/PROTOCOL.md": C.sha_file(protocol)},
          "inputs_sha256": {p: C.sha_file(os.path.join(repo, p)) for p in ins},
          "answers_scorer_only": {answers: C.sha_file(answers)},
          "neural_pools": folder_pin("outputs/pools"),
          "development_inputs_sha256": {training: C.sha_file(training),
                                        "outputs/dev/challenges_used.json":
                                            C.sha_file(os.path.join(repo, "outputs/dev/challenges_used.json"))},
          "development_pools": folder_pin("outputs/dev/pools"),
          "construction_code_sha256": {"code_stub.py": C.sha_file(os.path.join(repo, "code_stub.py"))},
          "selected": {"primary": {"tasks": len(tasks), "outputs": len(outs)},
                       "development_training": {"tasks": len(dev), "outputs": sum(len(t["x"]) for t in dev.values())},
                       "subgroup_cora_only_fails_or_abstains": {
                           "tasks": len({o.split(":")[0] for o in sub}), "outputs": len(sub),
                           "excluded_correct_outputs": sorted(correct)}}}
    pf = os.path.join(exp, "PROTOCOL_FREEZE.json")
    _w(pf, fr)
    cf = os.path.join(exp, "CODE_FREEZE.json")
    write_code_freeze(repo, cf, protocol, pf)
    cfg = DR.Config(repo=repo, protocol=protocol, protocol_freeze=pf, code_freeze=cf, runs=os.path.join(exp, "runs"),
                    roles={"eval_challenges": "outputs/eval_challenges.json",
                           "cora_only_submission": "outputs/cora_submission.json",
                           "cora_only_score": "outputs/score.json", "eval_attempts": "outputs/submission_A.json",
                           "dev_challenges": "outputs/dev/challenges_used.json", "training_challenges": training},
                    arm_cpu_s=arm_cpu_s, arm_wall_s=arm_wall_s, run_cpu_s=run_cpu_s,
                    worker=SYNTH_WORKER if worker == "synthetic" else REAL_WORKER, poll_s=0.02, recovery_wait_s=15.0)
    return World(root, cfg, answers, training_answers)


def write_code_freeze(repo, cf, protocol, pf):
    files = {os.path.relpath(p, repo): C.sha_file(p) for p in sorted(glob.glob(os.path.join(repo, REL_EXP, "testb",
                                                                                          "*.py")))}
    _w(cf, {"files": files, "construction_data": {"corpus_stub.json": C.sha_file(os.path.join(repo, "corpus_stub.json"))},
            "protocol_sha256": C.sha_file(protocol), "protocol_freeze_sha256": C.sha_file(pf)})


def release(w):
    """Write runs/GO_B for the world, binding its current protocol, protocol freeze and code freeze."""
    os.makedirs(w.cfg.runs, exist_ok=True)
    with open(os.path.join(w.cfg.runs, "GO_B"), "w") as f:
        f.write(f"protocol_sha256 {C.sha_file(w.cfg.protocol)}\nprotocol_freeze_sha256 "
                f"{C.sha_file(w.cfg.protocol_freeze)}\ncode_freeze_sha256 {C.sha_file(w.cfg.code_freeze)}\n")


def release_score(w, review_text=None):
    """Write an output-chain review that passes and names the outputs freeze, and runs/GO_SCORE binding it."""
    of = C.sha_file(os.path.join(w.cfg.run_dir, "OUTPUTS_FREEZE.json"))
    review = os.path.join(w.root, "OUTPUT_CHAIN_REVIEW.md")
    with open(review, "w") as f:
        f.write(review_text if review_text is not None else
                f"Synthetic output-chain review.\nOutputs freeze {of}.\nTEST_B_OUTPUT_CHAIN_REVIEW: PASS\n")
    scorer = os.path.join(w.cfg.repo, REL_EXP, "testb", "scorer.py")
    with open(os.path.join(w.cfg.runs, "GO_SCORE"), "w") as f:
        f.write(f"outputs_freeze_sha256 {of}\nscorer_sha256 {C.sha_file(scorer)}\n"
                f"output_chain_review_sha256 {C.sha_file(review)}\n")
    return review


def rebase(w, new_root):
    """A copy of a world at new_root (paths inside the world's repository rewritten; Downloads stays shared)."""
    shutil.copytree(os.path.join(w.root, "repo"), os.path.join(new_root, "repo"), symlinks=True)
    d = dataclasses.asdict(w.cfg)
    for k, v in d.items():
        if isinstance(v, str) and v.startswith(os.path.join(w.root, "repo")):
            d[k] = v.replace(w.root, new_root, 1)
    rv = os.path.join(w.root, "OUTPUT_CHAIN_REVIEW.md")
    if os.path.exists(rv):
        shutil.copy2(rv, os.path.join(new_root, "OUTPUT_CHAIN_REVIEW.md"))
    return World(new_root, DR.Config(**d), w.answers, w.training_answers)
