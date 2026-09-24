"""Fit the Stage-B scorer on the v1.2 corpus, per the sealed preregistration.

Version 4, after adversarial review. Three changes the review forced, all
made before any fit was run:

  * the scorer is now STATE-CONDITIONAL. It previously accepted the grammar
    state and ignored it, so it scored block one and block two identically
    while the metric demanded an ordered match. A probe that knew the target's
    exact token multiset scored only 2 of 32 under the old design, and 0 of 20
    on episodes containing a Select, so the experiment could not have tested
    its hypothesis.
  * features constant on the fit set are DROPPED before standardizing. Their
    weights could never move off zero, and one of them was being manipulated
    by a control, which was therefore inert.
  * ablation vectors are filled with the fit-set mean rather than raw zero, so
    an ablated input is neutral rather than an extreme extrapolation.

Log-linear conditional model over grammar-legal tokens, masked by the existing
GrammarState. Non-LLM, no hidden layer. Nothing reads a target, digest, family
label, split, seed or generation metadata at inference.
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
for _p in (TTI, HERE):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from cora_tti import constructive_vocabulary as CV                # noqa: E402

#: the 18 frozen allowlisted features, fixed deterministic order
FEATURE_ORDER = (
    "defined_value_signature_count", "distinct_frontier_operator_count",
    "empty_frontier", "exact_count", "executed_not_exact_count",
    "fraction_wrong_mean", "frontier_term_count", "mean_cells_changed",
    "mean_fraction_changed", "n_demonstrations", "palette_extra_mean",
    "palette_introduced_mean", "palette_removed_mean", "same_shape_all",
    "search_deadline_hit", "shape_mismatch_count", "slot_fit_failed_count",
    "slot_fit_ok_count",
)

#: features the aggregate-only control ablates
CANDIDATE_ASSOCIATED = (
    "frontier_term_count", "distinct_frontier_operator_count",
    "slot_fit_failed_count", "slot_fit_ok_count", "executed_not_exact_count",
    "exact_count", "defined_value_signature_count", "fraction_wrong_mean",
    "palette_extra_mean", "shape_mismatch_count",
)

#: structural decoder-state inputs, scaled by their frozen grammar bounds
STATE_FEATURES = ("blocks_done", "selects_in_block", "in_block",
                  "awaiting_paint", "stages_used")


def terminals() -> list:
    v = CV.vocab()
    out = [("P", p) for p in v["partitions"]]
    out += [("S", p) for p in v["predicates"]]
    out += [("M", f) for f in v["key_features"]]
    out += [("PAINT",), ("EOS",)]
    return out


TERMINALS = terminals()
TERMINAL_INDEX = {t: i for i, t in enumerate(TERMINALS)}


def state_vector(state) -> list:
    v = CV.vocab()
    return [state.blocks_done / max(v["max_blocks"], 1),
            state.selects_in_block / max(v["max_selects"], 1),
            1.0 if state.in_block else 0.0,
            1.0 if state.awaiting_paint else 0.0,
            state.stages_used / max(v["max_stages"], 1)]


class FeatureVector:
    """Evidence carrier with the shape propose_ast expects."""

    def __init__(self, features: dict):
        self.features = dict(features)

    def as_dict(self) -> dict:
        return dict(self.features)

    def raw(self, order) -> list:
        out = []
        for name in order:
            value = self.features.get(name, 0)
            out.append(1.0 if value is True else 0.0 if value is False
                       else float(value))
        return out


class Standardizer:
    """Zero mean, unit variance, fitted on the fit set alone.

    Features with no variance on the fit set are dropped, not floored: a
    constant input can never move its weights, and keeping it invites a
    control to manipulate a column that cannot act.
    """

    def __init__(self, order=None, mean=None, std=None, dropped=None):
        self.order = tuple(order) if order else None
        self.mean = list(mean) if mean else None
        self.std = list(std) if std else None
        self.dropped = tuple(dropped) if dropped else ()

    def fit(self, vectors):
        n = len(vectors)
        keep, dropped = [], []
        for i, name in enumerate(FEATURE_ORDER):
            mean = sum(v[i] for v in vectors) / n
            var = sum((v[i] - mean) ** 2 for v in vectors) / n
            (keep if math.sqrt(var) > 1e-9 else dropped).append(
                (name, i, mean, math.sqrt(var)))
        self.order = tuple(k[0] for k in keep)
        self.mean = [k[2] for k in keep]
        self.std = [k[3] for k in keep]
        self.dropped = tuple(d[0] for d in dropped)
        return self

    def standardize(self, fv: FeatureVector) -> list:
        raw = fv.raw(self.order)
        return [(raw[i] - self.mean[i]) / self.std[i]
                for i in range(len(self.order))]

    def mean_vector(self) -> FeatureVector:
        """The fit-set mean, which standardizes to exactly zero."""
        return FeatureVector({name: self.mean[i]
                              for i, name in enumerate(self.order)})

    def neutralize(self, fv: FeatureVector, names) -> FeatureVector:
        """Replace the named features with the fit-set mean, leaving the rest."""
        out = dict(fv.features)
        for i, name in enumerate(self.order):
            if name in names:
                out[name] = self.mean[i]
        return FeatureVector(out)

    def to_dict(self) -> dict:
        return {"order": list(self.order), "mean": self.mean,
                "std": self.std, "dropped": list(self.dropped)}


class LogLinearScorer:
    """Fitted scorer, interface-compatible with the unfitted EvidenceScorer."""

    def __init__(self, weights=None, standardizer: Standardizer | None = None):
        self.standardizer = standardizer or Standardizer()
        self.dim = 1 + len(self.standardizer.order or ()) + len(STATE_FEATURES)
        self.weights = weights or [[0.0] * self.dim for _ in TERMINALS]

    def inputs(self, evidence, state) -> list:
        fv = evidence if isinstance(evidence, FeatureVector) \
            else FeatureVector(evidence)
        return [1.0] + self.standardizer.standardize(fv) + state_vector(state)

    def logits(self, legal, x) -> list:
        out = []
        for token in legal:
            w = self.weights[TERMINAL_INDEX[token]]
            out.append(sum(w[i] * x[i] for i in range(self.dim)))
        return out

    @staticmethod
    def _logsoftmax(raw) -> list:
        top = max(raw)
        exps = [math.exp(r - top) for r in raw]
        total = sum(exps)
        return [math.log(e / total) for e in exps]

    def token_logprobs(self, state, legal, evidence, interface) -> list:
        return self._logsoftmax(self.logits(legal, self.inputs(evidence, state)))

    def sequence_logprob(self, evidence, tokens) -> tuple:
        """Teacher-forced log-likelihood of one target, and its step count."""
        total, state, steps = 0.0, CV.GrammarState(), 0
        for token in tokens:
            legal = state.legal_tokens()
            logs = self.token_logprobs(state, legal, evidence, None)
            total += logs[legal.index(token)]
            state = state.advance(token)
            steps += 1
        return total, steps

    def to_dict(self) -> dict:
        return {"terminals": [list(t) for t in TERMINALS],
                "state_features": list(STATE_FEATURES),
                "weights": self.weights,
                "standardizer": self.standardizer.to_dict()}


def token_steps(tokens):
    """(state, legal, chosen) at every decision point of one target."""
    state = CV.GrammarState()
    steps = []
    for token in tokens:
        steps.append((state, state.legal_tokens(), token))
        state = state.advance(token)
    return steps


def fit(examples, standardizer, *, lr=0.5, l2=1e-3, max_epochs=2000,
        plateau_epochs=200, eval_every=25, evaluate=None, log=print):
    """Full-batch gradient ascent on the masked conditional log-likelihood."""
    scorer = LogLinearScorer(standardizer=standardizer)
    dim = scorer.dim
    prepared = []
    for fv, tokens in examples:
        prepared.append([(scorer.inputs(fv, state), legal, chosen)
                         for state, legal, chosen in token_steps(tokens)])
    best, best_epoch, best_weights = -float("inf"), 0, None
    history = []
    epoch = 0
    for epoch in range(1, max_epochs + 1):
        grad = [[0.0] * dim for _ in TERMINALS]
        n_steps = 0
        for steps in prepared:
            for x, legal, chosen in steps:
                raw = scorer.logits(legal, x)
                top = max(raw)
                exps = [math.exp(r - top) for r in raw]
                total = sum(exps)
                for token, e in zip(legal, exps):
                    coeff = (1.0 if token == chosen else 0.0) - e / total
                    row = grad[TERMINAL_INDEX[token]]
                    for i in range(dim):
                        row[i] += coeff * x[i]
                n_steps += 1
        for t in range(len(TERMINALS)):
            row, g = scorer.weights[t], grad[t]
            for i in range(dim):
                row[i] += lr * (g[i] / n_steps - 2.0 * l2 * row[i])
        if evaluate is not None and epoch % eval_every == 0:
            score = evaluate(scorer)
            history.append({"epoch": epoch, "validation_metric": round(score, 6)})
            log(f"  epoch {epoch:5d}  validation mean target logprob {score:.5f}")
            if score > best:
                best, best_epoch = score, epoch
                best_weights = [r[:] for r in scorer.weights]
            elif epoch - best_epoch >= plateau_epochs:
                log(f"  plateau at epoch {epoch}; best {best:.5f} at {best_epoch}")
                break
    final = LogLinearScorer(weights=[r[:] for r in scorer.weights],
                            standardizer=standardizer)
    if best_weights is not None:
        scorer.weights = best_weights
    return scorer, final, {"best_validation_metric": round(best, 6),
                           "best_epoch": best_epoch, "epochs_run": epoch,
                           "dropped_constant_features": list(standardizer.dropped),
                           "parameters": len(TERMINALS) * dim,
                           "history": history}
