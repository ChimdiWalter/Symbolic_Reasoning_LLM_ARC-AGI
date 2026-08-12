import numpy as np
import pytest

from reasoning_project.neural.dataset import pad_grids
from reasoning_project.neural.grid_encoder import torch_available
from reasoning_project.neural.grid_jepa import GridJEPA, GridMaskSampler

if torch_available():
    import torch
else:  # pragma: no cover
    torch = None


def test_grid_mask_sampler_respects_valid_region():
    sampler = GridMaskSampler(patch_size=2, mask_ratio=0.5, seed=7)
    grids = [
        np.asarray([[1, 1, 0], [0, 2, 2]], dtype=int),
        np.asarray([[3, 0], [0, 4], [4, 4]], dtype=int),
    ]
    batch_mask = sampler.sample_batch(grids)

    assert batch_mask.shape == (2, 3, 3)
    assert batch_mask[0].sum() > 0
    assert not bool(batch_mask[1, 0, 2])


@pytest.mark.skipif(not torch_available(), reason="GridJEPA requires torch")
def test_grid_jepa_forward_emits_finite_losses():
    model = GridJEPA(hidden_dim=16, num_layers=1, num_heads=4, dropout=0.0, pair_prediction_weight=0.5)
    sampler = GridMaskSampler(patch_size=1, mask_ratio=0.5, seed=3)
    input_grids = [
        np.asarray([[1, 0], [0, 2]], dtype=int),
        np.asarray([[0, 3], [3, 3]], dtype=int),
    ]
    output_grids = [
        np.asarray([[0, 1], [2, 0]], dtype=int),
        np.asarray([[3, 3], [0, 3]], dtype=int),
    ]
    input_padded, input_mask = pad_grids(input_grids)
    output_padded, output_mask = pad_grids(output_grids)
    target_mask = sampler.sample_batch(input_grids)

    payload = model(
        torch.as_tensor(input_padded, dtype=torch.long),
        torch.as_tensor(input_mask, dtype=torch.bool),
        torch.as_tensor(target_mask, dtype=torch.bool),
        output_grids=torch.as_tensor(output_padded, dtype=torch.long),
        output_valid_mask=torch.as_tensor(output_mask, dtype=torch.bool),
    )
    task_context = model.encode_task_context(list(zip(input_grids, output_grids)), device="cpu")

    assert float(payload["loss"].detach().cpu()) >= 0.0
    assert float(payload["latent_loss"].detach().cpu()) >= 0.0
    assert float(payload["pair_loss"].detach().cpu()) >= 0.0
    assert task_context.shape == (64,)
