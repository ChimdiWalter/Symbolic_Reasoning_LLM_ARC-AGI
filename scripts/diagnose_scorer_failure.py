"""Diagnose why the candidate-associated features failed to add value.

Implements docs/SCORER_FAILURE_DIAGNOSTIC_PREREG_v1.md
sha256 6e95a7a8d26a8e1f42609b8548cab132b1e1081bb754b0fce461a6e80f4a128e,
sealed before any outcome was computed.

DIAGNOSIS ONLY. It does not modify the corpus, the controls, the official
scorer or the frozen verdict, and it cannot earn a positive result.
"""
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import scorer_fit as SF                         # noqa: E402
from cora_tti import constructive_vocabulary as CV                # noqa: E402

CORPUS = os.path.join(HERE, "outputs", "tti", "v12_corpus")
OUT = os.path.join(HERE, "outputs", "tti", "scorer_diagnosis.json")

DEMO = ("n_demonstrations", "mean_cells_changed", "mean_fraction_changed",
        "palette_introduced_mean", "palette_removed_mean")
CANDIDATE = ("frontier_term_count", "distinct_frontier_operator_count",
             "slot_fit_failed_count", "slot_fit_ok_count",
             "executed_not_exact_count", "exact_count",
             "defined_value_signature_count", "fraction_wrong_mean",
             "palette_extra_mean", "search_deadline_hit")
FULL = DEMO + CANDIDATE

N_TERM = len(SF.TERMINALS)
EPOCHS = 400
LR = 0.5
L2 = 1e-3
HIDDEN = 32
FOLDS = 5
CRITERION_FOLDS = 4
CRITERION_DELTA = 0.01


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

def load_train():
    eps = []
    for name in sorted(os.listdir(CORPUS)):
        if name.startswith("slot") and name.endswith(".json"):
            with open(os.path.join(CORPUS, name)) as handle:
                d = json.load(handle)
            if d["admitted"] and d.get("episode") \
                    and d["episode"]["split"] == "train":
                eps.append(d["episode"])
    return sorted(eps, key=lambda e: e["target_digest"])


def raw_descriptor(tfg_json) -> dict:
    """Richer readout built only from fields already in the stored graph."""
    nodes = tfg_json.get("nodes", [])
    out = {f"op_bucket_{i}": 0 for i in range(16)}
    outcomes = Counter()
    surfaces, ops = [], set()
    cells, fracs, extras = [], [], []
    shape_mismatch = 0
    defined = 0
    execution = {}
    for node in nodes:
        kind = node.get("kind")
        attrs = node.get("attrs", {})
        if kind == "frontier_term":
            op = str(attrs.get("op", ""))
            bucket = int(hashlib.sha1(op.encode()).hexdigest(), 16) % 16
            out[f"op_bucket_{bucket}"] += 1
            outcomes[str(attrs.get("outcome"))] += 1
            surfaces.append(float(attrs.get("surface_nodes", 0)))
            ops.add(op)
        elif kind == "value_signature" and attrs.get("defined"):
            defined += 1
            if attrs.get("cells_wrong") is not None:
                cells.append(float(attrs["cells_wrong"]))
            if attrs.get("fraction_wrong") is not None:
                fracs.append(float(attrs["fraction_wrong"]))
            if attrs.get("palette_extra") is not None:
                extras.append(float(attrs["palette_extra"]))
            if not attrs.get("shape_matches"):
                shape_mismatch += 1
        elif kind == "execution":
            execution = attrs
    for name in ("typecheck_failed", "typed", "slot_fit_failed",
                 "slot_fit_ok", "executed_not_exact", "exact"):
        out[f"outcome_{name}"] = outcomes.get(name, 0)
    for label, seq in (("surface", surfaces), ("cells_wrong", cells),
                       ("fraction_wrong", fracs), ("palette_extra", extras)):
        out[f"{label}_min"] = min(seq) if seq else 0.0
        out[f"{label}_mean"] = (sum(seq) / len(seq)) if seq else 0.0
        out[f"{label}_max"] = max(seq) if seq else 0.0
    out["distinct_ops"] = len(ops)
    out["defined_signatures"] = defined
    out["shape_mismatch"] = shape_mismatch
    for key in ("typed", "generated", "rejected", "max_depth",
                "semantic_classes"):
        out[f"exec_{key}"] = float(execution.get(key, 0) or 0)
    return out


