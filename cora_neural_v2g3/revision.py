"""ncv2-g3 failure-driven revision (Phase 5): a minimal, rule-based, executable revision controller. Demonstrations only.

The spec is docs/NEURAL_CORA_REVISION_CONTROLLER_SPEC.md. No learned-revision advantage is claimed: this prototype
exists so that a later, separately frozen experiment can compare an authentic controller with its controls.

**State:** the current program, its object view, its per-demonstration mismatch (delta.mismatch), known alternative
programs, uncertainty (how many demonstrations fail, and how), and the remaining evaluation budget.

**Actions** are concrete AST edits:
- change_view; change_selector; change_reference (a REF inside the action);
- change_operation (an action of the same kind family, e.g. another colour or vector);
- add_guard (`(and SEL P)`) and remove_guard; add_rule and remove_rule; reorder (swap neighbours);
- allocate_search (run the ncv2-g3 search with part of the remaining budget).

**One step:** the policy orders the actions; each action yields candidate edits; every candidate is EXECUTED on every
demonstration and compared with the current program (cells newly right, cells newly wrong). The first candidate with
fewer wrong cells is kept; otherwise the edit is rolled back. A revision therefore always changes an executable
program and its execution. The loop stops when the program fits, when no action improves it, or when the budget is
spent.

**Policies:** `AuthenticPolicy` orders actions from the mismatch diagnosis. Controls for a future experiment:
`FixedOrderPolicy` (failure-blind), `ShuffledTracePolicy` (another task's diagnosis), and `TryAllPolicy`.
"""
from dataclasses import dataclass, field

import numpy as np

from cora_neural_v2 import search as G1S
from cora_neural_v2.rast import ASTError, N, to_sexpr
from cora_neural_v2g2 import search as S2
from cora_neural_v2g3 import delta as D
from cora_neural_v2g3 import joint as J
from cora_neural_v2g3 import scene as SC

ACTIONS = ("change_parameter", "change_reference", "change_selector", "add_guard", "remove_guard", "add_rule",
           "remove_rule", "reorder", "change_view", "allocate_search")
REF_OPS = ("nearest", "unique", "largest", "nearest_of_color", "container", "contained", "shape_twin")


def wrong_cells(ds, train):
    """Total wrong cells; a demonstration with the wrong output shape counts as entirely wrong."""
    return sum(d.n_wrong if d.shape_ok else int(np.asarray(b).size) for d, (_, b) in zip(ds, train))


def change(before, after):
    """(cells newly right, cells newly wrong) between two executions, over same-shape demonstrations."""
    right = wrong = 0
    for x, y in zip(before, after):
        if x.shape_ok and y.shape_ok:
            right += int((x.wrong & ~y.wrong).sum())
            wrong += int((~x.wrong & y.wrong).sum())
    return right, wrong


# ------------------------------------------------------------------ policies
class AuthenticPolicy:
    """Order actions from the diagnosis: wrong colours suggest a parameter or reference; broken cells an
    over-selecting selector; remaining cells a missing rule or an under-selecting selector; failures in only some
    demonstrations a guard."""

    def order(self, diag, prog):
        if any(not d["shape_ok"] for d in diag):
            return ["change_view", "allocate_search"]
        tot = lambda k: sum(d.get(k, 0) for d in diag)                           # noqa: E731
        failing = sum(d["n_wrong"] > 0 for d in diag)
        acts = []
        if tot("wrong_colour") and not tot("broken"):
            acts += ["change_parameter", "change_reference"]
        if tot("broken"):
            acts += ["change_selector", "add_guard", "remove_rule"]
        if tot("remaining") and not tot("broken"):
            acts += ["add_rule", "change_selector"]
        if 0 < failing < len(diag):
            acts += ["add_guard"]
        acts += list(ACTIONS)
        return list(dict.fromkeys(acts))


class FixedOrderPolicy:
    """Failure-blind: the same actions, always in the same order."""

    def order(self, diag, prog):
        return list(ACTIONS)


@dataclass
class ShuffledTracePolicy:
    """The authentic ordering computed from ANOTHER task's diagnosis."""
    foreign_diag: list

    def order(self, diag, prog):
        return AuthenticPolicy().order(self.foreign_diag, prog)


class TryAllPolicy(FixedOrderPolicy):
    """Every action's candidates, within the budget (the matched-compute style control); same order as fixed."""


