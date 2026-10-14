"""SHADOW answer-arbitration study on saved development predictions.
Native v23 is not modified and nothing is rerun.

  python -m cora_funnel.arbitration_shadow --corpus dev60
      -> outputs/funnel_v0/arbitration_shadow_<corpus>.json

Inputs, all saved:
- the whole-harness run (`harness_run.py`, or the ceiling test's arm A for
  c2dev), per task:
  - the layers that claimed it;
  - attempt_1, the first claiming layer's render (pipeline, then geocat,
    then object);
  - attempt_2, the object layer's uncertified partial, which the notebook
    fills with attempt_1 when absent;
- the funnel run of the same native object layer, per task:
  - its LOO-certified render;
  - its rank-1 train-exact candidate (uncertified).

Every policy decides from these inference-time fields only. Answers are
read by the scorer, after the decisions.

| policy | attempt_1 | attempt_2 |
|---|---|---|
| A frozen | first claimer (as submitted) | object partial, else a copy of attempt_1 |
| B object-certificate-first | object certified render if any, else as A | the A attempt_1 if different, else as A |
| C pipeline-first, conservative override | as A (never displaced) | object certified render when it differs from attempt_1, else as A |
| D complementarity | as A | first of [object certified render, A attempt_2, object rank-1 candidate] that differs from attempt_1, else as A |

The object certificate is evidence, not a guarantee. These policies are
answer arbitration, an inference/engineering change, not capability
construction.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "funnel_v0")
SOURCES = {"dev60": (os.path.join(OUT, "harness_dev60", "working"), os.path.join(OUT, "rows_dev60_native.jsonl")),
           "c2dev": (os.path.join(HERE, "outputs", "hybrid_c2_dev", "A_native", "working"), os.path.join(OUT, "rows_c2dev_native.jsonl"))}


def inference_view(corpus):
    """Per task, the fields a policy may use (no answers)."""
    work, rows_path = SOURCES[corpus]
    sub = json.load(open(os.path.join(work, "submission.json")))
    prog = {json.loads(l)["task_id"]: json.loads(l) for l in open(os.path.join(work, "run", "progress.jsonl"))}
    rows = {json.loads(l)["key"]: json.loads(l) for l in open(rows_path)}
    view = {}
    for k, ent in sub.items():
        r, f = prog.get(k, {}), rows.get(k)
        claims = "".join(c if bool((r.get(n) or {}).get("solved")) else "-" for c, n in (("P", "pipeline"), ("G", "geocat"), ("O", "object")))
        obj_cert = f["predictions"] if f and f["solved"] and f.get("predictions") else None
        first = next((e for e in (f["events"] if f else []) if e["type"] == "search" and e["frame"] == 0 and e["n_programs"] > 0), None)
        rank1 = None
        if first and first.get("outputs"):
            i = first["rank"][0] if first.get("rank") else 0
            rank1 = first["outputs"][i] if i < len(first["outputs"]) else None
        view[k] = {"a1": [e["attempt_1"] for e in ent], "a2": [e["attempt_2"] for e in ent], "claims": claims,
                   "a1_source": (r.get("predictions") or {}).get("attempt_1_source"), "obj_cert": obj_cert, "obj_rank1": rank1,
                   "harness_object_certified": "O" in claims, "funnel_object_certified": bool(f and f["solved"])}
    return view


def policy(name, v):
    a1, a2 = v["a1"], v["a2"]
    if name == "A":
        return a1, a2, v["a1_source"] or "none"
    if name == "B":
        if v["obj_cert"] is not None:
            return v["obj_cert"], (a1 if a1 != v["obj_cert"] else a2), "object_certified"
        return a1, a2, v["a1_source"] or "none"
    if name == "C":
        if v["obj_cert"] is not None and v["obj_cert"] != a1:
            return a1, v["obj_cert"], (v["a1_source"] or "none") + "+object_certified_as_attempt_2"
        return a1, a2, v["a1_source"] or "none"
    if name == "D":
        for alt, tag in ((v["obj_cert"], "object_certified"), (a2, "object_partial"), (v["obj_rank1"], "object_rank1_uncertified")):
            if alt is not None and alt != a1:
                return a1, alt, (v["a1_source"] or "none") + "+" + tag
        return a1, a2, v["a1_source"] or "none"
    raise ValueError(name)


def main(argv=None):
    from cora_funnel.evaluate import answers
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="dev60", choices=tuple(SOURCES))
    a = ap.parse_args(argv)
    view = inference_view(a.corpus)
    ans = answers(a.corpus)                                            # scorer only, after every decision
    ok = lambda att, out: isinstance(att, list) and len(att) == len(out) and all(x == y for x, y in zip(att, out))
    res, per = {}, collections.defaultdict(dict)
    for name in "ABCD":
        hits, src, wrong_claims = 0, collections.Counter(), 0
        for k, v in view.items():
            out = ans[k][0]
            p1, p2, s = policy(name, v)
            c = ok(p1, out) or ok(p2, out)
            per[k][name] = c
            hits += c
            if c:
                src["attempt_1" if ok(p1, out) else "attempt_2", s] += 1
            if v["claims"] != "---" and not ok(p1, out):
                wrong_claims += 1
        res[name] = {"exact_2attempt": hits, "correct_by_slot_and_source": {f"{x}|{y}": n for (x, y), n in sorted(src.items())},
                     "claimed_tasks_with_wrong_attempt_1": wrong_claims}
    for name in "BCD":
        res[name]["gained_vs_A"] = sorted(k for k in per if per[k][name] and not per[k]["A"])
        res[name]["lost_vs_A"] = sorted(k for k in per if per[k]["A"] and not per[k][name])
    agree = sum(v["harness_object_certified"] == v["funnel_object_certified"] for v in view.values())
    out = {"corpus": a.corpus, "label": "SHADOW arbitration on saved predictions (DEVELOPMENT for dev60, SYNTHETIC for c2dev); not a Kaggle result",
           "tasks": len(view), "policies": res, "object_certified_agreement_harness_vs_funnel": f"{agree}/{len(view)}",
           "runtime_overhead": "none at inference: every field is already produced by native; B-D only reorder answers"}
    json.dump(out, open(os.path.join(OUT, f"arbitration_shadow_{a.corpus}.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
