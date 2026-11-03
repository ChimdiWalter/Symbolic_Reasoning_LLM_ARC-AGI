"""Per-task candidate generation without test-time training.

For each test input: build the prompt under several augmentations (D8 symmetry, colour permutation keeping 0,
demonstration order), decode greedily with the grid constraint, map every decoded grid back to the original frame,
and score every distinct candidate under every augmentation (teacher forcing). The full candidate pool is returned
so that selection rules can be compared offline on the same pool.
"""
import copy
import math
import time
import zlib

import numpy as np

from . import grids as G
from . import textfmt as F

MAX_PROMPT = 12000            # tokens; longer prompts drop their longest demonstrations first
BATCH_TOKENS = 64000          # cap on (batch size x (prompt + answer)) tokens for one decoding batch


def task_seed(task_id, idx):
    return zlib.crc32(f"{task_id}:{idx}".encode()) & 0x7FFFFFFF


def fit_prompt(pairs, test_input, max_tokens=MAX_PROMPT):
    """Drop the longest demonstrations until the prompt fits; returns (kept pair indices, n_tokens)."""
    keep = list(range(len(pairs)))

    def n_tok(ix):
        return len(F.prompt_ids([pairs[i] for i in ix], test_input))
    n = n_tok(keep)
    while n > max_tokens and len(keep) > 1:
        longest = max(keep, key=lambda i: len(F.grid_ids(pairs[i][0])) + len(F.grid_ids(pairs[i][1])))
        keep.remove(longest)
        n = n_tok(keep)
    return keep, n


def predict_output(lm, pairs, test_input, n_gen, n_score, seed, max_prompt=MAX_PROMPT, deadline=None, _prefix_token=None):
    """Candidate pool for one test input. n_gen augmentations decode; n_score >= n_gen augmentations score.
    The first n_gen scoring augmentations are the decoding ones."""
    t0 = time.time()
    keep, n_prompt = fit_prompt(pairs, test_input, max_prompt)
    kp = [pairs[i] for i in keep]
    augs = G.make_augs(max(n_gen, n_score), len(kp), seed)
    prompts = []
    for a in augs:
        ap, at = a.apply_task(kp, [test_input])
        prompts.append(F.prompt_ids(ap, at[0]))
    cands = {}
    gen_info = []
    bs = max(1, BATCH_TOKENS // (max(len(p) for p in prompts) + F.MAX_OUT_TOKENS))
    i = 0
    while i < n_gen:
        idx = list(range(i, min(n_gen, i + bs)))
        for j, (toks, lp) in zip(idx, lm.greedy([prompts[j] for j in idx])):
            g = F.parse_ids(toks)
            if g is None or not toks or toks[-1] != F.IME:
                gen_info.append({"aug": j, "valid": False})
                continue
            orig = augs[j].inv(np.asarray(g))
            k = G.key(orig)
            c = cands.setdefault(k, {"grid": G.to_list(orig), "votes": 0, "gen_augs": [], "gen_logp": []})
            c["votes"] += 1
            c["gen_augs"].append(j)
            c["gen_logp"].append(round(lp, 4))
            gen_info.append({"aug": j, "valid": True})
        i = idx[-1] + 1
        if deadline is not None and time.time() > deadline:
            break
    pool = list(cands.values())
    t_gen = time.time() - t0
    n_scored = 0
    for c in pool:
        c["scores"] = []
    def output():
        return {"candidates": pool, "kept_demos": keep, "prompt_tokens": n_prompt, "n_gen": n_gen,
                "n_score_done": n_scored, "augs": [a.describe() for a in augs[:max(n_gen, n_score)]],
                "gen_info": gen_info, "gen_s": round(t_gen, 2), "total_s": round(time.time() - t0, 2)}
    try:
        if pool:
            for j, a in enumerate(augs[:n_score]):
                if deadline is not None and time.time() > deadline and j >= 1:
                    break
                targets = [F.target_ids(a.fwd(np.asarray(c["grid"]))) for c in pool]
                raw = list(lm.score(prompts[j], targets))
                if len(raw) != len(pool):
                    raise ValueError("incomplete all-candidate scoring pass")
                if any(isinstance(s, (bool, np.bool_)) or not isinstance(s, (int, float, np.integer, np.floating))
                       or not math.isfinite(float(s)) for s in raw):
                    raise ValueError("nonfinite or nonnumeric candidate score")
                values = [round(float(s), 4) for s in raw]
                # Commit this augmentation only after every candidate's score is valid.
                for c, s in zip(pool, values):
                    c["scores"].append(s)
                n_scored += 1
    except Exception as error:
        # A reused exception object must never carry a stale prefix into another query.
        for attribute in ("completed_score_prefix", "completed_score_prefix_token", "recovered_query_index", "prefix_checkpoint_error"):
            if hasattr(error, attribute):
                delattr(error, attribute)
        if n_scored > 0 and all(len(c["scores"]) == n_scored for c in pool):
            error.completed_score_prefix = copy.deepcopy(output())
            error.completed_score_prefix_token = _prefix_token
            error.completed_score_prefix["recovery"] = {"kind": "complete_score_prefix",
                                                       "error": type(error).__name__}
        raise
    return output()


def predict_task(lm, task_id, task, n_gen=8, n_score=8, max_prompt=MAX_PROMPT, deadline=None, on_query=None):
    pairs = [(np.asarray(p["input"]), np.asarray(p["output"])) for p in task["train"]]
    outs = []
    for idx, t in enumerate(task["test"]):
        prefix_token = object()
        try:
            if deadline is not None and time.time() >= deadline:
                raise TimeoutError("task deadline reached before query")
            outs.append(predict_output(lm, pairs, np.asarray(t["input"]), n_gen, n_score, task_seed(task_id, idx),
                                       max_prompt, deadline, _prefix_token=prefix_token))
            if on_query is not None:
                on_query(idx, outs[:])
        except Exception as e:
            recovered = (getattr(e, "completed_score_prefix", None)
                         if getattr(e, "completed_score_prefix_token", None) is prefix_token else None)
            if recovered is not None:
                outs.append(recovered)
                e.recovered_query_index = idx
                if on_query is not None:
                    try:
                        on_query(idx, outs[:])
                    except Exception as checkpoint_error:
                        # Preserve both the scoring fault and in-memory prefix if persistence fails.
                        e.prefix_checkpoint_error = type(checkpoint_error).__name__
            e.partial_outputs = outs
            raise
    return outs
