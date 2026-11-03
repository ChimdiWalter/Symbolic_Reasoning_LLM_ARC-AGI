"""TTT pilot (authorized by the author on 26 Oct; Kaggle L4x4 only, at most 2 h of runtime in total).

  smoke: one LoRA configuration per GPU. Peak memory and time per step at the longest pilot sequence and at 8,192
         tokens, adapter inference time, and a leave-one-demonstration-out (LOO) check on three NON-pilot puzzles
         (adapt on all demonstrations but the last, then predict the last one's output: its NLL and greedy vote
         before and after). Demonstrations only.
  pilot: for each pilot puzzle, in one process: the LOO check, the no-TTT arm (fresh adapter = the base model) and
         the TTT arm (a fresh adapter trained on all demonstrations), both with the same inference. Query answers
         are never read.
  python -m sf.pilot smoke|pilot --rank R --challenges C --model M --out DIR --tasks a,b,c [--cfg JSON]
"""
import argparse
import json
import os
import time

import numpy as np
import torch

from . import grids as G
from . import textfmt as F
from .lm import LM
from .predict import predict_output, task_seed
from .runner import atomic_json
from .ttt import TTT


def peak_reset():
    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()


def peak():
    if not torch.cuda.is_available():
        return 0.0
    torch.cuda.synchronize()
    return round(torch.cuda.max_memory_allocated() / 1e9, 2)


def device():
    return os.environ.get("SF_DEVICE", "cuda:0")


def pairs_of(task):
    return [(np.asarray(p["input"]), np.asarray(p["output"])) for p in task["train"]]


def loo_eval(lm, pairs, n_aug, seed):
    """Predict the last demonstration's output from the others: NLL of the true output (identity prompt), and
    whether the top vote of a greedy decode under n_aug augmentations equals it."""
    ctx, (hin, hout) = pairs[:-1], pairs[-1]
    p = F.prompt_ids(ctx, hin)
    nll = -lm.score(p, [F.target_ids(hout)])[0]
    res = predict_output(lm, ctx, hin, n_gen=n_aug, n_score=0, seed=seed)
    pool = sorted(res["candidates"], key=lambda c: -c["votes"])
    top = pool[0]["grid"] if pool else None
    hit_any = any(c["grid"] == G.to_list(hout) for c in pool)
    return {"nll": round(nll, 4), "top_vote_correct": top == G.to_list(hout), "in_pool": hit_any,
            "n_cands": len(pool), "s": res["total_s"]}


def synthetic_pairs(n_tokens, rng):
    """Random 30 x 30 pairs until the LOO sequence reaches about n_tokens (memory test only)."""
    pairs = []
    while sum(len(F.grid_ids(i)) + len(F.grid_ids(o)) + 12 for i, o in pairs) < n_tokens:
        pairs.append((rng.integers(0, 10, (30, 30)), rng.integers(0, 10, (30, 30))))
    return pairs


def smoke(a, cfg, ch):
    lm = LM(a.model, device=device())
    out = {"cfg": cfg, "load_s": round(lm.load_s, 1),
           "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"}
    peak_reset()
    ttt = TTT(lm, rank=cfg["rank"], alpha=cfg["alpha"], lr=cfg["lr"], max_tokens=cfg.get("max_tokens", 8192))
    out["lora_params"] = ttt.n_params
    out["mem_after_wrap_gb"] = peak()
    big = cfg["big_task"]
    rng = np.random.default_rng(0)
    for name, pairs in (("longest_pilot", pairs_of(ch[big])), ("synthetic_8192", synthetic_pairs(8000, rng))):
        peak_reset()
        st = ttt.train(pairs, steps=cfg.get("mem_steps", 4), seed=1, log_every=1)
        out[f"mem_{name}"] = {"peak_gb": peak(), "s_per_step": round(st["train_s"] / max(1, st["steps"]), 2),
                              "tokens_per_step": st["tokens"] // max(1, st["steps"]), "loss": st["loss_curve"]}
        atomic_json(os.path.join(a.out, f"smoke_{a.rank}.json"), out)
    peak_reset()
    ttt.reset(seed=3)
    t0 = time.time()
    x = ch[big]["test"][0]["input"]
    r = predict_output(lm, pairs_of(ch[big]), np.asarray(x), cfg["n_gen"], cfg["n_score"], task_seed(big, 0))
    out["adapter_inference"] = {"task": big, "s": round(time.time() - t0, 2), "peak_gb": peak(),
                                "n_cands": len(r["candidates"]), "prompt_tokens": r["prompt_tokens"]}
    out["loo"] = []
    for tid in cfg["loo_tasks"]:
        pairs = pairs_of(ch[tid])
        ttt.reset(seed=task_seed(tid, 99))
        before = loo_eval(lm, pairs, cfg["loo_augs"], task_seed(tid, 7))
        peak_reset()
        st = ttt.train(pairs[:-1], steps=cfg["steps"], seed=task_seed(tid, 99))
        after = loo_eval(lm, pairs, cfg["loo_augs"], task_seed(tid, 7))
        out["loo"].append({"task": tid, "before": before, "after": after, "train": st, "peak_gb": peak()})
        atomic_json(os.path.join(a.out, f"smoke_{a.rank}.json"), out)
    out["lm_stats"] = lm.stats
    out["done"] = True
    atomic_json(os.path.join(a.out, f"smoke_{a.rank}.json"), out)


def pilot(a, cfg, ch):
    lm = LM(a.model, device=device())
    ttt = TTT(lm, rank=cfg["rank"], alpha=cfg["alpha"], lr=cfg["lr"], max_tokens=cfg.get("max_tokens", 8192))
    for tid in a.tasks.split(","):
        path = os.path.join(a.out, "pilot", f"{tid}.json")
        if os.path.exists(path):
            continue
        pairs = pairs_of(ch[tid])
        rec = {"task": tid, "cfg": cfg, "n_demos": len(pairs)}
        seed = task_seed(tid, 99)
        if cfg.get("loo", True) and len(pairs) >= 2:
            ttt.reset(seed)
            before = loo_eval(lm, pairs, cfg["loo_augs"], task_seed(tid, 7))
            peak_reset()
            st = ttt.train(pairs[:-1], steps=cfg["steps"], seed=seed)
            rec["loo"] = {"before": before, "after": loo_eval(lm, pairs, cfg["loo_augs"], task_seed(tid, 7)),
                          "train": st, "peak_gb": peak()}
        for arm in ("no_ttt", "ttt"):
            ttt.reset(seed)
            peak_reset()
            st = None
            if arm == "ttt":
                st = ttt.train(pairs, steps=cfg["steps"], seed=seed)
            t0 = time.time()
            outs = [predict_output(lm, pairs, np.asarray(x["input"]), cfg["n_gen"], cfg["n_score"],
                                   task_seed(tid, j)) for j, x in enumerate(ch[tid]["test"])]
            rec[arm] = {"outputs": outs, "train": st, "infer_s": round(time.time() - t0, 2), "peak_gb": peak()}
        atomic_json(path, rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["smoke", "pilot"])
    ap.add_argument("--rank", type=int, default=0)
    ap.add_argument("--challenges", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tasks", default="")
    ap.add_argument("--cfg", required=True)
    a = ap.parse_args()
    cfg = json.loads(a.cfg)
    ch = json.load(open(a.challenges))
    os.makedirs(os.path.join(a.out, "pilot"), exist_ok=True)
    (smoke if a.mode == "smoke" else pilot)(a, cfg, ch)


if __name__ == "__main__":
    main()
