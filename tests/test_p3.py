"""P3 implementation tests (docs/CORA_P3_SAFETY_PREFLIGHT_v1.md section 2)."""
import difflib
import hashlib
import inspect
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
CORPUS = os.path.join(HERE, "outputs", "p3", "adversarial_corpus.json")


def _task(tid):
    t = next(x for x in json.load(open(CORPUS))["corpus"] if x["id"] == tid)
    return [(np.asarray(a), np.asarray(b)) for a, b in t["train"]]


def _coherent(pairs):
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.types import to_grid_pairs
    gp = to_grid_pairs(pairs)
    return gp, [r for r in (I.evaluate_variant(v, gp) for v in I.SEGMENTATION_TRIAL_ORDER) if r.coherent]


def test_build_check():
    import build_p3
    assert open(build_p3.OUT).read() == build_p3.build()


def test_only_marked_lines_differ():
    import geocat_arc.object_reasoning.inducer as I
    from cora_p3 import induce_candidate_p3 as G
    diff = [d for d in difflib.ndiff(inspect.getsource(I._induce_candidate).splitlines(), G.SOURCE.splitlines())
            if d[:2] in ("+ ", "- ")]
    added = [d for d in diff if d.startswith("+ ")]
    assert len(added) == 2 and all(d.rstrip().endswith("# P3") for d in added)
    assert len([d for d in diff if d.startswith("- ")]) == 1          # only the def line is replaced
    assert G.ENGINE_SOURCE_SHA256 == hashlib.sha256(inspect.getsource(I._induce_candidate).encode()).hexdigest()


def test_install_and_restore():
    import geocat_arc.object_reasoning.inducer as I
    from cora_p3.dedup import p3
    original = I._induce_candidate
    with p3():
        assert I._induce_candidate is not original and "_p3_dedup" in I.__dict__
    assert I._induce_candidate is original and "_p3_dedup" not in I.__dict__


def test_distinct_views_are_untouched_and_dedup_is_idempotent():
    from cora_p3.dedup import dedup, signature
    for tid in ("halo_500", "translate_down_503", "multicolor_majority_501"):
        train = _task(tid)
        for sub in ((0, 1, 2), (0, 1), (0, 2), (1, 2)):
            gp, segs = _coherent([train[i] for i in sub])
            once = dedup(segs, gp)
            assert [s.variant for s in dedup(once, gp)] == [s.variant for s in once]
            sigs = [signature(s, gp) for s in segs]
            if len(set(sigs)) == len(sigs):
                assert [s.variant for s in once] == [s.variant for s in segs]


def test_order_kept_nothing_added_nothing_incoherent():
    from cora_p3.dedup import dedup
    train = _task("translate_down_503")                                 # family A: duplicates fill the cap
    changed = 0
    for sub in ((0, 1, 2), (0, 1), (0, 2), (1, 2)):
        gp, segs = _coherent([train[i] for i in sub])
        out = dedup(segs, gp)
        it = iter(segs)
        assert all(any(o is s for s in it) for o in out)                # a subsequence, in trial order
        assert all(o.coherent for o in out)
        changed += len(out) < len(segs)
    assert changed


def test_heldout_demonstration_cannot_change_a_folds_classes():
    """Family G: in the engine's own leave-one-out the fold (0,1) receives only
    demonstrations 0 and 1. Mutating demonstration 2, its held-out pair, must
    leave that fold's equivalence classes unchanged."""
    import geocat_arc.object_reasoning.inducer as I
    from cora_p3.dedup import p3
    from geocat_arc.object_reasoning.types import to_grid_pairs
    train = _task("translate_down_503")
    mutated = list(train)
    mutated[2] = (train[2][0], np.random.default_rng(7).integers(0, 10, size=train[2][1].shape))
    fold_sha = hashlib.sha256(json.dumps([[a.tolist(), b.tolist()] for a, b in train[:2]]).encode()).hexdigest()[:16]
    seen = []
    for pairs in (train, mutated):
        with p3(log=True) as ev:
            I.loo_validate(lambda sub: I.induce_program(sub, I.InductionConfig(budget_s=4.0)), to_grid_pairs(pairs))
            seen.append([e["classes"] for e in ev["log"] if e["pairs_sha"] == fold_sha])
            assert all(e["pairs"] <= 2 for e in ev["log"])              # no fold sees more than its own pairs
    assert seen[0] and seen[0] == seen[1]
