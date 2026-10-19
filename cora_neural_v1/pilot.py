"""Neural-CORA v1 pilot runner. The frozen protocol is `records/NEURAL_CORA_V1_PILOT_PROTOCOL.md`.

    python -m cora_neural_v1.pilot freeze     # sha256 of every frozen baseline -> records/NEURAL_CORA_V1_FREEZE_MANIFEST.json
    python -m cora_neural_v1.pilot generate   # corpora; solver-facing evaluation files hold no programs or outputs
    python -m cora_neural_v1.pilot audit      # learning-data audit and the held-out primary set (demonstrations only)
    python -m cora_neural_v1.pilot targets    # extensional targets for train/val (demonstrations only)
    python -m cora_neural_v1.pilot features qwen|hand
    python -m cora_neural_v1.pilot train      # L1, L1h, L0s heads (real gradient updates); L0 untrained
    python -m cora_neural_v1.pilot run        # every arm on the evaluation tasks; rows hold predictions only
    python -m cora_neural_v1.evaluate         # the evaluator: the first and only read of the answers

Outputs go to `outputs/neural_cora_v1/` (gitignored). Every file's sha256 is recorded in `manifest.json`.
The engineering check (`NEURAL_CORA_DEV=1`) uses separate seeds and TRAIN families only (`outputs/neural_cora_v1_dev/`).
"""
import glob
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
DEV = bool(os.environ.get("NEURAL_CORA_DEV"))
OUT = os.path.join(HERE, "outputs", "neural_cora_v1_dev" if DEV else "neural_cora_v1")
CORPUS = os.path.join(OUT, "corpus")

SPLITS = {   # family set, seed range: fixed before any learned run (protocol section 3)
    "train": ("TRAIN", range(0, 300)),
    "val": ("TRAIN", range(1000, 1030)),
    "eval_iid": ("TRAIN", range(2000, 2020)),
    "eval_heldout": ("HELDOUT", range(3000, 3060)),
}
if DEV:                                            # no HELD-OUT family is touched in the engineering check
    SPLITS = {"train": ("TRAIN", range(10000, 10080)), "val": ("TRAIN", range(11000, 11010)),
              "eval_iid": ("TRAIN", range(12000, 12010)), "eval_heldout": ("TRAIN", range(12100, 12101))}
# every typed arm runs once to its B_MAX candidates; smaller budgets are exact truncations of that run. C+H and L1
# (the two budget curves) run to 3000; the other typed arms to 1000, which covers every primary comparison.
B_MAX = {"C+": 1000, "C+H": 3000, "L0": 1000, "L0s": 1000, "L1": 3000, "L1h": 1000}
BUDGETS = (100, 300, 500, 1000, 3000)
B_LEARNED, B_SYMBOLIC = 500, 1000                  # the primary comparison: symbolic arms get twice the candidates
C0_CPU_S = 5.0            # native inducer CPU budget per task
SEED = 20261019
TYPED_ARMS = ("C+", "C+H", "L0", "L0s", "L1", "L1h")
MAIN_ARMS = ("C0",) + TYPED_ARMS


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _w(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def _r(path):
    return [json.loads(l) for l in open(path)]


def _manifest(update):
    """Read-modify-write under an exclusive lock: the GPU feature job and the CPU jobs may finish at the same time."""
    import fcntl
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "manifest.json")
    with open(os.path.join(OUT, ".manifest.lock"), "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        m = json.load(open(p)) if os.path.exists(p) else {}
        m.update(update)
        tmp = p + ".tmp"
        json.dump(m, open(tmp, "w"), indent=1, sort_keys=True)
        os.replace(tmp, p)


def _fams():
    from cora_neural_v1 import generator as G
    return {"TRAIN": G.TRAIN_FAMILIES, "HELDOUT": G.HELDOUT_FAMILIES}


# ------------------------------------------------------------------ freeze (baselines are hashed, never modified)
FROZEN = {
    "native_cora_v23_geocat_arc": "geocat_arc/**/*.py",
    "cora_fhr": "cora_fhr/**/*.py",
    "cora_revision_v2": "cora_revision_v2/**/*.py",
    "phase2a_frozen_outputs": "outputs/cora_revision_v2/phase2a_evaluator/*.json",
    "cora_funnel_cpu_clock": "cora_funnel/**/*.py",
    "nvarc_27p64_deployment_kaggle_neural_v1": "kaggle/neural_v1/**/*",
    "nvarc_qwen3_4b_checkpoint": "outputs/neural_cora_v0/models/nvarc_qwen3_4b_grids15_sft139_v1/*",
    "cora_neural_v1_code_at_freeze": "cora_neural_v1/*.py",
}


def freeze():
    rec = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "groups": {}}
    for name, pat in FROZEN.items():
        files = sorted(f for f in glob.glob(os.path.join(HERE, pat), recursive=True)
                       if os.path.isfile(f) and "__pycache__" not in f and not f.endswith(".pyc"))
        per = {os.path.relpath(f, HERE): _sha(f) for f in files}
        agg = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in per.items()).encode()).hexdigest()
        rec["groups"][name] = {"pattern": pat, "n_files": len(per), "aggregate_sha256": agg, "files": per}
        print(name, len(per), agg[:16], flush=True)
    p = os.path.join(HERE, "records", "NEURAL_CORA_V1_FREEZE_MANIFEST.json")
    json.dump(rec, open(p, "w"), indent=1, sort_keys=True)


