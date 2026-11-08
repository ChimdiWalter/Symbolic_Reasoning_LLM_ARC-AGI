"""Results of a block order at a budget, computed from a hole's development trace (PROTOCOL.md section 4) without
re-running the search. The rule is the engine's: an operation is applied only while the counter is at most the
budget, so a block starting at counter C finds a candidate whose last operation has place a inside the block iff
C + a <= budget, and runs to its end iff it was not cut in the trace and C + n - 1 <= budget (then C += n; otherwise
the counter passes the budget and nothing later is found). A two-rule block runs only if it ran in the trace (every
single-rule block of its view ended, none verified) and no single-rule block of its view verified in this run.
Then the engine's `finish`: hand-set place, symmetry forms, de-duplication, grouping on the agreement keys, sort by
(group, simplicity), cut at 8."""
from objgrow import construct as CS


def simulate(hole, sequence, budget):
    tb = {tuple(b["block"]): b for b in hole["trace"]["blocks"]}
    pos = {tuple(b["block"]): b["pos"] for b in hole["blocks"]}
    C = 0
    found = []
    s_found = set()
    for b in sequence:
        b = tuple(b)
        if C > budget:
            break
        r = tb.get(b)
        if r is None:
            continue
        if b[0] == "T" and b[1] in s_found:
            continue
        for c in r["cands"]:
            if C + c["at"] <= budget:
                found.append((pos[b], c["inblock"], c))
        if not r["cut"] and C + r["n"] - 1 <= budget:
            C += r["n"]
            if b[0] == "S" and r["cands"]:
                s_found.add(b[1])
        else:
            C = budget + 1
    capped = C > budget
    found.sort(key=lambda t: (t[0], t[1]))
    cands = [c for _, _, c in found] + hole["trace"]["sym"]
    seen, uniq = set(), []
    for c in cands:
        if c["sid"] not in seen:
            seen.add(c["sid"])
            uniq.append(c)
    groups = {}
    for c in uniq:
        groups[c["pk"]] = groups.get(c["pk"], 0) + 1
    out = []
    for c in uniq:
        d = dict(c)
        d["group"] = groups[c["pk"]] if c["valid"] else 0
        out.append(d)
    out.sort(key=lambda c: (-c["group"], c["simplicity"]))
    ops = min(C, budget + 1) + hole["trace"]["sym_ops"] + len(uniq) * hole["trace"]["n_test"]
    return out[:CS.MAX_CANDS], {"capped": capped, "ops": ops, "block_ops": min(C, budget + 1)}


def comparable(top):
    return [[c["sid"], bool(c["loo"]), c["proposing"], c["group"], list(c["simplicity"]), c.get("view")]
            for c in top]
