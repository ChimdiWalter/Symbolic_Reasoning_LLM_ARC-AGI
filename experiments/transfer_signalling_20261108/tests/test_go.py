"""Test of the GO checks in scripts/score_held.py (verify_go) on a throwaway git repository.
Run: python3 -I tests/test_go.py <empty scratch directory>"""
import hashlib
import json
import os
import secrets
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))
import score_held as S  # noqa: E402


def git(repo, *a):
    subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True,
                   capture_output=True)


def write(repo, rel, text):
    p = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def refused(fn):
    try:
        fn()
    except SystemExit as e:
        return str(e)
    return None


def main(repo):
    assert not os.listdir(repo), "use an empty directory"
    git(repo, "init", "-q")
    st = "exp/study"
    write(repo, f"{st}/code.py", "x = 1\n")
    h = hashlib.sha256(b"x = 1\n").hexdigest()
    write(repo, f"{st}/FREEZE.json", json.dumps({"files": {f"{st}/code.py": h}}))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "freeze 1")
    old = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    write(repo, f"{st}/FREEZE.json", json.dumps({"files": {f"{st}/code.py": h}, "v": 2}))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "freeze 2")
    fz = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    fz_sha = hashlib.sha256(open(os.path.join(repo, st, "FREEZE.json"), "rb").read()).hexdigest()

    def go(commit, nonce=None, fsha=fz_sha):
        g = {"freeze_commit": commit, "freeze_json_sha256": fsha, "utc": "2026-11-08T00:00:00Z",
             "nonce": nonce or secrets.token_hex(32), "pre_run_review_sha256": "r1", "change_review_sha256": "r2"}
        write(repo, f"{st}/GO.json", json.dumps(g, indent=1))
        git(repo, "add", f"{st}/GO.json")
        git(repo, "commit", "-q", "-m", "GO")
        return hashlib.sha256(open(os.path.join(repo, st, "GO.json"), "rb").read()).hexdigest()

    salt = go(fz)
    prov = S.verify_go(repo, st, salt)
    assert prov["salt"] == salt and prov["freeze_commit"] == fz, prov
    results = [("wrong salt", refused(lambda: S.verify_go(repo, st, "0" * 64)))]
    assert "salt" in results[0][1], results[0][1]
    write(repo, f"{st}/code.py", "x = 2\n")
    results.append(("frozen file edited", refused(lambda: S.verify_go(repo, st, salt))))
    write(repo, f"{st}/code.py", "x = 1\n")
    write(repo, f"{st}/GO.json", open(os.path.join(repo, st, "GO.json")).read() + " ")
    results.append(("GO.json differs from its commit", refused(lambda: S.verify_go(repo, st, salt))))
    git(repo, "checkout", "-q", "--", f"{st}/GO.json")
    write(repo, f"{st}/FREEZE.json", open(os.path.join(repo, st, "FREEZE.json")).read() + " ")
    results.append(("FREEZE.json differs from its commit", refused(lambda: S.verify_go(repo, st, salt))))
    git(repo, "checkout", "-q", "--", f"{st}/FREEZE.json")
    assert S.verify_go(repo, st, salt)["salt"] == salt, "clean state must pass again"
    s2 = go(old)
    results.append(("GO names an old freeze commit", refused(lambda: S.verify_go(repo, st, s2))))
    s3 = go(fz, nonce="abc")
    results.append(("bad nonce", refused(lambda: S.verify_go(repo, st, s3))))
    s4 = go(fz, fsha="f" * 64)
    results.append(("wrong FREEZE.json sha256 in GO", refused(lambda: S.verify_go(repo, st, s4))))
    for n, r in results:
        assert r is not None, f"not refused: {n}"
        print(f"refused as expected ({n}): {r}")
    print("ok: GO checks pass on a valid GO and refuse", len(results), "invalid cases")


if __name__ == "__main__":
    main(sys.argv[1])
