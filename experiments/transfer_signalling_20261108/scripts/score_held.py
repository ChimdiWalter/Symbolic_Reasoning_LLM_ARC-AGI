"""T5 held scoring (PROTOCOL.md, amendment 1). One detached run after GO; it never runs during development.

  python -I scripts/score_held.py --salt <sha256 of GO.json>    the scored run (creates results_held/)
  python -I scripts/score_held.py --dry-run                     the smoke test (writes results_dryrun/):
      salt "DRYRUN", 3 P1 tasks, 3 S2 tasks, and S1's code path on the CellNOpt toy data instead of DREAM.

The scored run refuses to start unless all of these hold:
- results_held/ does not exist;
- GO.json and FREEZE.json are byte-identical to their committed copies at HEAD;
- GO.json holds freeze_commit, freeze_json_sha256, utc and a 64-hex nonce;
- GO.json's freeze_json_sha256 is the sha256 of FREEZE.json;
- its freeze_commit is the last commit that changed FREEZE.json and an ancestor of the commit that last changed
  GO.json;
- every file listed in FREEZE.json has its recorded sha256;
- --salt equals the sha256 of the GO.json bytes.

Families:
- P1, the primary: the held synthetic family on the real DREAM network and design, with labels "held|<salt>|P1|<i>".
  Its statistics are written to results_held/P1_RESULT.json before any secondary runs.
- S1: the 25 real DREAM conditions, in 5 folds dealt by a hash with the salt.
- S2: the toy-network synthetic family, with labels "held|<salt>|S2|<i>".
A secondary that fails is recorded and does not void a completed primary. Every family runs four arms: static, grown,
shuffled and the CellNOpt-style comparator (S3).
"""
import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(HERE))
STUDY = os.path.relpath(HERE, REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "universality_boolean_bbm_20261103"))
from t5.data import Dataset, design_only  # noqa: E402
from t5.tasks import hash_folds, make_task, run_arms, synthetic_task  # noqa: E402
from u6.stats import Bootstrap, diff_of_ratios, holm  # noqa: E402

RAW = os.path.join(HERE, "data", "raw")
ARMS = ("static", "grown", "shuffled", "classical")
SENSITIVITY_EDGE = "mek12 1 erk12"


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha(path):
    with open(path, "rb") as f:
        return sha_bytes(f.read())


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, check=False)


def verify_go(repo, study, salt):
    """All refusal checks of the scored run except the results_held/ check. Returns the provenance."""
    def refuse(msg):
        raise SystemExit("refusing: " + msg)
    go_rel, fz_rel = f"{study}/GO.json", f"{study}/FREEZE.json"
    go_path, fz_path = os.path.join(repo, go_rel), os.path.join(repo, fz_rel)
    if not os.path.exists(go_path):
        refuse("GO.json does not exist")
    go_bytes, fz_bytes = open(go_path, "rb").read(), open(fz_path, "rb").read()
    for rel, b in ((go_rel, go_bytes), (fz_rel, fz_bytes)):
        c = _git(repo, "show", f"HEAD:{rel}")
        if c.returncode != 0 or c.stdout != b:
            refuse(f"{rel} differs from its committed copy at HEAD")
    try:
        go = json.loads(go_bytes)
    except ValueError:
        refuse("GO.json is not valid JSON")
    for k in ("freeze_commit", "freeze_json_sha256", "utc", "nonce"):
        if k not in go:
            refuse(f"GO.json lacks {k}")
    if not re.fullmatch(r"[0-9a-f]{64}", str(go["nonce"])):
        refuse("GO.json's nonce is not 64 lowercase hex characters")
    if go["freeze_json_sha256"] != sha_bytes(fz_bytes):
        refuse("GO.json's freeze_json_sha256 is not the sha256 of FREEZE.json")
    last_fz = _git(repo, "log", "-1", "--format=%H", "--", fz_rel).stdout.decode().strip()
    if go["freeze_commit"] != last_fz:
        refuse(f"GO.json does not name the latest freeze commit ({last_fz})")
    go_commit = _git(repo, "log", "-1", "--format=%H", "--", go_rel).stdout.decode().strip()
    if not go_commit:
        refuse("GO.json is not committed")
    if _git(repo, "merge-base", "--is-ancestor", last_fz, go_commit).returncode != 0:
        refuse("the freeze commit is not an ancestor of the GO commit")
    fz = json.loads(fz_bytes)
    bad = [p for p, h in fz["files"].items() if not os.path.exists(os.path.join(repo, p))
           or sha(os.path.join(repo, p)) != h]
    if bad:
        refuse(f"files differ from FREEZE.json: {bad}")
    expected = sha_bytes(go_bytes)
    if salt != expected:
        refuse("--salt is not the sha256 of GO.json")
    head = _git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    return {"salt": expected, "go_json_sha256": expected, "go_commit": go_commit, "freeze_commit": last_fz,
            "freeze_json_sha256": sha_bytes(fz_bytes), "git_head_at_start": head}


