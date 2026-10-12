"""Variant-carrying installation (the one licensed repair).

A growth extension is constructed from instances the native engine memorized
in one segmentation variant V. The engine searches at most
inducer.MAX_SEG_VARIANTS_TRIED coherent variants in SEGMENTATION_TRIAL_ORDER,
and coherence depends on the demonstration subset, so a reduced subset can
cut V or make it incoherent and the installed relation is then never
searched (records/LOO_V1_DIAGNOSIS_20261012.md). While an extension is
installed, `variant_first(V)` makes the engine's object-program search try V
first and admit it even when the coherence filter would not. Nothing else
changes: the other variants, their order and the cap, the acceptance gate
(train-exact and the engine's own leave-one-out), every other engine phase,
K alone (no extension, no overlay) and the failure-evidence extraction.

Two inducer module attributes are wrapped for the duration and restored on
exit, verified by identity: SEGMENTATION_TRIAL_ORDER (V moved to the front)
and evaluate_variant (V's result admitted). geocat_arc is not edited.
"""
from __future__ import annotations

import contextlib
import dataclasses

_STATE = {"active": None}


def _mods():
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.types import SegmentationVariant
    return I, SegmentationVariant


def originals():
    I, _ = _mods()
    return (I.SEGMENTATION_TRIAL_ORDER, I.evaluate_variant)


@contextlib.contextmanager
def variant_first(variant: str):
    """Within the context the engine's object-program search tries the
    segmentation variant named `variant` (e.g. "S6") first and admits it.
    Yields a record: evaluations of V, and how many the coherence filter
    would have rejected."""
    I, SV = _mods()
    if _STATE["active"] is not None:
        raise RuntimeError("a variant is already promoted")
    v = next((x for x in SV if x.value == variant), None)
    if v is None:
        raise ValueError(f"unknown segmentation variant {variant!r}")
    saved = originals()
    order0, evaluate0 = saved
    record = {"variant": variant, "evaluations": 0, "admitted_incoherent": 0}

    def evaluate_variant(variant_, train_pairs):
        res = evaluate0(variant_, train_pairs)
        if variant_ is v:
            record["evaluations"] += 1
            if not res.coherent:
                record["admitted_incoherent"] += 1
                res = dataclasses.replace(res, coherent=True)
        return res
    evaluate_variant.__cora_reach2__ = True
    I.SEGMENTATION_TRIAL_ORDER = (v,) + tuple(x for x in order0 if x is not v)
    I.evaluate_variant = evaluate_variant
    _STATE["active"] = variant
    try:
        yield record
    finally:
        I.SEGMENTATION_TRIAL_ORDER, I.evaluate_variant = order0, evaluate0
        _STATE["active"] = None
        record["restored"] = originals() == saved
        if not record["restored"]:
            raise RuntimeError("the variant overlay left engine state behind")


def restored() -> bool:
    I, _ = _mods()
    return _STATE["active"] is None and not getattr(I.evaluate_variant, "__cora_reach2__", False)
