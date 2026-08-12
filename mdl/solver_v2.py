#!/usr/bin/env python3
"""Per-task MDL solver v2: v1 core + directional ops + multi-sample voting.

Improvements over v1 (mdl/solver.py):
  1. Directional ops: cumulative max and shift along 4 axes (parameter-free
     core, with learned 1x1 projection in/out) — captures rays, edges,
     and propagation patterns critical for ARC.
  2. Multi-sample decoding with majority voting at test time (8 z samples
     from prior, per-cell majority vote).
  3. Reduced latent dim (16 vs 24) — mild pressure toward decoder reliance.

Levers tested and set aside (recorded for honest reporting):
  - DeepSets colour-equivariant encoder: too weak, 0% train exact.
  - Colour augmentation: incompatible with fixed nn.Embedding.
  - D4 train augmentation: collapses KL->0, kills z_opt at test time.
  - D4 test-time averaging: model is NOT equivariant, so TTA corrupts
    the correct prediction with 7 wrong-orientation logits.

Keeps same CLI contract as run_batch.py. Target: <300K params.
"""

import time
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


N_COLORS = 11
MAX_GRID = 30


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class MDLConfigV2:
    """Hyperparameters for the v2 MDL solver."""
    # Architecture
    hidden_dim: int = 48
    latent_dim: int = 16           # REDUCED from 24
    n_res_blocks: int = 3
    kernel_size: int = 3
    dir_dim: int = 12              # directional projection dimension

    # Training
    max_steps: int = 2000
    lr: float = 0.008              # same as v1
    beta1: float = 0.5
    beta2: float = 0.9
    beta_kl: float = 0.1          # same as v1 (D4+directional+voting carry the load)
    weight_decay: float = 1e-4
    early_stop_patience: int = 200

    # Augmentation
    d4_augment: bool = False        # D4 at train time collapses KL->0; use TTA only
    color_augment: bool = False     # incompatible with fixed nn.Embedding

    # Test decoding
    test_z_steps: int = 300
    test_z_lr: float = 0.01
    n_test_samples: int = 8       # z samples for majority voting
    d4_test_average: bool = False  # TTA hurts without D4 train augment

    # Misc
    seed: int = 42
    device: str = "cuda"
    log_interval: int = 200


# ---------------------------------------------------------------------------
# D4 and colour-permutation utilities
# ---------------------------------------------------------------------------

def _make_d4_transforms():
    """Return list of 8 (forward_fn, inverse_fn) pairs for the D4 group."""
    transforms = []
    for k in range(4):
        for flip in (False, True):
            def _fwd(x, _k=k, _flip=flip):
                if _flip:
                    x = torch.flip(x, [-1])
                if _k:
                    x = torch.rot90(x, _k, [-2, -1])
                return x

            def _inv(x, _k=k, _flip=flip):
                if _k:
                    x = torch.rot90(x, -_k, [-2, -1])
                if _flip:
                    x = torch.flip(x, [-1])
                return x

            transforms.append((_fwd, _inv))
    return transforms


D4_TRANSFORMS = _make_d4_transforms()


def random_color_perm(rng: np.random.RandomState):
    """Random permutation of the 11 ARC colours."""
    perm = list(range(N_COLORS))
    rng.shuffle(perm)
    return perm


def apply_color_perm(grid: torch.Tensor, perm: list, device):
    """Apply colour relabelling.  grid: long tensor of any shape."""
    lut = torch.tensor(perm, dtype=torch.long, device=device)
    return lut[grid]


# ---------------------------------------------------------------------------
# Building blocks (reuse v1 core + new directional layer)
# ---------------------------------------------------------------------------

