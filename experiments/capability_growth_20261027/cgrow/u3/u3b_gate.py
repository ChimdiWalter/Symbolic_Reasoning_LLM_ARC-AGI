"""Test U3b provenance gate (stdlib only; fails closed).

    python3 -I cgrow/u3/u3b_gate.py STAGE          STAGE: start | build | arms | eval | save

Checked before every stage, from the live files:
1. runs/GO_U3B, written by the coordinator, whose first two lines are exactly
       protocol_sha256 <sha256 of u3b_list_functions/PROTOCOL.md>
       freeze_sha256 <sha256 of u3b_list_functions/PROTOCOL_FREEZE.json>
2. every file listed in PROTOCOL_FREEZE.json has its recorded sha256.
Then, by stage:
- build: no build manifest and no arms outputs yet (a finished construction is verified, never redone);
- arms: build/BUILD_MANIFEST.json lists exactly BUILD_OUTPUTS (no missing or extra entry, never itself), each with
  its live sha256; no arms freeze and no evaluation outputs yet;
- eval: as for arms, and arms/ARMS_FREEZE.json matches units.json and c7m.json and names the verified build
  manifest; no evaluation freeze yet;
- save: as for eval, and eval/EVAL_FREEZE.json matches results.json and names the verified arms freeze and build
  manifest.
Prints one line, "ok STAGE: <verified digests>" or "FAIL STAGE: <problems>"; exit status 0 only if every check passes.
run_u3b.py imports this module: its entry points run the same check first, and its stages read build and arms
outputs only through read_verified.
"""
import hashlib
import json
import os
import sys

EXP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))    # the experiment folder
ROOT = "u3b_list_functions"
PROTOCOL = ROOT + "/PROTOCOL.md"
FREEZE = ROOT + "/PROTOCOL_FREEZE.json"
GO = "runs/GO_U3B"
BUILD_OUTPUTS = ("concept_flow.json", "full_dsl_search.json", "g0_search.json", "plan.json", "records.pkl",
                 "tasks_eval.json", "tasks_system.json")
MUST_FREEZE = (PROTOCOL, "chain_u3b.sh", "resume_u3b.sh", "cgrow/u3/u3b_gate.py", "cgrow/u3/run_u3b.py")
STAGES = ("start", "build", "arms", "eval", "save")