def binom_two_sided(w, l):
    """Exact two-sided sign (or McNemar) test on w wins and l losses, ties excluded."""
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def _exact(r, arm):
    return sum(h["exact"] for h in r["arms"][arm]["held"].values())


def family_stats(results, n_boot):
    """Per-task exact counts per arm; sign tests over tasks, McNemar over conditions, task bootstrap of the
    difference in exact proportions."""
    out = {"tasks": len(results), "held_conditions": sum(r["n_held"] for r in results), "arms": {}, "pairs": {}}
    for a in ARMS:
        out["arms"][a] = sum(_exact(r, a) for r in results)
    units = [r["task"] for r in results]
    bs = Bootstrap(units, n_boot) if units else None
    for a, b in (("grown", "shuffled"), ("grown", "static"), ("shuffled", "static"), ("classical", "static"),
                 ("grown", "classical")):
        tw = tl = cw = cl = 0
        num_a, num_b, den = {}, {}, {}
        for r in results:
            ea, eb = _exact(r, a), _exact(r, b)
            tw += ea > eb
            tl += ea < eb
            for k, h in r["arms"][a]["held"].items():
                hb = r["arms"][b]["held"][k]["exact"]
                cw += h["exact"] and not hb
                cl += (not h["exact"]) and hb
            num_a[r["task"]], num_b[r["task"]], den[r["task"]] = ea, eb, r["n_held"]
        ci = diff_of_ratios(bs, num_a, den, num_b, den) if bs else {}
        out["pairs"][f"{a}_vs_{b}"] = {
            "tasks_won": tw, "tasks_lost": tl, "tasks_tied": len(results) - tw - tl, "sign_p": binom_two_sided(tw, tl),
            "conditions_won": cw, "conditions_lost": cl, "mcnemar_p": binom_two_sided(cw, cl),
            "difference": ci.get("point"), "ci95": ci.get("ci95")}
    return out


def per_edge_table(results):
    rows = {}
    for r in results:
        e = r["synthetic"]["removed_edge"]
        t = rows.setdefault(e, {"tasks": 0, "held_conditions": 0, **{f"exact_{a}": 0 for a in ARMS},
                                "H1_won": 0, "H1_lost": 0, "H2_won": 0, "H2_lost": 0})
        t["tasks"] += 1
        t["held_conditions"] += r["n_held"]
        for a in ARMS:
            t[f"exact_{a}"] += _exact(r, a)
        g, s, st = _exact(r, "grown"), _exact(r, "shuffled"), _exact(r, "static")
        t["H1_won"] += g > s
        t["H1_lost"] += g < s
        t["H2_won"] += g > st
        t["H2_lost"] += g < st
    return dict(sorted(rows.items()))


def run_family(name, make, n_tasks, max_seeds, cfg, log, t_start, budget):
    results, skipped = [], 0
    i = 0
    while len(results) < n_tasks and i < max_seeds:
        made = make(i)
        i += 1
        if made is None:
            skipped += 1
            continue
        task, info = made
        r = run_arms(task, cfg, ARMS)
        r["synthetic"] = info
        r["n_held"] = len(task.held_conds)
        results.append(r)
        log.write(json.dumps({"family": name, **r}) + "\n")
        log.flush()
        if time.process_time() - t_start > budget:
            raise RuntimeError(f"CPU budget exceeded during {name} after {len(results)} tasks")
    return results, {"seeds_tried": i, "seeds_skipped": skipped}


