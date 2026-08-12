# submission_builder_tiny.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os, sys, json, time, gc, signal
import numpy as np

# ---- light imports from your tree ----
from components import Grid
from heuristics import heuristics_two_attempts

# prefer stronger miner if available
try:
    from rule_miner_stronger import infer_two_attempts as miner_infer_two_attempts
except Exception:
    from rule_miner import infer_two_attempts as miner_infer_two_attempts  # type: ignore

# symbolic is optional & OFF by default to avoid OOM
try:
    from solver_plus import SolverPlus, SolverPlusConfig
except Exception:
    SolverPlus = None  # type: ignore

# -------------- utils --------------
def _to_np(lst: List[List[int]]) -> np.ndarray:
    return np.asarray(lst, dtype=np.int8)

def _sanitize10(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.int16, copy=False)
    if a.size:
        a[a < 0] = 0
        a[a > 9] = 9
    return a.astype(np.int8, copy=False)

def _ensure_two(preds: List[np.ndarray], H: int, W: int) -> Tuple[List[List[int]], List[List[int]]]:
    if not preds:
        z = [[0]*W for _ in range(H)]
        return z, z
    if len(preds) == 1:
        a = preds[0].astype(int).tolist()
        return a, a
    return preds[0].astype(int).tolist(), preds[1].astype(int).tolist()

