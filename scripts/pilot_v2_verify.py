"""Terminal verifier for the real ARC growth-repair pilot v2 (written before
any pilot run).

  python scripts/pilot_v2_verify.py      -> logs/pilot_v2/verify_pilot.json

Recomputes from the committed artifacts, the pinned solutions and the pinned
sealed record with its OWN scoring code (it does not call
cora_pilot2.evaluator's scoring), and checks the evaluator's report against
it. Exit code 0 only when every check passes.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
OUT = os.path.join(HERE, "outputs", "pilot_v2")
LOG = os.path.join(HERE, "logs", "pilot_v2")
BUNDLE = os.path.join(HERE, "records", "pilot_v2", "pilot_bundle.json")
KEYMAP = os.path.join(HERE, "records", "pilot_v2_evaluator", "pilot_keymap.json")
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append({"check": name, "pass": bool(ok), "detail": detail if not ok else ""})


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha(path):
    with open(path, "rb") as handle:
        return sha_bytes(handle.read())


def rows(path):
    out, dup = {}, []
    with open(path) as handle:
        for line in handle:
            if line.strip():
                r = json.loads(line)
                if r["key"] in out:
                    dup.append(r["key"])
                out[r["key"]] = r
    return out, dup


def same(p, t):
    return p is not None and p == t


def every(preds, targets):
    return isinstance(preds, list) and len(preds) == len(targets) and all(same(p, t) for p, t in zip(preds, targets))


def solved2(att, targets):
    return isinstance(att, list) and len(att) == len(targets) and all(
        any(same(a, t) for a in (pair or [])) for pair, t in zip(att, targets))


def independent_outcome(p, r, tg, in_sealed):
    """(native solved, causal witness, invention witness, outcome) for one
    task, recomputed here."""
    g = r.get("gates") or {}
    n = len(tg)
    na = [[(p["native"]["attempt_1"] or [None] * n)[i], (p["native"]["attempt_2"] or [None] * n)[i]]
          for i in range(n)]
    native_ok = solved2(na, tg)
    act = bool(p["activated"])
    T = act and every(p["cora_prediction"], tg)
    A = not every(p["removed"], tg) and not every(p["matched"], tg)
    B_ = not native_ok and not in_sealed
    P_ = bool((r.get("fc") or {}).get("proposals")) and bool(g.get("compile"))
    U = bool(g.get("accepted")) and bool(g.get("uses")) and bool(g.get("attribution"))
    L_ = bool(g.get("loo"))
    S = bool((r.get("separation") or {}).get("separated"))
    F = not any(every(v, tg) for v in (p.get("controls") or {}).values())
    alone, rem = r.get("kalone") or {}, r.get("removed") or {}
    integ = (bool(g.get("determinism")) and bool(g.get("replay")) and bool(g.get("attribution"))
             and bool(r.get("restored"))
             and all(rem.get(x) == alone.get(x) for x in ("accepted", "program_sha", "predictions")))
    wit = act and B_ and P_ and U and L_ and T and A and integ
    inv = wit and S and F
    if act and not T:
        o = "WRONG_ACTIVATION"
    elif native_ok or in_sealed:
        o = "BASELINE_ALREADY_SOLVES"
    elif act and not A:
        o = "ABLATION_FAILURE"
    elif act:
        o = "CORRECT_CAUSAL_RESCUE" if wit else "INTEGRITY_FAILURE"
    elif p["cora_with_e"] is not None and any(x is not None for x in p["cora_with_e"]):
        o = "MISSED_RESCUE" if every(p["cora_with_e"], tg) else "HELDOUT_MISMATCH"
    else:
        o = "NO_CHANGE"
    return native_ok, wit, inv, o


def main():
    import freeze_pilot_v2 as FZ
    import pilot_v2_run as RUN
    from cora_pilot import isolation as ISO
    from cora_pilot import bundle as B
    from cora_pilot import evaluator as EV1
    from cora_pilot2 import reasoner as RS
    from cora_reach import measure as M
    fz = FZ.freeze_problems("evaluator")
    check("freeze intact (evaluator role)", fz == [], str(fz))
    man = json.load(open(FZ.MANIFEST))
    commit = json.load(open(os.path.join(LOG, "predictions_commit.json")))["commit"]
    check("reasoner marker names the commit",
          open(os.path.join(HERE, "logs", "PILOT_V2_REASONER_DONE")).read().strip() == commit)
    for name in ("committed_predictions.json", "reasoner_record.json", "native_rows.jsonl", "instances_rows.jsonl",
                 "cora_rows.jsonl"):
        blob = subprocess.run(["git", "show", f"{commit}:outputs/pilot_v2/{name}"], cwd=HERE,
                              capture_output=True).stdout
        check(f"committed {name} equals disk", sha_bytes(blob) == sha(os.path.join(OUT, name)))
    start = json.load(open(os.path.join(LOG, "start.json")))
    check("start record bundle hash", start["bundle_sha256"] == sha(BUNDLE))
    bundle = json.load(open(BUNDLE))
    keys = sorted(bundle["tasks"])
    check("bundle keys equal the manifest", keys == man["pilot"]["keys"])
    check("no development task in the pilot",
          not ({json.load(open(KEYMAP))["keys"][k]["task_id"] for k in keys}
               & set(json.load(open(os.path.join(HERE, "records", "pilot_v1", "selection.json")))["dev"])))
    problems = {}
    for ph in RUN.PHASES:
        for w in range(RUN.WORKERS):
            path = os.path.join(LOG, f"isolation_{ph}_{w}.json")
            problems[f"{ph}_{w}"] = ISO.audit_log(json.load(open(path))) if os.path.exists(path) else ["missing"]
    check("isolation: no refused access, every log present", not any(problems.values()),
          json.dumps({k: v for k, v in problems.items() if v})[:500])
    nat, dn = rows(os.path.join(OUT, "native_rows.jsonl"))
    ins, di = rows(os.path.join(OUT, "instances_rows.jsonl"))
    cor, dc = rows(os.path.join(OUT, "cora_rows.jsonl"))
    check("one row per key in every phase",
          sorted(nat) == keys and sorted(ins) == keys and sorted(cor) == keys and not (dn or di or dc),
          f"native {len(nat)} instances {len(ins)} cora {len(cor)} dup {dn + di + dc}")
    for k in keys:
        path = os.path.join(OUT, "instances", f"{k}.json")
        if not os.path.exists(path) or (cor[k].get("evidence") or {}).get("sha256") not in (sha(path), None):
            check(f"{k}: evidence file matches the CORA row", False)
    committed = json.load(open(os.path.join(OUT, "committed_predictions.json")))
    check("committed predictions recompose from the rows", RS.compose(bundle["tasks"], nat, cor) == committed)
    bad = []
    for k, r in cor.items():
        g = r.get("gates") or {}
        if r.get("path_class") == "RUN_ERROR":
            continue
        if r.get("activated") != (r.get("path_class") == "ACTIVATED"):
            bad.append(k)
        if g.get("compile"):
            failed = [cls for gate, cls in M.GATES if not g.get(gate)]
            if r.get("path_class") != (failed[0] if failed else "ACTIVATED"):
                bad.append(k)
        if r.get("activated") and committed[k]["cora_prediction"] != (r.get("with_e") or {}).get("predictions"):
            bad.append(k)
        if r.get("control_proposals", {}).get("SHUFFLED_FAILURE", {}).get("donor") != RS.donor(keys, k):
            bad.append(k)
    check("activation equals the frozen gate order; donors", not bad, str(bad[:5]))
    keymap = json.load(open(KEYMAP))
    sol = json.loads(open(B.SOLUTIONS, "rb").read())
    check("solutions hash", sha(B.SOLUTIONS) == B.SOLUTIONS_SHA256)
    sealed_a = json.load(open(EV1.SEALED_V23))
    sealed_b = json.load(open(EV1.SEALED_ARB))
    sealed = {r["task_id"] for r in sealed_a["solved"]} | {r["task_id"] for r in sealed_b["solved"]}
    check("sealed record is 185 and pinned", len(sealed) == 185 and sha(EV1.SEALED_V23) == EV1.SEALED_V23_SHA256
          and sha(EV1.SEALED_ARB) == EV1.SEALED_ARB_SHA256)
    report = json.load(open(os.path.join(OUT, "pilot_report.json")))
    mine = {}
    for k in keys:
        tid = keymap["keys"][k]["task_id"]
        tg = sol[tid]
        native_ok, wit, inv, o = independent_outcome(committed[k], cor[k], tg, tid in sealed)
        mine[k] = {"witness": wit, "invention": inv, "outcome": o, "native": native_ok,
                   "system": solved2(committed[k]["system"], tg)}
    rt = report.get("tasks") or {}
    diff = [k for k in keys if (rt.get(k) or {}).get("outcome") != mine[k]["outcome"]
            or (rt.get(k) or {}).get("witness") != mine[k]["witness"]
            or (rt.get(k) or {}).get("invention_witness") != mine[k]["invention"]]
    check("per-task outcomes, witnesses and invention witnesses recomputed", not diff, str(diff[:5]))
    wit = sorted(k for k in keys if mine[k]["witness"])
    inv = sorted(k for k in keys if mine[k]["invention"])
    s = report.get("summary") or {}
    net = sum(m["system"] for m in mine.values()) - sum(m["native"] for m in mine.values())
    check("summary witnesses, invention witnesses and net score",
          s.get("witness_keys") == wit and s.get("invention_witness_keys") == inv and s.get("net_score") == net,
          f"{s.get('witness_keys')} vs {wit}; {s.get('invention_witness_keys')} vs {inv}; {s.get('net_score')} vs {net}")
    leak = any(problems.values())
    errs = sum(1 for r in cor.values() if r.get("path_class") == "RUN_ERROR") + sum(
        1 for r in nat.values() if r.get("path_class") == "RUN_ERROR")
    label = ("PILOT_LEAKAGE" if leak else "NO_VERDICT_RUN_ERROR" if errs > 0.10 * len(keys)
             else "REAL_ARC_INVENTION_WITNESS_ESTABLISHED" if inv
             else "REAL_ARC_CAUSAL_WITNESS_ESTABLISHED" if wit else "NO_REAL_ARC_WITNESS")
    check("outcome label recomputed", report.get("outcome") == label, f"{report.get('outcome')} vs {label}")
    marker = open(os.path.join(HERE, "logs", "PILOT_V2_DONE")).read().split()
    check("evaluator marker names the report", marker[0] == report.get("outcome")
          and marker[1] == sha(os.path.join(OUT, "pilot_report.json")))
    out = {"checks": CHECKS, "passed": sum(c["pass"] for c in CHECKS), "total": len(CHECKS),
           "label": label, "witnesses": wit, "invention_witnesses": inv}
    with open(os.path.join(LOG, "verify_pilot.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(f"{out['passed']}/{out['total']} checks pass; label {label}; witnesses {len(wit)}; "
          f"invention witnesses {len(inv)}")
    sys.exit(0 if out["passed"] == out["total"] else 1)


if __name__ == "__main__":
    main()
