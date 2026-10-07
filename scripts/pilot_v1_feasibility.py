"""Real ARC pilot v1: static feasibility from the development dry run
(protocol section 12; the rule was committed in f47c795 before the run).

  python scripts/pilot_v1_feasibility.py   -> outputs/pilot_v1_dev/feasibility.json

Reads the development rows and isolation logs only (reasoner side; nothing
is scored and no target exists for these runs).
"""
from __future__ import annotations

import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_pilot import bundle as B                                  # noqa: E402
from cora_pilot import isolation as ISO                             # noqa: E402

OUT = os.path.join(HERE, "outputs", "pilot_v1_dev")
LOG = os.path.join(HERE, "logs", "pilot_v1_dev")
DEV_NATIVE = 6
WORKERS = 4
TARGET_ACTIVATIONS = 4


def rows(name):
    path = os.path.join(OUT, f"{name}_rows.jsonl")
    out = {}
    if os.path.exists(path):
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                out[r["key"]] = r
    return out


def stats(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    if not xs:
        return None
    return {"n": len(xs), "mean": round(statistics.mean(xs), 1), "median": round(statistics.median(xs), 1),
            "max": round(max(xs), 1), "sum": round(sum(xs), 1)}


def count(values):
    out = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


def choose_n(a, dev_size=B.DEV_SIZE):
    """Protocol section 12: the smallest allowed N with N x a / 60 >= 4; 120
    when a = 0 or no allowed value reaches 4."""
    for n in B.ALLOWED_N:
        if a and n * a / dev_size >= TARGET_ACTIVATIONS:
            return n
    return max(B.ALLOWED_N)


def main():
    cora, nat = rows("cora"), rows("native")
    iso = {}
    for f in sorted(os.listdir(LOG)):
        if f.startswith("isolation_") and f.endswith(".json"):
            iso[f] = ISO.audit_log(json.load(open(os.path.join(LOG, f))))
    installed = [k for k, r in cora.items() if "with_e" in r]
    compiled = [k for k, r in cora.items() if (r.get("gates") or {}).get("compile")]
    activated = [k for k, r in cora.items() if r.get("activated")]
    gates = {}
    for r in cora.values():
        for g, v in (r.get("gates") or {}).items():
            gates.setdefault(g, {"true": 0, "false": 0})["true" if v else "false"] += 1
    controls = {arm: count(((r.get("controls") or {}).get(arm) or {}).get("class") for r in cora.values())
                for arm in ("DEMO_ONLY", "SHUFFLED_FRONTIER")}
    ctrl_installed = {arm: sum(1 for r in cora.values() if ((r.get("controls") or {}).get(arm) or {}).get("with_e"))
                      for arm in ("DEMO_ONLY", "SHUFFLED_FRONTIER")}
    run_errors = [k for k, r in list(cora.items()) + list(nat.items()) if r.get("path_class") == "RUN_ERROR"]
    ready = {
        "isolation_clean": not any(iso.values()) and len(iso) == 2 * WORKERS,
        "cora_complete": len(cora) == B.DEV_SIZE,
        "native_complete": len(nat) == DEV_NATIVE,
        "no_run_error": not run_errors,
        "loop_operable": len(installed) >= 1,
    }
    a = len(activated)
    n = choose_n(a)
    nat_s = stats([r.get("seconds") for r in nat.values()])
    cora_s = stats([r.get("seconds") for r in cora.values()])
    projected = None
    if nat_s and cora_s:
        projected = round((n * nat_s["mean"] + n * cora_s["mean"]) / WORKERS / 60, 1)
    out = {"ready": ready, "READY": all(ready.values()), "activations": a, "installed": len(installed),
           "compiled": len(compiled), "n_rule": {"a": a, "dev": B.DEV_SIZE, "target": TARGET_ACTIVATIONS, "N": n,
                                                 "expected_activations_at_N": round(n * a / B.DEV_SIZE, 2)},
           "path_classes": count(r.get("path_class") for r in cora.values()),
           "fc_classes": count((r.get("fc") or {}).get("class") for r in cora.values()),
           "k_classes": count((r.get("fc") or {}).get("k_class") for r in cora.values()),
           "partial_tops": count((r.get("fc") or {}).get("partial_tops") for r in cora.values()),
           "selection_levels": count((r.get("fc") or {}).get("level") for r in cora.values() if r.get("fc", {}).get("level")),
           "kstar_prime_alone_accepted": sum(1 for r in cora.values() if (r.get("kstar_prime_alone") or {}).get("accepted")),
           "gates": gates, "controls": controls, "controls_installed": ctrl_installed,
           "by_stratum": {}, "run_errors": run_errors,
           "isolation_problems": {k: v for k, v in iso.items() if v},
           "seconds": {"cora": cora_s, "native": nat_s,
                       "native_layers": {ly: stats([(r.get("layer_seconds") or {}).get(ly) for r in nat.values()])
                                         for ly in ("pipeline", "geocat", "object")}},
           "native": {"claimed": sum(1 for r in nat.values() if r.get("claimed")),
                      "attempt_1": sum(1 for r in nat.values() if any(x is not None for x in r.get("attempt_1") or [])),
                      "attempt_2": sum(1 for r in nat.values() if any(x is not None for x in r.get("attempt_2") or [])),
                      "errors": count(e for r in nat.values() for e in (r.get("errors") or {}).values() if e)},
           "projected_pilot_minutes_at_N": projected}
    bundle = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))
    for k, r in cora.items():
        nt = len(bundle["tasks"][k]["train"])
        s = "n3" if nt == 3 else ("n4" if nt == 4 else "n5p")
        d = out["by_stratum"].setdefault(s, {"tasks": 0, "installed": 0, "activated": 0})
        d["tasks"] += 1
        d["installed"] += int("with_e" in r)
        d["activated"] += int(bool(r.get("activated")))
    with open(os.path.join(OUT, "feasibility.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("READY", "ready", "activations", "installed", "compiled", "n_rule",
                                          "path_classes", "fc_classes", "projected_pilot_minutes_at_N")},
                     sort_keys=True, indent=1))


if __name__ == "__main__":
    main()
