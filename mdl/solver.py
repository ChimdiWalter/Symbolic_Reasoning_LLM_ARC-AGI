#!/usr/bin/env python3
"""Per-task MDL solver: CompressARC-style per-task compression via gradient descent.

For a single ARC task (train pairs + test input), trains a small network from
scratch to jointly compress the train outputs under minimum-description-length.
The network that best compresses the demos encodes the task's rule; the test
output is decoded from the same network conditioned on the test input.

Architecture (simplified, faithful variant of CompressARC):
  - Per-example latent codes z_i ~ N(mu_i, sigma_i) (learned per train pair)
  - Shared small decoder: input grid -> conv features, concatenated with z,
    processed by a few residual conv blocks -> per-cell 11-class logits
  - MDL objective: sum_i CE(output_i, pred_i) + beta * KL(q(z_i) || N(0,I))
                   + lambda * ||theta||^2  (weight description length)
  - Test: optimize a fresh z_test while keeping decoder frozen, or simply
    run the decoder with z=0 (MAP prior) conditioned on test input.

No pretraining. No external data. ~50-150K params depending on grid size.
"""

import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


# ARC: 11 colors (0=black, 1-9 = colors, 10 = padding/background)
N_COLORS = 11
MAX_GRID = 30


@dataclass
class MDLConfig:
    """Hyperparameters for the per-task MDL solver."""
    # Architecture  (target <200K params total)
    hidden_dim: int = 48          # conv channel width
    latent_dim: int = 24          # per-example latent dimension
    n_res_blocks: int = 3         # residual conv blocks in decoder
    kernel_size: int = 3          # conv kernel size

    # Training
    max_steps: int = 2000         # max gradient steps
    lr: float = 0.008             # Adam learning rate
    beta1: float = 0.5            # Adam beta1
    beta2: float = 0.9            # Adam beta2
    beta_kl: float = 0.1          # KL weight (beta in beta-VAE)
    weight_decay: float = 1e-4    # L2 regularization (param description length)
    early_stop_patience: int = 200  # stop if train CE = 0 for this many steps

    # Test decoding
    test_z_steps: int = 300       # steps to optimize z_test with frozen decoder
    test_z_lr: float = 0.01       # lr for z_test optimization

    # Misc
    seed: int = 42
    device: str = "cuda"
    log_interval: int = 100       # print every N steps


class ResBlock(nn.Module):
    """Pre-norm residual block with two conv layers."""

    def __init__(self, channels, kernel_size=3):
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
    """Encode an ARC input grid into feature maps."""

    def __init__(self, hidden_dim, kernel_size=3):
        super().__init__()
        pad = kernel_size // 2
        # Embed each cell's color into hidden_dim channels
        self.color_embed = nn.Embedding(N_COLORS, hidden_dim)
        self.conv1 = nn.Conv2d(hidden_dim, hidden_dim, kernel_size, padding=pad)
        self.conv2 = nn.Conv2d(hidden_dim, hidden_dim, kernel_size, padding=pad)
        self.norm = nn.GroupNorm(8, hidden_dim)

    def forward(self, grid_tensor):
        """grid_tensor: (B, H, W) long tensor of color indices."""
        # (B, H, W, C) -> (B, C, H, W)
        x = self.color_embed(grid_tensor).permute(0, 3, 1, 2)
        x = F.silu(self.conv1(x))
        x = self.norm(F.silu(self.conv2(x)))
        return x  # (B, hidden_dim, H, W)


