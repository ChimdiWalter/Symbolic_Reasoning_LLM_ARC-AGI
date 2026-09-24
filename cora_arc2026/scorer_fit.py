"""Fit the Stage-B scorer on the v1.2 corpus, per the sealed preregistration.

Preregistration: docs/SCORER_FIT_PREREGISTRATION_v1.md,
sha256 ed4ac9d2109e499aed0311b86e553db804ba597316a5dee17f3ad7be207dc860.

The minimal member of the frozen model family: a log-linear conditional model
over grammar-legal tokens, masked by the existing GrammarState. Non-LLM, no
hidden layer, 21 terminals by 19 inputs = 399 parameters. Nothing here reads a
target, a digest, a family label, a split, a seed or any generation metadata
at inference time.
"""
from __future__ import annotations

import json
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

#: the 18 frozen allowlisted features, in a fixed deterministic order
FEATURE_ORDER = (
    "defined_value_signature_count", "distinct_frontier_operator_count",
    "empty_frontier", "exact_count", "executed_not_exact_count",
    "fraction_wrong_mean", "frontier_term_count", "mean_cells_changed",
    "mean_fraction_changed", "n_demonstrations", "palette_extra_mean",
    "palette_introduced_mean", "palette_removed_mean", "same_shape_all",
    "search_deadline_hit", "shape_mismatch_count", "slot_fit_failed_count",
    "slot_fit_ok_count",
)

#: features zeroed by the aggregate-only control
CANDIDATE_ASSOCIATED = (
    "frontier_term_count", "distinct_frontier_operator_count",
    "slot_fit_failed_count", "slot_fit_ok_count", "executed_not_exact_count",
    "exact_count", "defined_value_signature_count", "fraction_wrong_mean",
    "palette_extra_mean", "shape_mismatch_count",
)


def terminals() -> list:
    v = CV.vocab()
    out = [("P", p) for p in v["partitions"]]
    out += [("S", p) for p in v["predicates"]]
    out += [("M", f) for f in v["key_features"]]
    out += [("PAINT",), ("EOS",)]
    return out


TERMINALS = terminals()
TERMINAL_INDEX = {t: i for i, t in enumerate(TERMINALS)}
DIM = len(FEATURE_ORDER) + 1          # bias plus features


class FeatureVector:
    """Evidence carrier with the shape propose_ast expects."""

    def __init__(self, features: dict):
        self.features = dict(features)

    def as_dict(self) -> dict:
        return dict(self.features)

    def vector(self) -> list:
        out = []
        for name in FEATURE_ORDER:
            value = self.features.get(name, 0)
            out.append(1.0 if value is True else 0.0 if value is False
                       else float(value))
        return out


class Standardizer:
    """Zero mean, unit variance, fitted on the fit set alone."""

    def __init__(self, mean=None, std=None):
        self.mean = list(mean) if mean else None
        self.std = list(std) if std else None

    def fit(self, vectors):
        n = len(vectors)
        self.mean = [sum(v[i] for v in vectors) / n for i in range(len(FEATURE_ORDER))]
        self.std = []
        for i in range(len(FEATURE_ORDER)):
            var = sum((v[i] - self.mean[i]) ** 2 for v in vectors) / n
            self.std.append(max(math.sqrt(var), 1e-6))
        return self

    def apply(self, vector) -> list:
        return [1.0] + [(vector[i] - self.mean[i]) / self.std[i]
                        for i in range(len(FEATURE_ORDER))]

    def to_dict(self) -> dict:
        return {"mean": self.mean, "std": self.std}


class LogLinearScorer:
    """Fitted scorer, interface-compatible with the unfitted EvidenceScorer."""

    def __init__(self, weights=None, standardizer: Standardizer | None = None):
        self.weights = weights or [[0.0] * DIM for _ in TERMINALS]
        self.standardizer = standardizer or Standardizer()

    def _x(self, evidence) -> list:
        vec = evidence.vector() if isinstance(evidence, FeatureVector) \
            else FeatureVector(evidence).vector()
        return self.standardizer.apply(vec)

    def logits(self, legal, x) -> list:
        out = []
        for token in legal:
            w = self.weights[TERMINAL_INDEX[token]]
            out.append(sum(w[i] * x[i] for i in range(DIM)))
        return out

    def token_logprobs(self, state, legal, evidence, interface) -> list:
        x = self._x(evidence)
        raw = self.logits(legal, x)
        top = max(raw)
        exps = [math.exp(r - top) for r in raw]
        total = sum(exps)
        return [math.log(e / total) for e in exps]

    def to_dict(self) -> dict:
        return {"terminals": [list(t) for t in TERMINALS],
                "feature_order": list(FEATURE_ORDER),
                "weights": self.weights,
                "standardizer": self.standardizer.to_dict()}

    @classmethod
    def from_dict(cls, data):
        std = Standardizer(data["standardizer"]["mean"],
                           data["standardizer"]["std"])
        return cls(weights=data["weights"], standardizer=std)


# --------------------------------------------------------------------------
# teacher-forced fitting
# --------------------------------------------------------------------------

def token_steps(tokens):
    """(legal_tokens, chosen) at every decision point of one target."""
    state = CV.GrammarState()
    steps = []
    for token in tokens:
        legal = state.legal_tokens()
        steps.append((legal, token))
        state = state.advance(token)
    return steps


def fit(examples, standardizer, *, lr=0.1, l2=1e-3, max_epochs=2000,
        plateau_epochs=200, eval_every=25, evaluate=None, log=print):
    """Full-batch gradient ascent on the masked conditional log-likelihood.

    ``examples`` is a list of (FeatureVector, token list). ``evaluate`` is the
    early-stopping callback returning exact@5; it never sees the test set.
    """
    scorer = LogLinearScorer(standardizer=standardizer)
    prepared = [(scorer.standardizer.apply(fv.vector()), token_steps(tokens))
                for fv, tokens in examples]
    best, best_epoch, best_weights = -1.0, 0, None
    history = []
    for epoch in range(1, max_epochs + 1):
        grad = [[0.0] * DIM for _ in TERMINALS]
        n_steps = 0
        for x, steps in prepared:
            for legal, chosen in steps:
                raw = scorer.logits(legal, x)
                top = max(raw)
                exps = [math.exp(r - top) for r in raw]
                total = sum(exps)
                for token, e in zip(legal, exps):
                    p = e / total
                    coeff = (1.0 if token == chosen else 0.0) - p
                    row = grad[TERMINAL_INDEX[token]]
                    for i in range(DIM):
                        row[i] += coeff * x[i]
                n_steps += 1
        for t in range(len(TERMINALS)):
            for i in range(DIM):
                scorer.weights[t][i] += lr * (grad[t][i] / n_steps
                                              - 2.0 * l2 * scorer.weights[t][i])
        if evaluate is not None and epoch % eval_every == 0:
            score = evaluate(scorer)
            history.append({"epoch": epoch, "early_stop_exact_at_5": score})
            log(f"  epoch {epoch:5d}  early-stop exact@5 {score:.4f}")
            if score > best:
                best, best_epoch = score, epoch
                best_weights = [row[:] for row in scorer.weights]
            elif epoch - best_epoch >= plateau_epochs:
                log(f"  plateau at epoch {epoch}, best {best:.4f} "
                    f"at epoch {best_epoch}")
                break
    if best_weights is not None:
        scorer.weights = best_weights
    return scorer, {"best_early_stop_exact_at_5": best, "best_epoch": best_epoch,
                    "history": history}
