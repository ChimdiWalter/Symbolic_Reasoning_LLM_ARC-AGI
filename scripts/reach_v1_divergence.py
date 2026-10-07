"""Leave-one-out divergence by structural signature (corrects the census
STRUCT/PARAM split, which treated learned-table string keys as structure).

  python scripts/reach_v1_divergence.py   -> outputs/reach_v1/divergence.json

Signature of a program: its class, its segmentation, and per rule the
action's delta type, the growth mode when present, and the selector's
feature names; every literal value (numbers, colours, offsets, table
entries, hashes) is ignored. Per DE_LOO task, from census_programs/:
  SAME_SIGNATURE   every failed fold re-derives the reference signature
                   (values differ: a fitted-value instability)
  FEWER_RULES      some fold has a strict subset of the reference rules
                   (a rule witnessed only by the held-out pair)
  OTHER_SIGNATURE  otherwise
  NOFOLD           some failed fold derived no program
Also counts the reference programs' growth modes and parameter classes.
"""
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs", "reach_v1")


def _const_arg(expr):
    if isinstance(expr, dict) and expr.get("op") == "const" and expr.get("args"):
        return expr["args"][0]
    return None


def _features(sel):
    out = set()

    def walk(v):
        if isinstance(v, dict):
            if v.get("op") == "test" and v.get("args"):
                out.add(str(v["args"][0]))
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(sel)
    return tuple(sorted(out))


def rule_sig(r):
    act = r.get("action") or {}
    mode = _const_arg((act.get("params") or {}).get("mode"))
    return (act.get("delta_type"), mode if isinstance(mode, str) else None, _features(r.get("selector")))


def signature(d):
    if not isinstance(d, dict):
        return None
    if d.get("program_class") in ("framed",) and isinstance(d.get("inner"), dict):
        return ("framed",) + signature(d["inner"])
    rules = d.get("rules")
    if isinstance(rules, list):
        return (d.get("program_class", "object"), d.get("segmentation_variant"),
                tuple(sorted(rule_sig(r) for r in rules)))
    return (d.get("program_class", "object"), d.get("mode"), tuple(sorted(k for k in (d.get("params") or {}))))


def main():
    rows = {json.loads(l)["key"]: json.loads(l) for l in open(os.path.join(OUT, "census_rows.jsonl")) if l.strip()}
    classes, modes, pclasses, per_rule_objects = Counter(), Counter(), Counter(), Counter()
    for key, r in sorted(rows.items()):
        if (r.get("diagnosis") or {}).get("class") != "DE_LOO":
            continue
        path = os.path.join(OUT, "census_programs", f"{key}.json")
        if not os.path.exists(path):
            classes["NO_PROGRAM_FILE"] += 1
            continue
        p = json.load(open(path))
        ref = p.get("identity_program") or p.get("near_solve_partial")
        rs = signature(ref)
        for rule in (ref or {}).get("rules") or []:
            act = rule.get("action") or {}
            mode = _const_arg((act.get("params") or {}).get("mode"))
            modes[f"{act.get('delta_type')}:{mode if isinstance(mode, str) else '-'}"] += 1
            pclasses[act.get("parameter_class")] += 1
        if not (ref or {}).get("rules"):
            modes[f"{(ref or {}).get('program_class', 'none')}:{(ref or {}).get('mode', '-')}"] += 1
        for n in (r.get("near_solve") or {}).get("objects_explained") or []:
            per_rule_objects[n] += 1
        cls = "SAME_SIGNATURE"
        for dv in p.get("loo_divergence") or []:
            fp = dv.get("fold_program")
            if fp is None:
                cls = "NOFOLD"
                break
            fs = signature(fp)
            if fs == rs:
                continue
            if rs and fs and rs[:2] == fs[:2] and isinstance(rs[2], tuple) and set(fs[2]) < set(rs[2]):
                cls = "FEWER_RULES" if cls == "SAME_SIGNATURE" else cls
            else:
                cls = "OTHER_SIGNATURE"
        classes[cls] += 1
    out = {"de_loo_tasks": sum(classes.values()), "divergence": dict(classes),
           "reference_rule_modes": dict(modes.most_common()), "reference_parameter_classes": dict(pclasses),
           "objects_explained_per_rule": dict(sorted(per_rule_objects.items(), key=lambda kv: str(kv[0])))}
    with open(os.path.join(OUT, "divergence.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
