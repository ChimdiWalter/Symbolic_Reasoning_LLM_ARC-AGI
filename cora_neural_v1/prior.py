"""The learned program prior of Neural-CORA v1, and its controls.

**Encoder** (frozen): the NVARC Qwen3-4B checkpoint `sorokin/qwen3_4b_grids15_sft139` (Apache-2.0; NVARC team).
- Fp16 on one GPU.
- It reads the demonstrations and the test input in NVARC's own chat format, the format it was trained on.
- Features: the mean last-layer hidden state over all tokens and over output-grid tokens; the last token's state;
  and the means of layers 27 and 18 (12,800 values). Their meaning is learned; nothing is hand-chosen inside them.
- The checkpoint cannot emit program text (16-token vocabulary). So the trainable part reads its hidden states.

**Trainable adapter** (ours; real gradient updates): an MLP with five heads.
- variant: 7, multi-label;
- number of rules: 2, softmax;
- default: 2, softmax;
- selector bag: 31, multi-label;
- action bag: 92, multi-label.

It is trained on CORA's own execution-validated synthetic tasks.

**Targets are extensional:** every component value that, swapped into the generating program, still reproduces every
demonstration counts as correct. So equivalent programs are grouped, not penalized for different spelling.

**Scores:** log-probabilities over the components. CORA's enumerator (`space.enumerate_programs`) turns them into a
best-first order. The prior never sees a test output, never outputs a grid and never decides acceptance.

**Controls:**
- L0: the same heads, untrained (fixed seed);
- L0s: heads trained on targets shuffled across tasks;
- L1h: the same heads trained on ~90 hand-crafted delta features, with no neural encoder, to test whether the
  encoder matters.
"""
import os

import numpy as np

from cora_neural_v1 import interp as I
from cora_neural_v1 import space as SP
from cora_neural_v1.ir import ACTIONS, ACT_INDEX, DEFAULTS, SELECTORS, SEL_INDEX, VARIANTS, VAR_INDEX, Hypothesis, Rule

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(HERE, "outputs", "neural_cora_v0", "models", "nvarc_qwen3_4b_grids15_sft139_v1")
LAYERS = (-1, 27, 18)
FEAT_DIM = 5 * 2560


# ------------------------------------------------------------------ targets (execution-derived, demonstrations only)
def targets(task):
    """Multi-hot extensional targets from the generating program; reads the demonstrations only."""
    h = Hypothesis.from_dict(task["program"])
    train = task["train"]
    y_var = np.zeros(len(VARIANTS), np.float32)
    for v in VARIANTS:
        if I.fit(Hypothesis(v, h.rules, h.default), train)[0]:
            y_var[VAR_INDEX[v]] = 1
    y_sel = np.zeros(len(SELECTORS), np.float32)
    y_act = np.zeros(len(ACTIONS), np.float32)
    for i, r in enumerate(h.rules):
        for s in SELECTORS:
            rules = tuple(Rule(s, x.action) if j == i else x for j, x in enumerate(h.rules))
            if s == r.selector or I.fit(Hypothesis(h.variant, rules, h.default), train)[0]:
                y_sel[SEL_INDEX[s]] = 1
        for a in ACTIONS:
            rules = tuple(Rule(x.selector, a) if j == i else x for j, x in enumerate(h.rules))
            if a == r.action or I.fit(Hypothesis(h.variant, rules, h.default), train)[0]:
                y_act[ACT_INDEX[a]] = 1
    y_def = np.zeros(2, np.float32)
    for d in DEFAULTS:
        if d == h.default or I.fit(Hypothesis(h.variant, h.rules, d), train)[0]:
            y_def[DEFAULTS.index(d)] = 1
    y_n = np.float32(len(h.rules) - 1)
    return {"var": y_var, "sel": y_sel, "act": y_act, "def": y_def, "n": y_n}


# ------------------------------------------------------------------ encoder features
def g2s(g):
    return "\n".join("".join(str(int(c)) for c in row) for row in g)


def task_text(task):
    t = "".join(f"<|im_start|>user\n{g2s(a)}<|im_end|><|im_start|>assistant\n{g2s(b)}<|im_end|>" for a, b in task["train"])
    return t + f"<|im_start|>user\n{g2s(task['test_inputs'][0])}<|im_end|>"