def _bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def _digest(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def sha(path):
    return _digest(_bytes(path))


def _json(data):
    try:
        return json.loads(data)
    except (TypeError, ValueError):
        return None


def read_verified(path, want):
    """The bytes of path, read once, only if their sha256 equals want (the verified bytes are the bytes used)."""
    data = _bytes(path)
    if not want or _digest(data) != want:
        raise SystemExit(f"provenance gate: {path} is missing or differs from its recorded sha256")
    return data


def go_problems(exp):
    raw = _bytes(os.path.join(exp, GO))
    if raw is None:
        return ["HELD: runs/GO_U3B absent"], {}
    ph, fh = sha(os.path.join(exp, PROTOCOL)), sha(os.path.join(exp, FREEZE))
    if ph is None or fh is None:
        return ["the protocol or its freeze manifest is missing"], {}
    want = [f"protocol_sha256 {ph}", f"freeze_sha256 {fh}"]
    if raw.decode("utf-8", "replace").split("\n")[:2] != want:
        return [f"HELD: the first two lines of runs/GO_U3B are not exactly '{want[0]}' and '{want[1]}'"], {}
    return [], {"protocol": ph, "freeze": fh}


def freeze_problems(exp):
    fz = _json(_bytes(os.path.join(exp, FREEZE)))
    files = fz.get("files_sha256") if isinstance(fz, dict) else None
    if not isinstance(files, dict) or not files:
        return ["PROTOCOL_FREEZE.json is unreadable or lists no files"]
    probs = [f"PROTOCOL_FREEZE.json does not list {m}" for m in MUST_FREEZE if m not in files]
    return probs + [f"frozen file changed or missing: {rel}" for rel, want in sorted(files.items())
                    if sha(os.path.join(exp, rel)) != want]


def build_check(root):
    """(problems, sha256 of the manifest bytes, listed digests) for root/build/BUILD_MANIFEST.json."""
    b = os.path.join(root, "build")
    raw = _bytes(os.path.join(b, "BUILD_MANIFEST.json"))
    man = _json(raw)
    files = man.get("files_sha256") if isinstance(man, dict) else None
    if not isinstance(files, dict):
        return ["build/BUILD_MANIFEST.json is missing or unreadable"], None, {}
    probs = ["the build manifest lists its own digest"] if "BUILD_MANIFEST.json" in files else []
    missing = [f for f in BUILD_OUTPUTS if f not in files]
    extra = sorted(f for f in files if f not in BUILD_OUTPUTS and f != "BUILD_MANIFEST.json")
    if missing:
        probs.append(f"the build manifest lacks required outputs {missing}")
    if extra:
        probs.append(f"the build manifest lists unexpected entries {extra}")
    probs += [f"build output changed or missing: build/{f}" for f in BUILD_OUTPUTS
              if f in files and sha(os.path.join(b, f)) != files[f]]
    return probs, _digest(raw), files


def arms_check(root, build_sha):
    """(problems, sha256 of the freeze bytes, freeze record) for root/arms/ARMS_FREEZE.json."""
    a = os.path.join(root, "arms")
    raw = _bytes(os.path.join(a, "ARMS_FREEZE.json"))
    af = _json(raw)
    if not isinstance(af, dict):
        return ["arms/ARMS_FREEZE.json is missing or unreadable"], None, {}
    probs = [f"arms output changed after its freeze or missing: arms/{f}"
             for key, f in (("units_json_sha256", "units.json"), ("c7m_json_sha256", "c7m.json"))
             if not af.get(key) or sha(os.path.join(a, f)) != af[key]]
    if not build_sha or af.get("build_manifest_sha256") != build_sha:
        probs.append("the arms freeze does not name the verified build manifest")
    return probs, _digest(raw), af


def eval_check(root, build_sha, arms_sha):
    """(problems, sha256 of the freeze bytes) for root/eval/EVAL_FREEZE.json."""
    e = os.path.join(root, "eval")
    raw = _bytes(os.path.join(e, "EVAL_FREEZE.json"))
    ef = _json(raw)
    if not isinstance(ef, dict):
        return ["eval/EVAL_FREEZE.json is missing or unreadable"], None
    probs = []
    if not ef.get("results_json_sha256") or sha(os.path.join(e, "results.json")) != ef["results_json_sha256"]:
        probs.append("evaluation results changed after their freeze or missing: eval/results.json")
    if not arms_sha or ef.get("arms_freeze_sha256") != arms_sha:
        probs.append("the evaluation freeze does not name the verified arms freeze")
    if not build_sha or ef.get("build_manifest_sha256") != build_sha:
        probs.append("the evaluation freeze does not name the verified build manifest")
    return probs, _digest(raw)


def check(stage, exp=EXP):
    """(problems, verified digests) before STAGE; no problems means the stage may run."""
    if stage not in STAGES:
        return [f"unknown stage {stage!r}"], {}
    probs, dig = go_problems(exp)
    if not probs:
        probs = freeze_problems(exp)
    if probs:
        return probs, dig
    root = os.path.join(exp, ROOT)

    def exists(*parts):
        return os.path.exists(os.path.join(root, *parts))
    if stage == "build" and (exists("build", "BUILD_MANIFEST.json") or exists("arms")):
        probs.append("the construction finished earlier or arms outputs exist: it is verified, never redone")
    if stage in ("arms", "eval", "save"):
        bp, dig["build_manifest"], _ = build_check(root)
        probs += bp
    if stage == "arms" and (exists("arms", "ARMS_FREEZE.json") or exists("eval")):
        probs.append("the arms were frozen earlier or evaluation outputs exist: they are verified, never rerun")
    if stage in ("eval", "save"):
        ap, dig["arms_freeze"], _ = arms_check(root, dig["build_manifest"])
        probs += ap
    if stage == "eval" and exists("eval", "EVAL_FREEZE.json"):
        probs.append("the evaluation was frozen earlier: it is verified, never rerun")
    if stage == "save":
        ep, dig["eval_freeze"] = eval_check(root, dig["build_manifest"], dig["arms_freeze"])
        probs += ep
    return probs, dig


def main(argv):
    stage = argv[1] if len(argv) == 2 else ""
    probs, dig = check(stage)
    if probs:
        print(f"FAIL {stage}: " + "; ".join(probs))
        return 1
    print(f"ok {stage}: " + " ".join(f"{k} {v}" for k, v in dig.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
