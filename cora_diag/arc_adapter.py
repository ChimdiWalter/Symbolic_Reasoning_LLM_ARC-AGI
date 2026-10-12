"""ARC adapter: recorded ARC traces -> domain-neutral observations (diagnose.py keys).

Units are attempts of the reach v1 measurement:
- a full-data run, which sees all training demonstrations;
- an outer adaptive leave-one-out fold, which sees all but one.

Only permitted fields are read: proposals and their view, the extraction's
support flags, the engine's verdict, failure stage, timeout, deadline
counts, its inner leave-one-out (failed inner folds and their programs), and
the static census of training subsets. A fold may also use its unlabelled
inputs: the removed demonstration's input and the task's test inputs.

Never read: heldout_exact, heldout_distinguish, full_ext_reproduces,
same_as_full, predictions scored against targets, or any field of the
full-data run when diagnosing a fold.
"""
import numpy as np


def _top_sha(ind):
    return ((ind.get("program") or (ind.get("near_solve") or {}).get("partial") or {}) or {}).get("sha")


def _engine_obs(engine):
    if not engine:
        return {}
    ind = ((engine.get("trace") or {}).get("inductions") or [{}])[0]
    loo = ind.get("loo") or {}
    top = _top_sha(ind)
    failed = list(loo.get("failed") or [])
    changed = any((d.get("fold_program") or {}).get("sha") not in (None, top) for d in loo.get("divergence") or [])
    timeout = bool(engine.get("timeout"))
    stage = engine.get("failure_stage")
    return {"accepted": bool(engine.get("accepted")), "hard_cap_hit": timeout,
            "deadline_hits": int(sum((engine.get("deadline_hits") or {}).values())),
            "verdict_reached": (not timeout) and (bool(engine.get("accepted")) or stage is not None),
            "top_level_fit": bool(engine.get("accepted")) or stage == "loo",
            "rederivations": int(loo.get("folds") or 0), "rederivations_failed": len(failed),
            "rederivation_changed_program": changed, "_failed_inner": failed}


def _excluded(view, train_idx, failed_inner, census):
    """Was the evidence view cut or ineligible in any failed inner subset?"""
    if view is None or not failed_inner:
        return None
    hits = []
    for j in failed_inner:
        if j >= len(train_idx):
            continue
        sub = "".join(str(i) for i in train_idx if i != train_idx[j])
        rec = census.get(sub)
        if rec is None:
            return None
        hits.append(view not in rec["kept"])
    return any(hits) if hits else None


def _disagree(proposals, inputs):
    """Direct execution of each fitting repair, in its own view, on the permitted unlabelled inputs."""
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import SegmentationVariant as SV, to_grid_pairs
    from cora_reach import relations as REL
    preds = []
    for p in proposals:
        V = next(x for x in SV if x.value == p["variant"])
        outs = []
        for grid in inputs:
            g = to_grid_pairs([(np.asarray(grid), np.asarray(grid))])[0][0]
            out = np.asarray(grid).copy()
            for o in S.segment(g, V, S.background_for(g, V)):
                for (r, c) in (REL.apply(p["family"], p.get("params") or {}, set(o.cells), np.asarray(grid)) or ()):
                    if 0 <= r < out.shape[0] and 0 <= c < out.shape[1]:
                        out[r, c] = o.color
            outs.append(out.tolist())
        preds.append(outs)
    return any(x != preds[0] for x in preds[1:])


def unit_observations(task, n_train, fold, measure_row, diag_row, census, unlabelled_inputs):
    """fold None = the full-data run; else the outer fold that removed demonstration `fold`."""
    train_idx = [i for i in range(n_train) if i != fold] if fold is not None else list(range(n_train))
    if fold is None:
        proposals = [{"family": p["family"], "variant": p["variant"], "params": p.get("params") or {}}
                     for p in measure_row["fc"]["proposals"]]
        engine = (diag_row or {}).get("A_E_WALL")
        if not engine:
            we = measure_row.get("with_e") or {}
            engine = {"accepted": we.get("accepted"), "timeout": we.get("timeout"), "failure_stage": we.get("failure_stage")}
        support = None
    else:
        b = (diag_row or {}).get("B_WALL") or {}
        proposals = [{"family": p["family"], "variant": p["variant"], "params": p.get("params") or {}}
                     for p in (b.get("proposals") or [])]
        engine = b.get("engine")
        variants = ((b.get("analysis") or {}).get("variants") or {})
        support = any(v.get("support_ok") for v in variants.values()) if variants else None
    obs = {"repairs_proposed": len(proposals), "repair_support_ok": support, "competing_repairs": len(proposals)}
    eo = _engine_obs(engine) if proposals else {}
    failed_inner = eo.pop("_failed_inner", [])
    obs.update(eo)
    view = proposals[0]["variant"] if proposals else None
    obs["evidence_unit_excluded_in_failed_rederivation"] = _excluded(view, train_idx, failed_inner, census)
    if len(proposals) >= 2:
        obs["competing_repairs_disagree"] = _disagree(proposals, unlabelled_inputs)
    return {k: v for k, v in obs.items() if v is not None}