class MDLDecoder(nn.Module):
    """Shared decoder: input features + latent -> output grid logits.

    The decoder processes the input grid features concatenated with a
    spatially-broadcast latent code through residual conv blocks, then
    produces per-cell color logits.
    """

    def __init__(self, cfg: MDLConfig):
        super().__init__()
        self.cfg = cfg
        hd = cfg.hidden_dim
        ld = cfg.latent_dim

        self.input_enc = InputEncoder(hd, cfg.kernel_size)

        # Project latent to spatial features (broadcast then conv)
        self.latent_proj = nn.Linear(ld, hd)

        # Fuse input features + latent features
        self.fuse = nn.Conv2d(hd * 2, hd, 1)

        # Residual blocks
        self.res_blocks = nn.ModuleList([
            ResBlock(hd, cfg.kernel_size) for _ in range(cfg.n_res_blocks)
        ])

        # Output head: per-cell color logits
        self.out_norm = nn.GroupNorm(8, hd)
        self.out_head = nn.Conv2d(hd, N_COLORS, 1)

    def forward(self, input_grid, z, out_h, out_w):
        """
        input_grid: (B, H_in, W_in) long
        z: (B, latent_dim)
        out_h, out_w: target output dimensions
        Returns: (B, N_COLORS, out_h, out_w) logits
        """
        B = input_grid.shape[0]

        # Encode input grid
        inp_feat = self.input_enc(input_grid)  # (B, hd, H_in, W_in)

        # Resize input features to output grid size
        if inp_feat.shape[2] != out_h or inp_feat.shape[3] != out_w:
            inp_feat = F.interpolate(inp_feat, size=(out_h, out_w),
                                     mode='bilinear', align_corners=False)

        # Broadcast latent to spatial
        z_feat = self.latent_proj(z)  # (B, hd)
        z_feat = z_feat.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, out_h, out_w)

        # Fuse
        x = self.fuse(torch.cat([inp_feat, z_feat], dim=1))  # (B, hd, H, W)

        # Residual blocks
        for block in self.res_blocks:
            x = block(x)

        # Output head
        x = self.out_head(F.silu(self.out_norm(x)))  # (B, N_COLORS, H, W)
        return x