# ------------------------------------------------------------------ generate
def generate():
    from cora_neural_v1 import generator as G
    fams = _fams()
    rec = {}
    for split, (fs, seeds) in SPLITS.items():
        rows, missing = [], 0
        for fam in fams[fs]:
            for s in seeds:
                t = G.make_task(fam, s)
                if t is None:
                    missing += 1
                    continue
                rows.append(t)
        if split.startswith("eval"):
            pub = [{"task_id": f"{split}_{i:05d}", "train": t["train"], "test_inputs": [t["test"][0][0]]}
                   for i, t in enumerate(rows)]
            ans = [{"task_id": f"{split}_{i:05d}", "test_output": t["test"][0][1], "family": t["family"],
                    "program": t["program"], "source": t["task_id"]} for i, t in enumerate(rows)]
            _w(os.path.join(CORPUS, f"{split}_public.jsonl"), pub)
            _w(os.path.join(OUT, "evaluator", f"{split}_answers.jsonl"), ans)
            rec[split] = {"n": len(rows), "missing": missing,
                          "public_sha256": _sha(os.path.join(CORPUS, f"{split}_public.jsonl")),
                          "answers_sha256": _sha(os.path.join(OUT, "evaluator", f"{split}_answers.jsonl"))}
        else:
            _w(os.path.join(CORPUS, f"{split}.jsonl"), rows)
            rec[split] = {"n": len(rows), "missing": missing, "sha256": _sha(os.path.join(CORPUS, f"{split}.jsonl"))}
        print(split, rec[split], flush=True)
    _manifest({"corpus": rec, "generator": G.GEN_VERSION, "splits": {k: [v[0], v[1].start, v[1].stop]
                                                                      for k, v in SPLITS.items()}})


# ------------------------------------------------------------------ audit (generator side; never reads answers)
def audit_cmd():
    from cora_neural_v1 import audit as A
    t0 = time.process_time()
    rec, flags, tasks = A.run_audit(SPLITS, _fams())
    # the regenerated tasks must be exactly the generated corpora (same order, same content)
    for split in ("train", "val"):
        assert [t["task_id"] for t in tasks[split]] == [t["task_id"] for t in _r(os.path.join(CORPUS, f"{split}.jsonl"))]
    for split in ("eval_iid", "eval_heldout"):
        pub = _r(os.path.join(CORPUS, f"{split}_public.jsonl"))
        norm = lambda x: json.loads(json.dumps(x))                  # tuples (generator) vs lists (JSON corpus)
        assert len(pub) == len(tasks[split]) and all(p["train"] == norm(t["train"]) for p, t in zip(pub, tasks[split]))
    primary = {f"eval_heldout_{i:05d}": {"aliased_train_templates": v, "primary": not v} for i, v in flags.items()}
    rec["audit_cpu_s"] = round(time.process_time() - t0, 1)
    os.makedirs(os.path.join(OUT, "audit"), exist_ok=True)
    json.dump(rec, open(os.path.join(OUT, "audit", "data_audit.json"), "w"), indent=1, sort_keys=True)
    json.dump(primary, open(os.path.join(OUT, "audit", "eval_heldout_primary.json"), "w"), indent=1, sort_keys=True)
    _manifest({"audit": {"data_audit_sha256": _sha(os.path.join(OUT, "audit", "data_audit.json")),
                         "heldout_primary_sha256": _sha(os.path.join(OUT, "audit", "eval_heldout_primary.json")),
                         "heldout_primary_n": rec["heldout_primary_n"]}})
    print(json.dumps({k: v for k, v in rec.items() if k != "splits"}, indent=1)[:3000], flush=True)