class DirectionalOps(nn.Module):
    """Cumulative-max and shift along 4 axes.

    The cummax/shift operations themselves are parameter-free; learned 1x1
    convolutions project features in and out.
    """

    def __init__(self, in_channels: int, dir_dim: int = 12):
        super().__init__()
        self.proj_in = nn.Conv2d(in_channels, dir_dim, 1)
        self.proj_out = nn.Conv2d(dir_dim * 8 + in_channels, in_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        d = self.proj_in(x)
        parts = []

        # Cummax along 4 axes
        parts.append(torch.cummax(d, dim=2)[0])
        parts.append(torch.cummax(d.flip(2), dim=2)[0].flip(2))
        parts.append(torch.cummax(d, dim=3)[0])
        parts.append(torch.cummax(d.flip(3), dim=3)[0].flip(3))

        # Shift-by-1 along 4 axes
        parts.append(F.pad(d[:, :, :-1, :], (0, 0, 1, 0)))
        parts.append(F.pad(d[:, :, 1:, :], (0, 0, 0, 1)))
        parts.append(F.pad(d[:, :, :, :-1], (1, 0, 0, 0)))
        parts.append(F.pad(d[:, :, :, 1:], (0, 1, 0, 0)))

        return self.proj_out(torch.cat([x] + parts, dim=1))


class ResBlock(nn.Module):
    """Pre-norm residual block (identical to v1)."""

    def __init__(self, channels: int, kernel_size: int = 3):
        super().__init__()
        pad = kernel_size // 2
        self.norm1 = nn.GroupNorm(8, channels)
        self.conv1 = nn.Conv2d(channels, channels, kernel_size, padding=pad)
        self.norm2 = nn.GroupNorm(8, channels)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size, padding=pad)

    def forward(self, x):
        h = self.conv1(F.silu(self.norm1(x)))
        h = self.conv2(F.silu(self.norm2(h)))
        return x + h


class InputEncoder(nn.Module):
    """Encode an ARC input grid into feature maps (same as v1)."""

    def __init__(self, hidden_dim: int, kernel_size: int = 3):
        super().__init__()
        pad = kernel_size // 2
        self.color_embed = nn.Embedding(N_COLORS, hidden_dim)
        self.conv1 = nn.Conv2d(hidden_dim, hidden_dim, kernel_size, padding=pad)
        self.conv2 = nn.Conv2d(hidden_dim, hidden_dim, kernel_size, padding=pad)
        self.norm = nn.GroupNorm(8, hidden_dim)

    def forward(self, grid_tensor: torch.Tensor) -> torch.Tensor:
        x = self.color_embed(grid_tensor).permute(0, 3, 1, 2)
        x = F.silu(self.conv1(x))
        x = self.norm(F.silu(self.conv2(x)))
        return x


# ---------------------------------------------------------------------------
# Full decoder
# ---------------------------------------------------------------------------

