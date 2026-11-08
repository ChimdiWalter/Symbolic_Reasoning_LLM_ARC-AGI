"""Split-guarded task loading. Policy-side tasks carry demonstrations and query inputs only.

    tasks = load_split("S_train")            # [{"task_id", "split", "train": [(in, out)], "test_inputs": [...]}]
    labels = source_labels("S_train")        # {task_id: [test output, ...]}  (S_train / S_select ONLY)
    syn = synthetic_task("v3d_ctrl_ring_recolour", seed=3, n_visible=3, n_withheld=2)

S_confirm (real and synthetic) is refused unless experiments/architecture_sweep_20261026/FROZEN_FINALISTS.json
exists (written only after all five screens, when finalists are frozen). ARC_eval_dev answers are never loaded here:
they are read by harness/scorer.py in its own process.
"""
import json
import os

from harness import paths as P

MANIFEST = os.path.join(P.EXP, "splits", "SPLITS_MANIFEST.json")
SEALED = os.path.join(P.EXP, "splits", "S_CONFIRM_SEALED.json")
FINALISTS = os.path.join(P.EXP, "FROZEN_FINALISTS.json")
_CACHE = {}


class SplitRefused(PermissionError):
    pass


def manifest():
    if "man" not in _CACHE:
        with P.open_allowed(MANIFEST) as f:
            _CACHE["man"] = json.load(f)
    return _CACHE["man"]


def _challenges(which):
    k = "ch:" + which
    if k not in _CACHE:
        with P.open_allowed(P.TRAIN_CHALLENGES if which == "train" else P.EVAL_CHALLENGES) as f:
            _CACHE[k] = json.load(f)
    return _CACHE[k]


def confirm_ok():
    return os.path.exists(FINALISTS)


def split_ids(name):
    m = manifest()
    if name in ("S_train", "S_select", "ARC_eval_dev"):
        return list(m[name])
    if name == "ARC_eval_dev_file_order":
        return list(m["ARC_eval_dev_file_order"])
    if name in ("S_confirm", "S_confirm_syn"):
        if not confirm_ok():
            raise SplitRefused("S_confirm is sealed until FROZEN_FINALISTS.json exists (after all five screens)")
        with P.open_allowed(SEALED) as f:
            return list(json.load(f)[name])
    if name in ("S_train_syn", "S_select_syn"):
        return list(m["synthetic"][name])
    raise KeyError(name)


def task_record(tid, split):
    src = _challenges("eval" if split == "ARC_eval_dev" else "train")[tid]
    return {"task_id": tid, "split": split, "train": [(p["input"], p["output"]) for p in src["train"]],
            "test_inputs": [t["input"] for t in src["test"]]}


def load_split(name, limit=None):
    if name.endswith("_syn"):
        raise KeyError("synthetic splits are families: use synthetic_task")
    ids = split_ids(name)
    if limit is not None:
        ids = ids[:limit]
    return [task_record(t, name) for t in ids]


def source_labels(name):
    """Test outputs of source tasks (S_train / S_select only): they supervise training outcomes and define withheld
    targets of source episodes; they never enter an observation state."""
    if name not in ("S_train", "S_select"):
        raise SplitRefused(f"no source labels for {name}")
    with P.open_allowed(P.TRAIN_SOLUTIONS, role="source_labels") as f:
        sol = json.load(f)
    return {t: sol[t] for t in split_ids(name)}


def family_module(family):
    P.ensure_import_paths()
    from cora_neural_v2g2 import families as F2
    from cora_neural_v2g3 import families_v3 as F3
    if family in F2.FAMILIES:
        return F2
    if family in F3.FAMILIES:
        return F3
    raise KeyError(family)


def family_program_text(family):
    spec = family_module(family).FAMILIES[family]
    return spec[1] if len(spec) == 3 else spec[2]


def synthetic_task(family, seed, n_visible=3, n_withheld=2):
    """(visible task, withheld outputs, family program text) or None. Outputs come from native CORA executing the
    family's program on fresh scenes (execution-verified by construction)."""
    m = manifest()["synthetic"]
    if family not in m["families"]:
        raise KeyError(family)
    if family not in m["S_train_syn"] and family not in m["S_select_syn"] and not confirm_ok():
        raise SplitRefused(f"{family} is in S_confirm_syn (sealed)")
    F = family_module(family)
    r = F.make_task(family, seed, n_demos=n_visible + n_withheld - 1)
    if r is None:
        return None
    task, last = r
    pairs = [(a, b) for a, b in task["train"]] + [(task["test_inputs"][0], last.tolist())]
    vis, wh = pairs[:n_visible], pairs[n_visible:]
    vt = {"task_id": f"syn:{family}#{seed}", "split": "syn", "family": family, "train": vis,
          "test_inputs": [a for a, _ in wh]}
    return vt, [b for _, b in wh], family_program_text(family)
