"""Per-puzzle LoRA test-time training (pilot; authorized 26 Oct for Kaggle L4x4 only).

Own implementation on peft (Apache-2.0). One LoRA wrapper is created around the frozen base; before each puzzle its
adapter weights are re-initialised (A: Kaiming-uniform, B: zero, i.e. peft's default fresh adapter, so the adapted
model starts exactly at the base) with a puzzle-specific seed, and a new optimiser is built. Training uses only
that puzzle's visible demonstrations: each sequence is a leave-one-demonstration-out chat (the other
demonstrations, then the held-out one), under one pair-consistent augmentation (a D8 symmetry and a colour
permutation keeping 0 applied to every grid of the sequence, and a shuffled demonstration order). The loss is the
cross-entropy of every demonstration output after the first (each is predicted from the pairs before it).
Test inputs and their answers are never used.
"""
import importlib
import math
import random
import time

import numpy as np
import torch
from peft import LoraConfig, get_peft_model

from . import grids as G
from . import textfmt as F

TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def _disable_torchao():
    """peft probes for torchao when it dispatches LoRA layers and raises on the old torchao of the Kaggle image;
    torchao is not used here (no quantisation), so the probe is answered False."""
    for mod in ("peft.import_utils", "peft.tuners.lora.torchao", "peft.utils.quantization_utils"):
        try:
            m = importlib.import_module(mod)
        except Exception:
            continue
        if hasattr(m, "is_torchao_available"):
            m.is_torchao_available = lambda: False


def lora_modules(model):
    for m in model.modules():
        if hasattr(m, "lora_A") and "default" in getattr(m, "lora_A", {}):
            yield m


class TTT:
    def __init__(self, lm, rank=64, alpha=64, lr=1e-4, max_tokens=8192, grad_ckpt=True, targets=None):
        self.lm, self.rank, self.alpha, self.lr, self.max_tokens = lm, rank, alpha, lr, max_tokens
        _disable_torchao()
        cfg = LoraConfig(r=rank, lora_alpha=alpha, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
                         target_modules=targets or TARGETS)
        self.model = get_peft_model(lm.model, cfg)
        lm.model = self.model                              # inference now runs through the adapter
        if grad_ckpt:
            self.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        self.params = [p for p in self.model.parameters() if p.requires_grad]
        self.n_params = sum(p.numel() for p in self.params)
        self.model.eval()

    def reset(self, seed):
        """A fresh adapter: the adapted model equals the frozen base again."""
        g = torch.Generator().manual_seed(seed)
        for p in self.params:                              # no gradient survives an interrupted step
            p.grad = None
        with torch.no_grad():
            for m in lora_modules(self.model):
                a, b = m.lora_A["default"].weight, m.lora_B["default"].weight
                bound = 1.0 / math.sqrt(a.shape[1])        # kaiming_uniform_(a=sqrt(5)) bound for fan_in
                a.copy_(torch.empty(a.shape).uniform_(-bound, bound, generator=g).to(a.dtype))
                b.zero_()

    def examples(self, pairs, seed):
        """An endless deterministic stream of (ids, labels) training sequences from the demonstrations."""
        rng = random.Random(seed)
        n = len(pairs)
        k = 0
        while True:
            hold = k % n
            k += 1
            t = rng.randrange(8)
            perm = G.random_perm(rng, keep_zero=True)
            aug = G.Aug(t, perm)
            ctx = [j for j in range(n) if j != hold]
            rng.shuffle(ctx)
            order = ctx + [hold]
            seq = [(aug.fwd(pairs[j][0]), aug.fwd(pairs[j][1])) for j in order]
            ids, labels = self._encode(seq)
            while len(ids) > self.max_tokens and len(seq) > 1:
                longest = max(range(len(seq) - 1), key=lambda i: len(F.grid_ids(seq[i][0])) +
                              len(F.grid_ids(seq[i][1])))
                seq.pop(longest)
                ids, labels = self._encode(seq)
            yield ids, labels

    @staticmethod
    def _encode(seq):
        """Chat tokens of the pairs; labels on every output after the first (on the only one if it is alone)."""
        ids, labels = [], []
        for idx, (i, o) in enumerate(seq):
            u = F.user_turn(i)
            ids += u
            labels += [-100] * len(u)
            head = [F.IMS, F.ASSIST, F.NL]
            body = F.grid_ids(o) + [F.IME]
            ids += head + body + [F.NL]
            labels += [-100] * len(head) + (body if idx > 0 or len(seq) == 1 else [-100] * len(body)) + [-100]
        return ids, labels

    def train(self, pairs, steps, seed, deadline=None, log_every=10):
        """Adapt a fresh adapter on the demonstrations. Returns statistics (loss curve, timing, memory)."""
        self.reset(seed)
        opt = torch.optim.AdamW(self.params, lr=self.lr, weight_decay=0.0, betas=(0.9, 0.999))
        opt.zero_grad(set_to_none=True)
        warm = max(1, steps // 10)

        def lr_at(s):
            if s < warm:
                return (s + 1) / warm
            return max(0.0, (steps - s) / max(1, steps - warm))
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_at)
        dev = self.lm.device
        stream = self.examples(pairs, seed)
        self.model.train()
        t0, tokens, curve, done = time.time(), 0, [], 0
        use_amp = self.lm.dtype == torch.bfloat16
        try:
            for s in range(steps):
                if deadline is not None and time.time() > deadline:
                    break
                ids, labels = next(stream)
                x = torch.tensor([ids], device=dev)
                y = torch.tensor([labels], device=dev)
                with torch.autocast(device_type=dev.type, dtype=torch.bfloat16, enabled=use_amp):
                    logits = self.model(input_ids=x, use_cache=False).logits[0, :-1].float()
                loss = torch.nn.functional.cross_entropy(logits, y[0, 1:], ignore_index=-100)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.params, 1.0)
                opt.step()
                sched.step()
                opt.zero_grad(set_to_none=True)
                tokens += len(ids)
                done += 1
                if s % log_every == 0 or s == steps - 1:
                    curve.append((s, round(float(loss.detach()), 4)))
        finally:
            self.model.eval()
            del opt
        return {"steps": done, "tokens": tokens, "train_s": round(time.time() - t0, 2), "loss_curve": curve,
                "rank": self.rank, "alpha": self.alpha, "lr": self.lr}