def _load_challenges_json(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r") as f:
        data = json.load(f)
    if isinstance(data, dict) and "challenges" in data and isinstance(data["challenges"], dict):
        return data["challenges"]
    return data

def _read_rss_mb() -> float:
    # Linux: read VmRSS from /proc
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    return kb / 1024.0
    except Exception:
        pass
    return 0.0

# -------------- per-task timeout --------------
class Timeout:
    def __init__(self, seconds: int):
        self.seconds = seconds
    def __enter__(self):
        if self.seconds <= 0:
            return
        signal.signal(signal.SIGALRM, self._handle)
        signal.alarm(self.seconds)
    def __exit__(self, exc_type, exc, tb):
        try:
            signal.alarm(0)
        except Exception:
            pass
        return False
    @staticmethod
    def _handle(signum, frame):
        raise TimeoutError("task timed out")

# -------------- solve one task --------------
def solve_task(
    train_pairs: List[Tuple[Grid, Grid]],
    tests: List[Grid],
    *,
    use_symbolic: bool = False,
    beam: int = 32,
    depth: int = 2,
    policy_npz: Optional[str] = None,
    geom_radius: int = 2,
    perm_beam: int = 16,
    timeout_sec: int = 25,
    rss_soft_mb: int = 4096,
) -> List[List[Grid]]:

    # adaptive knobs if memory is already high
    rss = _read_rss_mb()
    if rss > 0 and rss > rss_soft_mb:
        beam = max(16, beam // 2)
        perm_beam = max(8, perm_beam // 2)
        geom_radius = max(1, geom_radius - 1)

    # 1) optional symbolic (OFF by default)
    sym_outs = None
    if use_symbolic and SolverPlus is not None:
        try:
            with Timeout(timeout_sec):
                sv = SolverPlus(SolverPlusConfig(
                    beam=beam, max_depth=depth, use_prune=True, use_repair=True, policy=None
                ))
                sym_outs = sv.solve_task(train_pairs, tests)
        except Exception:
            sym_outs = None

    # 2) miner (low RAM)
    tr_np = [(x.data, y.data) for (x,y) in train_pairs]
    te_np = [t.data for t in tests]

    priors = None
    if policy_npz and os.path.exists(policy_npz):
        try:
            dat = np.load(policy_npz, allow_pickle=True)
            priors = dict(dat.items())
        except Exception:
            priors = None

    try:
        with Timeout(timeout_sec):
            miner_outs: List[List[np.ndarray]] = miner_infer_two_attempts(
                tr_np, te_np, policy=priors, geom_radius=geom_radius, perm_beam=perm_beam, keep_top=2
            )
    except Exception:
        miner_outs = [[] for _ in te_np]

    finals: List[List[Grid]] = []
    for i, x in enumerate(tests):
        chosen: List[np.ndarray] = []

        # symbolic first if present
        if sym_outs is not None and i < len(sym_outs) and sym_outs[i]:
            for g in sym_outs[i][:2]:
                chosen.append(np.array(g.data, copy=True))

        # miner next
        if len(chosen) < 2 and i < len(miner_outs):
            for yhat in miner_outs[i]:
                if len(chosen) < 2:
                    chosen.append(np.array(yhat, copy=True))

        # heuristics fallback
        if len(chosen) < 2:
            try:
                hs = heuristics_two_attempts(train_pairs, [x])[0]
                for g in hs:
                    if len(chosen) < 2:
                        chosen.append(np.array(g.data, copy=True))
            except Exception:
                pass

        H, W = x.data.shape
        if not chosen:
            z = np.zeros((H, W), np.int8); chosen=[z,z]
        elif len(chosen) == 1:
            chosen=[chosen[0], chosen[0].copy()]
        else:
            chosen = chosen[:2]

        chosen = [_sanitize10(c) for c in chosen]
        finals.append([Grid(chosen[0]), Grid(chosen[1])])

    # clear big buffers
    del tr_np, te_np, miner_outs, sym_outs
    gc.collect()
    return finals

# -------------- streaming & resume --------------
def build_streaming(
    ch_path: str,
    out_path: str,
    *,
    use_symbolic: bool = False,   # default OFF to avoid OOM
    beam: int = 32,
    depth: int = 2,
    policy_npz: Optional[str] = None,
    geom_radius: int = 2,
    perm_beam: int = 16,
    timeout_sec: int = 25,
    rss_soft_mb: int = 4096,
    allow_resume: bool = True,
    only_tids: Optional[set[str]] = None,
):
    raw = _load_challenges_json(ch_path)
    tids = sorted(raw.keys())

    # resume support: if file exists and is a valid partial JSON object, load keys done
    done = set()
    if allow_resume and os.path.exists(out_path):
        try:
            with open(out_path, "r") as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                done = set(existing.keys())
        except Exception:
            pass

    # open a *second* file and stream to it; we’ll merge at end to avoid corrupting the prior file
    tmp_path = out_path + ".part"
    fp = open(tmp_path, "w")
    fp.write("{\n")
    wrote_any = False

    try:
        for tid in tids:
            if only_tids and tid not in only_tids:
                continue
            if tid in done:
                # copy from existing directly
                per_task = raw_task_to_existing(out_path, tid)
            else:
                spec = raw[tid]
                train_pairs = [(Grid(_to_np(z["input"])), Grid(_to_np(z["output"]))) for z in spec.get("train", [])]
                tests = [Grid(_to_np(z["input"])) for z in spec.get("test", [])]

                try:
                    per_task = []
                    preds = solve_task(
                        train_pairs, tests,
                        use_symbolic=use_symbolic, beam=beam, depth=depth, policy_npz=policy_npz,
                        geom_radius=geom_radius, perm_beam=perm_beam,
                        timeout_sec=timeout_sec, rss_soft_mb=rss_soft_mb,
                    )
                    for i, x in enumerate(tests):
                        H, W = x.data.shape
                        cands = [g.data for g in preds[i]] if i < len(preds) else []
                        a1, a2 = _ensure_two(cands, H, W)
                        per_task.append({"attempt_1": a1, "attempt_2": a2})
                except Exception:
                    # absolute last resort: two zeros with input size to guarantee format
                    if tests:
                        H, W = tests[0].data.shape
                    else:
                        # degenerate but still valid
                        H, W = 1, 1
                    z = [[0]*W for _ in range(H)]
                    per_task = [{"attempt_1": z, "attempt_2": z}]

                # free per-task
                del train_pairs, tests, preds
                gc.collect()

            # stream write this task
            if wrote_any:
                fp.write(",\n")
            fp.write(f"  \"{tid}\": ")
            json.dump(per_task, fp)
            wrote_any = True

            # tiny flush to disk frequently
            fp.flush()
            os.fsync(fp.fileno())

            # adapt if memory too high mid-run
            rss = _read_rss_mb()
            if rss and rss > rss_soft_mb:
                beam = max(16, beam // 2)
                perm_beam = max(8, perm_beam // 2)

        fp.write("\n}\n")
        fp.close()

        # atomically move to final path
        os.replace(tmp_path, out_path)
    except Exception:
        # make sure partial is closed
        try:
            fp.close()
        except Exception:
            pass
        raise

def raw_task_to_existing(out_path: str, tid: str) -> List[Dict[str, Any]]:
    with open(out_path, "r") as f:
        exist = json.load(f)
    return exist.get(tid, [])

# -------------- CLI --------------
def _parse_argv(argv: List[str]):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="challenges JSON")
    ap.add_argument("--output", required=True, help="submission.json")
    ap.add_argument("--beam", type=int, default=32)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--policy", type=str, default=None)
    ap.add_argument("--geom_radius", type=int, default=2)
    ap.add_argument("--perm_beam", type=int, default=16)
    ap.add_argument("--timeout_sec", type=int, default=25)
    ap.add_argument("--rss_soft_mb", type=int, default=4096)
    ap.add_argument("--symbolic", action="store_true", help="enable symbolic search (higher RAM)")
    ap.add_argument("--resume", action="store_true", help="resume from existing output file")
    ap.add_argument("--only", type=str, default="", help="comma-separated task ids to run")
    return ap.parse_args(argv)

def main(argv: List[str]) -> int:
    args = _parse_argv(sys.argv[1:])
    only = set([t.strip() for t in args.only.split(",") if t.strip()]) or None

    build_streaming(
        args.input,
        args.output,
        use_symbolic=args.symbolic,
        beam=args.beam,
        depth=args.depth,
        policy_npz=args.policy,
        geom_radius=args.geom_radius,
        perm_beam=args.perm_beam,
        timeout_sec=args.timeout_sec,
        rss_soft_mb=args.rss_soft_mb,
        allow_resume=args.resume,
        only_tids=only,
    )
    print(f"Wrote {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
