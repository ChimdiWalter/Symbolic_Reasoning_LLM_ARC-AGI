#!/usr/bin/env python3
"""TRM training (2510.04871 recipe): deep supervision + EMA + halting.

Resumable: checkpoints every epoch to trm/checkpoints/latest.pt (model,
EMA, optimizer, epoch).  Detach-friendly; logs to stdout.

Usage: train.py [epochs=50] [batch=96] [device=cuda]
CPU smoke: train.py 1 8 cpu --smoke   (100 examples, 1 step)
"""
import os, sys, time, math
import numpy as np
import torch
import torch.nn.functional as F
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trm.model import TRM, SEQ, VOCAB, count_params

EPOCHS = int(sys.argv[1]) if len(sys.argv) > 1 else 50
BATCH = int(sys.argv[2]) if len(sys.argv) > 2 else 96
DEVICE = sys.argv[3] if len(sys.argv) > 3 else (
    "cuda" if torch.cuda.is_available() else "cpu")
SMOKE = "--smoke" in sys.argv
N_SUP = int(os.environ.get("TRM_NSUP", "16"))
D = int(os.environ.get("TRM_D", "256"))
LAYERS = int(os.environ.get("TRM_LAYERS", "2"))
FRAC = float(os.environ.get("TRM_FRAC", "1.0"))   # dataset fraction/epoch
WARMUP = int(os.environ.get("TRM_WARMUP", "2000"))
BASE_LR = 1e-4
VAL_AUGS = 20            # augments per val task (build_dataset.py)
EMA_DECAY = 0.999
CKPT = os.path.join(os.path.dirname(__file__), "checkpoints")


def load(split):
    d = np.load(os.path.join(os.path.dirname(__file__), "data",
                             f"{split}.npz"))
    x, y = d["x"], d["y"]
    if SMOKE:
        x, y = x[:100], y[:100]
    return torch.from_numpy(x.astype(np.int64)), \
        torch.from_numpy(y.astype(np.int64))


def main():
    xtr, ytr = load("train")
    xva, yva = load("val")
    print(f"train {tuple(xtr.shape)} val {tuple(xva.shape)} "
          f"device={DEVICE}", flush=True)
    cfg = {"d": D, "layers": LAYERS}
    model = TRM(**cfg).to(DEVICE)
    ema = TRM(**cfg).to(DEVICE)
    ema.load_state_dict(model.state_dict())
    for p in ema.parameters():
        p.requires_grad_(False)
    print(f"params {count_params(model)/1e6:.1f}M cfg={cfg} "
          f"nsup={N_SUP} frac={FRAC}", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=BASE_LR,
                            weight_decay=0.1)
    start_ep = 0
    os.makedirs(CKPT, exist_ok=True)
    latest = os.path.join(CKPT, "latest.pt")
    if os.path.exists(latest):
        ck = torch.load(latest, map_location=DEVICE)
        model.load_state_dict(ck["model"]); ema.load_state_dict(ck["ema"])
        opt.load_state_dict(ck["opt"]); start_ep = ck["epoch"] + 1
        print(f"resumed from epoch {start_ep}", flush=True)

    n = xtr.shape[0]
    n_ep = max(BATCH, int(n * FRAC))
    steps = max(1, n_ep // BATCH)
    gstep = start_ep * steps
    for ep in range(start_ep, EPOCHS):
        model.train()
        perm = torch.randperm(n)[:n_ep]
        t0, tot, seen = time.time(), 0.0, 0
        for si in range(steps):
            gstep += 1
            lr = BASE_LR * min(1.0, gstep / max(1, WARMUP))
            for g in opt.param_groups:
                g["lr"] = lr
            idx = perm[si * BATCH:(si + 1) * BATCH]
            x = xtr[idx].to(DEVICE)
            tgt = ytr[idx].view(-1, SEQ).to(DEVICE)
            y = z = None
            opt.zero_grad(set_to_none=True)
            for sup in range(2 if SMOKE else N_SUP):
                logits, y, z, halt = model(x, y, z)
                loss = F.cross_entropy(logits.reshape(-1, VOCAB),
                                       tgt.reshape(-1))
                solved = (logits.argmax(-1) == tgt).all(dim=1).float()
                loss = loss + 0.5 * F.binary_cross_entropy_with_logits(
                    halt, solved)
                loss.backward()
                opt.step()
                opt.zero_grad(set_to_none=True)
                with torch.no_grad():
                    for pe, pm in zip(ema.parameters(),
                                      model.parameters()):
                        pe.mul_(EMA_DECAY).add_(pm, alpha=1 - EMA_DECAY)
                if solved.mean() > 0.99:
                    break
            tot += loss.item(); seen += 1
            if si % 50 == 0:
                print(f"ep{ep} step {si}/{steps} loss {tot/seen:.4f} "
                      f"({time.time()-t0:.0f}s)", flush=True)
            if SMOKE and si >= 1:
                break
        # val (EMA weights): example exact + task-level (any augment)
        ema.eval()
        exact_flags = []
        with torch.no_grad():
            for vi in range(0, xva.shape[0], BATCH):
                x = xva[vi:vi+BATCH].to(DEVICE)
                tgt = yva[vi:vi+BATCH].view(-1, SEQ).to(DEVICE)
                y = z = None
                for _ in range(2 if SMOKE else N_SUP):
                    logits, y, z, halt = ema(x, y, z)
                pred = logits.argmax(-1)
                exact_flags += (pred == tgt).all(dim=1).cpu().tolist()
                if SMOKE:
                    break
        correct = sum(exact_flags)
        ntasks = len(exact_flags) // VAL_AUGS
        tasks_solved = sum(
            any(exact_flags[t * VAL_AUGS:(t + 1) * VAL_AUGS])
            for t in range(ntasks)) if ntasks else 0
        print(f"EPOCH {ep}: loss {tot/max(1,seen):.4f} "
              f"val_exact {correct}/{len(exact_flags)} "
              f"val_tasks {tasks_solved}/{ntasks}", flush=True)
        torch.save({"model": model.state_dict(), "ema": ema.state_dict(),
                    "opt": opt.state_dict(), "epoch": ep, "cfg": cfg},
                   latest)
        torch.save({"ema": ema.state_dict(), "epoch": ep, "cfg": cfg},
                   os.path.join(CKPT, "ema_only.pt"))
        torch.save({"ema": ema.state_dict(), "epoch": ep, "cfg": cfg},
                   os.path.join(CKPT, f"ema_ep{ep}.pt"))
        stop_file = os.path.join(os.path.dirname(__file__), "STOP_AFTER_EPOCH")
        stop_at = os.environ.get("TRM_STOP_AFTER_EPOCH")
        if os.path.exists(stop_file):
            print(f"PAUSED by {stop_file} after epoch {ep}", flush=True)
            break
        if stop_at is not None and ep >= int(stop_at):
            print(f"STOPPED at epoch {ep} (TRM_STOP_AFTER_EPOCH={stop_at})",
                  flush=True)
            break
    print("TRAINING COMPLETE", flush=True)


if __name__ == "__main__":
    main()
