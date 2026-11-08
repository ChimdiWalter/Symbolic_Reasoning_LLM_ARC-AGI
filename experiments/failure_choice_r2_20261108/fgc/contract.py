"""The strong full-bank control: one explicit contract shared by every arm (revision 2: three interventions).

Every arm of a choice test runs through `run_arm` below, and through nothing else. The contract:
1. ONE BANK. Every arm (the static full bank, every router, the random order, the shuffled diagnosis, the oracle)
   gets the IDENTICAL executable bank `BANK`, executed by the one function `execute`, on the CURRENT task's own
   measurement only. Every intervention in a measurement was run on that task's own demonstrations and query inputs,
   with the same grammar, searches, views, 211 structures and gates, whichever arm later uses it.
2. ONE METER. Every arm gets the same total budget, charged by one `Meter`: the base attempt's calls, the failure
   descriptor's calls when the arm reads a descriptor, then each intervention's calls.
3. ARMS DIFFER ONLY IN ORDER. An arm is an order function from a failure DESCRIPTOR (features of a failure record)
   and the task's opaque id to an ordering of BANK. The order is the only arm-dependent input to `run_arm` (with the
   descriptor charge, which every descriptor-reading arm pays alike).
4. SHUFFLED DIAGNOSIS changes only the descriptor: it is the fixed router's order function applied to a donor task's
   descriptor. The donor's demonstrations, measurement and budget are never passed to `run_arm`, which takes the
   current task's measurement only. Donor demonstrations are never used as the control.
5. Exceptions, by design and named: arm B ("base plus extra search") gives search every remaining call and its bank
   is search only; arm A runs no intervention; arm H's order comes from the generator's cause (an upper bound).
Search-like interventions (deeper search, the view search) have no cheap applicability check: given c calls they
commit their first fit if it came within c, and otherwise spend all c (or less, if their fragment was exhausted).
Construction runs to its own end; with fewer calls remaining than it needs it is cut off and commits nothing.
"""
BANK = ("search", "view", "construct")
SEARCH_LIKE = ("search", "view")


class Meter:
    """The one total meter: calls charged against one budget."""

    def __init__(self, budget):
        self.budget = budget
        self.spent = 0

    def remaining(self):
        return self.budget - self.spent

    def charge(self, calls):
        if calls < 0:
            raise ValueError("negative charge")
        self.spent += calls


def execute(iv, m, meter, caps, search_all=False):
    """Run intervention `iv` of BANK on the current task's measurement `m`; charge `meter`; return the committed
    predictions or None. The same code, the same inputs, for every arm. caps: {search-like intervention: cap}."""
    if iv not in BANK:
        raise ValueError(f"not in the bank: {iv}")
    rem = meter.remaining()
    if rem <= 0:
        return None
    if iv in SEARCH_LIKE:
        s = m[iv]
        cap = rem if (search_all and iv == "search") else min(caps[iv], rem)
        if s["fit"] and s["calls"] <= cap:
            meter.charge(s["calls"])
            return s["preds"]
        if not s["fit"] and s["stop"] not in ("budget", "cpu_cap"):
            meter.charge(min(cap, s["calls"]))                   # its fragment was exhausted before the cap
        else:
            meter.charge(cap)
        return None
    c = m["construct"]
    if c["calls"] <= rem:
        meter.charge(c["calls"])
        return c["preds"] if c["fit"] else None
    meter.charge(rem)                                            # cut off before it finished: nothing committed
    return None


def run_arm(m, order, budget, caps, search_all=False, descriptor_calls=0):
    """(committed predictions or None, what committed them, calls spent) for one arm on one task."""
    if len(set(order)) != len(order) or any(iv not in BANK for iv in order):
        raise ValueError(f"an order is a sequence of distinct bank interventions: {order}")
    meter = Meter(budget)
    meter.charge(m["base"]["calls"])
    if m["base"]["fit"]:
        return m["base"]["preds"], "base", meter.spent
    meter.charge(descriptor_calls)
    for iv in order:
        preds = execute(iv, m, meter, caps, search_all)
        if preds:
            return preds, iv, meter.spent
    return None, None, meter.spent