RAW_ORDER = None


def episode_rows(ep):
    """(feature dict, raw descriptor, token list) for one episode."""
    return (ep["model_view"]["features"], raw_descriptor(ep["full_engine_tfg"]),
            [tuple(t) for t in ep["target_tokens"]])


# --------------------------------------------------------------------------
# step expansion, shared by every readout
# --------------------------------------------------------------------------

def expand(rows, names, source):
    """Flatten episodes into per-token decision steps.

    Returns raw evidence matrix, state matrix, legality mask, chosen index and
    the episode index of every step.
    """
    ev, st, mask, chosen, owner = [], [], [], [], []
    for index, row in enumerate(rows):
        features = row[source]
        vec = [float(features.get(n, 0) or 0) if not isinstance(
            features.get(n, 0), bool) else float(features.get(n, 0))
            for n in names]
        state = CV.GrammarState()
        for token in row[2]:
            legal = state.legal_tokens()
            m = np.zeros(N_TERM, dtype=bool)
            for t in legal:
                m[SF.TERMINAL_INDEX[t]] = True
            ev.append(vec)
            st.append(SF.state_vector(state))
            mask.append(m)
            chosen.append(SF.TERMINAL_INDEX[token])
            owner.append(index)
            state = state.advance(token)
    ev = np.asarray(ev, dtype=float) if names else np.zeros((len(chosen), 0))
    return (ev, np.asarray(st, dtype=float), np.asarray(mask),
            np.asarray(chosen), np.asarray(owner))


def standardize(train_ev, ev):
    if train_ev.shape[1] == 0:
        return ev, None
    mean = train_ev.mean(axis=0)
    std = train_ev.std(axis=0)
    keep = std > 1e-9
    if not keep.any():
        return np.zeros((ev.shape[0], 0)), keep
    return (ev[:, keep] - mean[keep]) / std[keep], keep


def design(ev_std, st):
    return np.hstack([np.ones((ev_std.shape[0], 1)), ev_std, st])


def masked_logsoftmax(logits, mask):
    z = np.where(mask, logits, -np.inf)
    z = z - z.max(axis=1, keepdims=True)
    e = np.where(mask, np.exp(z), 0.0)
    return z - np.log(e.sum(axis=1, keepdims=True))


def fit_linear(X, mask, chosen):
    W = np.zeros((N_TERM, X.shape[1]))
    onehot = np.zeros((X.shape[0], N_TERM))
    onehot[np.arange(X.shape[0]), chosen] = 1.0
    for _ in range(EPOCHS):
        logits = X @ W.T
        p = np.exp(masked_logsoftmax(logits, mask))
        G = (onehot - p).T @ X / X.shape[0]
        W += LR * (G - 2.0 * L2 * W)
    return W


def score_linear(W, X, mask, chosen, owner, n_episodes):
    lp = masked_logsoftmax(X @ W.T, mask)[np.arange(X.shape[0]), chosen]
    per = np.zeros(n_episodes)
    cnt = np.zeros(n_episodes)
    np.add.at(per, owner, lp)
    np.add.at(cnt, owner, 1.0)
    return float(np.mean(per / np.maximum(cnt, 1)))


def init_matrix(rows, cols, offset=0):
    i = np.arange(rows).reshape(-1, 1)
    j = np.arange(cols).reshape(1, -1)
    return 0.1 * np.sin(9973 * i + 101 * j + offset)


