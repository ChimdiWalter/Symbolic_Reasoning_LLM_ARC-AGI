"""Reach v1: growth extensions, construction and the reversible bridge
(synthetic fixtures only; no ARC data)."""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_reach import bridge as BR                                  # noqa: E402
from cora_reach import construct as CN                               # noqa: E402
from cora_reach import growth_ext as GE                              # noqa: E402
from cora_reach import relations as REL                              # noqa: E402

#: an asymmetric shape and its copy one gap to the right (copies_bbox sr 0, sc 1, gap 1)
SHAPE = {(1, 1): 3, (1, 2): 3, (2, 1): 3, (3, 1): 3, (3, 2): 3, (3, 3): 3}


def scene(shape, h=7, w=12, origin=(0, 0)):
    g = np.zeros((h, w), dtype=int)
    cells = {(r + origin[0], c + origin[1]): v for (r, c), v in shape.items()}
    for (r, c), v in cells.items():
        g[r, c] = v
    return g, cells


def test_extension_is_canonical_and_reload_refuses_tampering():
    e = GE.make("copies_bbox", {"until_border": False, "gap": 1, "sc": 1, "sr": 0})
    assert GE.load(GE.serialize(e)) == e and e["name"].startswith("gx_")
    bad = json.loads(GE.serialize(e))
    bad["params"]["gap"] = 0
    with pytest.raises(GE.ExtensionError):
        GE.load(GE.canonical_json(bad))
    with pytest.raises(GE.ExtensionError):
        GE.make("copies_bbox", {"sr": 0, "sc": 1, "gap": 7, "until_border": False})
    with pytest.raises(GE.ExtensionError):
        GE.make("lookup_table", {})


def test_relation_renders_the_copy():
    G, cells = scene(SHAPE)
    added = REL.copies_bbox(set(cells), G, 0, 1, 1, False)
    assert added == {(r, c + 4) for r, c in cells}


def test_detect_grow_substitution_only_inside_the_context():
    import geocat_arc.object_reasoning.correspondence as CO
    G, cells = scene(SHAPE)
    out = dict(cells)
    out.update({(r, c + 4): 3 for r, c in cells})
    e = GE.make("copies_bbox", {"sr": 0, "sc": 1, "gap": 1, "until_border": False})
    before = CO.detect_grow(cells, out, G.shape, G)
    assert before is not None and before["mode"] == "pattern"
    saved = BR.originals()
    with BR.installed(e) as rec:
        inside = CO.detect_grow(cells, out, G.shape, G)
        import geocat_arc.object_reasoning.growth as GR
        assert e["name"] in GR.GROW_MODES and GR.GROW_MODES[-1] == "pattern"
    assert inside == {"mode": e["name"], "color": 3}
    assert rec["restored"] and BR.restored(saved) and BR.originals() == saved
    assert CO.detect_grow(cells, out, G.shape, G)["mode"] == "pattern"


def test_no_substitution_when_the_relation_does_not_reproduce_exactly():
    import geocat_arc.object_reasoning.correspondence as CO
    G, cells = scene(SHAPE)
    out = dict(cells)
    out.update({(r, c + 4): 3 for r, c in cells})
    out[(5, 5)] = 3                                   # one extra cell
    e = GE.make("copies_bbox", {"sr": 0, "sc": 1, "gap": 1, "until_border": False})
    with BR.installed(e):
        assert CO.detect_grow(cells, out, G.shape, G)["mode"] == "pattern"


def test_restoration_after_an_exception_and_no_double_install():
    e = GE.make("bbox_ring", {})
    saved = BR.originals()
    with pytest.raises(ValueError):
        with BR.installed(e):
            raise ValueError("boom")
    assert BR.restored(saved)
    with BR.installed(e):
        with pytest.raises(RuntimeError):
            with BR.installed(GE.make("bbox_fill", {})):
                pass
    assert BR.restored(saved)


def test_attribution():
    e = GE.make("bbox_ring", {})
    prog = {"rules": [{"action": {"delta_type": "grow", "params": {"mode": {"op": "const", "args": [e["name"]]}}}}]}
    assert BR.uses(prog, e) and not BR.uses({"rules": []}, e)
    other = GE.make("bbox_fill", {})
    assert not BR.uses(prog, other)


def test_construction_needs_two_demonstrations_and_all_instances():
    G, cells = scene(SHAPE)
    out = dict(cells)
    out.update({(r, c + 4): 3 for r, c in cells})

    def inst(demo, variant="S1"):
        return {"variant": variant, "demo": demo, "grid": G.tolist(),
                "in": [[list(k), v] for k, v in cells.items()], "out": [[list(k), v] for k, v in out.items()]}
    one = CN.propose([inst(0)], grammar=["copies_bbox"])
    two = CN.propose([inst(0), inst(1)], grammar=["copies_bbox"])
    assert one["proposals"] == []
    names = [p["ext"]["family"] for p in two["proposals"]]
    assert names and all(n == "copies_bbox" for n in names)
    bad = inst(2)
    bad["out"] = bad["out"] + [[[6, 11], 3]]
    assert CN.propose([inst(0), inst(1), bad], grammar=["copies_bbox"])["proposals"] == []


def test_engine_run_with_the_extension_installed_is_reversible():
    """End to end on a synthetic task: the native engine (short budget) runs
    with the extension installed; detection is substituted, and the engine
    state is identical afterwards (fresh process for isolation from caches)."""
    code = r'''
import json, os, sys, numpy as np
sys.path.insert(0, %r)
from cora_reach import bridge as BR, growth_ext as GE
from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
from geocat_arc.object_reasoning.inducer import InductionConfig
import geocat_arc.object_reasoning.correspondence as CO
shapes = [{(1,4):3,(2,4):3}, {(3,6):4,(3,7):4,(4,7):4}, {(2,2):2}, {(4,9):6,(5,9):6}]
pairs = []
for sh in shapes:
    g = np.zeros((7, 12), dtype=int)
    for (r, c), v in sh.items(): g[r, c] = v
    o = g.copy()
    col = next(iter(sh.values()))
    for r in {r for r, _ in sh}:
        for c in range(12):
            if o[r, c] == 0: o[r, c] = col
    pairs.append((g, o))
e = GE.make("band", {"axis": "rows"})
hits = []
saved = BR.originals()
with BR.installed(e):
    orig = CO.detect_grow
    def spy(*a, **k):
        r = orig(*a, **k); hits.append((r or {}).get("mode")); return r
    CO.detect_grow = spy
    try:
        res = ObjectReasoningEngine(%r, use_library=False, config=InductionConfig(budget_s=20.0)).solve("t", pairs)
    finally:
        CO.detect_grow = orig
prog = res.solution.program_json if res.solution else None
print(json.dumps({"hit": e["name"] in hits, "accepted": res.solution is not None,
                  "uses": bool(prog and BR.uses(prog, e)), "restored": BR.restored(saved)}))
''' % (HERE, os.path.join("/tmp", "reach_bridge_test_engine"))
    from cora_pilot.native import CHAIN_FLAGS            # the sealed native configuration passes the scene
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARC_")}
    env.update(CHAIN_FLAGS)
    env.update(PYTHONHASHSEED="0", PYTHONPATH=os.pathsep.join([HERE, os.path.join(HERE, "src"),
                                                              "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"]))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600, env=env, cwd=HERE)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["hit"] and out["restored"], (out, r.stderr[-800:])
    assert out["accepted"] and out["uses"], out          # the engine's unchanged gate accepts a program using e
