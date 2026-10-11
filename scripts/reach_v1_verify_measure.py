"""Independent terminal verification of the reach v1 measurement, and its
repair funnel (docs/CORA_REAL_TASK_REACH_DEV_v1.md, sections 5.1 and 6).
Written before the run's outcome was read. Development: no target is read.

  PYTHONHASHSEED=0 ARC_DIHEDRAL_FRAMES=45 ARC_GENERATIVE=1 ARC_PATTERN_DERIVE=1 \\
  ARC_VARIANT_BUDGET=1 ARC_RAY_EXT=1 PYTHONPATH=.:src:<Reasoning_Project_tti> \\
  .venv_arc2026/bin/python scripts/reach_v1_verify_measure.py
      -> logs/reach_v1/verify_measure.json, outputs/reach_v1/measure_funnel.json

Every verdict here is recomputed from the raw rows, the frozen inputs and
the git history, not read from the summary script: run identity, rows,
isolation, absence of any answer in the reasoner's input, run errors,
restoration, reproducible construction (all three construction paths
re-executed), every gate from its run records, the leave-one-out folds,
the controls, the budgets of the removed and matched arms, the separation
legs (the renaming leg re-executed with the engine's own detect_grow) and
the compute accounting.
"""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "reach_v1")
LOG = os.path.join(HERE, "logs", "reach_v1")
MANIFEST = os.path.join(OUT, "measure_manifest.json")
FREEZE_COMMIT = "c8d8e3a"
BASELINE_COMMIT = "ce123e8"


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True)


def jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            if line.strip():
                out.append(json.loads(line))
    return out