def fit_mlp(X, mask, chosen):
    W1 = init_matrix(HIDDEN, X.shape[1])
    W2 = init_matrix(N_TERM, HIDDEN, offset=17)
    onehot = np.zeros((X.shape[0], N_TERM))
    onehot[np.arange(X.shape[0]), chosen] = 1.0
    n = X.shape[0]
    for _ in range(EPOCHS):
        H = np.tanh(X @ W1.T)
        p = np.exp(masked_logsoftmax(H @ W2.T, mask))
        dlog = (onehot - p)
        G2 = dlog.T @ H / n
        dH = (dlog @ W2) * (1.0 - H ** 2)
        G1 = dH.T @ X / n
        W2 += LR * (G2 - 2.0 * L2 * W2)
        W1 += LR * (G1 - 2.0 * L2 * W1)
    return W1, W2


def score_mlp(W, X, mask, chosen, owner, n_episodes):
    W1, W2 = W
    lp = masked_logsoftmax(np.tanh(X @ W1.T) @ W2.T, mask)[
        np.arange(X.shape[0]), chosen]
    per = np.zeros(n_episodes)
    cnt = np.zeros(n_episodes)
    np.add.at(per, owner, lp)
    np.add.at(cnt, owner, 1.0)
    return float(np.mean(per / np.maximum(cnt, 1)))


def readout(rows, folds, names, source, model):
    """Five-fold held-out mean per-token target log-likelihood."""
    out = []
    for f in range(FOLDS):
        tr = [r for i, r in enumerate(rows) if folds[i] != f]
        te = [r for i, r in enumerate(rows) if folds[i] == f]
        ev_tr, st_tr, m_tr, c_tr, o_tr = expand(tr, names, source)
        ev_te, st_te, m_te, c_te, o_te = expand(te, names, source)
        if names:
            mean, std = ev_tr.mean(axis=0), ev_tr.std(axis=0)
            keep = std > 1e-9
            a = (ev_tr[:, keep] - mean[keep]) / std[keep] if keep.any() \
                else np.zeros((ev_tr.shape[0], 0))
            b = (ev_te[:, keep] - mean[keep]) / std[keep] if keep.any() \
                else np.zeros((ev_te.shape[0], 0))
        else:
            a = np.zeros((ev_tr.shape[0], 0))
            b = np.zeros((ev_te.shape[0], 0))
        Xtr, Xte = design(a, st_tr), design(b, st_te)
        if model == "M1":
            W = fit_linear(Xtr, m_tr, c_tr)
            out.append(score_linear(W, Xte, m_te, c_te, o_te, len(te)))
        else:
            W = fit_mlp(Xtr, m_tr, c_tr)
            out.append(score_mlp(W, Xte, m_te, c_te, o_te, len(te)))
    return out


def criterion(delta):
    wins = sum(1 for d in delta if d > 0)
    return {"per_fold": [round(d, 6) for d in delta],
            "folds_positive": wins, "mean": round(float(np.mean(delta)), 6),
            "meets": wins >= CRITERION_FOLDS
            and float(np.mean(delta)) >= CRITERION_DELTA}


def permuted_readout(rows, folds):
    """FULL with real candidate features vs FULL with conditionally permuted ones."""
    real, perm, pairs = [], [], []
    for f in range(FOLDS):
        tr = [r for i, r in enumerate(rows) if folds[i] != f]
        te_idx = [i for i in range(len(rows)) if folds[i] == f]
        te = [rows[i] for i in te_idx]
        ev_tr, st_tr, m_tr, c_tr, _ = expand(tr, FULL, 0)
        mean, std = ev_tr.mean(axis=0), ev_tr.std(axis=0)
        keep = std > 1e-9
        Xtr = design((ev_tr[:, keep] - mean[keep]) / std[keep], st_tr)
        W = fit_linear(Xtr, m_tr, c_tr)

        #  nearest neighbour inside the fold by standardized DEMO vector,
        #  ties broken by ascending target digest
        demo_tr = np.asarray([[float(r[0].get(n, 0) or 0) for n in DEMO]
                              for r in tr])
        dmean, dstd = demo_tr.mean(axis=0), demo_tr.std(axis=0)
        dkeep = dstd > 1e-9
        demo_te = np.asarray([[float(r[0].get(n, 0) or 0) for n in DEMO]
                              for r in te])
        Z = (demo_te[:, dkeep] - dmean[dkeep]) / dstd[dkeep]
        partner = []
        for i in range(len(te)):
            best, best_d = None, None
            for j in range(len(te)):
                if i == j:
                    continue
                d = float(np.linalg.norm(Z[i] - Z[j]))
                if best_d is None or d < best_d - 1e-12:
                    best, best_d = j, d
            partner.append(best)
            pairs.append({"fold": f, "demo_distance": round(best_d, 5)})

        swapped = []
        for i, row in enumerate(te):
            merged = dict(row[0])
            donor = te[partner[i]][0]
            for n in CANDIDATE:
                merged[n] = donor.get(n, 0)
            swapped.append((merged, row[1], row[2]))

        for label, data, sink in (("real", te, real), ("perm", swapped, perm)):
            ev, st, m, c, o = expand(data, FULL, 0)
            X = design((ev[:, keep] - mean[keep]) / std[keep], st)
            sink.append(score_linear(W, X, m, c, o, len(data)))
    return real, perm, pairs


