"""Outcome labels and no-fit flags (PROTOCOL.md section 4). Standard library only.

An arm with no program is labelled NO_FIT_IN_BOUNDED_PROPOSAL: the declared search (base search, up to three holes,
up to three retries) found no fit. The label describes that bounded search only.
"""
NO_FIT = "NO_FIT_IN_BOUNDED_PROPOSAL"
CPU_GUARD = "CPU_GUARD"
FIT = {"VERIFIED", "REACHABLE"}
FINISHED = FIT | {NO_FIT, CPU_GUARD}
UNFINISHED = {"NOT_STARTED", "INTERRUPTED", "KILLED", "WORKER_ERROR"}
# search.run's stop values: "budget" (150,000 executions), "cpu_cap" (20 CPU-s), "max_size" (the enumeration
# finished every cost level: no stop reason), "fits" (stopped after its fits).
STOP_REASON = {"budget": "budget", "cpu_cap": "cpu_cap", "max_size": None, "fits": "fits"}


def no_fit_flags(searches, guard_stop=False):
    """The four flags of a no-fit arm, from the searches it finished (and whether its per-arm guard stopped it)."""
    return {"complete_search": (not guard_stop and bool(searches)
                                and all(s["stop"] == "max_size" and not s["closure_capped"] for s in searches)),
            "execution_budget_stop": any(s["stop"] == "budget" for s in searches),
            "cpu_limit_stop": guard_stop or any(s["stop"] == "cpu_cap" for s in searches),
            "enumeration_capped": any(s["closure_capped"] for s in searches)}


def closest_of(searches, cells_total):
    """The arm's closest right-shaped program over every search it finished: the most correct cells of any
    non-fitting program whose outputs have every pair's shape (search.run's track_partial record); the earliest
    search wins a tie."""
    best = None
    for s in searches:
        c = s.get("closest")
        if c and (best is None or c["cells_correct"] > best["cells_correct"]):
            best = dict(c, search=s["search"])
    if best is None:
        return {"found": False, "cells_total": cells_total}
    return {"found": True, "search": best["search"], "program": best["program"],
            "cells_correct": best["cells_correct"], "cells_total": cells_total,
            "share_correct": round(best["cells_correct"] / cells_total, 6) if cells_total else None}