def tree_digest(root):
    """Independent restatement of the manifest's tree digest."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            if name.endswith((".py", ".json")):
                p = os.path.join(dirpath, name)
                h.update(os.path.relpath(p, root).encode() + b"\0")
                with open(p, "rb") as handle:
                    h.update(handle.read())
                h.update(b"\0")
    return h.hexdigest()


def clamp(x, lo, hi):
    return min(hi, max(lo, x))


def main():
    from cora_pilot import isolation as ISO
    from cora_pilot import native as N
    from cora_reach import construct as CN
    from cora_reach import growth_ext as GE
    from cora_reach import measure as M
    import numpy as np
    problems, notes = [], []

    def need(cond, msg):
        if not cond:
            problems.append(msg)
    env = N.environment_problems()
    if env:                    # the renaming leg re-executes detect_grow, whose modes the chain flags gate
        raise SystemExit(f"verifier environment differs from the workers': {env}")

    # ---------------------------------------------------------- identity
    manifest = json.load(open(MANIFEST))
    committed = git("show", f"{FREEZE_COMMIT}:outputs/reach_v1/measure_manifest.json")
    need(committed.returncode == 0 and hashlib.sha256(committed.stdout.encode()).hexdigest() == sha(MANIFEST),
         "manifest differs from the one committed in the freeze commit")
    state = manifest["state"]
    for f, digest in state["files"].items():
        need(sha(os.path.join(HERE, f)) == digest, f"frozen file changed: {f}")
    for t, digest in state["trees"].items():
        need(tree_digest(os.path.join(HERE, t)) == digest, f"frozen tree changed: {t}")
    need(git("diff", "--quiet", manifest["head"], FREEZE_COMMIT, "--", *state["files"]).returncode == 0,
         "frozen files differ between the manifest head and the freeze commit")
    start = json.load(open(os.path.join(LOG, "measure_0_start.json")))
    need(git("merge-base", "--is-ancestor", FREEZE_COMMIT, start["head"]).returncode == 0,
         "the run started from a commit that does not contain the freeze")
    need(not os.path.exists(os.path.join(LOG, "measure_0_resumes.jsonl")), "the run was resumed")
    boot_now = open("/proc/sys/kernel/random/boot_id").read().strip()
    notes.append(f"boot id at start {start['boot_id']}, at verification {boot_now}")
    rec_path = os.path.join(LOG, "measure_0_record.json")
    record = json.load(open(rec_path)) if os.path.exists(rec_path) else None
    need(os.path.exists(os.path.join(LOG, "MEASURE_0_DONE")), "no completion marker")
    need(record is not None, "no coordinator record")
    if record is not None:
        need(record["missing"] == [] and all(c == 0 for c in record["exit_codes"]),
             f"coordinator record: missing {record['missing']}, exit codes {record['exit_codes']}")

    # ---------------------------------------------------------- rows
    bundle = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))["tasks"]
    keys = sorted(bundle)
    lines = jsonl(os.path.join(OUT, "measure_rows.jsonl"))
    by_key = {}
    for r in lines:
        need(r["key"] not in by_key, f"duplicate row {r['key']}")
        by_key[r["key"]] = r
    need(len(lines) == 60 and sorted(by_key) == keys, f"{len(lines)} rows; keys equal to the bundle: "
                                                       f"{sorted(by_key) == keys}")

    # ---------------------------------------------------------- isolation and answers
    logs = sorted(f for f in os.listdir(LOG) if f.startswith("isolation_measure_0_"))
    need(len(logs) == 4, f"{len(logs)} isolation logs for 4 workers")
    for f in logs:
        rep = json.load(open(os.path.join(LOG, f)))
        for p in ISO.audit_log(rep):
            problems.append(f"isolation {f}: {p}")
        need(not rep.get("denied"), f"isolation {f}: refused accesses")
    for k, t in bundle.items():
        need(all(set(p) == {"input"} for p in t["test"]), f"bundle task {k} carries more than test inputs")
        need(all(set(p) == {"input", "output"} for p in t["train"]), f"bundle task {k}: demonstration fields")
    for f in sorted(os.listdir(LOG)):
        if f.startswith("worker_measure_0_"):
            need(os.path.getsize(os.path.join(LOG, f)) == 0, f"worker log {f} is not empty")

    # ---------------------------------------------------------- per task
    inst_rows = {r["key"]: r for r in jsonl(os.path.join(OUT, "instances2_rows.jsonl"))}
    census = {r["key"]: r for r in jsonl(os.path.join(OUT, "census_rows.jsonl"))}
    funnel_rows, compute = {}, {"total_s": 0.0, "by_arm_s": {}}

    def charge(arm, s):
        compute["by_arm_s"][arm] = round(compute["by_arm_s"].get(arm, 0.0) + float(s or 0.0), 3)

    for k in keys:
        r = by_key.get(k)
        if r is None:
            continue
        if (r.get("diagnosis") or {}).get("class") == "RUN_ERROR" or "path_class" not in r:
            problems.append(f"{k}: RUN_ERROR {r.get('error')}")
            continue
        compute["total_s"] += r["seconds"]
        need(r["restored"] is True, f"{k}: engine state not restored")
        train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in bundle[k]["train"]]
        tests = [np.asarray(p["input"], dtype=int) for p in bundle[k]["test"]]
        # reproducible construction
        raw, digest = M.read_instances(os.path.join(OUT, "instances2"), k)
        need(digest == r["evidence"]["sha256"], f"{k}: evidence digest")
        fc = CN.propose(raw)
        need([p["ext"]["name"] for p in fc["proposals"]] == [p["name"] for p in r["fc"]["proposals"]],
             f"{k}: FC construction not reproduced")
        demo = M.demo_only_propose(train)
        need([p["ext"]["name"] for p in demo["proposals"]]
             == [p["name"] for p in r["control_proposals"]["DEMO_ONLY"]["proposals"]],
             f"{k}: DEMO_ONLY construction not reproduced")
        donor = keys[(keys.index(k) + 1) % len(keys)]
        need(r["control_proposals"]["SHUFFLED_FAILURE"]["donor"] == donor, f"{k}: donor")
        shuf = CN.propose(M.read_instances(os.path.join(OUT, "instances2"), donor)[0])
        need([p["ext"]["name"] for p in shuf["proposals"]]
             == [p["name"] for p in r["control_proposals"]["SHUFFLED_FAILURE"]["proposals"]],
             f"{k}: SHUFFLED construction not reproduced")
        any_prop = bool(fc["proposals"] or demo["proposals"] or shuf["proposals"])
        need(("kalone" in r) == any_prop, f"{k}: KALONE ran {'kalone' in r}, any proposal {any_prop}")
        if "kalone" in r:
            need(r["kalone"]["budget_s"] == M.BUDGET_S and r["kalone"]["installed"] is None, f"{k}: KALONE arm")
            charge("kalone", r["kalone"]["seconds"])
        for arm, prop in (("DEMO_ONLY", demo), ("SHUFFLED_FAILURE", shuf)):
            c = r["controls"][arm]
            need((c["class"] == "INSTALLED") == (bool(prop["proposals"]) and any_prop), f"{k}: {arm} class")
            if c["class"] == "INSTALLED":
                need(c["selected"] == prop["proposals"][0]["ext"]["name"], f"{k}: {arm} selection")
                fc_name = fc["proposals"][0]["ext"]["name"] if fc["proposals"] else None
                need(c["same_as_fc"] == (c["selected"] == fc_name), f"{k}: {arm} same_as_fc")
                need(c["with_e"].get("restored") is True, f"{k}: {arm} not restored")
                need(c["with_e"]["uses"] == bool(c["with_e"]["accepted"] and c["with_e"]["uses"]), f"{k}: {arm} uses")
                charge(arm, c["with_e"]["seconds"])
        cen = census.get(k, {})
        layers = cen.get("layers") or {}
        f = {"A_native_baseline_failure": (cen.get("diagnosis") or {}).get("class") != "NATIVE_CERTIFIED"
             and ("kalone" not in r or not r["kalone"]["accepted"]),
             "A_detail": {"census_class": (cen.get("diagnosis") or {}).get("class"),
                          "harness_solved_layers": [n for n in ("pipeline", "geocat", "object")
                                                    if (layers.get(n) or {}).get("solved")],
                          "kalone_accepted": r["kalone"]["accepted"] if "kalone" in r else None},
             "B_usable_failure_evidence": r["evidence"]["with_grid"] > 0,
             "C_proposal": bool(fc["proposals"])}
        for x in ("D_canonical_extension", "E_compilation", "F_installation", "G_accepted_program",
                  "H_uses_extension", "I_exact_replay", "J_deterministic", "K_adaptive_loo",
                  "L_bounded_separation", "M_support", "N_activation"):
            f[x] = False
        f["path_class"] = r["path_class"]
        funnel_rows[k] = f
        if not fc["proposals"]:
            need(r["path_class"] == "NO_PROPOSAL" and not r["activated"], f"{k}: class without a proposal")
            continue
        # gates from their run records
        g, e = r["gates"], r["extension"]
        need(e["name"] == fc["proposals"][0]["ext"]["name"], f"{k}: selected extension")
        canon = GE.serialize(GE.make(e["family"], e["params"])) == GE.serialize(e)
        need(g["compile"] == (canon and GE.load(GE.serialize(e)) == e), f"{k}: compile gate")
        f["D_canonical_extension"], f["E_compilation"] = canon, g["compile"]
        if not g["compile"]:
            continue
        w1, w2 = r["with_e"], r["with_e_repeat"]
        need(w1["installed"] == e["name"] and w1["budget_s"] == M.BUDGET_S, f"{k}: K + e arm")
        need(w1.get("restored") is True and w2.get("restored") is True, f"{k}: K + e not restored")
        need(r["progression"]["install"] == (w1.get("restored") is True), f"{k}: install stage")
        need(g["accepted"] == bool(w1["accepted"]), f"{k}: accepted gate")
        need(g["uses"] == bool(w1.get("uses")), f"{k}: uses gate")
        need(g["replay"] == bool(w1.get("replays_training")), f"{k}: replay gate")
        need(g["attribution"] == bool(w1.get("direct_equals_engine")), f"{k}: attribution gate")
        need(g["prediction"] == (bool(w1["accepted"]) and all(p is not None for p in w1["predictions"])),
             f"{k}: prediction gate")
        need(g["determinism"] == (w1["accepted"] == w2["accepted"] and w1["program_sha"] == w2["program_sha"]
                                  and w1["predictions"] == w2["predictions"]), f"{k}: determinism gate")
        folds = r["loo"]["folds"]
        need([fo["fold"] for fo in folds] == list(range(len(train))), f"{k}: fold indices")
        for fo in folds:
            if fo["class"] == "SUCCESS":
                need(fo["accepted"] and fo["uses"] and fo["heldout_exact"], f"{k}: fold {fo['fold']} SUCCESS fields")
            elif fo["class"] == "LOO_FAILURE":
                need(fo["selected"] is not None and not (fo["accepted"] and fo["uses"] and fo["heldout_exact"]),
                     f"{k}: fold {fo['fold']} LOO_FAILURE fields")
            elif fo["class"] == "NO_PROPOSAL":
                need(fo.get("proposals") == [] and fo["selected"] is None, f"{k}: fold {fo['fold']} NO_PROPOSAL")
            elif fo["class"] == "RESOURCE_EXHAUSTED":
                need(fo.get("extract_seconds", 0) >= M.EXTRACT_CAP_S - 5, f"{k}: fold {fo['fold']} cap")
            else:
                problems.append(f"{k}: fold class {fo['class']}")
            if fo.get("selected") is not None:
                need(fo.get("restored") is True, f"{k}: fold {fo['fold']} not restored")
            charge("loo_extract", fo.get("extract_seconds"))
            charge("loo_engine", fo.get("engine_seconds"))
        loo_ok = bool(folds) and all(fo["class"] == "SUCCESS" for fo in folds)
        need(g["loo"] == loo_ok == r["loo"]["passed"], f"{k}: loo gate")
        others = r["pool"]["others"]
        need(r["pool"]["size"] == len(fc["proposals"]), f"{k}: pool size")
        if w1["accepted"]:
            need(others is not None and len(others) == len(fc["proposals"]) - 1, f"{k}: pool members")
            need(g["unanimity"] == (g["prediction"] and all(m["predictions"] == w1["predictions"] for m in others)),
                 f"{k}: unanimity gate")
        else:
            need(g["unanimity"] is False, f"{k}: unanimity without acceptance")
        need(g["support"] == bool((w1.get("support") or {}).get("ok")), f"{k}: support gate")
        if w1["accepted"] and w1.get("support"):
            s = w1["support"]
            need(s["ok"] == (s["insufficient_count"] == 0), f"{k}: support verdict")
            need(len(s["e_cells_per_test"]) == len(tests), f"{k}: support per test")
        # removed and matched
        rem, mat, kal = r["removed"], r["matched"], r["kalone"]
        need(rem["installed"] is None and rem["budget_s"] == M.BUDGET_S, f"{k}: REMOVED arm")
        spent = float(inst_rows.get(k, {}).get("seconds") or 0.0) + float(r["fc"]["seconds"] or 0.0) + float(w1["seconds"])
        need(abs(mat["budget_s"] - round(clamp(spent, M.MATCHED_MIN_S, M.MATCHED_MAX_S), 2)) < 0.02,
             f"{k}: matched budget {mat['budget_s']} vs {spent}")
        need(r["unchanged_baseline"] == (rem["accepted"] == kal["accepted"] and rem["program_sha"] == kal["program_sha"]
                                         and rem["predictions"] == kal["predictions"]), f"{k}: unchanged baseline")
        # separation
        sep = r["separation"]
        need(sep["non_composition_bounded"] == (not kal["accepted"] and not mat["accepted"]), f"{k}: separation iii")
        need(sep["non_caching"] == all(isinstance(v, (bool, int, str)) for v in e["params"].values()),
             f"{k}: separation ii")
        import geocat_arc.object_reasoning.correspondence as CO
        modes = []
        for i in raw:
            if str(i.get("variant")) != fc["proposals"][0]["variant"] or i.get("grid") is None:
                continue
            in_cc = {tuple(c): col for c, col in i["in"]}
            out_cc = {tuple(c): col for c, col in i["out"]}
            added = {c: col for c, col in out_cc.items() if c not in in_cc}
            if not added or len(set(added.values())) != 1:
                continue
            res = CO.detect_grow(in_cc, out_cc, tuple(i["bounds"]), np.asarray(i["grid"]))
            modes.append((res or {}).get("mode"))
            if len(modes) >= CN.MAX_INSTANCES:
                break
        need(sep["non_renaming"] == (bool(modes) and all(m == "pattern" for m in modes)), f"{k}: separation i")
        need(sep["separated"] == (sep["non_renaming"] and sep["non_caching"] and sep["non_composition_bounded"]),
             f"{k}: separation verdict")
        # classes
        failed = [cls for gate, cls in M.GATES if not g.get(gate)]
        need(r["path_class"] == (failed[0] if failed else "ACTIVATED"), f"{k}: path class")
        need(r["activated"] == (not failed), f"{k}: activation")
        for arm, s in (("with_e", w1["seconds"]), ("with_e_repeat", w2["seconds"]), ("removed", rem["seconds"]),
                       ("matched", mat["seconds"])):
            charge(arm, s)
        f.update({"F_installation": r["progression"]["install"], "G_accepted_program": g["accepted"],
                  "H_uses_extension": g["uses"], "I_exact_replay": g["replay"], "J_deterministic": g["determinism"],
                  "K_adaptive_loo": g["loo"], "L_bounded_separation": sep["separated"], "M_support": g["support"],
                  "N_activation": r["activated"]})
        f["conditions_1_to_5"] = bool(f["A_native_baseline_failure"] and f["C_proposal"] and g["compile"]
                                      and f["F_installation"] and sep["separated"] and g["loo"])

    stages = ("A_native_baseline_failure", "B_usable_failure_evidence", "C_proposal", "D_canonical_extension",
              "E_compilation", "F_installation", "G_accepted_program", "H_uses_extension", "I_exact_replay",
              "J_deterministic", "K_adaptive_loo", "L_bounded_separation", "M_support", "N_activation")
    funnel = {s: sum(1 for v in funnel_rows.values() if v[s]) for s in stages}
    compute["total_s"] = round(compute["total_s"], 1)
    verdict = {"verified": not problems, "problems": problems, "notes": notes, "rows": len(lines),
               "manifest_sha256": sha(MANIFEST), "manifest_head": manifest["head"], "freeze_commit": FREEZE_COMMIT,
               "run_head": start["head"], "run_start_utc": start["first_start_utc"],
               "isolation_logs": len(logs), "funnel": funnel, "compute": compute,
               "saved_baseline": {"commit": BASELINE_COMMIT, "installed": 0, "activated": 0}}
    os.makedirs(LOG, exist_ok=True)
    with open(os.path.join(LOG, "verify_measure.json"), "w") as handle:
        json.dump(verdict, handle, indent=1, sort_keys=True)
    with open(os.path.join(OUT, "measure_funnel.json"), "w") as handle:
        json.dump({"funnel": funnel, "per_task": funnel_rows}, handle, indent=1, sort_keys=True)
    print(json.dumps({k: verdict[k] for k in ("verified", "rows", "funnel", "problems")}, indent=1))


if __name__ == "__main__":
    main()
