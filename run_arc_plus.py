from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
import os
import sys
import hashlib

# orjson is fast; fall back to stdlib json if unavailable
try:
    import orjson as _json
    def json_dumps(obj):
        return _json.dumps(obj)
    def json_loads(b):
        return _json.loads(b)
except Exception:  # pragma: no cover
    import json as _json
    def json_dumps(obj):
        return _json.dumps(obj).encode("utf-8")
    def json_loads(b):
        return _json.loads(b.decode("utf-8") if isinstance(b, (bytes, bytearray)) else b)

import numpy as np

from components import Grid
from solver import Solver, SolverConfig
from vision_solver import ModeConfig, LLMSolverConfig, solve_with_mode

# =========================================
# ARC-style dataset I/O (Kaggle-compatible)
# =========================================

def _to_np(grid_list: List[List[int]]) -> np.ndarray:
    return np.array(grid_list, dtype=np.int8)


def load_task_json(path: str) -> Tuple[List[Tuple[Grid, Grid]], List[Grid]]:
    with open(path, "rb") as f:
        data = json_loads(f.read())
    train_pairs: List[Tuple[Grid, Grid]] = []
    for pair in data["train"]:
        xin = Grid(_to_np(pair["input"]))
        yout = Grid(_to_np(pair["output"]))
        train_pairs.append((xin, yout))
    tests: List[Grid] = []
    for t in data["test"]:
        tests.append(Grid(_to_np(t["input"])) )
    return train_pairs, tests

# ======================
# Simple content hashing
# ======================

def hash_grid(arr: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(arr.tobytes())
    h.update(np.array(arr.shape, dtype=np.int32).tobytes())
    return h.hexdigest()[:16]


def hash_task(train_pairs: List[Tuple[Grid, Grid]], tests: List[Grid]) -> str:
    h = hashlib.sha256()
    for x, y in train_pairs:
        h.update(hash_grid(x.data).encode())
        h.update(hash_grid(y.data).encode())
    for x in tests:
        h.update(hash_grid(x.data).encode())
    return h.hexdigest()[:16]

# ======================
# Disk cache (optional)
# ======================
@dataclass
class Cache:
    root: str = ".arc_cache"

    def _path(self, key: str) -> str:
        os.makedirs(self.root, exist_ok=True)
        return os.path.join(self.root, f"{key}.json")

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        p = self._path(key)
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return json_loads(f.read())
            except Exception:
                return None
        return None

    def put(self, key: str, obj: Dict[str, Any]):
        p = self._path(key)
        with open(p, "wb") as f:
            f.write(json_dumps(obj))

# ======================
# Optional LLM bridge loader
# ======================

def _load_llm_fn(spec: str):
    import importlib
    if ':' in spec:
        mod_name, func_name = spec.split(':', 1)
    elif '.' in spec:
        mod_name, func_name = spec.rsplit('.', 1)
    else:
        raise ValueError("--llm-func must be 'module:func' or 'module.func'")
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, func_name, None)
    if not callable(fn):
        raise ValueError(f"Function '{func_name}' not found or not callable in module '{mod_name}'")
    return fn

# ======================
# Unified solve
# ======================