def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salt")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(HERE, "config_held.json")))
    t_start = time.process_time()
    import numpy
    prov = {"python": platform.python_version(), "numpy": numpy.__version__}
    if a.dry_run:
        salt, out_dir = "DRYRUN", os.path.join(HERE, "results_dryrun")
        n1, n2 = 3, 3
        if os.path.exists(os.path.join(HERE, "FREEZE.json")):
            fz = json.load(open(os.path.join(HERE, "FREEZE.json")))
            bad = [p for p, h in fz["files"].items() if sha(os.path.join(REPO, p)) != h]
            print("dry run: FREEZE.json file check", "passes" if not bad else f"FAILS for {bad}")
        os.makedirs(out_dir, exist_ok=True)
    else:
        if not a.salt:
            raise SystemExit("refusing: the scored run needs --salt <sha256 of GO.json>")
        out_dir = os.path.join(HERE, "results_held")
        if os.path.exists(out_dir):
            raise SystemExit("refusing: results_held/ exists (one scored run only)")
        prov.update(verify_go(REPO, STUDY, a.salt))
        salt = prov["salt"]
        n1, n2 = cfg["P1"]["n_tasks"], cfg["S2"]["n_tasks"]
        os.makedirs(out_dir)
    status = os.path.join(out_dir, "status.txt")
    open(status, "w").write(f"RUNNING {stamp()}\n")
    log = open(os.path.join(out_dir, "tasks.jsonl"), "w")
    budget = cfg["cpu_budget_s"]
    res = {"label": "held" if not a.dry_run else "dry run (not held)", "salt": salt, "config": cfg,
           "provenance": prov, "families": {}}
    syn = cfg["syn"]
    dream_path = (os.path.join(RAW, "LiverPKNDREAM.sif"), os.path.join(RAW, "LiverDataDREAMMIDAS.csv"))
    # ------------------------------------------------------------------ the primary: a failure here fails the run
    try:
        dream_design = design_only(Dataset("LiverDREAM", *dream_path))
        r1, m1 = run_family("P1", lambda i: synthetic_task(dream_design, f"held|{salt}|P1|{i}", cfg["P1"]["n_held"],
                                                           syn["flip"], syn),
                            n1, cfg["P1"]["max_seeds"], cfg, log, t_start, budget)
        st1 = family_stats(r1, cfg["bootstrap_resamples"])
        st1["seeds"] = m1
        hp = holm({"H1_grown_vs_shuffled": st1["pairs"]["grown_vs_shuffled"]["sign_p"],
                   "H2_grown_vs_static": st1["pairs"]["grown_vs_static"]["sign_p"]}, cfg["alpha"])
        st1["holm"] = hp
        st1["decision"] = {}
        for h, pair in (("H1_grown_vs_shuffled", "grown_vs_shuffled"), ("H2_grown_vs_static", "grown_vs_static")):
            d = st1["pairs"][pair]
            st1["decision"][h] = {"p_holm": hp[h]["p_holm"], "tasks_won": d["tasks_won"], "tasks_lost": d["tasks_lost"],
                                  "supported": bool(hp[h]["p_holm"] is not None and hp[h]["p_holm"] <= cfg["alpha"]
                                                    and d["tasks_won"] > d["tasks_lost"])}
        st1["per_removed_edge"] = per_edge_table(r1)
        rest = [r for r in r1 if r["synthetic"]["removed_edge"] != SENSITIVITY_EDGE]
        sens = family_stats(rest, cfg["bootstrap_resamples"])
        st1["sensitivity_without_mek12_erk12"] = {
            "note": "no gate; tasks whose removed edge is mek12 -> erk12 are excluded",
            "tasks": sens["tasks"], "held_conditions": sens["held_conditions"], "arms": sens["arms"],
            "H1_grown_vs_shuffled": sens["pairs"]["grown_vs_shuffled"],
            "H2_grown_vs_static": sens["pairs"]["grown_vs_static"]}
        st1["cpu_s_at_end"] = round(time.process_time() - t_start, 1)
        res["families"]["P1"] = st1
        json.dump({"label": res["label"], "salt": salt, "provenance": prov, "P1": st1},
                  open(os.path.join(out_dir, "P1_RESULT.json"), "w"), indent=1)
        open(status, "a").write(f"P1_DONE {stamp()} cpu_s={st1['cpu_s_at_end']}\n")
    except Exception as ex:
        open(status, "a").write(f"FAILED_PRIMARY {stamp()} {type(ex).__name__}: {ex}\n")
        raise
    # ------------------------------------------------------------- the secondaries: a failure is recorded only
    failures = []
    try:
        toy_real = Dataset("Toy", os.path.join(RAW, "ToyPKNMMB.sif"), os.path.join(RAW, "ToyDataMMB.csv"))
        real = toy_real if a.dry_run else Dataset("LiverDREAM", *dream_path)
        keys = [c["key"] for c in real.conditions]
        folds = hash_folds(keys, salt, real.name, cfg["S1"]["n_folds"])
        r_s1 = []
        for f, held in enumerate(folds):
            train = [i for i in range(len(keys)) if i not in held]
            task = make_task(real, train, held, f"held|{salt}|S1|{f}", threshold=cfg["threshold"])
            r = run_arms(task, cfg, ARMS)
            r["n_held"] = len(held)
            r_s1.append(r)
            log.write(json.dumps({"family": "S1", **r}) + "\n")
            log.flush()
        s1 = family_stats(r_s1, cfg["bootstrap_resamples"])
        s1["pre_registered"] = ("grown_vs_static: exact McNemar over the held conditions (mcnemar_p); the fold-level "
                                "sign tests and bootstrap are computed but not pre-registered for this family")
        s1["folds"] = [[keys[i] for i in fd] for fd in folds]
        res["families"]["S1"] = s1
        open(status, "a").write(f"S1_DONE {stamp()}\n")
    except Exception as ex:
        res["families"]["S1"] = {"failed": f"{type(ex).__name__}: {ex}"}
        failures.append("S1")
        open(status, "a").write(f"FAILED_S1 {stamp()} {type(ex).__name__}: {ex}\n")
    try:
        toy_design = design_only(Dataset("Toy", os.path.join(RAW, "ToyPKNMMB.sif"), os.path.join(RAW, "ToyDataMMB.csv")))
        r2, m2 = run_family("S2", lambda i: synthetic_task(toy_design, f"held|{salt}|S2|{i}", cfg["S2"]["n_held"],
                                                           syn["flip"], syn),
                            n2, cfg["S2"]["max_seeds"], cfg, log, t_start, budget)
        st2 = family_stats(r2, cfg["bootstrap_resamples"])
        st2["seeds"] = m2
        res["families"]["S2"] = st2
        open(status, "a").write(f"S2_DONE {stamp()}\n")
    except Exception as ex:
        res["families"]["S2"] = {"failed": f"{type(ex).__name__}: {ex}"}
        failures.append("S2")
        open(status, "a").write(f"FAILED_S2 {stamp()} {type(ex).__name__}: {ex}\n")
    res["secondary_failures"] = failures
    res["cpu_s"] = round(time.process_time() - t_start, 1)
    json.dump(res, open(os.path.join(out_dir, "RESULT.json"), "w"), indent=1)
    open(status, "a").write(f"DONE {stamp()} cpu_s={res['cpu_s']} secondary_failures={failures}\n")
    for fam, st in res["families"].items():
        if "failed" in st:
            print(f"{fam}: FAILED {st['failed']}")
            continue
        print(f"{fam}: tasks={st['tasks']} held conditions={st['held_conditions']} "
              + " ".join(f"{k}={v}" for k, v in st["arms"].items()))
        for k, d in st["pairs"].items():
            print(f"  {k}: tasks {d['tasks_won']}-{d['tasks_lost']} (tied {d['tasks_tied']}) sign p={d['sign_p']:.3g};"
                  f" conditions {d['conditions_won']}-{d['conditions_lost']} McNemar p={d['mcnemar_p']:.3g};"
                  f" diff={d['difference']} ci95={d['ci95']}")
    if "decision" in res["families"].get("P1", {}):
        print("P1 decision:", json.dumps(res["families"]["P1"]["decision"]))
        print("P1 per removed edge:", json.dumps(res["families"]["P1"]["per_removed_edge"]))
    print(f"cpu_s={res['cpu_s']}")


if __name__ == "__main__":
    main()
