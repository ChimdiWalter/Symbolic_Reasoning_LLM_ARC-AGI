"""Neural-CORA pilot v0 runner. The protocol is `records/NEURAL_CORA_PILOT_v0_PROTOCOL.md`.

    python -m cora_neural_v1.pilot generate   # corpora; solver-facing evaluation file without programs or outputs
    python -m cora_neural_v1.pilot targets    # extensional targets for train/val (demonstrations only)
    python -m cora_neural_v1.pilot features   # NVARC Qwen3-4B features (GPU) and hand features
    python -m cora_neural_v1.pilot train      # L1, L1h, L0s heads (gradient training); L0 untrained
    python -m cora_neural_v1.pilot run        # every arm on the evaluation tasks; rows hold predictions only
    python -m cora_neural_v1.pilot evaluate   # the evaluator: the first and only read of the answers

Outputs go to `outputs/neural_cora_v0/` (gitignored). Every file's sha256 is recorded in `manifest.json`.
"""
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
DEV = bool(os.environ.get("NEURAL_CORA_DEV"))     # engineering check: separate seeds, TRAIN families only
OUT = os.path.join(HERE, "outputs", "neural_cora_v0_dev" if DEV else "neural_cora_v0")
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
B_LEARNED = 500           # candidate programs per task for L0, L0s, L1, L1h
B_SYMBOLIC = 1000         # C+ and C+H: twice the learned budget (covers the encoder's GPU time)
C0_CPU_S = 5.0            # native inducer CPU budget per task
SWEEP = (100, 300, 1000, 3000)
SEED = 20261019


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
    p = os.path.join(OUT, "manifest.json")
    m = json.load(open(p)) if os.path.exists(p) else {}
    m.update(update)
    json.dump(m, open(p, "w"), indent=1, sort_keys=True)


# ------------------------------------------------------------------ generate
def generate():
    from cora_neural_v1 import generator as G
    fams = {"TRAIN": G.TRAIN_FAMILIES, "HELDOUT": G.HELDOUT_FAMILIES}
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
    _manifest({"corpus": rec, "generator": G.GEN_VERSION})


# ------------------------------------------------------------------ targets
def _tgt(t):
    from cora_neural_v1.prior import targets
    y = targets(t)
    return {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in y.items()}