def solve_task_file(
    path: str,
    beam: int = 128,
    depth: int = 2,
    policy: Optional[object] = None,
    use_cache: bool = True,
    mode: str = "symbolic",
    solver_kind: str = "plus",  # default to plus here
    use_dsl_extra: bool = False,
    llm_func_spec: Optional[str] = None,
    llm_max_rules: int = 8,
    llm_fallback: bool = True,
) -> Dict[str, Any]:
    # Optional extra primitives
    if use_dsl_extra:
        try:
            import dsl_extra  # registers primitives
        except Exception:
            pass

    train_pairs, tests = load_task_json(path)
    task_key = hash_task(train_pairs, tests)

    cache = Cache()
    if use_cache:
        hit = cache.get(task_key + f"_{mode}_{solver_kind}_{int(use_dsl_extra)}")
        if hit is not None:
            return hit

    # Configure mode
    mode_cfg = ModeConfig(mode=mode, solver_cfg=SolverConfig(beam=beam, max_depth=depth))
    if mode in ("llm", "hybrid"):
        if llm_func_spec is None:
            raise ValueError("--mode llm or hybrid requires --llm-func module:function")
        llm_fn = _load_llm_fn(llm_func_spec)
        mode_cfg.llm_solver_cfg = LLMSolverConfig(llm_fn=llm_fn, max_rules=llm_max_rules, fallback_symbolic=llm_fallback)

    # Select solver implementation
    if solver_kind == "plus":
        from solver_plus import SolverPlus, SolverPlusConfig
        sym_solver = SolverPlus(SolverPlusConfig(beam=beam, max_depth=depth, use_prune=True, use_repair=True))
        if mode == "symbolic":
            preds_nested: List[List[Grid]] = sym_solver.solve_task(train_pairs, tests)
        else:
            preds_nested = solve_with_mode(train_pairs, tests, mode_cfg)
    else:
        preds_nested = solve_with_mode(train_pairs, tests, mode_cfg)

    # Serialize predictions
    ser_pred: List[List[List[List[int]]]] = []
    for per_test in preds_nested:
        outs = []
        for g in per_test:
            outs.append(g.data.astype(int).tolist())
        ser_pred.append(outs)

    out = {
        "task": os.path.basename(path),
        "task_hash": task_key,
        "num_tests": len(tests),
        "predictions": ser_pred,
        "mode": mode,
        "solver": solver_kind,
        "dsl_extra": bool(use_dsl_extra),
        "llm_func": llm_func_spec,
        "beam": beam,
        "depth": depth,
    }
    if use_cache:
        cache.put(task_key + f"_{mode}_{solver_kind}_{int(use_dsl_extra)}", out)
    return out

# ======================
# CLI
# ======================
USAGE = """
Usage:
  python -m run_arc_plus <task.json> [--beam 128] [--depth 2] [--no-cache]
                           [--mode symbolic|llm|hybrid] [--solver basic|plus]
                           [--dsl-extra]
                           [--llm-func module:function] [--llm-max 8] [--no-llm-fallback]
"""

def main(argv: List[str]):
    if len(argv) < 2:
        print(USAGE)
        return 2
    path = argv[1]
    beam = 128
    depth = 2
    use_cache = True
    mode = "symbolic"
    solver_kind = "plus"
    use_dsl_extra = False
    llm_func_spec = None
    llm_max = 8
    llm_fallback = True

    i = 2
    while i < len(argv):
        if argv[i] == "--beam" and i + 1 < len(argv):
            beam = int(argv[i + 1]); i += 2
        elif argv[i] == "--depth" and i + 1 < len(argv):
            depth = int(argv[i + 1]); i += 2
        elif argv[i] == "--no-cache":
            use_cache = False; i += 1
        elif argv[i] == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1].lower(); i += 2
        elif argv[i] == "--solver" and i + 1 < len(argv):
            solver_kind = argv[i + 1].lower(); i += 2
        elif argv[i] == "--dsl-extra":
            use_dsl_extra = True; i += 1
        elif argv[i] == "--llm-func" and i + 1 < len(argv):
            llm_func_spec = argv[i + 1]; i += 2
        elif argv[i] == "--llm-max" and i + 1 < len(argv):
            llm_max = int(argv[i + 1]); i += 2
        elif argv[i] == "--no-llm-fallback":
            llm_fallback = False; i += 1
        else:
            print(f"Unknown arg: {argv[i]}"); print(USAGE); return 2

    res = solve_task_file(path, beam=beam, depth=depth, policy=None, use_cache=use_cache,
                          mode=mode, solver_kind=solver_kind, use_dsl_extra=use_dsl_extra,
                          llm_func_spec=llm_func_spec, llm_max_rules=llm_max, llm_fallback=llm_fallback)
    out_bytes = json_dumps(res)
    sys.stdout.write(out_bytes.decode("utf-8") if isinstance(out_bytes, (bytes, bytearray)) else out_bytes)
    sys.stdout.write("\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