# ------------------------------------------------------------------ targets
def _tgt(t):
    from cora_neural_v1.prior import targets
    y = targets(t)
    return {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in y.items()}


def targets_cmd(workers=2):
    from multiprocessing import Pool
    rec = {}
    for split in ("train", "val"):
        rows = _r(os.path.join(CORPUS, f"{split}.jsonl"))
        t0 = time.time()
        with Pool(workers, initializer=os.nice, initargs=(10,)) as pool:
            ys = pool.map(_tgt, rows, chunksize=16)
        _w(os.path.join(OUT, "features", f"{split}_targets.jsonl"), ys)
        rec[split] = {"sha256": _sha(os.path.join(OUT, "features", f"{split}_targets.jsonl")), "n": len(ys),
                      "mean_valid_selectors": round(float(np.mean([sum(y["sel"]) for y in ys])), 3),
                      "mean_valid_actions": round(float(np.mean([sum(y["act"]) for y in ys])), 3),
                      "mean_valid_views": round(float(np.mean([sum(y["var"]) for y in ys])), 3),
                      "wall_s": round(time.time() - t0, 1)}
        print(split, rec[split], flush=True)
    _manifest({"targets": rec})


# ------------------------------------------------------------------ features
def _pubify(t):
    return {"train": t["train"], "test_inputs": [t["test"][0][0]]} if "test" in t else t


def features_cmd(which="qwen"):
    from cora_neural_v1 import prior as PR
    feat_dir = os.path.join(OUT, "features")
    os.makedirs(feat_dir, exist_ok=True)
    splits = {"train": os.path.join(CORPUS, "train.jsonl"), "val": os.path.join(CORPUS, "val.jsonl"),
              "eval_iid": os.path.join(CORPUS, "eval_iid_public.jsonl"),
              "eval_heldout": os.path.join(CORPUS, "eval_heldout_public.jsonl")}
    rec = {}
    if which == "hand":
        for s, p in splits.items():
            t0 = time.process_time()
            X = np.stack([PR.hand_features(_pubify(t)) for t in _r(p)])
            np.save(os.path.join(feat_dir, f"{s}_hand.npy"), X)
            rec[f"{s}_hand"] = {"sha256": _sha(os.path.join(feat_dir, f"{s}_hand.npy")), "shape": list(X.shape),
                                "cpu_s": round(time.process_time() - t0, 1)}
            print(s, "hand", X.shape, flush=True)
    else:
        import torch
        enc = PR.QwenEncoder()
        for s, p in splits.items():
            rows = _r(p)
            X, lens = [], []
            torch.cuda.synchronize()
            g0 = time.time()
            for i, t in enumerate(rows):
                f, n = enc.features(_pubify(t))
                X.append(f)
                lens.append(n)
                if i % 500 == 0:
                    print(s, i, len(rows), round(time.time() - g0, 1), flush=True)
            torch.cuda.synchronize()
            X = np.stack(X)
            np.save(os.path.join(feat_dir, f"{s}_qwen.npy"), X)
            rec[f"{s}_qwen"] = {"sha256": _sha(os.path.join(feat_dir, f"{s}_qwen.npy")), "n": len(rows),
                                "gpu_wall_s": round(time.time() - g0, 1), "mean_tokens": round(float(np.mean(lens)), 1),
                                "max_tokens": int(max(lens)),
                                "peak_gpu_mem_gb": round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)}
            print(s, "qwen", X.shape, rec[f"{s}_qwen"], flush=True)
        rec["encoder"] = {"model_dir": os.path.relpath(PR.MODEL_DIR, HERE), "checkpoint": "sorokin/qwen3_4b_grids15_sft139 v1",
                          "frozen": True, "dtype": "float16", "device": torch.cuda.get_device_name(0),
                          "safetensors_sha256": {f: _sha(os.path.join(PR.MODEL_DIR, f)) for f in sorted(os.listdir(PR.MODEL_DIR))
                                                 if f.endswith(".safetensors")}}
    _manifest({f"features_{which}": rec})


