"""Version 2's candidate stream (cora_neural_v2g2.search.enumerate_programs, imported unchanged), executed with or
without failure-derived pruning (prune.py) at an equal budget of EXECUTED candidates. Versions 3 and 4 also draw on
this stream; their own joint and constructed streams are not pruned here, since that would need new versions of
those modules. Pruned candidates are skipped without execution; the stream is read further instead. Both arms make
the same stream call, so they see the same candidates in the same order (the stream's budget argument only truncates
it); `class_sha` fingerprints the program-class prefix, whose generator has a wall-clock deadline, so that identity can
be checked. Each fit records its executed index, the native pick-set runs so far and the CPU so far.
"""
import hashlib
import time
from collections import Counter

from cora_neural_v2.rast import ASTError, to_sexpr
from cora_neural_v2g2 import search as S2
from cora_neural_v2g3 import delta as D
from cora_neural_v2g3 import select as SEL
from cora_neural_prune import prune as P

VERSION = "prune-v1"


def search(task, budget, prune=True, stream_factor=20, cpu_cap_s=None, keep=50, record_pruned=False, classes=True):
    train, tests = task["train"], task["test_inputs"]
    c0 = time.process_time()
    C = P.Constraints(train)
    n = pos = 0
    first_fit = first_fit_cpu = None
    preds, pred_at, pred_native, pred_cpu, programs, seen = [], [], [], [], [], {}
    pruned, pruned_progs = Counter(), []
    truncated = False
    info, class_sha = {}, hashlib.sha256()
    for prog, _ in S2.enumerate_programs(task, budget * stream_factor, classes=classes, info=info):
        if n >= budget:
            break
        if cpu_cap_s is not None and time.process_time() - c0 > cpu_cap_s:
            truncated = True
            break
        pos += 1
        if pos <= info.get("class_candidates", 0):
            class_sha.update(to_sexpr(prog).encode())
        key = P.family_key(prog) if prune else None
        if key is not None:
            reason = C.check(key)
            if reason:
                pruned[reason] += 1
                if record_pruned:
                    pruned_progs.append(prog)
                continue
        n += 1
        try:
            ds = D.deltas(prog, train, stop_early=True)
        except ASTError:
            continue
        if D.fits(ds, len(train)):
            if first_fit is None:
                first_fit, first_fit_cpu = n, round(time.process_time() - c0, 3)
            out = [D.execute(prog, t) for t in tests]
            if any(o is None for o in out):
                continue
            k = SEL.pred_key(out)
            if k not in seen:
                seen[k] = n
                if len(preds) < keep:
                    preds.append([o.tolist() for o in out])
                    pred_at.append(n)
                    pred_native.append(C.native_runs)
                    pred_cpu.append(round(time.process_time() - c0, 3))
                    programs.append(to_sexpr(prog))
        elif key is not None:
            C.learn(key, ds)
    rec = {"version": VERSION, "prune": prune, "budget": budget, "n_candidates": n, "stream_read": pos,
           "pruned": dict(pruned), "n_pruned": sum(pruned.values()), "learned": dict(C.learned),
           "native_runs": C.native_runs, "first_fit_at": first_fit, "first_fit_cpu": first_fit_cpu,
           "predictions": preds, "pred_at": pred_at, "pred_native": pred_native, "pred_cpu": pred_cpu,
           "programs": programs, "class_candidates": info.get("class_candidates"),
           "class_sha": class_sha.hexdigest()[:16], "n_distinct_predictions": len(seen), "cpu_truncated": truncated,
           "cpu_s": round(time.process_time() - c0, 3)}
    if record_pruned:
        rec["pruned_programs"] = pruned_progs
    return rec
