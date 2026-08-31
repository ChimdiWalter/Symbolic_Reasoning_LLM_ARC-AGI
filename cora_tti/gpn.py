"""Grammar Proposal Network — prototype (phase P2).

A deliberately small, fully deterministic, NON-LLM proposer: numpy softmax
regression over hand-rolled Typed-Failure-Graph features, with two heads:

    name head          q(production name | TFG)      — Stage-A reconstruction
    result-type head   q(result type      | TFG)     — signature-level evidence

The two-head design is the bridge past operator-ID recall: the name head cannot
generalize to held-out families by construction, so family-holdout evaluation
reads the SIGNATURE head, which predicts constructor-space structure (result
type; arg types come with the Stage-B sketch head). The prototype's job is to
prove the data pipeline and the "learn where to search" interface — a graph
network replaces the linear model later without changing either.

Contract (cora_parent.interfaces.GrammarProposalNetwork): propose() returns a
ranked list of Extension sketches. It PRIORITIZES; the immutable verifier
decides. No task identities are ever featurized (the TFG rejects them at
construction). Everything is seeded and serializable to JSON.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cora_parent.interfaces import Extension, GrammarProposalNetwork   # noqa: E402
from cora_parent.tfg import NODE_KINDS                                 # noqa: E402

_HASH_BUCKETS = 8


# --------------------------------------------------------------------------
# featurization (deterministic; no task identity by construction)
# --------------------------------------------------------------------------

def _bucket(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16) % _HASH_BUCKETS


def featurize(tfg_json: Mapping[str, Any]) -> np.ndarray:
    nodes = tfg_json["nodes"]
    kind_counts = {k: 0 for k in NODE_KINDS}
    delta = {"same_shape": [], "shrinks": [], "grows": []}
    palette = {"introduced": [], "removed": [], "n_in": [], "n_out": []}
    shape_fraction, execution = [], {}
    for n in nodes:
        kind_counts[n["kind"]] = kind_counts.get(n["kind"], 0) + 1
        attrs = n.get("attrs", {})
        if n["kind"] == "delta_signature":
            for key in delta:
                delta[key].append(float(bool(attrs.get(key, False))))
        elif n["kind"] == "palette_change":
            for key in palette:
                palette[key].append(float(attrs.get(key, 0)))
        elif n["kind"] == "shape_change":
            shape_fraction.append(float(attrs.get("fraction_changed", 0.0)))
        elif n["kind"] == "execution":
            execution = attrs

    def mean(xs):
        return float(np.mean(xs)) if xs else 0.0

    frontier, goal = tfg_json["interface"]
    onehot_frontier = [0.0] * _HASH_BUCKETS
    onehot_goal = [0.0] * _HASH_BUCKETS
    onehot_frontier[_bucket(frontier)] = 1.0
    onehot_goal[_bucket(goal)] = 1.0

    vector = (
        [float(kind_counts[k]) for k in NODE_KINDS]
        + [mean(delta[k]) for k in ("same_shape", "shrinks", "grows")]
        + [mean(palette[k]) for k in ("introduced", "removed", "n_in", "n_out")]
        + [mean(shape_fraction)]
        + [np.log1p(float(execution.get(k, 0))) for k in
           ("typed", "generated", "rejected", "max_depth", "semantic_classes")]
        + [float(bool(execution.get("deadline_hit", False)))]
        + onehot_frontier + onehot_goal
        + [float(len(tfg_json["edges"]))]
    )
    return np.asarray(vector, dtype=np.float64)


FEATURE_DIM = len(featurize({"interface": ["Grid", "Grid"],
                             "nodes": [], "edges": []}))


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------

def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


@dataclass
class Vocab:
    names: list
    result_types: list

    @classmethod
    def from_rows(cls, rows: Sequence[Mapping[str, Any]]) -> "Vocab":
        return cls(sorted({r["target"]["name"] for r in rows}),
                   sorted({r["target"]["result_type"] for r in rows}))


class GPNPrototype(GrammarProposalNetwork):
    """Two-head softmax regression over TFG features."""

    def __init__(self, vocab: Vocab, seed: int = 0):
        rng = np.random.default_rng(seed)
        self.vocab = vocab
        scale = 0.01
        self.w_name = rng.normal(0, scale, (FEATURE_DIM, len(vocab.names)))
        self.w_rtype = rng.normal(0, scale, (FEATURE_DIM, len(vocab.result_types)))
        self.mu = np.zeros(FEATURE_DIM)
        self.sigma = np.ones(FEATURE_DIM)

    # -- training -----------------------------------------------------------
    def fit(self, rows: Sequence[Mapping[str, Any]], epochs: int = 300,
            lr: float = 0.5, l2: float = 1e-4, seed: int = 0) -> dict:
        X = np.stack([featurize(r["tfg"]) for r in rows])
        self.mu = X.mean(axis=0)
        self.sigma = X.std(axis=0)
        self.sigma[self.sigma == 0] = 1.0
        X = (X - self.mu) / self.sigma
        y_name = np.array([self.vocab.names.index(r["target"]["name"])
                           for r in rows])
        y_rtype = np.array([self.vocab.result_types.index(
            r["target"]["result_type"]) for r in rows])
        rng = np.random.default_rng(seed)
        n = len(rows)
        for _ in range(epochs):
            order = rng.permutation(n)
            for head, w, y in (("name", self.w_name, y_name),
                               ("rtype", self.w_rtype, y_rtype)):
                probs = _softmax(X[order] @ w)
                grad = probs
                grad[np.arange(n), y[order]] -= 1.0
                w -= lr * (X[order].T @ grad / n + l2 * w)
        return self.evaluate(rows)

    def _scores(self, tfg_json, w) -> np.ndarray:
        x = (featurize(tfg_json) - self.mu) / self.sigma
        return _softmax(x @ w)

    def evaluate(self, rows: Sequence[Mapping[str, Any]], top_k: int = 3) -> dict:
        hit1_n = hitk_n = hit1_t = 0
        for r in rows:
            p_name = self._scores(r["tfg"], self.w_name)
            ranked = [self.vocab.names[i] for i in np.argsort(-p_name)]
            hit1_n += ranked[0] == r["target"]["name"]
            hitk_n += r["target"]["name"] in ranked[:top_k]
            p_rt = self._scores(r["tfg"], self.w_rtype)
            best_rt = self.vocab.result_types[int(np.argmax(p_rt))]
            hit1_t += best_rt == r["target"]["result_type"]
        n = max(1, len(rows))
        return {"n": len(rows), "name_top1": hit1_n / n,
                f"name_top{top_k}": hitk_n / n, "result_type_top1": hit1_t / n}

    def evaluate_signature_only(self, rows: Sequence[Mapping[str, Any]]) -> dict:
        """Family-holdout view: the name head is structurally blind to unseen
        names, so only the result-type head is meaningful there."""
        report = self.evaluate(rows)
        return {"n": report["n"], "result_type_top1": report["result_type_top1"]}

    # -- GrammarProposalNetwork contract -------------------------------------
    def propose(self, failure, top_k: int) -> Sequence[Extension]:
        tfg_json = failure.to_json() if hasattr(failure, "to_json") else failure
        p_name = self._scores(tfg_json, self.w_name)
        p_rtype = self._scores(tfg_json, self.w_rtype)
        best_rtype = self.vocab.result_types[int(np.argmax(p_rtype))]
        order = np.argsort(-p_name)[:top_k]
        return [Extension(kind="production",
                          signature=f"? -> {best_rtype}",
                          payload={"name": self.vocab.names[i]},
                          mdl=1.0,
                          provenance={"proposer": "GPNPrototype",
                                      "p": round(float(p_name[i]), 6)})
                for i in order]

    # -- persistence ---------------------------------------------------------
    def to_json(self) -> dict:
        return {"vocab": {"names": self.vocab.names,
                          "result_types": self.vocab.result_types},
                "w_name": self.w_name.tolist(), "w_rtype": self.w_rtype.tolist(),
                "mu": self.mu.tolist(), "sigma": self.sigma.tolist(),
                "feature_dim": FEATURE_DIM}

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "GPNPrototype":
        model = cls(Vocab(list(data["vocab"]["names"]),
                          list(data["vocab"]["result_types"])))
        model.w_name = np.asarray(data["w_name"])
        model.w_rtype = np.asarray(data["w_rtype"])
        model.mu = np.asarray(data["mu"])
        model.sigma = np.asarray(data["sigma"])
        return model


# --------------------------------------------------------------------------
# dataset helpers
# --------------------------------------------------------------------------

def load_rows(path: Path) -> list:
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def train_from_files(train_file: Path, holdout_file: Path | None = None,
                     seed: int = 0, epochs: int = 300) -> tuple:
    rows = load_rows(train_file)
    model = GPNPrototype(Vocab.from_rows(rows), seed=seed)
    train_metrics = model.fit(rows, epochs=epochs, seed=seed)
    report = {"train": train_metrics}
    if holdout_file is not None and Path(holdout_file).exists():
        holdout_rows = load_rows(holdout_file)
        if holdout_rows:
            report["family_holdout_signature_only"] = \
                model.evaluate_signature_only(holdout_rows)
    return model, report