# ------------------------------------------------------------------ train
def _Y(split):
    ys = _r(os.path.join(OUT, "features", f"{split}_targets.jsonl"))
    return {k: np.asarray([y[k] for y in ys], dtype=np.float32) for k in ("var", "sel", "act", "def", "n")}


def _std(Xtr, *others):
    mu = Xtr.astype(np.float32).mean(0)
    sd = Xtr.astype(np.float32).std(0) + 1e-3
    f = lambda X: np.clip((X.astype(np.float32) - mu) / sd, -8, 8)
    return (f(Xtr),) + tuple(f(X) for X in others), (mu, sd)


def train_cmd(device="cuda:0"):
    import torch
    from cora_neural_v1 import prior as PR
    fd = os.path.join(OUT, "features")
    md = os.path.join(OUT, "models")
    os.makedirs(md, exist_ok=True)
    Ytr, Yva = _Y("train"), _Y("val")
    rec = {"seed": SEED, "device": torch.cuda.get_device_name(0) if device.startswith("cuda") else device,
           "torch": torch.__version__, "python": platform.python_version(),
           "hyperparameters": {"epochs": 60, "lr": 1e-3, "weight_decay": 1e-4, "batch": 128, "hidden": [1024, 512],
                               "dropout": [0.2, 0.1], "loss": "BCE(view, default, selectors x4, actions x4) + CE(n_rules)",
                               "selection": "epoch with the best validation loss"},
           "models": {}}
    rng = np.random.default_rng(SEED)
    perm = rng.permutation(len(Ytr["n"]))
    Ysh = {k: v[perm] for k, v in Ytr.items()}                      # L0s: targets shuffled across tasks
    for name, feat, Y in (("L1", "qwen", Ytr), ("L1h", "hand", Ytr), ("L0s", "qwen", Ysh)):
        Xtr, Xva = np.load(os.path.join(fd, f"train_{feat}.npy")), np.load(os.path.join(fd, f"val_{feat}.npy"))
        (Xtr, Xva), (mu, sd) = _std(Xtr, Xva)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        t0, st = time.time(), {}
        m, hist = PR.train_heads(Xtr, Y, Xva, Yva, seed=SEED, device=device, stats=st)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        torch.save({"state": m.state_dict(), "in_dim": Xtr.shape[1], "mu": mu, "sd": sd, "feat": feat},
                   os.path.join(md, f"{name}.pt"))
        rec["models"][name] = {"checkpoint_sha256": _sha(os.path.join(md, f"{name}.pt")), "features": feat,
                               "targets": "shuffled across tasks" if name == "L0s" else "true",
                               "train_wall_s": round(time.time() - t0, 1), "best_val_loss": min(h["val_loss"] for h in hist),
                               "epochs": len(hist), **st, "history": hist}
        print(name, {k: v for k, v in rec["models"][name].items() if k not in ("history", "grad_norm_mean_by_epoch")},
              flush=True)
    Xtr = np.load(os.path.join(fd, "train_qwen.npy"))
    (_,), (mu, sd) = _std(Xtr)
    m0 = PR.build_heads(Xtr.shape[1], SEED)                           # L0: the same architecture and seed, untrained
    torch.save({"state": m0.state_dict(), "in_dim": Xtr.shape[1], "mu": mu, "sd": sd, "feat": "qwen"},
               os.path.join(md, "L0.pt"))
    rec["models"]["L0"] = {"checkpoint_sha256": _sha(os.path.join(md, "L0.pt")), "trained": False, "optimizer_steps": 0,
                           "weights_sha256": PR.weights_sha(m0),
                           "trainable_params": int(sum(p.numel() for p in m0.parameters()))}
    json.dump(rec, open(os.path.join(md, "training_log.json"), "w"), indent=1)
    _manifest({"training": {"log_sha256": _sha(os.path.join(md, "training_log.json")),
                            "models": {k: {kk: vv for kk, vv in v.items() if kk not in ("history", "grad_norm_mean_by_epoch")}
                                       for k, v in rec["models"].items()}}})