# ------------------------------------------------------------------ the controller
@dataclass
class Reviser:
    task: dict
    budget: int
    per_action: int = 40
    log: list = field(default_factory=list)

    def __post_init__(self):
        self.train = self.task["train"]
        self.ev = S2.evidence2(self.train)
        self.views = G1S.distinct_views(self.task)
        self.pools = J.build_pools(self.task, self.ev, self.views)
        self.sels = [s for s, _, _ in S2.selectors(self.ev)]
        self.used = 0

    # ---- candidate edits
    def _with_rules(self, prog, rules):
        return N("program", (prog.args[0], tuple(rules), prog.args[2], prog.args[3]))

    def candidates(self, action, prog):
        if not (isinstance(prog, N) and prog.op == "program"):
            return []
        view, rules, default, render = prog.args
        rules = list(rules)
        pool = self.pools.get(view, [])
        out = []
        if action == "change_view":
            out = [N("program", (v, tuple(rules), default, render)) for v in self.views if v != view]
        elif action == "change_selector":
            for i, r in enumerate(rules):
                if r.op == "rule":
                    out += [self._with_rules(prog, rules[:i] + [N("rule", (s, r.args[1]))] + rules[i + 1:])
                            for s in self._ranked_selectors(pool, r.args[1]) if s != r.args[0]]
        elif action == "change_parameter":
            for i, r in enumerate(rules):
                if r.op == "rule":
                    out += [self._with_rules(prog, rules[:i] + [N("rule", (r.args[0], a))] + rules[i + 1:])
                            for a in self._same_family(pool, r) if a != r.args[1]]
        elif action == "change_reference":
            refs = [x[0] for x in S2.references(self.ev)]
            for i, r in enumerate(rules):
                if r.op == "rule":
                    out += [self._with_rules(prog, rules[:i] + [N("rule", (r.args[0], a))] + rules[i + 1:])
                            for a in _swap_refs(r.args[1], refs)]
        elif action == "add_guard":
            preds = [p for p, _ in S2.feature_preds(self.ev)]
            for i, r in enumerate(rules):
                if r.op == "rule":
                    out += [self._with_rules(prog, rules[:i] + [N("rule", (N("and", (r.args[0], p)), r.args[1]))] + rules[i + 1:])
                            for p in preds if p != r.args[0]]
        elif action == "remove_guard":
            for i, r in enumerate(rules):
                if r.op == "rule" and r.args[0].op == "and":
                    out += [self._with_rules(prog, rules[:i] + [N("rule", (s, r.args[1]))] + rules[i + 1:]) for s in r.args[0].args]
        elif action == "add_rule":
            for cand, _, _ in pool[:self.per_action]:
                if cand not in rules:
                    out += [self._with_rules(prog, rules + [cand]), self._with_rules(prog, [cand] + rules)]
        elif action == "remove_rule":
            out = [self._with_rules(prog, rules[:i] + rules[i + 1:]) for i in range(len(rules))]
        elif action == "reorder":
            out = [self._with_rules(prog, rules[:i] + [rules[i + 1], rules[i]] + rules[i + 2:]) for i in range(len(rules) - 1)]
        return out[:self.per_action]

    def _ranked_selectors(self, pool, act):
        ranked = [r.args[0] for r, _, _ in pool if r.op == "rule" and r.args[1] == act]
        return list(dict.fromkeys(ranked + self.sels))

    def _same_family(self, pool, rule):
        """Other actions with the same op as the rule's action (another colour, vector, reference...): first those the
        pool pairs with this selector, best prior first, then every candidate action with that op."""
        op = rule.args[1].op
        acts = [r.args[1] for r, _, _ in pool if r.op == "rule" and r.args[0] == rule.args[0] and r.args[1].op == op]
        acts += [a for a, _, _ in S2.actions(self.ev, self.train) if isinstance(a, N) and a.op == op]
        return list(dict.fromkeys(acts))

    # ---- execution and the loop
    def _execute(self, prog):
        if self.used >= self.budget:
            return None
        self.used += 1
        try:
            return D.deltas(prog, self.train)
        except ASTError:
            return False

    def run(self, program, policy=None):
        policy = policy or AuthenticPolicy()
        cur = program
        cur_d = self._execute(cur)
        if not cur_d:
            return {"program": to_sexpr(cur), "fits": False, "used": self.used, "revisions": 0, "log": self.log}
        revisions = 0
        while not D.fits(cur_d, len(self.train)) and self.used < self.budget:
            diag = D.mismatch(cur, self.train, SC.analyse(self.train, cur.args[0]) if cur.op == "program" else None)
            improved = False
            for action in policy.order(diag, cur):
                cands = self._search_candidates() if action == "allocate_search" else self.candidates(action, cur)
                for cand in cands:
                    d = self._execute(cand)
                    if d is None:
                        break
                    if d is False:
                        continue
                    fixed, broke = change(cur_d, d)
                    better = wrong_cells(d, self.train) < wrong_cells(cur_d, self.train)
                    self.log.append({"action": action, "program": to_sexpr(cand), "newly_right": fixed,
                                     "newly_wrong": broke, "wrong_after": wrong_cells(d, self.train), "kept": better})
                    if better:
                        cur, cur_d, improved = cand, d, True
                        revisions += 1
                        break
                if improved or self.used >= self.budget:
                    break
            if not improved:
                break
        return {"program": to_sexpr(cur), "fits": D.fits(cur_d, len(self.train)), "used": self.used,
                "revisions": revisions, "log": self.log}

    def _search_candidates(self):
        from cora_neural_v2g3 import search as S3
        left = max(0, (self.budget - self.used) // 2)
        if not left:
            return []
        fits = S3.search(self.task, left, _fits_only=True)
        self.used += left
        return [f["prog"] for f in fits[:3]]


def _swap_refs(x, refs):
    """Every copy of `x` with one REF node replaced by another candidate REF."""
    out = []

    def walk(node, rebuild):
        if isinstance(node, N):
            if node.op in REF_OPS:
                out.extend(rebuild(r) for r in refs if r != node)
            for i, a in enumerate(node.args):
                walk(a, lambda new, i=i, node=node: rebuild(N(node.op, node.args[:i] + (new,) + node.args[i + 1:])))
        elif isinstance(node, tuple):
            for i, a in enumerate(node):
                walk(a, lambda new, i=i, node=node: rebuild(node[:i] + (new,) + node[i + 1:]))
    walk(x, lambda new: new)
    return out