def multinomial_heldout(rows, folds, labels):
    """Held-out accuracy predicting a categorical target from DEMO_ONLY."""
    classes = sorted(set(labels))
    idx = {c: i for i, c in enumerate(classes)}
    X = np.asarray([[float(r[0].get(n, 0) or 0) for n in DEMO] for r in rows])
    y = np.asarray([idx[l] for l in labels])
    correct = majority = 0
    for f in range(FOLDS):
        tr = folds != f
        te = ~tr
        mean, std = X[tr].mean(axis=0), X[tr].std(axis=0)
        keep = std > 1e-9
        A = np.hstack([np.ones((tr.sum(), 1)),
                       (X[tr][:, keep] - mean[keep]) / std[keep]])
        B = np.hstack([np.ones((te.sum(), 1)),
                       (X[te][:, keep] - mean[keep]) / std[keep]])
        W = np.zeros((len(classes), A.shape[1]))
        onehot = np.zeros((A.shape[0], len(classes)))
        onehot[np.arange(A.shape[0]), y[tr]] = 1.0
        for _ in range(600):
            z = A @ W.T
            z -= z.max(axis=1, keepdims=True)
            p = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
            W += 0.5 * ((onehot - p).T @ A / A.shape[0] - 2e-3 * W)
        pred = (B @ W.T).argmax(axis=1)
        correct += int((pred == y[te]).sum())
        top = Counter(y[tr].tolist()).most_common(1)[0][0]
        majority += int((y[te] == top).sum())
    n = len(rows)
    return {"classes": len(classes), "heldout_accuracy": round(correct / n, 4),
            "majority_baseline": round(majority / n, 4), "n": n}


