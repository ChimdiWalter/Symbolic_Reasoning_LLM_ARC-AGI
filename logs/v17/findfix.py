import os, sys, json
R = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
sys.path.insert(0, R)
import numpy as np
from cora_arc2026 import v15_sel as S
from cora_tti import scoped_slot_fitting as SF
from cora_tti import constructive_dataset as CD
from geocat_arc.object_reasoning import meta_ast as M, meta_induction as MI
found = []
for k in range(400):
    seed = 810_000_000 + k * 100
    fam = S.G.parse_family(S.FAMILIES[k % 5])
    schema = CD.sample_target(seed, fam)
    if sum(1 for s in schema[1] if s[0] == "Paint") < 2:
        continue
    gs = [seed * 97 + i for i in range(30)]
    concrete = CD.instantiate_tables(schema, [CD.generate_grid(s) for s in gs[:6]])
    if concrete is None:
        continue
    pairs, _ = CD.render_demonstrations(concrete, gs, min_demos=6)
    if len(pairs) < 8:
        continue
    train, held = pairs[:7], pairs[7]
    f, ev = SF.fit_induced_occurrences(schema, train)
    if f is None or SF.base_search_with_scoped_fitter(train)["exact"]:
        continue
    out = M.evaluate(f, held[0], MI.descriptors)
    if out is None or not np.array_equal(out, held[1]):
        continue
    ok = True
    for i in range(len(train)):
        sub = [p for j, p in enumerate(train) if j != i]
        g, _ = SF.fit_induced_occurrences(schema, sub)
        o = None if g is None else M.evaluate(g, train[i][0], MI.descriptors)
        if o is None or not np.array_equal(o, train[i][1]):
            ok = False; break
    if ok:
        found.append({"seed": seed, "family": S.FAMILIES[k % 5], "blocks": sum(1 for s in schema[1] if s[0] == "Paint"),
                      "schema": M.ast_to_json(schema)})
    if len(found) >= 4:
        break
print(json.dumps([{k: v for k, v in f.items() if k != "schema"} for f in found]))
json.dump(found, open("fixtures.json", "w"))
