"""Match input objects to output objects."""
from __future__ import annotations
from .objects import ARCObject


def shape_similarity(a: ARCObject, b: ARCObject) -> float:
    sig_a = a.shape_signature
    sig_b = b.shape_signature
    if sig_a == sig_b:
        return 1.0
    ha, wa = len(sig_a), len(sig_a[0]) if sig_a else 0
    hb, wb = len(sig_b), len(sig_b[0]) if sig_b else 0
    if ha != hb or wa != wb:
        return 0.0
    match = sum(1 for r in range(ha) for c in range(wa) if sig_a[r][c] == sig_b[r][c])
    total = ha * wa
    return match / total if total > 0 else 0.0


def color_similarity(a: ARCObject, b: ARCObject) -> float:
    return 1.0 if a.color == b.color else 0.0


def size_similarity(a: ARCObject, b: ARCObject) -> float:
    if a.size == 0 and b.size == 0:
        return 1.0
    return min(a.size, b.size) / max(a.size, b.size)


def location_similarity(a: ARCObject, b: ARCObject) -> float:
    ca, cb = a.centroid, b.centroid
    dist = ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5
    return 1.0 / (1.0 + dist)


def overall_similarity(a: ARCObject, b: ARCObject) -> float:
    return (
        0.3 * shape_similarity(a, b)
        + 0.2 * color_similarity(a, b)
        + 0.2 * size_similarity(a, b)
        + 0.3 * location_similarity(a, b)
    )


def match_objects(
    input_objects: list[ARCObject],
    output_objects: list[ARCObject],
) -> list[tuple[ARCObject, ARCObject, float]]:
    if not input_objects or not output_objects:
        return []

    matches = []
    used_output = set()

    scored = []
    for inp in input_objects:
        for out in output_objects:
            scored.append((inp, out, overall_similarity(inp, out)))

    scored.sort(key=lambda x: x[2], reverse=True)

    used_input = set()
    for inp, out, sim in scored:
        if inp.id in used_input or out.id in used_output:
            continue
        if sim > 0.1:
            matches.append((inp, out, sim))
            used_input.add(inp.id)
            used_output.add(out.id)

    return matches
