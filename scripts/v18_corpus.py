"""Item-2 v1.8 corpus law (generator side). The v1.7 acceptance filter,
unchanged, at a given seed base: seed = base + 100k, family
S.FAMILIES[k mod 5], k ascending; taken if the generator's schema has at
least 2 blocks and 8 demonstrations (7 training, 1 held out), the
occurrence-scoped fit of that schema is exact on the 7, K's single-block
search has no exact fit, and the scoped fit re-derives every training pair
under leave-one-out. The filter reads the schema and the 7 training pairs,
never the held-out pair or the engine.

The generator's schema is returned for post-hoc diagnostics only; it is
never passed to the proposer.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v15_sel as S                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402

DEV_BASE = 840_000_000
PROSPECTIVE_BASE = 860_000_000
MAX_TRIES = 2000


def tasks(seed_base, n, max_tries=MAX_TRIES, exclude_digests=frozenset()):
    import numpy as np
    from cora_tti import constructive_dataset as CD
    from cora_tti import scoped_slot_fitting as SF
    M, MI = X._meta()
    out = []
    for k in range(max_tries):
        seed = seed_base + 100 * k
        fam = S.FAMILIES[k % len(S.FAMILIES)]
        schema = CD.sample_target(seed, S.G.parse_family(fam))
        if sum(1 for st in schema[1] if st[0] == "Paint") < 2:
            continue
        if S.CV.digest(schema) in exclude_digests:
            continue
        gs = [seed * 97 + i for i in range(30)]
        concrete = CD.instantiate_tables(schema, [CD.generate_grid(s) for s in gs[:6]])
        if concrete is None:
            continue
        pairs, _ = CD.render_demonstrations(concrete, gs, min_demos=6)
        if len(pairs) < 8:
            continue
        train, held = pairs[:7], pairs[7]
        f, _ = SF.fit_induced_occurrences(schema, train)
        if f is None or SF.base_search_with_scoped_fitter(train)["exact"]:
            continue
        ok = True
        for i in range(len(train)):
            sub = [p for j, p in enumerate(train) if j != i]
            g, _ = SF.fit_induced_occurrences(schema, sub)
            o = None if g is None else M.evaluate(g, train[i][0], MI.descriptors)
            if o is None or not np.array_equal(o, train[i][1]):
                ok = False
                break
        if not ok:
            continue
        out.append({"k": k, "seed": seed, "family": fam, "schema": schema,
                    "digest": S.CV.digest(schema), "train": train, "held": held})
        if len(out) >= n:
            break
    return out
