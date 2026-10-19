"""Self-test of the eligibility checker on SYNTHETIC fixtures only (it never opens Step B's real manifest).

  python3 -I tools/stepb_eligibility/selftest.py SCRATCH_DIR
"""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(HERE, "check_eligibility.py")
SALT = "cora-level4-within-stage-holdout-2026-08-22"


def run(args, env):
    p = subprocess.run([sys.executable, "-I", CHECKER] + args, capture_output=True, text=True, env=env)
    return p.returncode, p.stdout.strip().splitlines()


def main(scratch):
    os.makedirs(scratch, exist_ok=True)
    ids = ["%08x" % (0x10000000 + 7919 * i) for i in range(1000)]
    splits = ["experience"] * 600 + ["promotion"] * 200 + ["lockbox"] * 200
    order = sorted(range(1000), key=lambda i: hashlib.sha256(("fixture" + ids[i]).encode()).hexdigest())
    tasks = [{"task_id": ids[i], "split": splits[k], "family_label": "x", "certified": False} for k, i in enumerate(order)]
    man = os.path.join(scratch, "fake_manifest.json")
    json.dump({"tasks": tasks}, open(man, "w"))
    msha = hashlib.sha256(open(man, "rb").read()).hexdigest()
    cands = ids[::10]
    cdoc = os.path.join(scratch, "fake_candidates.json")
    json.dump({"candidates_additions_only_ordered": cands, "candidates_sha256": hashlib.sha256(json.dumps(cands).encode()).hexdigest()},
              open(cdoc, "w"))
    env = dict(os.environ, ELIGIBILITY_SELFTEST="1")
    out = os.path.join(scratch, "out.json")
    rc, lines = run([cdoc, out, man, msha], env)
    rec = json.load(open(out))
    assert rc == 0 and len(lines) == 1 and lines[0].startswith("ELIGIBILITY_CHECK_DONE"), lines
    assert tuple(rec) == ("eligible_ids", "count", "checksums", "attestation")
    assert rec["attestation"]["status"] == "PASS" and rec["attestation"]["stepb_manifest_default_path"] is False
    split = {t["task_id"]: t["split"] for t in tasks}
    exp = sorted(t for t in split if split[t] == "experience")
    tr = set(sorted(exp, key=lambda t: hashlib.sha256((SALT + t).encode()).hexdigest())[450:])
    want = [c for c in cands if split[c] == "experience" and c not in tr]
    assert rec["eligible_ids"] == want and rec["count"] == len(want) and want
    text = open(out).read()
    assert "promotion" not in text and "lockbox" not in text.replace("lockbox_manifest", "")   # no per-candidate labels
    rc, lines = run([cdoc, out, man, "0" * 64], env)                            # wrong manifest hash: fail closed
    rec = json.load(open(out))
    assert rc == 1 and rec["eligible_ids"] is None and rec["attestation"]["status"] == "FAIL"
    rc, lines = run([cdoc, out, man, msha], dict(os.environ, ELIGIBILITY_SELFTEST="0"))   # overrides need the flag
    assert rc == 2
    print("SELFTEST_PASS eligible=%d of %d synthetic candidates" % (len(want), len(cands)))


if __name__ == "__main__":
    main(sys.argv[1])