def main():
    eps = load_train()
    rows = [episode_rows(e) for e in eps]
    folds = np.asarray([i % FOLDS for i in range(len(rows))])
    print(f"diagnosis on {len(rows)} training episodes, {FOLDS} folds, "
          f"sizes {Counter(folds.tolist())}")

    global RAW_ORDER
    RAW_ORDER = tuple(sorted(rows[0][1]))
    print(f"raw descriptor width {len(RAW_ORDER)}\n")

    results = {}
    print("held-out mean per-token target log-likelihood, by readout:")
    for model in ("M1", "M2"):
        for label, names, source in (("floor", (), 0), ("demo_only", DEMO, 0),
                                     ("candidate_only", CANDIDATE, 0),
                                     ("full", FULL, 0),
                                     ("raw_tfg", RAW_ORDER, 1)):
            key = f"{model}_{label}"
            results[key] = readout(rows, folds, names, source, model)
            print(f"  {key:22s} folds "
                  f"{' '.join(f'{v:+.4f}' for v in results[key])}  "
                  f"mean {np.mean(results[key]):+.5f}")

    deltas = {}
    for model in ("M1", "M2"):
        deltas[f"{model}_candidate_over_demo"] = criterion(
            np.asarray(results[f"{model}_full"])
            - np.asarray(results[f"{model}_demo_only"]))
        deltas[f"{model}_raw_over_demo"] = criterion(
            np.asarray(results[f"{model}_raw_tfg"])
            - np.asarray(results[f"{model}_demo_only"]))
        deltas[f"{model}_demo_over_floor"] = criterion(
            np.asarray(results[f"{model}_demo_only"])
            - np.asarray(results[f"{model}_floor"]))
        deltas[f"{model}_candidate_only_over_floor"] = criterion(
            np.asarray(results[f"{model}_candidate_only"])
            - np.asarray(results[f"{model}_floor"]))

    print("\nincremental value against the frozen criterion "
          f"(>{CRITERION_FOLDS-1}/5 folds positive and mean >= {CRITERION_DELTA}):")
    for key, d in deltas.items():
        print(f"  {key:34s} mean {d['mean']:+.5f}  folds+ {d['folds_positive']}/5"
              f"  meets {d['meets']}")

    real, perm, pairs = permuted_readout(rows, folds)
    perm_delta = criterion(np.asarray(real) - np.asarray(perm))
    print(f"\nconditional permutation: real {np.mean(real):+.5f}  "
          f"permuted {np.mean(perm):+.5f}  delta mean {perm_delta['mean']:+.5f}"
          f"  folds+ {perm_delta['folds_positive']}/5  meets {perm_delta['meets']}")

    #  redundancy: predict each candidate feature from DEMO_ONLY
    Xd = np.asarray([[float(r[0].get(n, 0) or 0) for n in DEMO] for r in rows])
    redundancy = {}
    for name in CANDIDATE:
        y = np.asarray([float(r[0].get(name, 0) or 0) for r in rows])
        resid = 0.0
        for f in range(FOLDS):
            tr, te = folds != f, folds == f
            A = np.hstack([np.ones((tr.sum(), 1)), Xd[tr]])
            B = np.hstack([np.ones((te.sum(), 1)), Xd[te]])
            beta, *_ = np.linalg.lstsq(A, y[tr], rcond=None)
            resid += float(((y[te] - B @ beta) ** 2).sum())
        total = float(((y - y.mean()) ** 2).sum())
        redundancy[name] = {
            "variance": round(float(y.var()), 5),
            "zero_fraction": round(float((y == 0).mean()), 4),
            "heldout_residual_fraction": round(resid / total, 4)
            if total > 1e-12 else None}

    #  collisions of the ten-feature summary
    sig = defaultdict(list)
    for i, r in enumerate(rows):
        key = tuple(round(float(r[0].get(n, 0) or 0), 6) for n in CANDIDATE)
        sig[key].append(i)
    groups = [v for v in sig.values() if len(v) > 1]
    collision_targets = [len({eps[i]["target_digest"] for i in g}) for g in groups]
    collisions = {
        "distinct_candidate_vectors": len(sig), "episodes": len(rows),
        "colliding_groups": len(groups),
        "episodes_in_collisions": sum(len(g) for g in groups),
        "max_group_size": max((len(g) for g in groups), default=0),
        "distinct_targets_within_collisions": collision_targets,
    }
    print(f"\ncandidate summary collisions: {len(sig)} distinct vectors for "
          f"{len(rows)} episodes; {len(groups)} colliding groups covering "
          f"{sum(len(g) for g in groups)} episodes")

    #  contrast pairs
    dmean, dstd = Xd.mean(axis=0), Xd.std(axis=0)
    dk = dstd > 1e-9
    Z = (Xd[:, dk] - dmean[dk]) / dstd[dk]
    Xc = np.asarray([[float(r[0].get(n, 0) or 0) for n in CANDIDATE] for r in rows])
    cmean, cstd = Xc.mean(axis=0), Xc.std(axis=0)
    ck = cstd > 1e-9
    Zc = (Xc[:, ck] - cmean[ck]) / cstd[ck]
    contrast = []
    for i in range(len(rows)):
        d = np.linalg.norm(Z - Z[i], axis=1)
        d[i] = np.inf
        j = int(d.argmin())
        contrast.append({
            "demo_distance": round(float(d[j]), 5),
            "candidate_distance": round(float(np.linalg.norm(Zc[i] - Zc[j])), 5),
            "targets_differ": eps[i]["target_digest"] != eps[j]["target_digest"],
            "same_family": eps[i]["structural_family"] == eps[j]["structural_family"],
        })
    near = [c for c in contrast if c["demo_distance"] <= np.percentile(
        [x["demo_distance"] for x in contrast], 25)]
    print(f"contrast pairs: {len(contrast)}; of the closest quartile by "
          f"demonstration distance, {sum(1 for c in near if c['targets_differ'])}"
          f"/{len(near)} have different targets")

    #  generator dominance
    part0 = [r[2][0][1] for r in rows]
    feat0 = [next(t[1] for t in r[2] if t[0] == "M") for r in rows]
    blocks = [sum(1 for t in r[2] if t[0] == "PAINT") for r in rows]
    dominance = {"block0_partition": multinomial_heldout(rows, folds, part0),
                 "block0_feature": multinomial_heldout(rows, folds, feat0),
                 "block_count": multinomial_heldout(rows, folds,
                                                    [str(b) for b in blocks])}
    print("\ngenerator dominance, predicting the target from demonstration "
          "statistics alone:")
    for key, v in dominance.items():
        print(f"  {key:20s} accuracy {v['heldout_accuracy']:.4f} vs majority "
              f"{v['majority_baseline']:.4f} over {v['classes']} classes")

    cand_m1 = deltas["M1_candidate_over_demo"]["meets"]
    cand_m2 = deltas["M2_candidate_over_demo"]["meets"]
    raw_any = (deltas["M1_raw_over_demo"]["meets"]
               or deltas["M2_raw_over_demo"]["meets"])
    demo_floor = (deltas["M1_demo_over_floor"]["meets"]
                  or deltas["M2_demo_over_floor"]["meets"])
    if cand_m2 and not cand_m1:
        classification = "MODEL_CAPACITY_LIMIT"
    elif not cand_m1 and not cand_m2 and raw_any:
        classification = "MODEL_VIEW_COMPRESSION_LOSS"
    elif not cand_m1 and not cand_m2 and not raw_any and demo_floor:
        classification = "CANDIDATE_SIGNAL_REDUNDANT_ON_V12"
    else:
        classification = "MIXED_OR_INCONCLUSIVE"

    report = {
        "note": "DIAGNOSIS ONLY. The corpus, controls, official scorer and the "
                "frozen verdict are unchanged.",
        "preregistration_sha256": hashlib.sha256(
            open(os.path.join(HERE, "docs",
                              "SCORER_FAILURE_DIAGNOSTIC_PREREG_v1.md"),
                 "rb").read()).hexdigest(),
        "episodes": len(rows), "folds": FOLDS,
        "fold_sizes": dict(Counter(folds.tolist())),
        "epochs": EPOCHS, "hidden_units": HIDDEN,
        "criterion": {"folds_positive_min": CRITERION_FOLDS,
                      "mean_delta_min": CRITERION_DELTA},
        "readouts": {k: [round(v, 6) for v in vals] for k, vals in results.items()},
        "readout_means": {k: round(float(np.mean(v)), 6) for k, v in results.items()},
        "deltas": deltas,
        "conditional_permutation": {"real_per_fold": [round(v, 6) for v in real],
                                    "permuted_per_fold": [round(v, 6) for v in perm],
                                    "delta": perm_delta},
        "redundancy": redundancy,
        "collisions": collisions,
        "contrast_pairs_summary": {
            "n": len(contrast),
            "median_demo_distance": round(float(np.median(
                [c["demo_distance"] for c in contrast])), 5),
            "closest_quartile_with_different_targets":
                sum(1 for c in near if c["targets_differ"]),
            "closest_quartile_n": len(near),
            "closest_quartile_same_family":
                sum(1 for c in near if c["same_family"])},
        "generator_dominance": dominance,
        "classification": classification,
    }
    with open(OUT, "w") as handle:
        json.dump(report, handle, indent=1)
    print(f"\nPRINCIPAL CLASSIFICATION: {classification}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
