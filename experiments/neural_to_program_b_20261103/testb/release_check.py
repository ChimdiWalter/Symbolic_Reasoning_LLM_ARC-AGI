"""Score-release check (PROTOCOL.md section 6): the transitive output chain, verified before any answer is read.
Standard library only; it never opens an answer file.

    python -I release_check.py                         chain from the outputs to GO_B, the full code and the
                                                       assignment (what the output-chain reviewer runs)
    python -I release_check.py --go-score REVIEW_PATH  also runs/GO_SCORE (exact lines) and the review it binds

Links checked (each one fails the release on its own):
  GO_SCORE -> OUTPUTS_FREEZE.json (sha256), the scorer file (sha256, equal to its CODE_FREEZE entry), the review
    (sha256; it must contain the line 'TEST_B_OUTPUT_CHAIN_REVIEW: PASS' and the outputs-freeze sha256);
  OUTPUTS_FREEZE -> runs/GO_B (sha256 and its three lines) -> PROTOCOL.md, PROTOCOL_FREEZE.json, CODE_FREEZE.json
    as they are now -> every frozen code file, the construction data and the 38 construction-code files;
  OUTPUTS_FREEZE -> RUN_CLAIM.json -> the same GO_B;
  OUTPUTS_FREEZE -> every file of the run folder, exactly that set, each sha256;
  ASSIGNMENT.json -> bound to GO_B, the code freeze and the run claim; rebuilt from the pinned inputs, it must be
    identical;
  every planned arm -> its record, bound to GO_B, the code freeze, the run claim and the assignment; its input
    rebuilt from the pinned tasks and the assignment; its target digest; its result, receipt and progress files;
    its start marker naming this interpreter, worker, guard and limits; its outcome re-derived from the receipt
    and result; or, without a record, listed unfinished;
  no record outside the plan;
  COMPLETENESS.json -> re-derived from the records and the assignment, with this configuration's limits.
"""
import json
import os
import sys

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import assign as A              # noqa: E402
from testb import common as C              # noqa: E402
from testb import driver as DR             # noqa: E402

GO_SCORE_KEYS = ("outputs_freeze_sha256", "scorer_sha256", "output_chain_review_sha256")
SCORER_REL = "experiments/neural_to_program_b_20261103/testb/scorer.py"
REVIEW_PASS = "TEST_B_OUTPUT_CHAIN_REVIEW: PASS"


ARM_SUFFIXES = (".input.json", ".started.json", ".result.json", ".receipt.json", ".progress.json", ".json", ".log",
                ".lock")


def arm_key_of(name):
    name = name[:-4] if name.endswith(".tmp") else name
    for suffix in ARM_SUFFIXES:
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return None


def _sha(p):
    return C.sha_file(p) if os.path.exists(p) else None


