"""Fixed-state replay metrics (identical stored states and actions for every arm; isolates ranking/allocation, not
online exploration) and task-clustered paired uncertainty.

    res = evaluate(states, choices, mode="revise")    # choices: one action index per state
    ci = paired_ci(states, choices_a, choices_b)       # bootstrap over task clusters of the difference in exact successes
"""
import zlib

import numpy as np

from harness import episode_io as IO


def cluster(meta):
    return meta["family"] if meta["split"].endswith("_syn") else meta["task_id"]


def outcome_rows(states, choices, mode="revise"):
    rows = []
    for st, j in zip(states, choices):
        lab = IO.action_labels(st, mode)
        rows.append({"y2": lab["y2"][j], "y1": lab["y1"][j], "b2": lab["base2"], "b1": lab["base1"],
                     "n_exec": lab["n_exec"][j], "kind": st["actions"][j][0], "variant": st["meta"]["variant"],
                     "cluster": cluster(st["meta"]), "revised": st["actions"][j][0] not in ("STOP", "COMMIT"),
                     "oracle2": float(lab["y2"].max()),
                     "unc": "structural" if st["glob"][5] > 0.5 else ("behavioural" if st["glob"][6] > 0.5 else "settled")})
    return rows


def summarize(rows):
    y2 = np.array([r["y2"] for r in rows])
    b2 = np.array([r["b2"] for r in rows])
    y1 = np.array([r["y1"] for r in rows])
    b1 = np.array([r["b1"] for r in rows])
    rev = np.array([r["revised"] for r in rows])
    by, unc = {}, {}
    for r in rows:
        u = unc.setdefault(r["unc"], [0, 0, 0])
        u[0] += r["y2"]
        u[1] += r["b2"]
        u[2] += 1
        v = by.setdefault(r["variant"], [0, 0])
        v[0] += r["y2"]
        v[1] += 1
    return {"states": len(rows), "exact2": float(y2.sum()), "exact1": float(y1.sum()), "base2": float(b2.sum()),
            "gains2": int(((y2 > 0) & (b2 == 0)).sum()), "losses2": int(((y2 == 0) & (b2 > 0)).sum()),
            "harm1": int(((y1 == 0) & (b1 > 0)).sum()),
            "false_revision_rate": float((((y1 == 0) & (b1 > 0)) & rev).sum() / max(1, (rev & (b1 > 0)).sum())),
            "revisions": int(rev.sum()), "mean_exec": float(np.mean([r["n_exec"] for r in rows])) if rows else 0.0,
            "oracle2": float(sum(r["oracle2"] for r in rows)), "by_variant": {k: v[0] for k, v in sorted(by.items())},
            "by_variant_n": {k: v[1] for k, v in sorted(by.items())},
            "by_uncertainty": {k: {"exact2": v[0], "base2": v[1], "n": v[2]} for k, v in sorted(unc.items())},
            "kinds": {k: int(sum(1 for r in rows if r["kind"] == k)) for k in sorted({r["kind"] for r in rows})}}


def evaluate(states, choices, mode="revise"):
    return summarize(outcome_rows(states, choices, mode))


def paired_ci(rows_a, rows_b, n_boot=2000, seed=0):
    """95% bootstrap interval (resampling task clusters) of sum(exact2_a - exact2_b)."""
    cl = {}
    for ra, rb in zip(rows_a, rows_b):
        cl.setdefault(ra["cluster"], []).append(ra["y2"] - rb["y2"])
    keys = sorted(cl)
    d = np.array([sum(cl[k]) for k in keys])
    rng = np.random.default_rng(seed)
    boots = [d[rng.integers(0, len(d), len(d))].sum() for _ in range(n_boot)] if len(d) else [0.0]
    return {"diff": float(d.sum()), "lo": float(np.percentile(boots, 2.5)), "hi": float(np.percentile(boots, 97.5)),
            "clusters": len(keys), "discordant_clusters": int((d != 0).sum())}


def seed_rng(*xs):
    return np.random.default_rng(zlib.crc32("|".join(map(str, xs)).encode()))
