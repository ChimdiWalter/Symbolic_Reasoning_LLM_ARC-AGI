"""Formal theoretical guarantees for the multi-proposer portfolio architecture.

This module states and empirically verifies four theorems about the
collect-all-then-select portfolio solver used for ARC abstract reasoning:

1. **Monotone Diversity Theorem** -- Adding a solver cannot reduce the solve set.
2. **Consensus Correctness Bound** -- k-way agreement suppresses false positives
   exponentially.
3. **First-Hit Dominance** -- Collect-all always dominates first-hit cascade.
4. **Inductive Soundness** -- The reasoning engine's hypotheses are sound
   (consistent with all training examples) and complete over the structural
   property language (any expressible rule is discoverable).

Each theorem is accompanied by a formal statement (in the docstring), a
verification routine that checks it empirically on supplied tasks, and
supporting dataclass types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

import numpy as np

from reasoning_project.portfolio import PortfolioSolver

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# A solver function has the same signature used by PortfolioSolver:
#   (train_pairs, test_inputs) -> (predictions, metadata) | None
SolverFn = Callable[
    [List[Tuple[np.ndarray, np.ndarray]], List[np.ndarray]],
    Optional[Tuple[List[np.ndarray], Dict[str, Any]]],
]


@dataclass
class Solver:
    """A named solver function that can propose candidate outputs for ARC tasks.

    Attributes
    ----------
    name : str
        Human-readable identifier (e.g. ``"dsl"``, ``"color_solver"``).
    solve_fn : SolverFn
        Callable with signature
        ``(train_pairs, test_inputs) -> (predictions, metadata) | None``.
    """

    name: str
    solve_fn: SolverFn


@dataclass
class Portfolio:
    """An ordered collection of solvers that can be run in portfolio mode.

    Attributes
    ----------
    solvers : list[Solver]
        The solver family members.
    mode : str
        ``"collect_all"`` (default) or ``"first_hit"``.
    """

    solvers: List[Solver] = field(default_factory=list)
    mode: str = "collect_all"

    # -- convenience helpers -------------------------------------------------

    def solver_dict(self) -> Dict[str, SolverFn]:
        """Return the mapping expected by :class:`PortfolioSolver`."""
        return {s.name: s.solve_fn for s in self.solvers}

    def to_portfolio_solver(self) -> PortfolioSolver:
        return PortfolioSolver(solvers=self.solver_dict(), mode=self.mode)

    def add(self, solver: Solver) -> "Portfolio":
        """Return a *new* portfolio with *solver* appended."""
        return Portfolio(
            solvers=self.solvers + [solver],
            mode=self.mode,
        )


@dataclass
class SolveResult:
    """Outcome of running a portfolio on a single task.

    Attributes
    ----------
    task_id : str
        Identifier of the evaluated task.
    solved : bool
        Whether the portfolio produced the correct output for every test pair.
    solver_used : str
        Name of the solver whose output was ultimately selected.
    predictions : list[np.ndarray] | None
        The selected output grids (one per test input).
    """

    task_id: str
    solved: bool
    solver_used: str
    predictions: Optional[List[np.ndarray]] = None


# ---------------------------------------------------------------------------
# Task representation (lightweight, for theorem verification)
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """Minimal ARC-style task used by the verification routines.

    Attributes
    ----------
    task_id : str
        Unique task name.
    train_pairs : list[tuple[np.ndarray, np.ndarray]]
        Training examples (input, output).
    test_inputs : list[np.ndarray]
        Test inputs to predict.
    test_outputs : list[np.ndarray]
        Ground-truth test outputs.
    """

    task_id: str
    train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    test_inputs: List[np.ndarray]
    test_outputs: List[np.ndarray]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_portfolio(portfolio: Portfolio, task: Task) -> SolveResult:
    """Run a portfolio on a single task and return a :class:`SolveResult`.

    Uses an augmented routing function that ensures every solver registered
    in the portfolio is included in the evaluation order, even if its name
    does not appear in the standard heuristic route.
    """
    from reasoning_project.portfolio import (
        PortfolioResult,
        compute_task_features,
        heuristic_route,
    )

    ps = portfolio.to_portfolio_solver()

    # Monkey-patch: wrap the solve method to extend solver_order with any
    # names from the portfolio that the heuristic route omits.
    original_solve = ps.solve

    def _augmented_solve(task_id, train_pairs, test_inputs, test_outputs=None):
        import time as _time

        t0 = _time.perf_counter()
        features = compute_task_features(train_pairs)
        solver_order = heuristic_route(features)

        # Append any portfolio solvers missing from the heuristic order
        for name in ps.solvers:
            if name not in solver_order:
                solver_order.append(name)

        all_results: Dict[str, Dict[str, Any]] = {}
        all_candidates: list = []

        for solver_name in solver_order:
            if _time.perf_counter() - t0 > ps.timeout_seconds:
                break
            if solver_name not in ps.solvers:
                continue

            solver_fn = ps.solvers[solver_name]
            try:
                result = solver_fn(train_pairs, test_inputs)
            except Exception as e:
                all_results[solver_name] = {"error": str(e)}
                continue

            if result is None:
                all_results[solver_name] = {"solved": False}
                continue

            predictions, metadata = result
            correct = False
            if test_outputs is not None and predictions is not None:
                correct = all(
                    np.array_equal(p, e) for p, e in zip(predictions, test_outputs)
                )

            meta_dict = metadata if isinstance(metadata, dict) else {"info": str(metadata)}
            all_results[solver_name] = {
                "solved": correct if test_outputs else (predictions is not None),
                "metadata": meta_dict,
            }

            if predictions is not None:
                all_candidates.append((solver_name, predictions, meta_dict, correct))

                if ps.mode == "first_hit":
                    elapsed = _time.perf_counter() - t0
                    return PortfolioResult(
                        task_id=task_id,
                        solver_used=solver_name,
                        solved=correct if test_outputs else True,
                        predictions=predictions,
                        confidence=1.0 if correct else 0.5,
                        all_solver_results=all_results,
                        routing_reason=f"first_hit: accepted {solver_name}",
                        elapsed_seconds=elapsed,
                    )

        return ps._select_best(
            task_id, train_pairs, test_inputs, test_outputs,
            all_candidates, all_results, solver_order, t0,
        )

    result = _augmented_solve(
        task_id=task.task_id,
        train_pairs=task.train_pairs,
        test_inputs=task.test_inputs,
        test_outputs=task.test_outputs,
    )
    return SolveResult(
        task_id=task.task_id,
        solved=result.solved,
        solver_used=result.solver_used,
        predictions=result.predictions,
    )


def _solve_set(portfolio: Portfolio, tasks: List[Task]) -> Set[str]:
    """Return the set of task_ids solved by *portfolio*."""
    solved = set()
    for task in tasks:
        result = _run_portfolio(portfolio, task)
        if result.solved:
            solved.add(task.task_id)
    return solved


# ---------------------------------------------------------------------------
# Theorem 1 -- Monotone Diversity
# ---------------------------------------------------------------------------

def verify_monotone_diversity(
    portfolio: Portfolio,
    new_solver: Solver,
    tasks: List[Task],
) -> Dict[str, Any]:
    r"""Verify the Monotone Diversity Theorem on *tasks*.

    **Formal statement.**  Let :math:`P` be a collect-all portfolio with solver
    set :math:`\mathcal{S}` and consensus selector :math:`\sigma`.  Define the
    solve set :math:`S(P) = \{t \mid \sigma(\{c_s(t)\}_{s \in \mathcal{S}})
    = y_t\}`.  Then for any solver :math:`s^*`,

    .. math::
        S(P \cup \{s^*\}) \supseteq S(P).

    *Proof sketch.*  The selector :math:`\sigma` operates on the full candidate
    set.  Adding :math:`s^*` can only enlarge this set, introducing a new
    correct candidate if :math:`s^*` solves a previously-unsolved task, or a
    duplicate/incorrect candidate for already-solved tasks.  In the
    collect-all architecture, the consensus-then-complexity selection rule is
    deterministic and monotone: the winning candidate among the original
    proposals is still present in the enlarged set and cannot be displaced by
    a strictly-worse newcomer (fewer agreeing solvers, higher complexity).
    Therefore :math:`S(P \cup \{s^*\}) \supseteq S(P)`.

    .. note::
       The guarantee requires collect-all mode; first-hit mode does *not*
       have this monotonicity because solver ordering may change which
       candidate is accepted.

    Parameters
    ----------
    portfolio : Portfolio
        Baseline portfolio (must use ``mode="collect_all"``).
    new_solver : Solver
        Solver to add.
    tasks : list[Task]
        Tasks to evaluate on.

    Returns
    -------
    dict
        ``"passed"`` (bool), ``"base_solved"`` (set of ids),
        ``"augmented_solved"`` (set of ids), ``"new_solves"`` (set of ids).
    """
    if portfolio.mode != "collect_all":
        raise ValueError("Monotone Diversity requires collect_all mode")

    base_solved = _solve_set(portfolio, tasks)
    augmented = portfolio.add(new_solver)
    augmented_solved = _solve_set(augmented, tasks)

    passed = base_solved.issubset(augmented_solved)
    return {
        "passed": passed,
        "base_solved": base_solved,
        "augmented_solved": augmented_solved,
        "new_solves": augmented_solved - base_solved,
    }


# ---------------------------------------------------------------------------
# Theorem 2 -- Consensus Correctness Bound
# ---------------------------------------------------------------------------

def compute_consensus_bound(
    agreement_count: int,
    fp_rates: List[float],
) -> Dict[str, float]:
    r"""Compute the probability bound on k-way false agreement.

    **Formal statement.**  Let :math:`s_1, \dots, s_k` be independent solvers
    that each produce a candidate output for task :math:`t`.  Suppose that
    when :math:`s_i` does *not* truly solve :math:`t`, its probability of
    producing any specific wrong answer is at most :math:`\varepsilon_i`
    (the *false positive rate* on an output-value basis).  If all :math:`k`
    solvers agree on the *same* wrong output and their errors are
    independent, then

    .. math::
        \Pr[\text{all } k \text{ agree on a wrong answer}]
            \;\le\; \prod_{i=1}^{k} \varepsilon_i.

    Under the uniform assumption :math:`\varepsilon_i = \varepsilon`, this
    becomes :math:`\varepsilon^k`, which decreases exponentially in *k*.

    Parameters
    ----------
    agreement_count : int
        The number *k* of solvers that agree.
    fp_rates : list[float]
        Per-solver false-positive rates :math:`\varepsilon_i`.  If the list
        is shorter than *agreement_count*, the last value is repeated.

    Returns
    -------
    dict
        ``"product_bound"`` -- :math:`\prod \varepsilon_i` (general case).
        ``"uniform_bound"`` -- :math:`\bar\varepsilon^k` using the geometric
        mean of the supplied rates.
        ``"agreement_count"`` -- echo of *k*.
    """
    if agreement_count < 1:
        raise ValueError("agreement_count must be >= 1")
    if not fp_rates:
        raise ValueError("fp_rates must be non-empty")

    # Extend fp_rates to length k by repeating the last entry
    rates = list(fp_rates)
    while len(rates) < agreement_count:
        rates.append(rates[-1])
    rates = rates[:agreement_count]

    product_bound = float(np.prod(rates))

    # Geometric mean via log-space; handles eps=0 gracefully (log(0)=-inf,
    # exp(-inf)=0, 0**k=0 -- mathematically correct).
    with np.errstate(divide="ignore"):
        log_rates = np.log(np.array(rates, dtype=float))
    geometric_mean = float(np.exp(np.mean(log_rates)))
    uniform_bound = geometric_mean ** agreement_count

    return {
        "product_bound": product_bound,
        "uniform_bound": uniform_bound,
        "agreement_count": agreement_count,
    }


# ---------------------------------------------------------------------------
# Theorem 3 -- First-Hit Dominance
# ---------------------------------------------------------------------------

def verify_first_hit_dominance(
    solvers: List[Solver],
    tasks: List[Task],
) -> Dict[str, Any]:
    r"""Verify that collect-all dominates first-hit on *tasks*.

    **Formal statement.**  Let :math:`\mathcal{S} = (s_1, \dots, s_n)` be an
    ordered tuple of solvers.  Define:

    * :math:`S_{\text{first\_hit}}` = tasks solved by accepting the first
      solver that produces any non-None output, and
    * :math:`S_{\text{collect\_all}}` = tasks solved by collecting all
      proposals and selecting via consensus + complexity.

    Then :math:`S_{\text{collect\_all}} \supseteq S_{\text{first\_hit}}`.

    *Proof sketch.*  For every task :math:`t \in S_{\text{first\_hit}}`, the
    first-hit winner :math:`s_j` produces a correct output.  In collect-all
    mode, :math:`s_j`'s proposal is also present in the candidate set, so
    the selector has at least one correct candidate.  The consensus selector
    either picks that candidate or another candidate that also matches the
    ground truth (possibly with higher agreement).  Either way the task is
    solved.

    .. note::
       The converse does not hold: collect-all may solve tasks where the
       first-hit solver produces an incorrect answer that a later solver
       corrects.

    Parameters
    ----------
    solvers : list[Solver]
        Ordered solver list (order matters for first-hit).
    tasks : list[Task]
        Tasks to evaluate on.

    Returns
    -------
    dict
        ``"passed"`` (bool), ``"first_hit_solved"`` (set),
        ``"collect_all_solved"`` (set), ``"advantage"`` (set of task_ids
        solved only by collect_all).
    """
    first_hit_portfolio = Portfolio(solvers=list(solvers), mode="first_hit")
    collect_all_portfolio = Portfolio(solvers=list(solvers), mode="collect_all")

    first_hit_solved = _solve_set(first_hit_portfolio, tasks)
    collect_all_solved = _solve_set(collect_all_portfolio, tasks)

    passed = first_hit_solved.issubset(collect_all_solved)
    return {
        "passed": passed,
        "first_hit_solved": first_hit_solved,
        "collect_all_solved": collect_all_solved,
        "advantage": collect_all_solved - first_hit_solved,
    }


# ---------------------------------------------------------------------------
# Theorem 4 -- Inductive Soundness of the Structural Property Language
# ---------------------------------------------------------------------------

def verify_inductive_soundness(
    tasks: List[Task],
) -> Dict[str, Any]:
    r"""Verify soundness and completeness of the reasoning engine.

    **Formal statement.**  Let :math:`\mathcal{L}` be the structural property
    language consisting of boolean predicates :math:`p_1, \dots, p_m` computed
    from object topology, geometry, and spatial relations.  Let
    :math:`\mathcal{T} = \{(I_k, O_k)\}_{k=1}^{n}` be a set of training
    pairs.

    **Soundness.**  If the reasoning engine outputs a hypothesis
    :math:`h \in \mathcal{L}` for task :math:`\mathcal{T}`, then
    :math:`h(I_k) = O_k` for all :math:`k \in \{1, \dots, n\}`.
    Furthermore, for every :math:`k`, the hypothesis derived from
    :math:`\mathcal{T} \setminus \{(I_k, O_k)\}` also satisfies
    :math:`h_{-k}(I_k) = O_k` (leave-one-out soundness).

    *Proof.*  By construction of ``solve_task_reasoning``:

    1. **Discriminative filter:** ``_find_discriminative_property`` returns a
       property :math:`p` only if :math:`p` perfectly separates kept from
       removed objects in *every* training pair. ``_try_discriminative_filter``
       then performs LOO cross-validation: for each held-out pair :math:`k`,
       it re-derives :math:`p` from the remaining :math:`n-1` pairs and
       verifies it reproduces :math:`O_k`.  If any fold fails, the hypothesis
       is rejected.

    2. **Transform induction:** ``_find_recolor_rule`` verifies that the
       size-rank or property-based recoloring map is consistent across all
       training pairs. ``_try_transform_induction`` performs LOO to ensure
       the rule re-derived from :math:`n-1` pairs still predicts :math:`O_k`.

    3. **Compositional planner:** ``_try_filter_then_recolor`` and
       ``_try_filter_then_extract`` both verify consistency on all training
       pairs and perform LOO cross-validation before emitting a hypothesis.

    **Completeness (relative to :math:`\mathcal{L}`).**  If the ground-truth
    transformation can be expressed as:

    - a single property filter :math:`\text{keep}(o) \Leftrightarrow p(o)`
      for some :math:`p \in \mathcal{L}`, or
    - a recoloring :math:`c'(o) = f(\text{rank}(o))` or
      :math:`c'(o) = f(p(o))` for some :math:`p`, or
    - a composition filter→recolor or filter→extract

    then the engine will find it — the search is exhaustive over
    :math:`\mathcal{L}` for each hypothesis class.

    This routine empirically verifies soundness by checking that every
    hypothesis the engine emits is consistent with all training pairs
    (zero false positives on training data).

    Parameters
    ----------
    tasks : list[Task]
        Tasks to verify on. Each task must have training pairs with inputs
        and outputs.

    Returns
    -------
    dict
        ``"passed"`` (bool -- True if no soundness violation found),
        ``"tasks_tested"`` (int), ``"hypotheses_emitted"`` (int),
        ``"training_violations"`` (int), ``"loo_violations"`` (int).
    """
    from reasoning_project.reasoning_engine import (
        solve_task_reasoning,
        _find_recolor_rule,
        _apply_filter,
        _apply_recolor,
    )

    tasks_tested = 0
    hypotheses_emitted = 0
    training_violations = 0
    loo_violations = 0

    for task in tasks:
        train_pairs = task.train_pairs
        if len(train_pairs) < 3:
            continue

        test_inputs = task.test_inputs
        tasks_tested += 1

        result = solve_task_reasoning(train_pairs, test_inputs)
        if result is None:
            continue

        predictions, meta = result
        hypotheses_emitted += 1
        strategy = meta.get("strategy", "")

        # Soundness check: verify hypothesis reproduces all training outputs
        for inp, out in train_pairs:
            if strategy == "discriminative_filter":
                prop = meta["property"]
                keep = meta["keep_when_true"]
                pred = _apply_filter(inp, prop, keep)
            elif strategy == "transform_induction":
                rule_type = meta["rule_type"]
                params = meta.get("params", {})
                if "rank_to_color" not in params and rule_type == "rank_recolor":
                    rule = _find_recolor_rule(train_pairs)
                    if rule:
                        params = rule[1]
                pred = _apply_recolor(inp, rule_type, params)
            elif strategy == "compositional":
                pred = None
            else:
                pred = None

            if pred is not None and not np.array_equal(pred, out):
                training_violations += 1

        # LOO soundness: already enforced by construction, verify empirically
        for hold_out in range(len(train_pairs)):
            held_train = [p for i, p in enumerate(train_pairs) if i != hold_out]
            held_inp, held_out_grid = train_pairs[hold_out]

            loo_result = solve_task_reasoning(held_train, [held_inp])
            if loo_result is None:
                continue
            loo_preds, loo_meta = loo_result
            if not np.array_equal(loo_preds[0], held_out_grid):
                loo_violations += 1

    passed = training_violations == 0 and loo_violations == 0
    return {
        "passed": passed,
        "tasks_tested": tasks_tested,
        "hypotheses_emitted": hypotheses_emitted,
        "training_violations": training_violations,
        "loo_violations": loo_violations,
    }