class PerTaskMDL:
    """Per-task MDL solver: trains a small network from scratch on one ARC task."""

    def __init__(self, task: dict, cfg: Optional[MDLConfig] = None,
                 solutions: Optional[list] = None):
        """
        task: ARC task dict with 'train' and 'test' keys.
              train: list of {input: grid, output: grid}
              test: list of {input: grid}
        solutions: optional list of test output grids (for scoring only,
                   NEVER used during training/optimization)
        cfg: MDLConfig
        """
        self.task = task
        self.cfg = cfg or MDLConfig()
        self.solutions = solutions
        self.device = torch.device(self.cfg.device if torch.cuda.is_available()
                                   else "cpu")

        # Parse grids
        self.train_inputs = [np.array(ex['input'], dtype=np.int64)
                             for ex in task['train']]
        self.train_outputs = [np.array(ex['output'], dtype=np.int64)
                              for ex in task['train']]
        self.test_inputs = [np.array(ex['input'], dtype=np.int64)
                            for ex in task['test']]
        self.n_train = len(self.train_inputs)

        # Determine output size strategy
        self._determine_output_size_strategy()

        # Set seed
        torch.manual_seed(self.cfg.seed)
        np.random.seed(self.cfg.seed)

        # Build model
        self.model = MDLDecoder(self.cfg).to(self.device)

        # Per-example latent parameters (mean + log_var)
        self.z_means = nn.ParameterList([
            nn.Parameter(torch.randn(self.cfg.latent_dim, device=self.device) * 0.01)
            for _ in range(self.n_train)
        ])
        self.z_log_vars = nn.ParameterList([
            nn.Parameter(torch.full((self.cfg.latent_dim,), -4.0,
                                    device=self.device))
            for _ in range(self.n_train)
        ])

        # Count params
        self.n_params = sum(p.numel() for p in self.model.parameters())
        self.n_params += sum(p.numel() for p in self.z_means.parameters())
        self.n_params += sum(p.numel() for p in self.z_log_vars.parameters())

    def _determine_output_size_strategy(self):
        """Determine how to predict output size for test examples.

        Strategy priority:
        1. output_same_as_input: all train outputs have same shape as their input
        2. fixed_output_size: all train outputs have the same fixed shape
        3. fallback: use mode of train output sizes
        """
        # Check if output shape = input shape for all train pairs
        same_as_input = all(
            self.train_outputs[i].shape == self.train_inputs[i].shape
            for i in range(self.n_train)
        )

        if same_as_input:
            self.size_strategy = 'same_as_input'
            return

        # Check if all outputs have the same shape
        shapes = [o.shape for o in self.train_outputs]
        if len(set(shapes)) == 1:
            self.size_strategy = 'fixed'
            self.fixed_out_shape = shapes[0]
            return

        # Fallback: mode of output shapes
        from collections import Counter
        shape_counts = Counter(shapes)
        self.size_strategy = 'mode'
        self.fixed_out_shape = shape_counts.most_common(1)[0][0]

    def _get_output_size(self, test_input):
        """Get predicted output size for a test input."""
        if self.size_strategy == 'same_as_input':
            return test_input.shape[0], test_input.shape[1]
        else:
            return self.fixed_out_shape

    def _prepare_train_batch(self):
        """Prepare all train pairs as a batch.

        Returns input tensors, output tensors, and per-pair output sizes.
        We handle variable output sizes by processing each pair individually
        if sizes differ, or as a batch if sizes are the same.
        """
        out_shapes = [o.shape for o in self.train_outputs]
        uniform = len(set(out_shapes)) == 1

        if uniform:
            # All same size -> batch together
            oh, ow = out_shapes[0]
            # Pad inputs to common size for batching
            max_ih = max(inp.shape[0] for inp in self.train_inputs)
            max_iw = max(inp.shape[1] for inp in self.train_inputs)

            inp_batch = torch.zeros(self.n_train, max_ih, max_iw,
                                    dtype=torch.long, device=self.device)
            out_batch = torch.zeros(self.n_train, oh, ow,
                                    dtype=torch.long, device=self.device)

            for i in range(self.n_train):
                ih, iw = self.train_inputs[i].shape
                inp_batch[i, :ih, :iw] = torch.from_numpy(self.train_inputs[i])
                out_batch[i] = torch.from_numpy(self.train_outputs[i])

            return [(inp_batch, out_batch, oh, ow)]
        else:
            # Variable sizes -> one "batch" per pair
            batches = []
            for i in range(self.n_train):
                oh, ow = out_shapes[i]
                inp = torch.from_numpy(self.train_inputs[i]).unsqueeze(0).to(self.device)
                out = torch.from_numpy(self.train_outputs[i]).unsqueeze(0).to(self.device)
                batches.append((inp, out, oh, ow))
            return batches

    def _reparameterize(self, mean, log_var):
        """Reparameterization trick."""
        std = torch.exp(0.5 * log_var)
        eps = torch.randn_like(std)
        return mean + eps * std

    def _kl_divergence(self, mean, log_var):
        """KL(q(z) || N(0,I))."""
        return -0.5 * torch.sum(1 + log_var - mean.pow(2) - log_var.exp())

    def train(self):
        """Train the MDL model on the task's train pairs.

        Returns dict with training history.
        """
        cfg = self.cfg
        model = self.model
        model.train()

        # Optimizer: model params + latent params
        all_params = (list(model.parameters())
                      + list(self.z_means.parameters())
                      + list(self.z_log_vars.parameters()))
        optimizer = torch.optim.Adam(all_params, lr=cfg.lr,
                                     betas=(cfg.beta1, cfg.beta2),
                                     weight_decay=cfg.weight_decay)

        # LR schedule: cosine annealing
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=cfg.max_steps, eta_min=cfg.lr * 0.01
        )

        batches = self._prepare_train_batch()
        out_shapes = [o.shape for o in self.train_outputs]
        uniform = len(set(out_shapes)) == 1

        history = {'loss': [], 'ce': [], 'kl': [], 'train_exact': []}
        exact_count = 0  # consecutive steps with perfect train reconstruction

        t0 = time.time()
        for step in range(cfg.max_steps):
            optimizer.zero_grad()
            total_ce = 0.0
            total_kl = 0.0

            if uniform:
                # Single batch path
                inp_batch, out_batch, oh, ow = batches[0]
                # Sample z for each example
                zs = []
                kl_sum = 0.0
                for i in range(self.n_train):
                    z = self._reparameterize(self.z_means[i], self.z_log_vars[i])
                    zs.append(z)
                    kl_sum = kl_sum + self._kl_divergence(
                        self.z_means[i], self.z_log_vars[i])
                z_batch = torch.stack(zs, dim=0)  # (N, latent_dim)

                logits = model(inp_batch, z_batch, oh, ow)  # (N, C, oh, ow)
                ce = F.cross_entropy(logits, out_batch, reduction='sum')
                total_ce = ce.item()
                total_kl = kl_sum.item()

                loss = ce + cfg.beta_kl * kl_sum
            else:
                # Per-pair path
                loss = torch.tensor(0.0, device=self.device)
                for i, (inp, out, oh, ow) in enumerate(batches):
                    z = self._reparameterize(
                        self.z_means[i], self.z_log_vars[i]).unsqueeze(0)
                    kl = self._kl_divergence(self.z_means[i], self.z_log_vars[i])
                    logits = model(inp, z, oh, ow)
                    ce = F.cross_entropy(logits, out, reduction='sum')
                    loss = loss + ce + cfg.beta_kl * kl
                    total_ce += ce.item()
                    total_kl += kl.item()

            loss.backward()
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(all_params, 1.0)
            optimizer.step()
            scheduler.step()

            # Check train exact match
            train_exact = self._check_train_exact()
            history['loss'].append(loss.item())
            history['ce'].append(total_ce)
            history['kl'].append(total_kl)
            history['train_exact'].append(train_exact)

            if train_exact:
                exact_count += 1
            else:
                exact_count = 0

            if step % cfg.log_interval == 0:
                elapsed = time.time() - t0
                print(f"  step {step:4d} | loss={loss.item():.3f} "
                      f"ce={total_ce:.3f} kl={total_kl:.3f} "
                      f"train_exact={train_exact} | {elapsed:.1f}s",
                      flush=True)

            # Early stop if train outputs reproduce exactly
            if exact_count >= cfg.early_stop_patience and step >= 400:
                print(f"  early stop at step {step} "
                      f"(exact for {exact_count} steps)", flush=True)
                break

        self.train_time = time.time() - t0
        self.final_train_exact = self._check_train_exact()
        return history

    @torch.no_grad()
    def _check_train_exact(self):
        """Check if all train outputs are exactly reproduced."""
        self.model.eval()
        out_shapes = [o.shape for o in self.train_outputs]
        for i in range(self.n_train):
            oh, ow = out_shapes[i]
            inp = torch.from_numpy(
                self.train_inputs[i]).unsqueeze(0).to(self.device)
            z = self.z_means[i].unsqueeze(0)  # MAP estimate
            logits = self.model(inp, z, oh, ow)
            pred = logits.argmax(1).squeeze(0).cpu().numpy()
            if not np.array_equal(pred, self.train_outputs[i]):
                self.model.train()
                return False
        self.model.train()
        return True

    def predict_test(self, test_idx=0):
        """Produce test output prediction.

        Uses three strategies and picks the one with lowest output entropy
        (most confident / most compressible):
        1. Zero-latent (z=0): decode with prior mean
        2. Optimized z_test: optimize a latent for the test input using
           the frozen decoder (maximize output confidence)
        3. Mean of train latents

        Returns: predicted grid as list of lists.
        """
        self.model.eval()
        # Freeze decoder for test prediction
        for p in self.model.parameters():
            p.requires_grad_(False)

        test_input = self.test_inputs[test_idx]
        out_h, out_w = self._get_output_size(test_input)

        inp = torch.from_numpy(test_input).unsqueeze(0).to(self.device)

        with torch.no_grad():
            # Strategy 1: z = 0 (prior mean)
            z_zero = torch.zeros(1, self.cfg.latent_dim, device=self.device)
            logits_zero = self.model(inp, z_zero, out_h, out_w)
            pred_zero = logits_zero.argmax(1).squeeze(0).cpu().numpy()
            ent_zero = self._grid_entropy(logits_zero)

            # Strategy 3: mean of train latents
            z_mean = torch.stack(
                [m.data for m in self.z_means]).mean(0, keepdim=True)
            logits_mean = self.model(inp, z_mean, out_h, out_w)
            pred_mean = logits_mean.argmax(1).squeeze(0).cpu().numpy()
            ent_mean = self._grid_entropy(logits_mean)

        # Strategy 2: optimized z_test (needs gradients for z only)
        pred_opt, ent_opt = self._optimize_test_z(inp, out_h, out_w)

        # Re-enable gradients on model params
        for p in self.model.parameters():
            p.requires_grad_(True)

        # Pick the strategy with lowest entropy
        candidates = [
            (pred_zero, 'z_zero', ent_zero),
            (pred_opt, 'z_opt', ent_opt),
            (pred_mean, 'z_mean', ent_mean),
        ]

        best = min(candidates, key=lambda c: c[2])
        self._test_strategy = best[1]
        return best[0].tolist()

    def _grid_entropy(self, logits):
        """Average per-cell entropy of the output distribution."""
        probs = F.softmax(logits, dim=1)  # (1, C, H, W)
        log_probs = F.log_softmax(logits, dim=1)
        entropy = -(probs * log_probs).sum(1).mean()
        return entropy.item()

    def _optimize_test_z(self, inp_tensor, out_h, out_w):
        """Optimize a test latent to minimize output entropy (maximize confidence).

        The decoder is frozen (requires_grad=False already set by caller).
        We find the z that produces the most confident output.
        Returns (best_pred_numpy, best_entropy).
        """
        z_test = nn.Parameter(
            torch.zeros(1, self.cfg.latent_dim, device=self.device))
        opt = torch.optim.Adam([z_test], lr=self.cfg.test_z_lr)

        best_pred = None
        best_entropy = float('inf')

        for step in range(self.cfg.test_z_steps):
            opt.zero_grad()
            logits = self.model(inp_tensor, z_test, out_h, out_w)
            # Minimize entropy
            probs = F.softmax(logits, dim=1)
            log_probs = F.log_softmax(logits, dim=1)
            entropy = -(probs * log_probs).sum(1).mean()
            # KL penalty to keep z near prior
            kl = 0.5 * z_test.pow(2).sum()
            loss = entropy + 0.01 * kl
            loss.backward()
            opt.step()

            if entropy.item() < best_entropy:
                best_entropy = entropy.item()
                best_pred = logits.detach().argmax(1).squeeze(0).cpu().numpy()

        return best_pred, best_entropy

    def solve(self):
        """Full pipeline: train on train pairs, predict test outputs.

        Returns dict with results.
        """
        t_start = time.time()

        # Train
        history = self.train()

        # Predict test outputs
        test_preds = []
        for i in range(len(self.test_inputs)):
            pred = self.predict_test(i)
            test_preds.append(pred)

        wall_time = time.time() - t_start

        # Score if solutions available
        test_correct = []
        if self.solutions:
            for i, pred in enumerate(test_preds):
                if i < len(self.solutions):
                    correct = (pred == self.solutions[i])
                    if isinstance(self.solutions[i], np.ndarray):
                        correct = np.array_equal(np.array(pred),
                                                 self.solutions[i])
                    else:
                        correct = (pred == self.solutions[i])
                    test_correct.append(correct)
                else:
                    test_correct.append(None)

        result = {
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
        return result
