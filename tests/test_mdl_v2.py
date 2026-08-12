#!/usr/bin/env python3
"""Tests for mdl/solver_v2.py — v2 MDL solver (v1 core + directional ops
+ D4/colour augmentation + multi-sample voting)."""

import os
import sys
import numpy as np
import pytest
import torch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from mdl.solver_v2 import (
    MDLConfigV2, MDLDecoderV2, PerTaskMDLv2,
    DirectionalOps, D4_TRANSFORMS, apply_color_perm, N_COLORS,
)


def _fast_cfg(**overrides):
    defaults = dict(
        hidden_dim=16, latent_dim=4, n_res_blocks=1,
        dir_dim=4, max_steps=50, lr=0.01, device="cpu", seed=42,
        d4_augment=False, color_augment=False, d4_test_average=False,
        n_test_samples=2, test_z_steps=10, log_interval=9999,
        early_stop_patience=9999,
    )
    defaults.update(overrides)
    return MDLConfigV2(**defaults)


# -- component tests -------------------------------------------------------

class TestDirectionalOps:
    def test_output_shape(self):
        dop = DirectionalOps(16, dir_dim=4)
        x = torch.randn(2, 16, 5, 7)
        assert dop(x).shape == x.shape

    def test_gradients_flow(self):
        dop = DirectionalOps(8, dir_dim=4)
        x = torch.randn(1, 8, 3, 3, requires_grad=True)
        y = dop(x)
        y.sum().backward()
        assert x.grad is not None and x.grad.shape == x.shape


class TestMDLDecoderV2:
    def test_forward_shapes(self):
        cfg = _fast_cfg()
        model = MDLDecoderV2(cfg)
        grid = torch.randint(0, N_COLORS, (1, 5, 5))
        z = torch.randn(1, cfg.latent_dim)
        logits = model(grid, z, 5, 5)
        assert logits.shape == (1, N_COLORS, 5, 5)

    def test_different_io_sizes(self):
        cfg = _fast_cfg()
        model = MDLDecoderV2(cfg)
        grid = torch.randint(0, N_COLORS, (1, 3, 4))
        z = torch.randn(1, cfg.latent_dim)
        logits = model(grid, z, 6, 8)
        assert logits.shape == (1, N_COLORS, 6, 8)

    def test_param_count_under_300k(self):
        cfg = MDLConfigV2(device="cpu")
        model = MDLDecoderV2(cfg)
        n = sum(p.numel() for p in model.parameters())
        assert n < 300_000, f"Model has {n} params, exceeds 300K limit"
        print(f"Full-size v2 model: {n} params")


# -- solver tests ----------------------------------------------------------

class TestPerTaskMDLv2:
    @staticmethod
    def _identity_task(h=3, w=3, n_train=3):
        pairs = []
        for _ in range(n_train):
            grid = np.random.randint(0, 5, (h, w)).tolist()
            pairs.append({'input': grid, 'output': grid})
        test_grid = np.random.randint(0, 5, (h, w)).tolist()
        return {'train': pairs, 'test': [{'input': test_grid}]}, [test_grid]

    def test_smoke_solve(self):
        np.random.seed(42)
        task, sols = self._identity_task()
        cfg = _fast_cfg(max_steps=100)
        solver = PerTaskMDLv2(task, cfg, solutions=sols)
        result = solver.solve()
        assert 'train_exact' in result
        assert len(result['test_preds']) == 1

    def test_with_d4_augment(self):
        np.random.seed(42)
        task, sols = self._identity_task()
        cfg = _fast_cfg(max_steps=80, d4_augment=True)
        result = PerTaskMDLv2(task, cfg, solutions=sols).solve()
        assert 'test_preds' in result

    def test_with_color_augment(self):
        np.random.seed(42)
        task, sols = self._identity_task()
        cfg = _fast_cfg(max_steps=80, color_augment=True)
        result = PerTaskMDLv2(task, cfg, solutions=sols).solve()
        assert 'test_preds' in result

    def test_with_d4_test_average(self):
        np.random.seed(42)
        task, sols = self._identity_task()
        cfg = _fast_cfg(max_steps=80, d4_test_average=True)
        result = PerTaskMDLv2(task, cfg, solutions=sols).solve()
        assert 'test_preds' in result

    def test_deterministic(self):
        np.random.seed(42)
        task, sols = self._identity_task()
        cfg1 = _fast_cfg(max_steps=60, seed=123)
        cfg2 = _fast_cfg(max_steps=60, seed=123)
        np.random.seed(42); r1 = PerTaskMDLv2(task, cfg1, solutions=sols).solve()
        np.random.seed(42); r2 = PerTaskMDLv2(task, cfg2, solutions=sols).solve()
        assert r1['test_preds'] == r2['test_preds']


# -- D4 transform tests ---------------------------------------------------

class TestD4Transforms:
    def test_eight_transforms(self):
        assert len(D4_TRANSFORMS) == 8

    def test_roundtrip(self):
        x = torch.randint(0, 10, (1, 4, 6))
        for fwd, inv in D4_TRANSFORMS:
            assert torch.equal(inv(fwd(x)), x)

    def test_identity_first(self):
        x = torch.randint(0, 10, (1, 3, 5))
        fwd, inv = D4_TRANSFORMS[0]
        assert torch.equal(fwd(x), x) and torch.equal(inv(x), x)


# -- color permutation test -----------------------------------------------

class TestColorPerm:
    def test_roundtrip(self):
        perm = [3, 0, 1, 2, 4, 5, 6, 7, 8, 9, 10]
        inv = [0] * N_COLORS
        for old, new in enumerate(perm):
            inv[new] = old
        grid = torch.randint(0, N_COLORS, (2, 4, 4))
        permuted = apply_color_perm(grid, perm, grid.device)
        recovered = apply_color_perm(permuted, inv, grid.device)
        assert torch.equal(grid, recovered)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
