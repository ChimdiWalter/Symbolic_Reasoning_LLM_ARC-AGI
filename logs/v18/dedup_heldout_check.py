"""DEVELOPMENT ONLY: for each development task, how many of the deduped
verified candidates (the set the selection hierarchy chooses among) predict
the held-out pair at fitter level, and how many are behaviourally equal to
the generator's extension. Shows how much the lower selection levels matter."""
import json, sys
R = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
sys.path.insert(0, R); sys.path.insert(0, R + "/scripts")
import numpy as np
from cora_arc2026 import v18_proposer as P
import v18_corpus as CORPUS
from cora_tti import scoped_slot_fitting as SF
tasks = CORPUS.tasks(CORPUS.DEV_BASE, 40)
out = []
for t in tasks:
    sem = P.Semantics(t["train"]); inp = P.build_input(t["train"], sem)
    verified = []
    for depth in (2, 3):
        verified = P.verify(P.propose(inp, depth, sem)["proposals"], sem)
        if verified: break
    reps = P.dedupe(verified)
    fitted, _ = SF.fit_induced_occurrences(t["schema"], t["train"]); tfp = P.behaviour(fitted)
    hx = sum(1 for c in reps if (lambda o: o is not None and np.array_equal(o, t["held"][1]))(P._evaluate(c["fitted"], t["held"][0])))
    out.append({"seed": t["seed"], "verified": len(verified), "deduped": len(reps), "heldout_exact": hx, "target_equivalent": sum(1 for c in reps if c["fingerprint"] == tfp)})
    print(json.dumps(out[-1]), flush=True)
json.dump(out, open(R + "/logs/v18/dedup_heldout_check.json", "w"), indent=1)
