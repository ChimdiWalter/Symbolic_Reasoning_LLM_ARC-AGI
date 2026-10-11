"""Growth-relation construction from the native engine's own failure
(reach v1 mechanism; docs/CORA_REAL_TASK_REACH_DEV_v1.md section 4).

Failure evidence: the objects the native engine memorized with the constant
`pattern` growth during an identity-frame induction on the demonstrations
(cora_reach.instances). Per segmentation variant, every relation setting of
the frozen grammar is tested against every memorized instance of that
variant; a setting is proposed only if it reproduces the added cells of ALL
of them exactly, each with one colour, and the instances come from at least
SUPPORT_DEMOS demonstrations. Deterministic order (variants by instance
count then name; settings in grammar order), duplicates removed by
extension name, at most MAX_PROPOSALS. Nothing reads a target or a task id.
"""
from __future__ import annotations

import time

import numpy as np

from cora_reach import growth_ext as GE
from cora_reach import relations as REL

#: frozen before the measurement run (protocol section 4.1, 2026-10-11): the
#: full grammar of relations.FAMILIES, named so that a later family cannot
#: enter it silently
GRAMMAR = ("window_fill", "empty_square", "bbox_fill", "bbox_ring", "band", "dilate", "connect",
           "copies_bbox", "copies_offset")
MAX_PROPOSALS = 8
SUPPORT_DEMOS = 2
MAX_INSTANCES = 64


def _instances(raw):
    out = {}
    for i in raw:
        if i.get("grid") is None:
            continue
        G = np.asarray(i["grid"])
        O = {tuple(c): col for c, col in i["in"]}
        out_cc = {tuple(c): col for c, col in i["out"]}
        A = {c: col for c, col in out_cc.items() if c not in O}
        if not A or len(set(A.values())) != 1:
            continue
        out.setdefault(str(i.get("variant")), []).append((set(O), set(A), G, i.get("demo")))
    return out


def propose(raw_instances, grammar=None) -> dict:
    t0 = time.time()
    groups = _instances(raw_instances)
    tried = 0
    proposals, seen = [], set()
    for variant, insts in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        insts = insts[:MAX_INSTANCES]
        demos = {d for *_x, d in insts if d is not None}
        if len(demos) < SUPPORT_DEMOS:
            continue
        for fam, params in REL.settings(grammar if grammar is not None else GRAMMAR):
            tried += 1
            if all(REL.apply(fam, params, O, G) == A for O, A, G, _d in insts):
                ext = GE.make(fam, params)
                if ext["name"] in seen:
                    continue
                seen.add(ext["name"])
                proposals.append({"ext": ext, "variant": variant, "instances": len(insts),
                                  "demos": sorted(demos)})
                if len(proposals) >= MAX_PROPOSALS:
                    break
        if len(proposals) >= MAX_PROPOSALS:
            break
    return {"proposals": proposals, "variants": {v: len(x) for v, x in groups.items()},
            "settings_tried": tried, "seconds": round(time.time() - t0, 3)}