def targets_cmd(workers=2):
    from multiprocessing import Pool
    for split in ("train", "val"):
        rows = _r(os.path.join(CORPUS, f"{split}.jsonl"))
        with Pool(workers, initializer=os.nice, initargs=(10,)) as pool:
            ys = pool.map(_tgt, rows, chunksize=16)
        _w(os.path.join(OUT, "features", f"{split}_targets.jsonl"), ys)
        alias = [sum(y["sel"]) for y in ys]
        print(split, "targets", len(ys), "mean selector aliases", round(float(np.mean(alias)), 2), flush=True)
    _manifest({"targets": {s: _sha(os.path.join(OUT, "features", f"{s}_targets.jsonl")) for s in ("train", "val")}})


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
            X = np.stack([PR.hand_features(_pubify(t)) for t in _r(p)])
            np.save(os.path.join(feat_dir, f"{s}_hand.npy"), X)
            rec[f"{s}_hand"] = _sha(os.path.join(feat_dir, f"{s}_hand.npy"))
            print(s, "hand", X.shape, flush=True)
    else:
        enc = PR.QwenEncoder()
        for s, p in splits.items():
            rows = _r(p)
            X, lens, t0 = [], [], time.time()
            g0 = time.time()
            for i, t in enumerate(rows):
                f, n = enc.features(_pubify(t))
                X.append(f)
                lens.append(n)
                if i % 500 == 0:
                    print(s, i, len(rows), round(time.time() - t0, 1), flush=True)
            X = np.stack(X)
            np.save(os.path.join(feat_dir, f"{s}_qwen.npy"), X)
            rec[f"{s}_qwen"] = {"sha256": _sha(os.path.join(feat_dir, f"{s}_qwen.npy")), "n": len(rows),
                                "gpu_wall_s": round(time.time() - g0, 1), "mean_tokens": round(float(np.mean(lens)), 1),
                                "max_tokens": int(max(lens))}
            print(s, "qwen", X.shape, rec[f"{s}_qwen"], flush=True)
        rec["encoder"] = {"model_dir": os.path.relpath(PR.MODEL_DIR, HERE), "checkpoint": "sorokin/qwen3_4b_grids15_sft139 v1",
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
    rec = {}
    rng = np.random.default_rng(SEED)
    perm = rng.permutation(len(Ytr["n"]))
    Ysh = {k: v[perm] for k, v in Ytr.items()}                      # L0s: targets shuffled across tasks
    for name, feat, Y in (("L1", "qwen", Ytr), ("L1h", "hand", Ytr), ("L0s", "qwen", Ysh)):
        Xtr, Xva = np.load(os.path.join(fd, f"train_{feat}.npy")), np.load(os.path.join(fd, f"val_{feat}.npy"))
        (Xtr, Xva), (mu, sd) = _std(Xtr, Xva)
        t0 = time.time()
        m, hist = PR.train_heads(Xtr, Y, Xva, Yva, seed=SEED, device=device)
        torch.save({"state": m.state_dict(), "in_dim": Xtr.shape[1], "mu": mu, "sd": sd, "feat": feat},
                   os.path.join(md, f"{name}.pt"))
        rec[name] = {"sha256": _sha(os.path.join(md, f"{name}.pt")), "train_s": round(time.time() - t0, 1),
                     "best_val": min(h["val_loss"] for h in hist), "epochs": len(hist), "history": hist}
        print(name, {k: v for k, v in rec[name].items() if k != "history"}, flush=True)
    # L0: untrained heads, the same architecture and seed
    Xtr = np.load(os.path.join(fd, "train_qwen.npy"))
    (_,), (mu, sd) = _std(Xtr)
    m0 = PR.build_heads(Xtr.shape[1], SEED)
    torch.save({"state": m0.state_dict(), "in_dim": Xtr.shape[1], "mu": mu, "sd": sd, "feat": "qwen"},
               os.path.join(md, "L0.pt"))
    rec["L0"] = {"sha256": _sha(os.path.join(md, "L0.pt")), "trained": False}
    _manifest({"models": {k: {kk: vv for kk, vv in v.items() if kk != "history"} for k, v in rec.items()}})
    json.dump(rec, open(os.path.join(md, "training_log.json"), "w"), indent=1)


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
        elif arm.startswith("C+H"):
            B = int(arm.split("@")[1]) if "@" in arm else B_SYMBOLIC
            r = S.search_typed(t, SP.heuristic_scores(doms, t["train"]), B)
        elif arm.startswith("C+"):
            B = int(arm.split("@")[1]) if "@" in arm else B_SYMBOLIC
            r = S.search_typed(t, SP.simplicity_scores(doms), B)
        else:
            name, B = (arm.split("@")[0], int(arm.split("@")[1])) if "@" in arm else (arm, B_LEARNED)
            m, ck = _CTX["models"][name]
            x = np.clip((_CTX["X"][ck["feat"]][i].astype(np.float32) - ck["mu"]) / ck["sd"], -8, 8)
            r = S.search_typed(t, PR.head_scores(m, x, doms), B)
        r.pop("kept", None)
        row["arms"][arm] = r
    return row


MAIN_ARMS = ("C0", "C+", "C+H", "L0", "L0s", "L1", "L1h")
SWEEP_ARMS = tuple(f"C+H@{b}" for b in SWEEP) + tuple(f"L1@{b}" for b in SWEEP)


def run_cmd(workers=2):
    from multiprocessing import Pool
    for split in ("eval_heldout", "eval_iid"):
        tasks = _r(os.path.join(CORPUS, f"{split}_public.jsonl"))
        out = os.path.join(OUT, "rows", f"{split}.jsonl")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        t0 = time.time()
        with Pool(workers, initializer=_init_worker, initargs=(split,)) as pool, open(out, "w") as f:
            for n, row in enumerate(pool.imap(_run_one, [(i, t, MAIN_ARMS + SWEEP_ARMS) for i, t in enumerate(tasks)],
                                              chunksize=4)):
                f.write(json.dumps(row) + "\n")
                if n % 50 == 0:
                    print(split, n, len(tasks), round(time.time() - t0, 1), flush=True)
        _manifest({f"rows_{split}": {"sha256": _sha(out), "n": len(tasks), "wall_s": round(time.time() - t0, 1)}})
        print(split, "done", round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"generate": generate, "targets": targets_cmd, "features": lambda: features_cmd(sys.argv[2] if len(sys.argv) > 2 else "qwen"),
     "train": train_cmd, "run": run_cmd}[cmd]()
