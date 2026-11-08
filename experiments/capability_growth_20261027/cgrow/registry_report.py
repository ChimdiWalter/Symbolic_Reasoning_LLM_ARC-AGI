"""CAPABILITY_REGISTRY.md from registry/testI_<arm>.json (system-side registries) plus evaluator annotations
(agreement with the removed reference and kind, from runs/<eval>/results.json), kept in separate columns.

    python -m cgrow.registry_report EVAL_ID > CAPABILITY_REGISTRY.md
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, registry as RG       # noqa: E402


def main(eval_id):
    res = {}
    rp = os.path.join(P.RUNS, eval_id, "results.json")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as f:
            res = json.load(f)
    ops = res.get("ops", {})
    lines = ["# Capability registry (Test I)", "",
             "System-side registries: `registry/testI_C2.json`, `testI_C3.json`, `testI_C5.json` (schema "
             "`REGISTRY_SCHEMA.json`). Every entry is INVENTED, level operation, substrate gridfn2_sandbox. The last "
             "two columns are evaluator-only annotations (never read by the system).", ""]
    for arm in ("C2", "C3", "C5"):
        path = os.path.join(P.REGISTRY_DIR, f"testI_{arm}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        errs = RG.validate(doc)
        st = collections.Counter(e["status"] for e in doc["entries"])
        lines.append(f"## {arm}: {len(doc['entries'])} entries ({', '.join(f'{k} {v}' for k, v in sorted(st.items()))}); "
                     f"{len(doc['versions'])} grammar versions; schema check: {'pass' if not errs else errs[:3]}")
        lines.append("")
        lines.append("| id | status | scope | motivating task | regression | validation (first new fit) | "
                     "reference agreement (evaluator) | kind (evaluator) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for e in doc["entries"]:
            v = e.get("validation") or {}
            reg = v.get("regression") or {}
            hv = v.get("held_out") or {}
            fnf = (hv.get("first_new_fit") or {}).get("task") if isinstance(hv, dict) else None
            o = ops.get(e["implementation"]["sha256"], {})
            lines.append(f"| {e['id']} | {e['status']} | {e['scope']} | {', '.join(e['provenance'].get('motivating_tasks', []))} "
                         f"| lost {len(reg.get('lost_fit', []))}, changed {len(reg.get('changed_prediction', []))} "
                         f"of {reg.get('checked')} | {fnf or '-'} | {o.get('ref_agreement', '-')} | {o.get('kind', '-')} |")
        lines.append("")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "eval_v1")
