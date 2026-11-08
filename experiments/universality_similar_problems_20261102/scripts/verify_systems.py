"""Re-hash every extracted system file against SYSTEMS_MANIFEST.json, and each frozen package MANIFEST against its
sha256. Appends to the run folder's verify_log.jsonl; exit 1 on any mismatch. Usage: python3 -I verify_systems.py STAGE"""
import hashlib
import json
import os
import sys
import time

R = "/path/to/repository"
E = os.path.join(R, "experiments/universality_similar_problems_20261102")
RUN = "/path/to/benchmark_data/runs"
MAN = {os.path.join(R, "experiments/cora_cast_20261026/kaggle_pkg/MANIFEST.json"):
       "acd57e12f6d7b2735821c06d9dfbcfafd3eaf5754383bd62a92956fd5d2d8f7a",
       os.path.join(R, "experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/MANIFEST.json"):
       "aa8551ad935722ed0775570ff1bb1173108a777d3befead17eaf5ce57251f7d0",
       os.path.join(R, "kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/MANIFEST.json"):
       "11eb2ee9cd10f1507a0ffdcc6ae069de2efed79eb569788888aebcc3fd685ef7"}
h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()      # noqa: E731


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "manual"
    sm = json.load(open(os.path.join(E, "SYSTEMS_MANIFEST.json")))
    bad, n = [], 0
    for sysname, files in sm["systems"].items():
        for rel, want in files.items():
            n += 1
            p = os.path.join(E, "systems", sysname, rel)
            if not os.path.exists(p) or h(p) != want:
                bad.append(f"{sysname}/{rel}")
    for p, want in MAN.items():
        n += 1
        if h(p) != want:
            bad.append(p)
    rec = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stage": stage, "checked": n, "mismatches": bad,
           "ok": not bad}
    os.makedirs(RUN, exist_ok=True)
    with open(os.path.join(RUN, "verify_log.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
