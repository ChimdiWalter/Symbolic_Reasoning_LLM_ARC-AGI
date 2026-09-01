"""The first end-to-end Certified Test-Time Invention loop (phase P2/P3 seam).

For one task (demonstration pairs only):

    ordinary certified search under K
        └─ solved -> done (no invention, no credit)
        └─ failed -> Typed Failure Graph (real trace evidence)
                  -> proposer ranks candidate extensions (GPN or fallback)
                  -> for each of the top-k, in order:
                         install the extension EPHEMERALLY
                         re-run the ordinary search
                         found + winner-uses-extension?
                         -> full leave-one-out re-induction under K ∪ {e}
                         -> ablation: remove e, re-run, must fail
                  -> first candidate passing EVERYTHING is the task's
                     certified task-local extension
        └─ ALWAYS: the ephemeral language is discarded afterwards (reset rule)

HONESty BOX — what this loop is and is not, fixed here so no later claim can
inflate it: in this Stage-A demonstration the candidate extensions are KNOWN
registry productions withheld from the crippled language, so a success shows
RECONSTRUCTION of a missing known operator from failure evidence at test
time. It is NOT semantic invention (Stage B constructs novel productions from
generic constructors; separation certificates decide novelty). The loop's
value is that the CHAIN is real: real failed search, real TFG, learned
proposal, real re-search, real LOO, real ablation, real reset.

Verification authority: only the frozen search/LOO functions certify.
The proposer and the loop merely order and orchestrate (soundness invariant 2
of the cognitive-plasticity theory).
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V              # noqa: E402
from level4_blind_runtime import env as E                  # noqa: E402
from level4_blind_runtime import search as SEARCH          # noqa: E402

from cora_parent.tfg import ConcreteTFG                    # noqa: E402
from cora_tti import tfg_extractor as TX                   # noqa: E402

#: a proposer maps (tfg, top_k) -> ranked production names
Proposer = Callable[[ConcreteTFG, int], Sequence[str]]


@dataclass
class TTIConfig:
    search_budget_s: float = 2.0
    loo_budget_s: float = 2.0
    top_k: int = 3
    #: the catalogue candidate productions are drawn from (Stage A: the full
    #: public registry; Stage B will swap in constructor-built candidates)
    catalogue: Mapping[str, Any] = field(default_factory=lambda: dict(V.REGISTRY))


def mdl_fallback_proposer(catalogue: Mapping[str, Any]) -> Proposer:
    """No learning: catalogue productions by ascending cost then name. The
    baseline every learned proposer must beat on proposals-tried-per-solve."""
    ranked = sorted(catalogue, key=lambda n: (catalogue[n].cost, n))

    def propose(tfg: ConcreteTFG, top_k: int) -> Sequence[str]:
        return ranked[:top_k]
    return propose


def gpn_proposer(model, catalogue: Mapping[str, Any]) -> Proposer:
    """Wrap a trained GPNPrototype; names outside the catalogue are dropped."""
    def propose(tfg: ConcreteTFG, top_k: int) -> Sequence[str]:
        out = []
        for ext in model.propose(tfg, top_k=max(top_k, 8)):
            name = ext.payload.get("name")
            if name in catalogue and name not in out:
                out.append(name)
            if len(out) == top_k:
                break
        return out
    return propose


def _search(pairs, env, budget_s):
    deadline = time.monotonic() + budget_s
    return SEARCH.search(pairs, deadline=deadline, env=env)


def _loo(pairs, env, budget_s) -> tuple[int, int]:
    """Frozen LOO-by-rediscovery, per-fold deadline-capped for the loop."""
    if len(pairs) < 2:
        return 0, 0
    passed = 0
    for held in range(len(pairs)):
        subset = [p for i, p in enumerate(pairs) if i != held]
        results, _ = _search(subset, env, budget_s)
        if not results:
            continue
        grid_in, grid_out = pairs[held]
        predicted = E.evaluate(results[0][0], grid_in, env)
        if predicted is not None and np.array_equal(predicted, grid_out):
            passed += 1
    return passed, len(pairs)


def solve_task(pairs, base_language: Mapping[str, Any],
               proposer: Proposer | None = None,
               config: TTIConfig = TTIConfig()) -> dict:
    """Run the full loop on one task; the ephemeral extension never escapes.

    base_language: the K the task is attempted under (a registry dict).
    Returns a report with the §XII evidence conjunction for any claimed
    TTI solve; `ephemeral_discarded` is asserted in the report itself.
    """
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in pairs]
    base_env = E.LanguageEnv(base=dict(base_language), label="K")
    report: dict = {"solved": False, "used_extension": None,
                    "proposals_tried": 0, "evidence": {},
                    "ephemeral_discarded": True}

    #  1. ordinary certified search under K
    results, _ = _search(pairs, base_env, config.search_budget_s)
    if results:
        report.update({"solved": True, "route": "ordinary"})
        return report
    report["route"] = "invention"

    #  2. the real failure evidence
    extraction = TX.extract(pairs, env=base_env,
                            budget_s=config.search_budget_s)
    if extraction["solved"]:            # a longer look solved it after all
        report.update({"solved": True, "route": "ordinary_second_look"})
        return report
    tfg = extraction["tfg"]
    report["tfg_digest"] = tfg.digest()

    #  3. ranked candidate extensions: rank over the MISSING catalogue only
    #  (proposals already in K are not extensions), then cap at top_k
    propose = proposer or mdl_fallback_proposer(config.catalogue)
    ranked = propose(tfg, len(config.catalogue))
    missing = [n for n in ranked
               if n in config.catalogue and n not in base_language]
    missing = missing[:config.top_k]

    #  4. try candidates in order; every certification is the frozen gate
    for name in missing:
        report["proposals_tried"] += 1
        extended = dict(base_language)
        extended[name] = config.catalogue[name]
        env_ext = E.LanguageEnv(base=extended, label=f"K+1")
        found, _ = _search(pairs, env_ext, config.search_budget_s)
        if not found:
            continue
        winner = found[0][0]
        uses = _uses_production(winner, name, env_ext)
        if not uses:
            continue
        loo_pass, loo_total = _loo(pairs, env_ext, config.loo_budget_s)
        #  ablation inside the loop: K alone already failed above, but re-run
        #  for the record with the same budget (the conjunction's own leg)
        ablation_found, _ = _search(pairs, base_env, config.search_budget_s)
        evidence = {
            "baseline_fails": not ablation_found,
            "production_proposed": True,
            "winner_uses_production": uses,
            "loo_all_folds_pass": loo_total > 0 and loo_pass == loo_total,
            "test_output_correct": None,     # filled by callers with test data
            "ablation_fails": not ablation_found,
        }
        certified = (evidence["baseline_fails"] and uses
                     and evidence["loo_all_folds_pass"])
        if certified:
            report.update({"solved": True, "used_extension": name,
                           "evidence": evidence,
                           "loo": [loo_pass, loo_total]})
            #  the ephemeral language dies here: env_ext goes out of scope and
            #  base_language was never mutated
            return report
    return report


def _uses_production(ast, name: str, env) -> bool:
    core = E.expand(ast, env)
    def walk(node):
        if not (isinstance(node, tuple) and len(node) == 2):
            return False
        if node[0] == name:
            return True
        return any(walk(arg) for arg in node[1] if isinstance(arg, tuple))
    return walk(core if core is not None else ast)


# --------------------------------------------------------------------------
# batch evaluation over dropout episodes (the loop's measurement harness)
# --------------------------------------------------------------------------

def evaluate_on_episodes(episodes: Sequence[Mapping[str, Any]],
                         proposer: Proposer | None = None,
                         config: TTIConfig = TTIConfig()) -> dict:
    """Run the loop on Stage-A episodes: each episode's crippled language is
    K minus the withheld production; success = the loop reconstructs it."""
    rows = []
    for episode in episodes:
        withheld = episode["target"]["name"]
        crippled = {k: v for k, v in V.REGISTRY.items() if k != withheld}
        pairs = [(np.asarray(d["input"]), np.asarray(d["output"]))
                 for d in episode["demonstrations"]]
        out = solve_task(pairs, crippled, proposer, config)
        rows.append({"withheld": withheld, "solved": out["solved"],
                     "route": out.get("route"),
                     "recovered": out.get("used_extension") == withheld,
                     "proposals_tried": out["proposals_tried"]})
    n = max(1, len(rows))
    return {"n": len(rows),
            "solved": sum(r["solved"] for r in rows) / n,
            "recovered_withheld": sum(r["recovered"] for r in rows) / n,
            "mean_proposals_tried": round(
                sum(r["proposals_tried"] for r in rows) / n, 3),
            "rows": rows}
