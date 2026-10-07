"""CORA-TTI Item-2 v1.9: the ONE repair, K*-4 installed-extension re-induction.

Diagnosis (records/ITEM2_V19_AUDIT_DIAGNOSIS.md, development data): 145 of
145 rejection events of K* + {e} are H1, re-induction instability. Inside
the engine's own leave-one-out by re-induction, two heuristics designed for
native hypotheses displace an extension whose fold-fitted semantics
reproduce the held-out pair:
- the scoped fitter's pre-emptive single-witness refusal (86 events), which,
  applied again inside every N-1 re-induction, demands a third witness the
  rule itself never asked for;
- the canonical parameter-class ranking (59 events), under which a
  pixel-rule reduction with an unpriced learned colour table (labelled
  RELATIONAL, 0 value-bound literals) outranks the extension.

K*-4, one rule with one principle: while an extension is installed, every
re-induction of the run re-derives the installed extension ITSELF from that
re-induction's demonstrations, and the engine's unchanged gate decides.
- fitting: the installed concept's induced tables are fitted by the frozen
  scoped fitter with every consistent witness (MIN_KEY_WITNESSES = 1 for
  the duration of the installed-concept search). Identification is left to
  the leave-one-out, which re-fits the concept without the held-out pair
  and requires that pair exactly; so a key is still needed in at least two
  demonstrations, the rule's own stated standard, enforced once by the gate;
- ranking: in every ranking of the run (inducer.rank_candidates,
  inducer.rank_by_score) the installed concept's candidates come first in
  the native order among themselves, then every native candidate in the
  native order. A native candidate still wins any re-induction whose
  demonstrations the installed concept does not verify.

Unchanged: geocat_arc, the acceptance gate (train-perfect and leave-one-out
by re-induction with every fold exact), the fitter's other admission rules
(coverage, region rules, functional tables, hidden keys, exact replay), the
native search, K* (rules 1 to 3), the v1.7 compiler and the v1.8 proposer.
Inert when nothing is installed: every patched function then returns the
native value (tested), so K* alone is identical.

Applies to installed productions with two or more blocks (the v1.8
proposer's compositions): a one-block production has the engine's own
shape and keeps the engine's own learner (K*-2), witness rule included.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os

from cora_arc2026 import v17_compiler as X

VERSION = "1.9.0-repair"
CLAUSES = ("fit", "rank")
REPAIR_RULE = (
    "K*-4 installed-extension re-induction: while an extension is installed (K*-3 overlay "
    "non-empty), (a) the installed concept's induced tables are fitted by the frozen scoped "
    "fitter with every consistent witness (MIN_KEY_WITNESSES = 1 during the installed-concept "
    "search), identification being left to the engine's leave-one-out, and (b) in every ranking "
    "of the run (inducer.rank_candidates, inducer.rank_by_score) the installed concept's "
    "candidates come first in the native order among themselves, then the native candidates in "
    "the native order. Inert when nothing is installed.")

_ACTIVE = {"on": False, "clauses": ()}


def module_sha256() -> str:
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()


def repair_identity() -> str:
    """Identity of K*' = K* + K*-4: K*'s identity, the rule text and this file."""
    return hashlib.sha256(X.canonical_json({"kstar": X.k_identity(), "rule": REPAIR_RULE,
                                            "implementation": module_sha256()})).hexdigest()


def _mods():
    from geocat_arc.object_reasoning import inducer as I
    from geocat_arc.object_reasoning import meta_induction as MI
    return I, MI, X._sf()


def installed_names() -> frozenset:
    return frozenset(c.name for c in X._STATE["overlay"])


def _partition(ranked):
    names = installed_names()
    if not names:
        return ranked
    ext = [p for p in ranked if getattr(p, "concept", None) in names]
    if not ext:
        return ranked
    return ext + [p for p in ranked if getattr(p, "concept", None) not in names]


def _w_rank(orig):
    def ranked(*args, **kwargs):
        return _partition(orig(*args, **kwargs))
    ranked.__name__ = orig.__name__
    ranked.__wrapped_original__ = orig
    return ranked


def _w_search(orig, SF):
    def search_with_concepts(pairs, concepts, deadline=None):
        names = installed_names()
        if not names or not any(getattr(c, "name", None) in names for c in concepts):
            return orig(pairs, concepts, deadline=deadline)
        prev = SF.MIN_KEY_WITNESSES
        SF.MIN_KEY_WITNESSES = 1
        try:
            return orig(pairs, concepts, deadline=deadline)
        finally:
            SF.MIN_KEY_WITNESSES = prev
    search_with_concepts.__wrapped_original__ = orig
    return search_with_concepts


@contextlib.contextmanager
def repaired(clauses=CLAUSES):
    """Run the frozen pipeline as K*' (K* + K*-4) for the duration. The
    patches are applied outside kstar(), so its restoration snapshot sees
    one consistent set of functions; all are restored on exit."""
    if _ACTIVE["on"]:
        raise RuntimeError("K*-4 is already active")
    clauses = tuple(clauses)
    if not set(clauses) <= set(CLAUSES):
        raise ValueError(clauses)
    I, MI, SF = _mods()
    saved = [(I, "rank_candidates", I.rank_candidates), (I, "rank_by_score", I.rank_by_score),
             (MI, "search_with_concepts", MI.search_with_concepts)]
    witness_before = SF.MIN_KEY_WITNESSES
    if "rank" in clauses:
        I.rank_candidates = _w_rank(I.rank_candidates)
        I.rank_by_score = _w_rank(I.rank_by_score)
    if "fit" in clauses:
        MI.search_with_concepts = _w_search(MI.search_with_concepts, SF)
    _ACTIVE.update(on=True, clauses=clauses)
    try:
        yield {"clauses": clauses, "identity": repair_identity()}
    finally:
        for mod, attr, fn in saved:
            setattr(mod, attr, fn)
        SF.MIN_KEY_WITNESSES = witness_before
        _ACTIVE.update(on=False, clauses=())


def run_reasoner(train_pairs, productions=(), budget_s=8.0, clauses=CLAUSES, **kw) -> dict:
    """The frozen runner (v17_compiler.run_reasoner) as K*'."""
    with repaired(clauses):
        return X.run_reasoner(train_pairs, productions, budget_s=budget_s, **kw)


def restored() -> bool:
    """True when no K*-4 patch is left and the witness constant is 2."""
    I, MI, SF = _mods()
    return (not _ACTIVE["on"] and SF.MIN_KEY_WITNESSES == 2
            and not hasattr(I.rank_candidates, "__wrapped_original__")
            and not hasattr(I.rank_by_score, "__wrapped_original__")
            and not hasattr(MI.search_with_concepts, "__wrapped_original__"))


def describe() -> str:
    return json.dumps({"version": VERSION, "rule": REPAIR_RULE, "clauses": list(CLAUSES)})