class QwenEncoder:
    def __init__(self, model_dir=MODEL_DIR, device="cuda:0"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForCausalLM.from_pretrained(model_dir, torch_dtype=torch.float16, device_map=device,
                                                          low_cpu_mem_usage=True).eval()
        self.device = device
        self.asst = self.tok.convert_tokens_to_ids("assistant")
        self.im_end = self.tok.convert_tokens_to_ids("<|im_end|>")

    def features(self, task):
        torch = self.torch
        ids = self.tok(task_text(task), return_tensors="pt").input_ids.to(self.device)
        with torch.no_grad():
            out = self.model(ids, output_hidden_states=True)
        hs = out.hidden_states
        seq = ids[0].tolist()
        mask = np.zeros(len(seq), bool)                      # tokens inside assistant turns = output grids
        inside = False
        for i, t in enumerate(seq):
            if t == self.asst:
                inside = True
                continue
            if t == self.im_end:
                inside = False
            mask[i] = inside
        m = torch.tensor(mask, device=self.device)
        last = hs[-1][0].float()
        parts = [last.mean(0), last[m].mean(0) if m.any() else last.mean(0), last[-1],
                 hs[LAYERS[1]][0].float().mean(0), hs[LAYERS[2]][0].float().mean(0)]
        f = torch.cat(parts).cpu().numpy()
        if not np.isfinite(f).all():
            raise FloatingPointError("non-finite encoder features")
        return f.astype(np.float16), len(seq)


def hand_features(task):
    """~90 hand-crafted delta features (the L1h control; no neural encoder)."""
    train = task["train"]
    f = []
    cin, cout, add, rem, rec = (np.zeros(10) for _ in range(5))
    nobj_in = nobj_out = 0
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        for c in range(10):
            cin[c] += (A == c).sum()
            cout[c] += (B == c).sum()
            add[c] += ((A == 0) & (B == c)).sum()
            rem[c] += ((A == c) & (B == 0)).sum()
            rec[c] += ((A == c) & (B != c) & (B != 0)).sum()
        nobj_in += len(SP._objects(A))
        nobj_out += len(SP._objects(B))
    ev = SP.change_kinds(train)
    tot = max(1.0, cin[1:].sum())
    f += list(cin[1:] / tot) + list(cout[1:] / tot) + list(add[1:] / tot) + list(rem[1:] / tot) + list(rec[1:] / tot)
    f += [nobj_in / 10, nobj_out / 10, (nobj_out - nobj_in) / 10]
    f += [float(k in ev["kinds"]) for k in ("recolour", "move", "delete", "line")]
    vec = np.zeros(len(SP.VECTORS))
    for (dr, dc), n in ev["vectors"].items():
        if (dr, dc) in SP.VECTORS:
            vec[SP.VECTORS.index((dr, dc))] += n
    f += list(vec / max(1.0, vec.sum()))
    f += [float(ev["line_added"]), float(ev["deleted_any"]), float(len(ev["kinds"]))]
    return np.asarray(f, np.float32)


# ------------------------------------------------------------------ the trainable heads
def build_heads(in_dim, seed, hidden=1024):
    import torch
    import torch.nn as nn
    torch.manual_seed(seed)

    class Heads(nn.Module):
        def __init__(self):
            super().__init__()
            self.trunk = nn.Sequential(nn.Linear(in_dim, hidden), nn.GELU(), nn.Dropout(0.2),
                                       nn.Linear(hidden, 512), nn.GELU(), nn.Dropout(0.1))
            self.var = nn.Linear(512, len(VARIANTS))
            self.n = nn.Linear(512, 2)
            self.dflt = nn.Linear(512, 2)
            self.sel = nn.Linear(512, len(SELECTORS))
            self.act = nn.Linear(512, len(ACTIONS))

        def forward(self, x):
            z = self.trunk(x)
            return {"var": self.var(z), "n": self.n(z), "def": self.dflt(z), "sel": self.sel(z), "act": self.act(z)}
    return Heads()


def _loss(out, Y):
    import torch.nn.functional as F
    return (F.binary_cross_entropy_with_logits(out["var"], Y["var"])
            + F.cross_entropy(out["n"], Y["n"].long())
            + F.binary_cross_entropy_with_logits(out["def"], Y["def"])
            + 4.0 * F.binary_cross_entropy_with_logits(out["sel"], Y["sel"])
            + 4.0 * F.binary_cross_entropy_with_logits(out["act"], Y["act"]))


def weights_sha(m):
    """sha256 of every parameter tensor's bytes, in state_dict order."""
    import hashlib
    h = hashlib.sha256()
    for k, v in m.state_dict().items():
        h.update(k.encode())
        h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def train_heads(X, Ys, Xv, Yv, seed, epochs=60, lr=1e-3, wd=1e-4, batch=128, device="cpu", log=None, stats=None):
    """Gradient training of the heads; the epoch with the best validation loss is kept. Returns (model, history).
    If `stats` is a dict, it receives the evidence that training happened: trainable parameter count, initial and
    final weight hashes, optimizer steps, per-epoch mean gradient norm, and the L2 distance the weights moved."""
    import copy
    import torch
    torch.manual_seed(seed)
    m = build_heads(X.shape[1], seed).to(device)
    w0 = {k: v.detach().clone() for k, v in m.state_dict().items()}
    if stats is not None:
        stats.update({"trainable_params": int(sum(p.numel() for p in m.parameters() if p.requires_grad)),
                      "initial_weights_sha256": weights_sha(m), "optimizer_steps": 0, "grad_norm_mean_by_epoch": []})
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=wd)
    Xt = torch.tensor(X, dtype=torch.float32, device=device)
    Yt = {k: torch.tensor(v, device=device) for k, v in Ys.items()}
    Xvt = torch.tensor(Xv, dtype=torch.float32, device=device)
    Yvt = {k: torch.tensor(v, device=device) for k, v in Yv.items()}
    g = torch.Generator(device="cpu").manual_seed(seed)
    best, best_state, hist = float("inf"), None, []
    for ep in range(epochs):
        m.train()
        perm = torch.randperm(len(Xt), generator=g)
        tl, gn = 0.0, []
        for i in range(0, len(Xt), batch):
            idx = perm[i:i + batch].to(device)
            loss = _loss(m(Xt[idx]), {k: v[idx] for k, v in Yt.items()})
            opt.zero_grad()
            loss.backward()
            if stats is not None:
                gn.append(float(torch.sqrt(sum((p.grad.detach() ** 2).sum() for p in m.parameters() if p.grad is not None))))
                stats["optimizer_steps"] += 1
            opt.step()
            tl += float(loss.detach()) * len(idx)
        if stats is not None:
            stats["grad_norm_mean_by_epoch"].append(round(float(np.mean(gn)), 5))
        m.eval()
        with torch.no_grad():
            vl = float(_loss(m(Xvt), Yvt))
        hist.append({"epoch": ep, "train_loss": round(tl / len(Xt), 5), "val_loss": round(vl, 5)})
        if log:
            log(hist[-1])
        if vl < best:
            best, best_state = vl, copy.deepcopy(m.state_dict())
    m.load_state_dict(best_state)
    m.eval()
    if stats is not None:
        moved = sum(float(((v.detach() - w0[k]) ** 2).sum()) for k, v in m.state_dict().items() if v.dtype.is_floating_point)
        stats.update({"final_weights_sha256": weights_sha(m), "kept_epoch": int(np.argmin([h["val_loss"] for h in hist])),
                      "weight_l2_moved": round(moved ** 0.5, 5)})
    return m, hist


def head_scores(m, x, doms, device="cpu"):
    """Component log-probabilities for one task, restricted to the arm-independent pruned domains."""
    import torch
    import torch.nn.functional as F
    with torch.no_grad():
        o = m(torch.tensor(x[None], dtype=torch.float32, device=device))
    lv = F.logsigmoid(o["var"][0]).cpu().numpy()
    ln = F.log_softmax(o["n"][0], -1).cpu().numpy()
    ld = F.log_softmax(o["def"][0], -1).cpu().numpy()
    ls = F.logsigmoid(o["sel"][0]).cpu().numpy()
    la = F.logsigmoid(o["act"][0]).cpu().numpy()
    return {"variant": {v: float(lv[VAR_INDEX[v]]) for v in doms["variants"]}, "n_rules": {1: float(ln[0]), 2: float(ln[1])},
            "default": {d: float(ld[DEFAULTS.index(d)]) for d in doms["defaults"]},
            "selector": {s: float(ls[SEL_INDEX[s]]) for s in doms["selectors"]},
            "action": {a: float(la[ACT_INDEX[a]]) for a in doms["actions"]}}
