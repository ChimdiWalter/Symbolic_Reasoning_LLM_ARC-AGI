"""The one scored run on held items (PROTOCOL.md, with Amendment 1). It refuses to start unless:
- no earlier results/held.jsonl exists;
- the coordinator's GO file (./GO) is committed at HEAD, unchanged since its first commit (the first committed GO is
  final), and its first line is exactly GO;
- GO names the current FREEZE.json's sha256 and a 64-hex nonce, and its freeze commit is the last commit on HEAD that
  changed FREEZE.json;
- every file hash in FREEZE.json matches, the data archives included;
- the Python, numpy and scikit-learn versions match FREEZE.json.
The salt is the sha256 of the committed GO file; the run derives it itself and records it with the freeze commit.

Launch, detached, from this folder (results/ is created by the run; the launcher logs to
outputs/detached/transfer_logic_held/):
  sh ../../scripts/run_detached.sh transfer_logic_held --slot python3 -I score_held.py
It writes results/run.status (STARTED, RUNNING with a count, DONE or a refusal or abort reason), results/held.jsonl
(one line per item and budget) and results/summary.json (the pre-registered analyses).
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tlogic import arms, data, stats  # noqa: E402

REL = "experiments/transfer_logic_20261108/"
CPU_CAP_S = 1800.0


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def git(*a):
    return subprocess.run(["git", "-C", HERE] + list(a), capture_output=True)


def write_status(msg):
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "run.status"), "w") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + msg + "\n")


def refuse(msg):
    write_status("REFUSED " + msg)
    sys.exit("refused: " + msg)


def checks():
    if os.path.exists(os.path.join(HERE, "results", "held.jsonl")):
        refuse("results/held.jsonl exists: one scored run only")
    go_path = os.path.join(HERE, "GO")
    if not os.path.exists(go_path):
        refuse("no GO file")
    go = open(go_path, "rb").read()
    lines = go.decode("utf-8").splitlines()
    if not lines or lines[0] != "GO":
        refuse("GO file does not start with the line GO")
    f = dict(l.split(": ", 1) for l in lines[1:] if ": " in l)
    if git("show", f"HEAD:{REL}GO").stdout != go:
        refuse("GO is not committed at HEAD or differs from it")
    if len(git("log", "--format=%H", "HEAD", "--", go_path).stdout.decode().split()) != 1:
        refuse("GO was changed after its first commit: the first committed GO is final")
    fz_bytes = open(os.path.join(HERE, "FREEZE.json"), "rb").read()
    if f.get("freeze_json_sha256") != hashlib.sha256(fz_bytes).hexdigest():
        refuse("GO names a different FREEZE.json")
    nonce = f.get("nonce", "")
    if len(nonce) != 64 or any(ch not in "0123456789abcdef" for ch in nonce):
        refuse("GO nonce is not 64 hex characters")
    fc = f.get("freeze_commit", "")
    # git runs with -C HERE, so the pathspec after "--" must be absolute (a repo-relative one would not match)
    last = git("log", "-n", "1", "--format=%H", "HEAD", "--", os.path.join(HERE, "FREEZE.json")).stdout.decode().strip()
    if fc != last or git("show", f"{fc}:{REL}FREEZE.json").stdout != fz_bytes:
        refuse("GO's freeze commit is not the last commit on HEAD that changed FREEZE.json")
    for rel, h in sorted(json.loads(fz_bytes)["sha256"].items()):
        p = os.path.normpath(os.path.join(HERE, rel))
        if not os.path.exists(p) or sha(p) != h:
            refuse("hash mismatch " + rel)
    import numpy
    import sklearn
    env = json.loads(fz_bytes)["environment"]
    have = {"python": platform.python_version(), "numpy": numpy.__version__, "scikit_learn": sklearn.__version__}
    for k, v in have.items():
        if env.get(k) != v:
            refuse(f"{k} version {v} differs from FREEZE.json ({env.get(k)})")
    return hashlib.sha256(go).hexdigest(), fc


def run(salt):
    cfg = data.load_config()
    t0 = time.process_time()
    held_c, held_p = data.held_items(cfg, salt)
    plan = [(i, "circuit", f) for f in cfg["scored"]["circuit_fractions"] for i in held_c]
    plan += [(i, "policy", f) for f in cfg["scored"]["policy_fractions"] for i in held_p]
    write_status(f"RUNNING 0/{len(plan)}")
    out = os.path.join(HERE, "results", "held.jsonl")
    rows = []
    with open(out, "w") as fo:
        for k, (it, dom, frac) in enumerate(plan):
            if time.process_time() - t0 > CPU_CAP_S:
                write_status(f"ABORTED_CPU_CAP after {k}/{len(plan)}")
                sys.exit("CPU cap reached")
            c = dict(cfg)
            c["budget"] = dict(cfg["budget"])
            c["budget"][dom] = {"fraction": frac}
            active = frac == cfg["scored"]["primary_fraction"]
            r = arms.run_item(it, c, cfg[dom]["arms"], True, active)
            r.update({"label": "held", "fraction": frac,
                      "data_label": "real" if dom == "circuit" else "synthetic from real seeds"})
            fo.write(json.dumps(r) + "\n")
            fo.flush()
            rows.append(r)
            if k % 25 == 0:
                write_status(f"RUNNING {k + 1}/{len(plan)}")
        os.fsync(fo.fileno())
    return rows, time.process_time() - t0, len(held_c), len(held_p)


def analyse(rows, cpu, n_c, n_p, salt, freeze_commit):
    cfg = data.load_config()
    pf = cfg["scored"]["primary_fraction"]

    def sel(dom, frac):
        return [r for r in rows if r["domain"] == dom and r["fraction"] == frac]

    prim = {"grown_vs_static": stats.compare(sel("circuit", pf), "grown", "static"),
            "grown_vs_shuffled": stats.compare(sel("circuit", pf), "grown", "shuffled")}
    ph = stats.holm({k: v["mcnemar_exact_p"] for k, v in prim.items()})
    for k, v in prim.items():
        v["holm"] = ph[k]
        v["supported"] = bool(ph[k]["reject"] and v["difference"] is not None and v["difference"] > 0
                              and v["cluster_bootstrap_ci95"][0] is not None
                              and v["cluster_bootstrap_ci95"][0] > 0)
    sec = {}
    for f in cfg["scored"]["circuit_fractions"]:
        if f != pf:
            sec[f"circuit_{f}_grown_vs_static"] = stats.compare(sel("circuit", f), "grown", "static")
            sec[f"circuit_{f}_grown_vs_shuffled"] = stats.compare(sel("circuit", f), "grown", "shuffled")
    sec["circuit_active_vs_random"] = stats.compare(sel("circuit", pf), "grown_active", "grown")
    sec["policy_grown_vs_static"] = stats.compare(sel("policy", pf), "grown", "static")
    sec["policy_grown_vs_shuffled"] = stats.compare(sel("policy", pf), "grown", "shuffled")
    sec["policy_active_vs_random"] = stats.compare(sel("policy", pf), "grown_active", "grown")
    sh = stats.holm({k: v["mcnemar_exact_p"] for k, v in sec.items()})
    for k, v in sec.items():
        v["holm"] = sh[k]
    ref = {"circuit_grown_vs_espresso_like": stats.compare(sel("circuit", pf), "grown", "espresso_like"),
           "circuit_grown_vs_cart": stats.compare(sel("circuit", pf), "grown", "cart"),
           "policy_grown_vs_full": stats.compare(sel("policy", pf), "grown", "full"),
           "policy_grown_vs_cart": stats.compare(sel("policy", pf), "grown", "cart")}
    verified = {}
    for dom in ("circuit", "policy"):
        rs = sel(dom, pf)
        for a in ("static", "grown", "shuffled"):
            v = [r for r in rs if r["arms"][a].get("verified") == 1]
            verified[f"{dom}_{a}"] = {"verified": len(v), "exact_among_verified": sum(r["arms"][a]["exact"] for r in v),
                                      "items": len(rs)}
    summary = {"label": "held", "salt": salt, "salt_rule": "sha256 of the committed GO file",
               "freeze_commit": freeze_commit, "held_circuit_items": n_c, "held_policy_items": n_p,
               "cpu_seconds": round(cpu, 1), "primary": prim, "secondary": sec, "reference_not_gate": ref,
               "verify_flag": verified}
    with open(os.path.join(HERE, "results", "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)


def main():
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    salt, fc = checks()
    write_status(f"STARTED salt {salt} freeze_commit {fc}")
    rows, cpu, n_c, n_p = run(salt)
    analyse(rows, cpu, n_c, n_p, salt, fc)
    write_status(f"DONE {len(rows)} item-budget rows, {cpu:.1f} CPU-seconds, salt {salt}, freeze_commit {fc}")


if __name__ == "__main__":
    main()
