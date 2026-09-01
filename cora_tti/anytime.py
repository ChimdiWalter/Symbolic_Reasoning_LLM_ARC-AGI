"""Anytime meta-reasoning scheduler + policy simulator (phase P2; plan §VIII).

Kaggle time is one global resource. The scheduler's job is to maximize expected
solved outputs per unit compute: easy tasks stop early, hard tasks earn larger
budgets from evidence, and no task identity is ever consulted (beliefs update
only from OBSERVED behavior of the solver on that task in this run).

Model. Per task j the scheduler holds a belief about solve probability as a
function of invested time, the standard exponential race:

    p_j(t) = p_max_j * (1 - exp(-t / tau_j))

with (p_max, tau) either given priors (from public/synthetic statistics) or the
uninformed default. The greedy-marginal policy repeatedly grants a quantum to
the task with the highest marginal expected solves per second,

    dp_j/dt = (p_max_j / tau_j) * exp(-t_j / tau_j),

which is provably the greedy-optimal order for independent concave p_j(t).
Failures decay the belief (evidence the task is harder than the prior); solves
retire the task and free its remaining time for the rest.

The SIMULATOR runs allocation policies against synthetic ground-truth tasks
(hidden (p_max, tau) the policy never sees) so policies can be compared under a
frozen seed before any real solver exists. The emulator's `schedule` hook is
served by `EmulatorAdapter` for single-pass runs; the full quantum loop is for
the later multi-round runner.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

import numpy as np

DEFAULT_PRIOR = (0.35, 60.0)     # (p_max, tau seconds): weakly optimistic


@dataclass
class TaskBelief:
    p_max: float = DEFAULT_PRIOR[0]
    tau: float = DEFAULT_PRIOR[1]
    invested_s: float = 0.0
    solved: bool = False
    attempts: int = 0

    def p_solve_by(self, t: float) -> float:
        return self.p_max * (1.0 - math.exp(-t / self.tau))

    def marginal_rate(self) -> float:
        """d p / d t at the current investment; 0 once solved."""
        if self.solved:
            return 0.0
        return (self.p_max / self.tau) * math.exp(-self.invested_s / self.tau)

    def observe_failure(self, spent_s: float, decay: float = 0.7) -> None:
        """A quantum ended without a solve: the task is harder than believed."""
        self.invested_s += spent_s
        self.attempts += 1
        self.p_max *= decay
        self.tau *= 1.0 + (1.0 - decay)

    def observe_solve(self, spent_s: float) -> None:
        self.invested_s += spent_s
        self.solved = True


class AnytimeScheduler:
    """Greedy-marginal allocator over TaskBeliefs under one global budget."""

    def __init__(self, task_ids: Sequence[str], total_budget_s: float,
                 quantum_s: float, priors: Mapping[str, tuple] | None = None,
                 min_quantum_s: float = 0.5):
        self.beliefs = {}
        for tid in task_ids:
            p_max, tau = (priors or {}).get(tid, DEFAULT_PRIOR)
            self.beliefs[tid] = TaskBelief(p_max=p_max, tau=tau)
        self.remaining_s = float(total_budget_s)
        self.quantum_s = float(quantum_s)
        self.min_quantum_s = float(min_quantum_s)

    def next_grant(self) -> tuple[str, float] | None:
        """(task_id, budget for the next quantum) or None when done."""
        if self.remaining_s < self.min_quantum_s:
            return None
        live = [(tid, b) for tid, b in self.beliefs.items() if not b.solved]
        if not live:
            return None
        #  deterministic: highest marginal rate; ties -> least-invested, then id
        live.sort(key=lambda kv: (-kv[1].marginal_rate(),
                                  kv[1].invested_s, kv[0]))
        tid = live[0][0]
        if self.beliefs[tid].marginal_rate() <= 0.0:
            return None
        return tid, min(self.quantum_s, self.remaining_s)

    def report(self, task_id: str, spent_s: float, solved: bool) -> None:
        self.remaining_s -= spent_s
        if solved:
            self.beliefs[task_id].observe_solve(spent_s)
        else:
            self.beliefs[task_id].observe_failure(spent_s)

    def solved_ids(self) -> list:
        return sorted(t for t, b in self.beliefs.items() if b.solved)


class EmulatorAdapter:
    """Serves the kaggle_emulator `schedule(remaining_s, remaining_tasks)` hook
    with a marginal-rate-weighted share instead of the equal split. Stateless
    with respect to task identity (the emulator does not say which task is
    next); it simply front-loads less time when many tasks remain and more as
    the pool shrinks, bounded by a per-task cap."""

    def __init__(self, cap_fraction: float = 3.0):
        self.cap_fraction = cap_fraction

    def __call__(self, remaining_s: float, remaining_tasks: int) -> float:
        equal = remaining_s / max(1, remaining_tasks)
        return min(equal * self.cap_fraction, remaining_s)


# --------------------------------------------------------------------------
# policy simulator over synthetic ground truth
# --------------------------------------------------------------------------

@dataclass
class SyntheticTask:
    """Hidden truth the policy never sees: solvable iff granted >= need_s
    total investment (p_max_true == 0 encodes an unsolvable task)."""
    need_s: float
    solvable: bool = True


def simulate(policy: str, tasks: Mapping[str, SyntheticTask],
             total_budget_s: float, quantum_s: float,
             priors: Mapping[str, tuple] | None = None,
             seed: int = 0) -> dict:
    """Run one allocation policy to exhaustion; return solves + accounting.

    policies: "equal"  — single pass, budget/n each, no revisits;
              "greedy" — AnytimeScheduler quanta with belief updates.
    """
    ids = sorted(tasks)
    solved, spent = set(), {tid: 0.0 for tid in ids}
    if policy == "equal":
        share = total_budget_s / len(ids)
        for tid in ids:
            grant = share
            spent[tid] = min(grant, tasks[tid].need_s
                             if tasks[tid].solvable else grant)
            if tasks[tid].solvable and grant >= tasks[tid].need_s:
                solved.add(tid)
        used = sum(min(share, tasks[t].need_s) if t in solved else share
                   for t in ids)
    elif policy == "greedy":
        scheduler = AnytimeScheduler(ids, total_budget_s, quantum_s, priors)
        used = 0.0
        while True:
            grant = scheduler.next_grant()
            if grant is None:
                break
            tid, budget = grant
            truth = tasks[tid]
            will_solve = (truth.solvable
                          and spent[tid] + budget >= truth.need_s)
            actually = (truth.need_s - spent[tid]) if will_solve else budget
            spent[tid] += actually
            used += actually
            scheduler.report(tid, actually, will_solve)
            if will_solve:
                solved.add(tid)
    else:
        raise ValueError(policy)
    return {"policy": policy, "solved": sorted(solved),
            "n_solved": len(solved), "used_s": round(used, 3),
            "per_task_spent": {k: round(v, 3) for k, v in spent.items()},
            "within_budget": used <= total_budget_s + 1e-9}
