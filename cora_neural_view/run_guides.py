"""Run every guide on the decisions of a split (Stage A, observation only).

  CUDA_VISIBLE_DEVICES=0 python -m cora_neural_view.run_guides --split dev
      -> outputs/neural_view_v0/guide_rows_<split>.jsonl

A decision is a task where:
- BASE and BASE_REPEAT both REJECT; and
- the full training set has at least one view cut by the cap.

The guide input is built by guides.decision_input from:
- the 3 training demonstrations;
- the held-out INPUTS only;
- the full-set census;
- the authentic BASE trace.

The shuffled trace (E arms) comes from the next decision in id order with
the same number of options, never the task itself.
"""
import argparse
import json
import os
import time

from cora_neural_view import guides as G

OUTDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "neural_view_v0")
RANDOM_SEEDS = range(5)


def load():
    rows = [json.loads(line) for line in open(os.path.join(OUTDIR, "reference_rows.jsonl"))]
    cen = {r["task"]: r["census"] for r in rows if r["kind"] == "census"}
    runs = {(r["task"], r["condition"]): r for r in rows if r["kind"] == "run"}
    corpus = {t["id"]: t for t in json.load(open(os.path.join(OUTDIR, "corpus.json")))["tasks"]}
    return cen, runs, corpus


def decisions(split, cen, runs, corpus):
    out = []
    for tid in sorted(corpus):
        t = corpus[tid]
        b1, b2 = runs.get((tid, "BASE")), runs.get((tid, "BASE_REPEAT"))
        if t["split"] != split or not (b1 and b2) or tid not in cen:
            continue
        if b1["outcome"] == b2["outcome"] == "REJECT" and cen[tid]["012"]["cut"]:
            inp = G.decision_input(t["train"], [a for a, _ in t["heldout"]], cen[tid]["012"], b1["trace"])
            out.append((tid, inp))
    return out


def shuffle_sources(decs):
    src = {}
    for i, (tid, inp) in enumerate(decs):
        for k in range(1, len(decs)):
            oid, oinp = decs[(i + k) % len(decs)]
            if oid != tid and len(oinp["options"]) == len(inp["options"]):
                src[tid] = (oid, oinp["trace"])
                break
        else:
            oid, oinp = decs[(i + 1) % len(decs)]
            src[tid] = (oid, oinp["trace"]) if oid != tid else (None, None)
    return src


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--no-neural", action="store_true")
    a = ap.parse_args(argv)
    cen, runs, corpus = load()
    decs = decisions(a.split, cen, runs, corpus)
    src = shuffle_sources(decs)
    models = json.load(open(os.path.join(OUTDIR, "models.json")))
    llm = jep = None
    if not a.no_neural:
        from cora_neural_view.jepa import JEPAGuide
        llm = G.LLMGuide(models["Qwen/Qwen2.5-1.5B-Instruct"]["path"])
        jep = JEPAGuide(models["facebook/ijepa_vith14_1k"]["path"])
    path = os.path.join(OUTDIR, f"guide_rows_{a.split}.jsonl")
    with open(path, "w") as handle:
        for tid, inp in decs:
            sid, strace = src[tid]
            arms = [("B1", lambda: G.guide_B1(inp)), ("B2", lambda: G.guide_B2(inp)), ("B3", lambda: G.guide_B3(inp))]
            arms += [(f"R{s}", (lambda s=s: G.guide_R(inp, seed=s))) for s in RANDOM_SEEDS]
            if llm is not None:
                arms += [("C", lambda: llm(inp, "C", 0)), ("D", lambda: llm(inp, "D", 0)),
                         ("E", lambda: llm(inp, "E", 0, shuffled_trace=strace)), ("F", lambda: llm(inp, "F", 0)),
                         ("D_perm1", lambda: llm(inp, "D", 1)), ("C_perm1", lambda: llm(inp, "C", 1)),
                         ("C-CF", lambda: G.cf_call(llm, inp, "C")), ("D-CF", lambda: G.cf_call(llm, inp, "D")),
                         ("E-CF", lambda: G.cf_call(llm, inp, "E", shuffled_trace=strace)),
                         ("J-C", lambda: jep(inp, "J-C")), ("J-D", lambda: jep(inp, "J-D")),
                         ("J-E", lambda: jep(inp, "J-E", shuffled_trace=strace))]
            for arm, fn in arms:
                t0 = time.time()
                out = fn()
                ranking, choice = out[0], out[1]
                info = out[2] if len(out) > 2 else {}
                handle.write(json.dumps({"task": tid, "arm": arm, "options": inp["options"], "ranking": ranking,
                                         "choice": choice, "shuffle_source": sid if arm.startswith(("E", "J-E")) else None,
                                         "input_sha": G.input_sha(inp), "seconds": round(time.time() - t0, 3),
                                         "info": info}) + "\n")
            handle.flush()
    print(json.dumps({"split": a.split, "decisions": len(decs), "rows": path}))


if __name__ == "__main__":
    main()