# ------------------------------------------------------------------ run arms
_CTX = {}


def _load_model(name):
    import torch
    from cora_neural_v1 import prior as PR
    ck = torch.load(os.path.join(OUT, "models", f"{name}.pt"), weights_only=False)
    m = PR.build_heads(ck["in_dim"], SEED)
    m.load_state_dict(ck["state"])
    m.eval()
    return m, ck


def _init_worker(split):
    os.nice(10)
    import torch
    torch.set_num_threads(1)
    fd = os.path.join(OUT, "features")
    _CTX["X"] = {f: np.load(os.path.join(fd, f"{split}_{f}.npy")) for f in ("qwen", "hand")}
    _CTX["models"] = {n: _load_model(n) for n in ("L0", "L0s", "L1", "L1h")}


def _run_one(args):
    from cora_neural_v1 import prior as PR
    from cora_neural_v1 import search as S
    from cora_neural_v1 import space as SP
    i, t, arms = args
    doms = SP.domains(t["train"])
    row = {"task_id": t["task_id"], "arms": {}}
    for arm in arms:
        if arm == "C0":
            r = S.search_native(t, C0_CPU_S)
        elif arm == "C+H":
            r = S.search_typed(t, SP.heuristic_scores(doms, t["train"]), B_MAX["C+H"])
        elif arm == "C+":
            r = S.search_typed(t, SP.simplicity_scores(doms), B_MAX["C+"])
        else:
            m, ck = _CTX["models"][arm]
            x = np.clip((_CTX["X"][ck["feat"]][i].astype(np.float32) - ck["mu"]) / ck["sd"], -8, 8)
            r = S.search_typed(t, PR.head_scores(m, x, doms), B_MAX[arm])
        r.pop("kept", None)
        row["arms"][arm] = r
    return row


def run_cmd(workers=2):
    from multiprocessing import Pool
    for split in ("eval_heldout", "eval_iid"):
        tasks = _r(os.path.join(CORPUS, f"{split}_public.jsonl"))
        if DEV and os.environ.get("NEURAL_CORA_LIMIT"):              # engineering smoke test only
            tasks = tasks[:int(os.environ["NEURAL_CORA_LIMIT"])]
        out = os.path.join(OUT, "rows", f"{split}.jsonl")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        done = {r["task_id"] for r in _r(out)} if os.path.exists(out) else set()   # resumable: append missing tasks
        todo = [(i, t, MAIN_ARMS) for i, t in enumerate(tasks) if t["task_id"] not in done]
        t0 = time.time()
        with Pool(workers, initializer=_init_worker, initargs=(split,)) as pool, open(out, "a") as f:
            for n, row in enumerate(pool.imap(_run_one, todo, chunksize=2)):
                f.write(json.dumps(row) + "\n")
                f.flush()
                if n % 25 == 0:
                    print(split, len(done) + n, len(tasks), round(time.time() - t0, 1), flush=True)
        rows = _r(out)
        assert len(rows) == len(tasks) and len({r["task_id"] for r in rows}) == len(tasks), "incomplete rows"
        _manifest({f"rows_{split}": {"sha256": _sha(out), "n": len(tasks), "wall_s_last_session": round(time.time() - t0, 1),
                                     "workers": workers, "B_MAX": B_MAX, "C0_CPU_S": C0_CPU_S}})
        print(split, "done", round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    W = int(os.environ.get("NEURAL_CORA_WORKERS", "2"))               # at most two low-priority CPU workers
    assert 1 <= W <= 2, "the pilot's resource cap is two CPU workers"
    {"freeze": freeze, "generate": generate, "audit": audit_cmd, "targets": lambda: targets_cmd(W),
     "features": lambda: features_cmd(sys.argv[2] if len(sys.argv) > 2 else "qwen"),
     "train": train_cmd, "run": lambda: run_cmd(W)}[cmd]()
