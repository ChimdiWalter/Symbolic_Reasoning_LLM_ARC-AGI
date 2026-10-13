"""CORA-NVG freeze v1: pins everything the single final run depends on.

  python -m cora_neural_view.freeze write     -> outputs/neural_view_v0/freeze_v1.json
  python -m cora_neural_view.freeze check     exit 1 on any difference

Pinned:
- the code files and the NVG tests;
- the plan record;
- the corpus;
- the model revisions and weight hashes;
- the prompt template (the LLM TEMPLATE plus a canonical sample prompt per
  condition);
- the final split's reference rows. These are evaluator-side, computed
  before any guide runs on the final split.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(HERE, "outputs", "neural_view_v0")
FREEZE = os.path.join(OUTDIR, "freeze_v1.json")
CODE = ["cora_neural_view/__init__.py", "cora_neural_view/corpus.py", "cora_neural_view/reference.py",
        "cora_neural_view/guides.py", "cora_neural_view/jepa.py", "cora_neural_view/run_guides.py",
        "cora_neural_view/evaluate.py", "cora_neural_view/freeze.py", "tests/test_nvg.py",
        "records/CORA_NEURAL_VIEW_GUIDANCE_PLAN_20261012.md"]


def _sha(path):
    return hashlib.sha256(open(os.path.join(HERE, path), "rb").read()).hexdigest()


def manifest():
    sys.path.insert(0, HERE)
    from cora_neural_view import guides as G
    from cora_neural_view.run_guides import decisions, load
    cen, runs, corpus = load()
    final = [t for t in corpus if corpus[t]["split"] == "final"]
    ref_final = sorted(json.dumps(r, sort_keys=True) for (t, c), r in runs.items() if t in final)
    sample = decisions("final", cen, runs, corpus)[:1]
    prompts = {c: hashlib.sha256(G.prompt(sample[0][1], c, 0)[0].encode()).hexdigest() for c in "CDF"} if sample else {}
    models = json.load(open(os.path.join(OUTDIR, "models.json")))
    return {"version": "nvg_freeze_v1", "code": {p: _sha(p) for p in CODE},
            "corpus_sha256": _sha("outputs/neural_view_v0/corpus.json"),
            "models": {k: {"revision": v["revision"], "weights": {f: w["sha256_local"] for f, w in v["weights"].items()}}
                       for k, v in models.items()},
            "llm_template_sha256": hashlib.sha256(G.LLMGuide.TEMPLATE.encode()).hexdigest(),
            "cf_question_sha256": hashlib.sha256(G.CF_QUESTION.encode()).hexdigest(),
            "sample_prompt_sha256": prompts,
            "final_reference_rows": len(ref_final),
            "final_reference_sha256": hashlib.sha256("\n".join(ref_final).encode()).hexdigest()}


def problems():
    if not os.path.exists(FREEZE):
        return ["no freeze_v1.json"]
    want, have = json.load(open(FREEZE)), manifest()
    out = []
    for k in want:
        if want[k] != have.get(k):
            out.append(k if not isinstance(want[k], dict) else
                       f"{k}: " + ", ".join(sorted(x for x in set(want[k]) | set(have.get(k) or {})
                                                   if want[k].get(x) != (have.get(k) or {}).get(x))))
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["write"]:
        json.dump(manifest(), open(FREEZE, "w"), indent=1)
        print("wrote", FREEZE)
    elif sys.argv[1:2] == ["check"]:
        p = problems()
        print("freeze_v1 problems:", p)
        sys.exit(1 if p else 0)
    else:
        sys.exit(__doc__)