class MDLDecoderV2(nn.Module):
    """v1 decoder + directional ops layer inserted after input encoding."""

    def __init__(self, cfg: MDLConfigV2):
        super().__init__()
        self.cfg = cfg
        hd = cfg.hidden_dim

        self.input_enc = InputEncoder(hd, cfg.kernel_size)
        self.directional = DirectionalOps(hd, cfg.dir_dim)
        self.latent_proj = nn.Linear(cfg.latent_dim, hd)
        self.fuse = nn.Conv2d(hd * 2, hd, 1)
        self.res_blocks = nn.ModuleList(
            [ResBlock(hd, cfg.kernel_size) for _ in range(cfg.n_res_blocks)])
        self.out_norm = nn.GroupNorm(8, hd)
        self.out_head = nn.Conv2d(hd, N_COLORS, 1)

    def forward(self, input_grid: torch.Tensor, z: torch.Tensor,
                out_h: int, out_w: int) -> torch.Tensor:
        B = input_grid.shape[0]

        inp_feat = self.input_enc(input_grid)
        inp_feat = self.directional(inp_feat)

        if inp_feat.shape[2] != out_h or inp_feat.shape[3] != out_w:
            inp_feat = F.interpolate(
                inp_feat, (out_h, out_w), mode='bilinear', align_corners=False)

        z_feat = self.latent_proj(z).unsqueeze(-1).unsqueeze(-1)
        z_feat = z_feat.expand(-1, -1, out_h, out_w)

        x = self.fuse(torch.cat([inp_feat, z_feat], dim=1))

        for blk in self.res_blocks:
            x = blk(x)

        return self.out_head(F.silu(self.out_norm(x)))


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class PerTaskMDLv2:
    """Per-task MDL solver v2: v1 core + directional ops + augmentation
    + reduced latent + multi-sample voting."""

    def __init__(self, task: dict, cfg: Optional[MDLConfigV2] = None,
                 solutions: Optional[list] = None):
        self.task = task
        self.cfg = cfg or MDLConfigV2()
        self.solutions = solutions
        self.device = torch.device(
            self.cfg.device if torch.cuda.is_available() else "cpu")

        self.train_inputs = [np.array(ex['input'], dtype=np.int64)
                             for ex in task['train']]
        self.train_outputs = [np.array(ex['output'], dtype=np.int64)
                              for ex in task['train']]
        self.test_inputs = [np.array(ex['input'], dtype=np.int64)
                            for ex in task['test']]
        self.n_train = len(self.train_inputs)

        self._determine_output_size_strategy()

        self._rng = np.random.RandomState(self.cfg.seed)
        torch.manual_seed(self.cfg.seed)

        self.model = MDLDecoderV2(self.cfg).to(self.device)

        ld = self.cfg.latent_dim
        self.z_means = nn.ParameterList([
            nn.Parameter(torch.randn(ld, device=self.device) * 0.01)
            for _ in range(self.n_train)])
        self.z_log_vars = nn.ParameterList([
            nn.Parameter(torch.full((ld,), -4.0, device=self.device))
            for _ in range(self.n_train)])

        self.n_params = (sum(p.numel() for p in self.model.parameters())
                         + sum(p.numel() for p in self.z_means.parameters())
                         + sum(p.numel() for p in self.z_log_vars.parameters()))

        # Pre-compute D4 variants of train data
        self._d4_train = self._precompute_d4_variants()
        self._valid_d4_indices = self._get_valid_d4_indices()

    # -- size strategy (same as v1) ----------------------------------------

    def _determine_output_size_strategy(self):
        same = all(self.train_outputs[i].shape == self.train_inputs[i].shape
                   for i in range(self.n_train))
        if same:
            self.size_strategy = 'same_as_input'
            return
        shapes = [o.shape for o in self.train_outputs]
        if len(set(shapes)) == 1:
            self.size_strategy = 'fixed'
            self.fixed_out_shape = shapes[0]
            return
        from collections import Counter as _C
        self.size_strategy = 'mode'
        self.fixed_out_shape = _C(shapes).most_common(1)[0][0]

    def _get_output_size(self, test_input):
        if self.size_strategy == 'same_as_input':
            return test_input.shape[0], test_input.shape[1]
        return self.fixed_out_shape

    def _get_valid_d4_indices(self):
        if self.size_strategy == 'same_as_input':
            return list(range(8))
        oh, ow = self.fixed_out_shape
        if oh == ow:
            return list(range(8))
        valid = []
        for idx, (fwd, _) in enumerate(D4_TRANSFORMS):
            probe = torch.zeros(1, oh, ow)
            out = fwd(probe)
            if out.shape[-2] == oh and out.shape[-1] == ow:
                valid.append(idx)
        return valid

    # -- D4 pre-computation ------------------------------------------------

    def _precompute_d4_variants(self):
        variants = []
        for fwd, _ in D4_TRANSFORMS:
            pairs = []
            for i in range(self.n_train):
                inp_t = torch.from_numpy(self.train_inputs[i])
                out_t = torch.from_numpy(self.train_outputs[i])
                pairs.append((fwd(inp_t), fwd(out_t)))
            variants.append(pairs)
        return variants

    # -- reparameterization ------------------------------------------------

    @staticmethod
    def _reparameterize(mean, log_var):
        return mean + torch.randn_like(mean) * torch.exp(0.5 * log_var)

    @staticmethod
    def _kl_divergence(mean, log_var):
        return -0.5 * torch.sum(1 + log_var - mean.pow(2) - log_var.exp())

    # -- batch helpers -----------------------------------------------------

    def _can_batch(self, d4_idx):
        shapes = set()
        for i in range(self.n_train):
            _, out_t = self._d4_train[d4_idx][i]
            shapes.add((out_t.shape[-2], out_t.shape[-1]))
        return len(shapes) == 1

    def _build_batch(self, d4_idx, color_perm):
        pairs = self._d4_train[d4_idx]
        oh, ow = pairs[0][1].shape[-2], pairs[0][1].shape[-1]

        max_ih = max(p[0].shape[-2] for p in pairs)
        max_iw = max(p[0].shape[-1] for p in pairs)

        inp_b = torch.zeros(self.n_train, max_ih, max_iw,
                            dtype=torch.long, device=self.device)
        out_b = torch.zeros(self.n_train, oh, ow,
                            dtype=torch.long, device=self.device)

        for i in range(self.n_train):
            inp_t, out_t = pairs[i]
            ih, iw = inp_t.shape[-2], inp_t.shape[-1]
            inp_i = inp_t.to(self.device)
            out_i = out_t.to(self.device)
            if color_perm is not None:
                inp_i = apply_color_perm(inp_i, color_perm, self.device)
                out_i = apply_color_perm(out_i, color_perm, self.device)
            inp_b[i, :ih, :iw] = inp_i
            out_b[i] = out_i

        return inp_b, out_b, oh, ow

    # -- training ----------------------------------------------------------

    def train(self):
        cfg = self.cfg
        model = self.model
        model.train()

        all_params = (list(model.parameters())
                      + list(self.z_means.parameters())
                      + list(self.z_log_vars.parameters()))
        optimizer = torch.optim.Adam(
            all_params, lr=cfg.lr, betas=(cfg.beta1, cfg.beta2),
            weight_decay=cfg.weight_decay)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=cfg.max_steps, eta_min=cfg.lr * 0.01)

        history = {'loss': [], 'ce': [], 'kl': [], 'train_exact': []}
        exact_count = 0
        t0 = time.time()

        for step in range(cfg.max_steps):
            optimizer.zero_grad()

            d4_idx = self._rng.randint(8) if cfg.d4_augment else 0
            color_perm = (random_color_perm(self._rng)
                          if cfg.color_augment else None)

            batchable = self._can_batch(d4_idx)

            if batchable:
                inp_b, out_b, oh, ow = self._build_batch(d4_idx, color_perm)
                zs = []
                kl_sum = torch.tensor(0.0, device=self.device)
                for i in range(self.n_train):
                    z = self._reparameterize(
                        self.z_means[i], self.z_log_vars[i])
                    zs.append(z)
                    kl_sum = kl_sum + self._kl_divergence(
                        self.z_means[i], self.z_log_vars[i])
                z_batch = torch.stack(zs)
                logits = model(inp_b, z_batch, oh, ow)
                ce = F.cross_entropy(logits, out_b, reduction='sum')
                loss = ce + cfg.beta_kl * kl_sum
                loss.backward()
                total_ce = ce.item()
                total_kl = kl_sum.item()
            else:
                total_ce = 0.0
                total_kl = 0.0
                for i in range(self.n_train):
                    inp_t, out_t = self._d4_train[d4_idx][i]
                    inp_t = inp_t.to(self.device)
                    out_t = out_t.to(self.device)
                    if color_perm is not None:
                        inp_t = apply_color_perm(
                            inp_t, color_perm, self.device)
                        out_t = apply_color_perm(
                            out_t, color_perm, self.device)
                    oh, ow = out_t.shape[-2], out_t.shape[-1]
                    z = self._reparameterize(
                        self.z_means[i], self.z_log_vars[i]).unsqueeze(0)
                    kl = self._kl_divergence(
                        self.z_means[i], self.z_log_vars[i])
                    logits = model(inp_t.unsqueeze(0), z, oh, ow)
                    ce = F.cross_entropy(logits, out_t.unsqueeze(0),
                                         reduction='sum')
                    (ce + cfg.beta_kl * kl).backward()
                    total_ce += ce.item()
                    total_kl += kl.item()

            torch.nn.utils.clip_grad_norm_(all_params, 1.0)
            optimizer.step()
            scheduler.step()

            train_exact = self._check_train_exact()
            total_loss = total_ce + cfg.beta_kl * total_kl
            history['loss'].append(total_loss)
            history['ce'].append(total_ce)
            history['kl'].append(total_kl)
            history['train_exact'].append(train_exact)

            exact_count = exact_count + 1 if train_exact else 0

            if step % cfg.log_interval == 0:
                elapsed = time.time() - t0
                print(f"  step {step:4d} | loss={total_loss:.3f} "
                      f"ce={total_ce:.3f} kl={total_kl:.3f} "
                      f"exact={train_exact} | {elapsed:.1f}s", flush=True)

            if exact_count >= cfg.early_stop_patience and step >= 400:
                print(f"  early stop at step {step} "
                      f"(exact for {exact_count} steps)", flush=True)
                break

        self.train_time = time.time() - t0
        self.final_train_exact = self._check_train_exact()
        return history

    @torch.no_grad()
    def _check_train_exact(self):
        self.model.eval()
        for i in range(self.n_train):
            oh, ow = self.train_outputs[i].shape
            inp = torch.from_numpy(
                self.train_inputs[i]).unsqueeze(0).to(self.device)
            z = self.z_means[i].unsqueeze(0)
            logits = self.model(inp, z, oh, ow)
            pred = logits.argmax(1).squeeze(0).cpu().numpy()
            if not np.array_equal(pred, self.train_outputs[i]):
                self.model.train()
                return False
        self.model.train()
        return True

    # -- test prediction ---------------------------------------------------

    def predict_test(self, test_idx: int = 0):
        """Multi-strategy + D4 averaging + voting."""
        self.model.eval()
        test_input = self.test_inputs[test_idx]
        out_h, out_w = self._get_output_size(test_input)

        for p in self.model.parameters():
            p.requires_grad_(False)

        # Strategy 1: z=0 with D4 averaging
        z_zero = torch.zeros(1, self.cfg.latent_dim, device=self.device)
        logits_zero = self._d4_logits(test_input, z_zero, out_h, out_w)
        pred_zero = logits_zero.argmax(1).squeeze(0).cpu().numpy()
        ent_zero = self._logit_entropy(logits_zero)

        # Strategy 2: mean of train z
        with torch.no_grad():
            z_mean = torch.stack(
                [m.data for m in self.z_means]).mean(0, keepdim=True)
        logits_mean = self._d4_logits(test_input, z_mean, out_h, out_w)
        pred_mean = logits_mean.argmax(1).squeeze(0).cpu().numpy()
        ent_mean = self._logit_entropy(logits_mean)

        # Strategy 3: optimised z
        z_opt = self._optimize_test_z(test_input, out_h, out_w)
        logits_opt = self._d4_logits(test_input, z_opt, out_h, out_w)
        pred_opt = logits_opt.argmax(1).squeeze(0).cpu().numpy()
        ent_opt = self._logit_entropy(logits_opt)

        # Strategy 4: multi-sample voting
        pred_vote = self._multi_sample_vote(test_input, out_h, out_w)
        ent_vote = self._pred_entropy_arr(np.array(pred_vote))

        for p in self.model.parameters():
            p.requires_grad_(True)

        # Pick lowest-entropy strategy
        candidates = [
            (pred_zero.tolist(), 'z_zero', ent_zero),
            (pred_mean.tolist(), 'z_mean', ent_mean),
            (pred_opt.tolist(), 'z_opt', ent_opt),
            (pred_vote, 'vote', ent_vote),
        ]

        best = min(candidates, key=lambda c: c[2])
        self._test_strategy = best[1]
        return best[0]

    @torch.no_grad()
    def _d4_logits(self, test_input_np, z, out_h, out_w):
        """Average logits over valid D4 transforms."""
        if not self.cfg.d4_test_average:
            indices = [0]
        else:
            indices = self._valid_d4_indices

        accum = None
        for idx in indices:
            fwd, inv = D4_TRANSFORMS[idx]
            inp_t = torch.from_numpy(test_input_np).to(self.device)
            inp_t = fwd(inp_t).unsqueeze(0)

            if self.size_strategy == 'same_as_input':
                cur_oh, cur_ow = inp_t.shape[-2], inp_t.shape[-1]
            else:
                cur_oh, cur_ow = out_h, out_w

            logits = self.model(inp_t, z, cur_oh, cur_ow)
            logits = inv(logits)

            accum = logits if accum is None else accum + logits

        return accum / len(indices)

    def _optimize_test_z(self, test_input_np, out_h, out_w):
        z_test = nn.Parameter(
            torch.zeros(1, self.cfg.latent_dim, device=self.device))
        opt = torch.optim.Adam([z_test], lr=self.cfg.test_z_lr)
        inp = torch.from_numpy(test_input_np).unsqueeze(0).to(self.device)

        best_z = z_test.data.clone()
        best_ent = float('inf')

        for _ in range(self.cfg.test_z_steps):
            opt.zero_grad()
            logits = self.model(inp, z_test, out_h, out_w)
            probs = F.softmax(logits, dim=1)
            log_probs = F.log_softmax(logits, dim=1)
            entropy = -(probs * log_probs).sum(1).mean()
            kl = 0.5 * z_test.pow(2).sum()
            (entropy + 0.01 * kl).backward()
            opt.step()
            if entropy.item() < best_ent:
                best_ent = entropy.item()
                best_z = z_test.data.clone()

        return best_z

    @torch.no_grad()
    def _multi_sample_vote(self, test_input_np, out_h, out_w):
        """Sample z from prior, D4-average, majority vote per cell."""
        preds = []
        for _ in range(self.cfg.n_test_samples):
            z = torch.randn(1, self.cfg.latent_dim, device=self.device)
            logits = self._d4_logits(test_input_np, z, out_h, out_w)
            pred = logits.argmax(1).squeeze(0).cpu().numpy()
            preds.append(pred)

        stacked = np.stack(preds)
        result = np.zeros((out_h, out_w), dtype=np.int64)
        for r in range(out_h):
            for c in range(out_w):
                counts = Counter(stacked[:, r, c].tolist())
                result[r, c] = counts.most_common(1)[0][0]
        return result.tolist()

    @staticmethod
    def _logit_entropy(logits):
        probs = F.softmax(logits, dim=1)
        log_probs = F.log_softmax(logits, dim=1)
        return -(probs * log_probs).sum(1).mean().item()

    @staticmethod
    def _pred_entropy_arr(arr):
        flat = arr.flatten()
        counts = np.bincount(flat, minlength=N_COLORS).astype(float)
        probs = counts / counts.sum()
        probs = probs[probs > 0]
        return -np.sum(probs * np.log(probs + 1e-12))

    # -- full solve --------------------------------------------------------

    def solve(self):
        t_start = time.time()
        history = self.train()

        test_preds = []
        for i in range(len(self.test_inputs)):
            pred = self.predict_test(i)
            test_preds.append(pred)

        wall_time = time.time() - t_start

        test_correct = []
        if self.solutions:
            for i, pred in enumerate(test_preds):
                if i < len(self.solutions):
                    sol = self.solutions[i]
                    if isinstance(sol, np.ndarray):
                        correct = np.array_equal(np.array(pred), sol)
                    else:
                        correct = (pred == sol)
                    test_correct.append(correct)

        return {
            'train_exact': self.final_train_exact,
            'test_preds': test_preds,
            'test_correct': test_correct if self.solutions else None,
            'wall_time': wall_time,
            'train_time': self.train_time,
            'n_params': self.n_params,
            'size_strategy': self.size_strategy,
            'test_strategy': getattr(self, '_test_strategy', 'unknown'),
            'n_train_pairs': self.n_train,
            'final_ce': history['ce'][-1] if history['ce'] else None,
            'final_kl': history['kl'][-1] if history['kl'] else None,
        }
