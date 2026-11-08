"""Download the three outside benchmarks of PROTOCOL.md at the exact commits the study used, and check every task file
against DATA_MANIFEST.json. No benchmark file is shipped with this repository.

    python3 -I scripts/download_benchmarks.py TARGET [--arc2 DIR]

TARGET/src/1d_arc, TARGET/src/mini_arc and TARGET/src/concept_arc become git clones of the benchmark authors'
repositories (1D-ARC, MIT; Mini-ARC, Apache 2.0; ConceptARC, MIT), checked out at the commits recorded in
DATA_MANIFEST.json. Every task file the manifest lists, and each licence file, must match its recorded sha256, and no
other JSON file may sit in a task folder. With --arc2 DIR, the four ARC-AGI-2 files that the freshness check reads
(the training and evaluation challenges and solutions of the Kaggle competition data) are checked against their
recorded sha256 as well. Exit status 0 means that everything matched.

To rerun the study, edit the folder constants at the top of each script (R, E, D or DATA, RUN, K, PKG, R29 and ARC2,
and the interpreter path in the shell scripts): they hold the absolute folders of the machine the study ran on, and
TARGET takes the place of D and DATA. The notebooks of the two released entries are in kaggle_entries/, and the three
package manifests that extract_systems.py and verify_systems.py check are in kaggle_entries/builder/ under their
research-repository paths; the notebook of the third system (cast_v1 alone) is not released. chain.sh and u2b_chain.sh
run each arm through a CPU-slot wrapper of the research repository that is not released; it only limits concurrency.
Then follow PROTOCOL.md and U2B_PROTOCOL.md: prepare_data.py, extract_systems.py, run_arm.sh for every system,
benchmark and arm, score.py score, then u2b_blind.py and u2b_analysis.py."""
import argparse
import hashlib
import json
import os
import subprocess
import sys

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git(*args):
    return subprocess.run(["git", "-c", "advice.detachedHead=false", *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def fetch(name, b, target):
    d = os.path.join(target, "src", name)
    if not os.path.isdir(os.path.join(d, ".git")):
        if os.path.exists(d) and os.listdir(d):
            sys.exit(f"{d} exists and is not a git clone; remove it or choose another TARGET")
        git("clone", "--quiet", b["url"], d)
    if subprocess.run(["git", "-C", d, "cat-file", "-e", b["commit"] + "^{commit}"], capture_output=True).returncode:
        git("-C", d, "fetch", "--quiet", "origin", b["commit"])
    git("-C", d, "checkout", "--quiet", "--detach", b["commit"])
    return d


def check(name, b, d):
    want = b["files_sha256"]
    have = {os.path.relpath(os.path.join(dp, f), d).replace(os.sep, "/")
            for dp, _, fn in os.walk(os.path.join(d, b["task_root"])) for f in fn if f.endswith(".json")}
    missing = sorted(set(want) - have)
    differ = sorted(r for r in set(want) & have if sha256(os.path.join(d, r)) != want[r])
    extra = sorted(have - set(want))
    head = git("-C", d, "rev-parse", "HEAD")
    licence = sha256(os.path.join(d, b["licence_file"])) == b["licence_sha256"]
    ok = head == b["commit"] and licence and not (missing or differ or extra)
    print(f"{name}: commit {head[:12]} ({'as recorded' if head == b['commit'] else 'NOT the recorded commit'}), "
          f"{len(want) - len(missing) - len(differ)} of {len(want)} task files match, {len(missing)} missing, "
          f"{len(differ)} different, {len(extra)} unlisted, licence {b['licence']} "
          f"{'matches' if licence else 'DIFFERS'}")
    for r in (missing + differ + extra)[:10]:
        print("   ", r)
    return ok


def main():
    ap = argparse.ArgumentParser(description="download and check the outside benchmarks (no data is shipped)")
    ap.add_argument("target", help="folder for the clones (TARGET/src/<benchmark>)")
    ap.add_argument("--arc2", help="folder with the four ARC-AGI-2 files, to check their sha256")
    a = ap.parse_args()
    with open(os.path.join(STUDY, "DATA_MANIFEST.json"), encoding="utf-8") as f:
        man = json.load(f)
    ok = True
    for name, b in man["benchmarks"].items():
        ok &= check(name, b, fetch(name, b, os.path.abspath(a.target)))
    if a.arc2:
        for fname, want in sorted(man["arc_agi_2_reference"].items()):
            p = os.path.join(a.arc2, fname)
            state = "missing" if not os.path.isfile(p) else "matches" if sha256(p) == want else "DIFFERS"
            print(f"ARC-AGI-2 {fname}: {state}")
            ok &= state == "matches"
    print("ALL MATCH" if ok else "MISMATCH: do not use these files for the study")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
