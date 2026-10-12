"""P3 overlay (docs/CORA_P3_SAFETY_PREFLIGHT_v1.md section 1).

Inside one call of the engine's _induce_candidate, the coherent views are
grouped by an INDUCTION-level signature computed from that call's training
pairs only; the earliest view of each class (trial order) is kept, then the
engine's unchanged cap applies. No view is added, reordered or admitted.
"""
import contextlib
import hashlib
import json

EVENTS = {"calls": 0, "deduplicated_calls": 0, "dropped_views": 0, "log": None}


def signature(seg, train_pairs) -> str:
    """What the reasoner receives from this view on these pairs."""
    import geocat_arc.object_reasoning.correspondence as C
    import geocat_arc.object_reasoning.features as F
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.types import cell_colors_of
    F.register_builtin_features()

    def typed(objs):
        return [(o.id, type(o).__name__, int(o.color), sorted((list(k), int(c)) for k, c in cell_colors_of(o).items()),
                 list(o.bounding_box)) for o in objs]
    rows = []
    for i, (gi, go) in enumerate(train_pairs):
        oi, oo, bg = seg.input_objects[i], seg.output_objects[i], seg.backgrounds[i]
        alts = C.match_pair(oi, oo, gi, go, pair_index=i)[:I.MAX_ALTS_PER_PAIR]
        corr = [(a.weights_profile, sorted((int(x), int(y), round(float(s), 9)) for x, y, s in a.matches),
                 sorted((int(k), sorted(int(z) for z in vs)) for k, vs in a.copies.items()),
                 sorted(int(z) for z in a.deleted_input_ids), sorted(int(z) for z in a.created_output_ids),
                 int(a.unreconciled_pixels), bool(a.is_object_preserving)) for a in alts]
        feats = [json.dumps(r, sort_keys=True, default=repr)
                 for r in F.compute_feature_table(oi, gi, bg, pair_index=i, role="input").rows]
        rows.append([int(bg), typed(oi), typed(oo), corr, feats])
    return json.dumps(rows, sort_keys=True, default=repr)


def dedup(seg_candidates, train_pairs):
    EVENTS["calls"] += 1
    seen, kept, classes = {}, [], []
    for s in seg_candidates:
        k = signature(s, train_pairs)
        if k in seen:
            classes[seen[k]].append(s.variant.value)
            continue
        seen[k] = len(kept)
        kept.append(s)
        classes.append([s.variant.value])
    if len(kept) < len(seg_candidates):
        EVENTS["deduplicated_calls"] += 1
        EVENTS["dropped_views"] += len(seg_candidates) - len(kept)
    if EVENTS["log"] is not None:
        digest = hashlib.sha256(json.dumps([[gi.to_numpy().tolist(), go.to_numpy().tolist()]
                                            for gi, go in train_pairs]).encode()).hexdigest()[:16]
        EVENTS["log"].append({"pairs": len(train_pairs), "pairs_sha": digest, "classes": classes})
    return kept


@contextlib.contextmanager
def p3(log=False):
    """Install P3 for the duration of the block; the engine is restored after."""
    import geocat_arc.object_reasoning.inducer as I
    from cora_p3 import induce_candidate_p3 as G
    if "_p3_dedup" in I.__dict__:
        raise RuntimeError("P3 is already installed")
    original = I._induce_candidate
    EVENTS.update(calls=0, deduplicated_calls=0, dropped_views=0, log=[] if log else None)
    I.__dict__["_p3_dedup"] = dedup
    exec(compile(G.SOURCE, "<cora_p3.induce_candidate_p3>", "exec"), I.__dict__)
    I._induce_candidate = I.__dict__.pop("_induce_candidate_p3")
    try:
        yield EVENTS
    finally:
        I._induce_candidate = original
        del I.__dict__["_p3_dedup"]
