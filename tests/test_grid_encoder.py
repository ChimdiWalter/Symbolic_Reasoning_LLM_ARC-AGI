import numpy as np
import pytest

from reasoning_project.neural.grid_encoder import HandcraftedGridEncoder, TorchGridEncoder, torch_available


def test_handcrafted_encoder_shapes_are_consistent():
    encoder = HandcraftedGridEncoder()
    input_grid = np.asarray([[0, 1, 1], [0, 0, 2], [3, 0, 2]], dtype=int)
    output_grid = np.asarray([[0, 0, 1], [0, 2, 2], [3, 0, 0]], dtype=int)

    encoding = encoder.encode_grid(input_grid)
    pair_latent = encoder.encode_pair(input_grid, output_grid)
    task_context = encoder.encode_task_context([(input_grid, output_grid)])
    empty_context = encoder.encode_task_context([])

    assert encoding.grid_latent.shape == (22,)
    assert pair_latent.shape == (88,)
    assert task_context.shape == pair_latent.shape
    assert empty_context.shape == pair_latent.shape
    assert encoding.valid_mask.shape == input_grid.shape
    assert len(encoding.object_latents) >= 1


@pytest.mark.skipif(not torch_available(), reason="torch-backed grid encoder unavailable")
def test_torch_grid_encoder_handles_variable_grid_sizes():
    encoder = TorchGridEncoder(hidden_dim=16, num_layers=1, num_heads=4, dropout=0.0, max_grid_size=30)
    small = np.asarray([[1, 0], [0, 2]], dtype=int)
    large = np.asarray([[0, 1, 1], [2, 2, 0], [0, 3, 3], [0, 0, 3]], dtype=int)

    grid_latent, token_latents, valid_mask = encoder.encode_numpy([small, large], device="cpu")
    single = encoder.encode_grid(large, device="cpu")

    assert tuple(grid_latent.shape) == (2, 16)
    assert tuple(token_latents.shape) == (2, 4, 3, 16)
    assert tuple(valid_mask.shape) == (2, 4, 3)
    assert single.grid_latent.shape == (16,)
    assert single.token_latents.shape == (4, 3, 16)
    assert single.valid_mask.shape == large.shape
