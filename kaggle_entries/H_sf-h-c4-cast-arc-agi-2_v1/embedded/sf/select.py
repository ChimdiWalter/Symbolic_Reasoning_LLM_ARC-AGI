"""Selection of two attempts from a fixed candidate pool, and the submission schema check.

Neural rules (no CORA): votes = number of decoding augmentations that produced the candidate; score = mean
teacher-forced log-probability over the first k scoring augmentations.
"""
import numpy as np

from . import grids as G


def mean_score(c, k=None):
    s = c.get("scores") or []
    s = s[:k] if k else s
    return float(np.mean(s)) if s else float("-inf")


def rank(pool, method="vote_score", k=None):
    """Candidate indices, best first. Ties are broken by the generation order (stable)."""
    ix = list(range(len(pool)))
    if method == "vote_score":
        key = lambda i: (-pool[i]["votes"], -mean_score(pool[i], k))
    elif method == "score":
        key = lambda i: (-mean_score(pool[i], k),)
    elif method == "vote_gen":
        key = lambda i: (-pool[i]["votes"], -max(pool[i]["gen_logp"]))
    elif method == "score_plus_logvotes":
        key = lambda i: (-(mean_score(pool[i], k) + 2.0 * np.log(pool[i]["votes"] + 1e-9)),)
    else:
        raise ValueError(method)
    return sorted(ix, key=key)


def fallback_grids(test_input):
    g = G.to_list(np.asarray(test_input))
    return [g, g]


def two_attempts(pool, test_input, order):
    picks = [pool[i]["grid"] for i in order[:2]]
    fb = fallback_grids(test_input)
    while len(picks) < 2:
        picks.append(fb[len(picks)])
    return {"attempt_1": picks[0], "attempt_2": picks[1]}


def check_submission(sub, challenges):
    """Schema check against the challenge file: every task, one entry per test input, two valid grids each."""
    problems = []
    if not isinstance(sub, dict):
        return ["submission is not a dict"]
    for tid, t in challenges.items():
        e = sub.get(tid)
        if not isinstance(e, list) or len(e) != len(t["test"]):
            problems.append(f"{tid}: wrong entry count")
            continue
        for j, a in enumerate(e):
            if not isinstance(a, dict) or set(a) != {"attempt_1", "attempt_2"}:
                problems.append(f"{tid}[{j}]: keys")
                continue
            for k in ("attempt_1", "attempt_2"):
                if not G.is_valid_grid(a[k]):
                    problems.append(f"{tid}[{j}].{k}: invalid grid")
    extra = set(sub) - set(challenges)
    if extra:
        problems.append(f"{len(extra)} unknown task ids")
    return problems