def check_chain(cfg, review=None, go_score=False, rebuild=True):
    """A list of failures; empty means every link verifies."""
    bad = []
    rd = cfg.run_dir
    of_path = os.path.join(rd, "OUTPUTS_FREEZE.json")
    if not os.path.exists(of_path):
        return ["no OUTPUTS_FREEZE.json"]
    of = C.load_json(of_path)
    of_sha = C.sha_file(of_path)
    cf = C.load_json(cfg.code_freeze)

    if go_score:
        try:
            gs = C.read_go(os.path.join(cfg.runs, "GO_SCORE"), GO_SCORE_KEYS)
        except (SystemExit, OSError) as e:
            return [f"GO_SCORE: {e}"]
        if gs["outputs_freeze_sha256"] != of_sha:
            bad.append("GO_SCORE names a different OUTPUTS_FREEZE.json")
        scorer = C.absp(SCORER_REL, cfg.repo)
        if not (gs["scorer_sha256"] == _sha(scorer) == cf["files"].get(SCORER_REL)):
            bad.append("GO_SCORE scorer digest, the scorer file and its CODE_FREEZE entry differ")
        if review is None or _sha(review) != gs["output_chain_review_sha256"]:
            bad.append("the output-chain review file does not match GO_SCORE")
        else:
            with open(review, encoding="utf-8") as f:
                text = f.read()
            if REVIEW_PASS not in text.splitlines() or of_sha not in text:
                bad.append("the review lacks its PASS line or the outputs-freeze sha256")

    go_path = os.path.join(cfg.runs, "GO_B")
    try:
        go = C.read_go(go_path, DR.GO_B_KEYS)
    except (SystemExit, OSError) as e:
        return bad + [f"GO_B: {e}"]
    if _sha(go_path) != of["go_b_sha256"]:
        bad.append("OUTPUTS_FREEZE names a different GO_B")
    if {k: go[k] for k in DR.GO_B_KEYS} != of["go_b"]:
        bad.append("GO_B lines differ from those in OUTPUTS_FREEZE")
    now = {"protocol_sha256": _sha(cfg.protocol), "protocol_freeze_sha256": _sha(cfg.protocol_freeze),
           "code_freeze_sha256": _sha(cfg.code_freeze)}
    for k in DR.GO_B_KEYS:
        if go[k] != now[k]:
            bad.append(f"GO_B {k} differs from the current file")
    if of["code_freeze_sha256"] != now["code_freeze_sha256"]:
        bad.append("OUTPUTS_FREEZE names a different CODE_FREEZE")
    for p, want in {**cf["files"], **cf["construction_data"]}.items():
        if _sha(C.absp(p, cfg.repo)) != want:
            bad.append(f"frozen file changed: {p}")
    if cf["protocol_sha256"] != now["protocol_sha256"] or cf["protocol_freeze_sha256"] != now["protocol_freeze_sha256"]:
        bad.append("CODE_FREEZE names a different protocol or protocol freeze")
    for p, want in C.load_json(cfg.protocol_freeze)["construction_code_sha256"].items():
        if _sha(C.absp(p, cfg.repo)) != want:
            bad.append(f"construction code changed: {p}")

    claim_path = os.path.join(cfg.runs, "RUN_CLAIM.json")
    claim = C.load_json(claim_path) if os.path.exists(claim_path) else {}
    if _sha(claim_path) != of["run_claim_sha256"] or claim.get("go_b_sha256") != of["go_b_sha256"] or \
            any(claim.get(k) != go[k] for k in DR.GO_B_KEYS):
        bad.append("RUN_CLAIM does not bind this GO_B and outputs freeze")

    present = {}
    for root, _d, names in os.walk(rd):
        for n in names:
            r = os.path.relpath(os.path.join(root, n), rd)
            if r != "OUTPUTS_FREEZE.json" and not n.endswith((".lock", ".tmp")):
                present[r] = C.sha_file(os.path.join(root, n))
    if set(present) != set(of["files_sha256"]):
        extra, missing = sorted(set(present) - set(of["files_sha256"])), sorted(set(of["files_sha256"]) - set(present))
        bad.append(f"run folder file set differs from OUTPUTS_FREEZE (extra {extra[:5]}, missing {missing[:5]})")
    for r, want in of["files_sha256"].items():
        if present.get(r) not in (None, want):
            bad.append(f"run file changed: {r}")

    asg_path = os.path.join(rd, "ASSIGNMENT.json")
    if not os.path.exists(asg_path):
        return bad + ["no ASSIGNMENT.json"]
    asg = C.load_json(asg_path)
    asg_sha = C.sha_file(asg_path)
    if asg_sha != of["assignment_sha256"]:
        bad.append("OUTPUTS_FREEZE names a different ASSIGNMENT")
    ctx = {"go_b_sha256": of["go_b_sha256"], "code_freeze_sha256": of["code_freeze_sha256"],
           "run_claim_sha256": of["run_claim_sha256"]}
    if any(asg.get(k) != v for k, v in ctx.items()):
        bad.append("ASSIGNMENT is not bound to this GO_B, code freeze and run claim")
    ctx["assignment_sha256"] = asg_sha
    core = asg["core"]
    challenges = None
    if rebuild:
        try:
            paths = DR.verify_pins(cfg)
        except SystemExit as e:
            return bad + [f"pins: {e}"]
        if C.canon(A.build(paths)) != C.canon(core):
            bad.append("ASSIGNMENT differs from the assignment rebuilt from the pinned inputs")
        challenges = {"eval": C.load_json(paths["eval_challenges"]), "dev": C.load_json(paths["dev_challenges"])}

    planned = {a["arm"] for a in core["plan"]}
    for n in sorted(os.listdir(os.path.join(rd, "arms"))):
        if arm_key_of(n) not in planned:
            bad.append(f"arm file outside the plan: {n}")
    units = A.unit_index(core)
    for arm in core["plan"]:
        p = DR.arm_paths(rd, arm["arm"])
        st, rec = DR.arm_status(rd, arm)
        if rec is None:
            continue
        if rec.get("binding") != ctx:
            bad.append(f"{arm['arm']}: record not bound to this GO_B, code freeze, claim and assignment")
        u = units[arm["unit"]]
        target = None if arm["name"] == "no_target" else u["targets"][arm["name"]]
        if rec.get("target_sha256") != C.sha_text(C.canon(target)):
            bad.append(f"{arm['arm']}: target digest differs from the assignment")
        for k in ("input", "result", "receipt", "progress"):
            if rec["files_sha256"].get(k) != _sha(p[k]):
                bad.append(f"{arm['arm']}: {k} file differs from its record")
        spec = C.load_json(p["input"]) if os.path.exists(p["input"]) else None
        if challenges is not None and spec != A.arm_spec(core, challenges, arm):
            bad.append(f"{arm['arm']}: worker input differs from the one rebuilt from the pinned tasks")
        started = C.load_json(p["started"]) if os.path.exists(p["started"]) else {}
        if (started.get("python"), started.get("worker"), started.get("guard"), started.get("cpu_limit_s"),
                started.get("wall_limit_s")) != (cfg.python, cfg.worker, DR.GUARD, cfg.arm_cpu_s, cfg.arm_wall_s):
            bad.append(f"{arm['arm']}: started with another worker, guard or limits")
        receipt = C.load_json(p["receipt"]) if os.path.exists(p["receipt"]) else None
        if receipt is not None and (receipt.get("cpu_limit_s"), receipt.get("wall_limit_s")) != (cfg.arm_cpu_s,
                                                                                                 cfg.arm_wall_s):
            bad.append(f"{arm['arm']}: guard receipt shows other limits")
        result = C.load_json(p["result"]) if os.path.exists(p["result"]) else None
        if result is not None and result.get("input_sha256") != _sha(p["input"]):
            bad.append(f"{arm['arm']}: result names a different input")
        if DR.classify(cfg, receipt, result, arm["arm"])[0] != rec["outcome"]:
            bad.append(f"{arm['arm']}: outcome does not follow from its receipt and result")

    comp_path = os.path.join(rd, "COMPLETENESS.json")
    if not os.path.exists(comp_path) or C.sha_file(comp_path) != of["completeness_sha256"]:
        return bad + ["COMPLETENESS.json missing or not the one in OUTPUTS_FREEZE"]
    comp = C.load_json(comp_path)
    re_ = DR.completeness(cfg, rd, core, comp["stop_reason"], comp["interrupted"], comp["cpu"]["driver_cpu_s"])
    for k in ("status", "stages", "guard_stops", "denominators"):
        if re_[k] != comp[k]:
            bad.append(f"COMPLETENESS {k} does not follow from the arm records")
    for k in ("arm_cpu_limit_s", "arm_wall_limit_s", "run_cpu_limit_s"):
        if re_["cpu"][k] != comp["cpu"][k]:
            bad.append(f"COMPLETENESS {k} is not the checked configuration's")
    for k in ("arm_receipts_cpu_s", "unrecovered_upper_bound_cpu_s"):
        if abs(re_["cpu"][k] - comp["cpu"][k]) > 1e-6:
            bad.append(f"COMPLETENESS cpu {k} does not follow from the receipts")
    if of["status"] != comp["status"]:
        bad.append("OUTPUTS_FREEZE status differs from COMPLETENESS")
    return bad


def main(argv):
    cfg = DR.Config()
    C.install_answer_guard(DR.blocked_paths(cfg))
    review = None
    if argv[:1] == ["--go-score"] and len(argv) == 2:
        review = argv[1]
    elif argv:
        raise SystemExit(__doc__)
    bad = check_chain(cfg, review=review, go_score=review is not None)
    print(json.dumps({"verified": not bad, "failures": bad,
                      "outputs_freeze_sha256": _sha(os.path.join(cfg.run_dir, "OUTPUTS_FREEZE.json"))}, indent=1))
    raise SystemExit(0 if not bad else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
