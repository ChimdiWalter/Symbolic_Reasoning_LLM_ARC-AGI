"""Block orders (PROTOCOL.md section 5). A block is (kind, view index, j); `blocks` is a hole's hand-set sequence.

    hand(blocks)                       the frozen sequence
    by_scores(blocks, scores)          largest score first, ties in hand-set order; a two-rule block's score is
                                       capped at the lowest score of its view's single-rule blocks
    hand_rule(blocks, view_recs)       views by full correspondence, then the share of changed objects explained,
                                       then the hand-set view order; the hand-set order inside a view
    donor_scores(blocks, keys, donor)  this hole's block scores from a donor hole's scored blocks, by key
"""


def hand(blocks):
    return list(blocks)


def by_scores(blocks, scores):
    sc = {tuple(b): float(s) for b, s in zip(blocks, scores)}
    low = {}
    for b in sc:
        if b[0] == "S":
            low[b[1]] = min(low.get(b[1], sc[b]), sc[b])
    for b in sc:
        if b[0] == "T" and b[1] in low:
            sc[b] = min(sc[b], low[b[1]])
    pos = {tuple(b): k for k, b in enumerate(blocks)}
    return sorted((tuple(b) for b in blocks), key=lambda b: (-sc[b], pos[b]))


def hand_rule(blocks, view_recs):
    """view_recs: the 12 views' pair-analysis records (engine.ViewState.rec), in the frozen view order."""
    def vkey(vi):
        r = view_recs[vi]
        if r.get("skipped"):
            return (1, 0.0, vi)
        ch = r["changed_objects"]
        return (0 if r["full"] else 1, -(r["explained_objects"] / ch if ch else 0.0), vi)
    pos = {tuple(b): k for k, b in enumerate(blocks)}
    return sorted((tuple(b) for b in blocks), key=lambda b: (vkey(b[1]), pos[b]))


def donor_scores(keys, donor):
    """keys: this hole's block keys; donor: [(key, score)] of the donor hole. Score by exact key, else the donor's
    best score for (kind, view), else -1 (after every other block)."""
    exact, kv = {}, {}
    for k, s in donor:
        k = tuple(k)
        exact[k] = max(exact.get(k, s), s)
        kv[k[:2]] = max(kv.get(k[:2], s), s)
    out = []
    for k in keys:
        k = tuple(k)
        if k in exact:
            out.append(exact[k])
        elif k[:2] in kv:
            out.append(kv[k[:2]])
        else:
            out.append(-1.0)
    return out
