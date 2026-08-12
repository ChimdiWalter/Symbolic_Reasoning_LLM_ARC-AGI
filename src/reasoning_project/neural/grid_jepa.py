"""Small JEPA-style latent prediction model for ARC-like colored grids."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from ..utils import read_json
from .dataset import pad_grids
from .grid_encoder import TorchGridEncoder, build_grid_encoder, torch_available

if torch_available():
    import torch
    import torch.nn.functional as F
    from torch import Tensor, nn
else:  # pragma: no cover - exercised on no-torch systems
    torch = None
    Tensor = Any
    nn = object
    F = None


@dataclass
class GridMaskSampler:
    patch_size: int = 2
    mask_ratio: float = 0.3
    seed: int = 0

    def sample(self, shape: Tuple[int, int]) -> np.ndarray:
        height, width = int(shape[0]), int(shape[1])
        patch = max(1, int(self.patch_size))
        patch_rows = max(1, int(np.ceil(height / patch)))
        patch_cols = max(1, int(np.ceil(width / patch)))
        total_patches = patch_rows * patch_cols
        masked_patches = max(1, int(round(total_patches * float(self.mask_ratio))))
        rng = np.random.default_rng(self.seed + height * 97 + width * 53)
        chosen = set(int(index) for index in rng.choice(total_patches, size=masked_patches, replace=False))
        mask = np.zeros((height, width), dtype=bool)
        for patch_index in chosen:
            pr = patch_index // patch_cols
            pc = patch_index % patch_cols
            row_start = pr * patch
            col_start = pc * patch
            mask[row_start : min(height, row_start + patch), col_start : min(width, col_start + patch)] = True
        return mask

    def sample_batch(self, grids: Sequence[np.ndarray]) -> np.ndarray:
        padded, valid_mask = pad_grids(grids)
        batch_mask = np.zeros_like(valid_mask, dtype=bool)
        for index, grid in enumerate(grids):
            sampled = self.sample(np.asarray(grid).shape)
            h, w = sampled.shape
            batch_mask[index, :h, :w] = sampled
        batch_mask &= valid_mask
        return batch_mask


class GridJEPA(nn.Module):
    """Predict masked target latents and optional output-grid latents."""

    def __init__(
        self,
        hidden_dim: int = 64,
        num_layers: int = 2,
        num_heads: int = 4,
        dropout: float = 0.1,
        max_grid_size: int = 30,
        pair_prediction_weight: float = 0.5,
    ) -> None:
        if not torch_available():  # pragma: no cover
            raise RuntimeError("GridJEPA requires torch")
        super().__init__()
        self.hidden_dim = int(hidden_dim)
        self.pair_prediction_weight = float(pair_prediction_weight)
        self.context_encoder = TorchGridEncoder(
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            dropout=dropout,
            max_grid_size=max_grid_size,
        )
        self.target_encoder = TorchGridEncoder(
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            dropout=dropout,
            max_grid_size=max_grid_size,
        )
        self.predictor = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.output_predictor = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self._sync_target_encoder()

    def _sync_target_encoder(self) -> None:
        self.target_encoder.load_state_dict(self.context_encoder.state_dict())
        for parameter in self.target_encoder.parameters():
            parameter.requires_grad_(False)

    @torch.no_grad()
    def update_target_encoder(self, momentum: float = 0.99) -> None:
        momentum = float(momentum)
        for target_parameter, context_parameter in zip(
            self.target_encoder.parameters(), self.context_encoder.parameters()
        ):
            target_parameter.data.mul_(momentum).add_(context_parameter.data, alpha=1.0 - momentum)

    def _pool_masked_target(self, token_latents: Tensor, target_mask: Tensor, grid_latents: Tensor) -> Tensor:
        batch_size = token_latents.shape[0]
        pooled = []
        flat_tokens = token_latents.view(batch_size, -1, token_latents.shape[-1])
        flat_mask = target_mask.view(batch_size, -1)
        for batch_index in range(batch_size):
            if bool(flat_mask[batch_index].any()):
                pooled.append(flat_tokens[batch_index][flat_mask[batch_index]].mean(dim=0))
            else:
                pooled.append(grid_latents[batch_index])
        return torch.stack(pooled, dim=0)

    def forward(
        self,
        input_grids: Tensor,
        valid_mask: Tensor,
        target_mask: Tensor,
        output_grids: Optional[Tensor] = None,
        output_valid_mask: Optional[Tensor] = None,
    ) -> Dict[str, Tensor]:
        masked_inputs = input_grids.clone()
        masked_inputs = masked_inputs.masked_fill(target_mask, 0)
        context_latent, _ = self.context_encoder(masked_inputs, valid_mask)
        with torch.no_grad():
            target_latent, target_tokens = self.target_encoder(input_grids, valid_mask)
        pooled_target = self._pool_masked_target(target_tokens, target_mask, target_latent)
        predicted_target = self.predictor(context_latent)
        mse_loss = F.mse_loss(predicted_target, pooled_target)
        cosine_loss = 1.0 - F.cosine_similarity(predicted_target, pooled_target, dim=-1).mean()
        total_loss = mse_loss + 0.1 * cosine_loss
        pair_loss = torch.zeros((), device=input_grids.device)
        if output_grids is not None and output_valid_mask is not None:
            with torch.no_grad():
                output_latent, _ = self.target_encoder(output_grids, output_valid_mask)
            predicted_output = self.output_predictor(context_latent)
            pair_loss = F.mse_loss(predicted_output, output_latent)
            total_loss = total_loss + self.pair_prediction_weight * pair_loss
        return {
            "loss": total_loss,
            "latent_loss": mse_loss + 0.1 * cosine_loss,
            "pair_loss": pair_loss,
            "context_latent": context_latent,
            "predicted_target": predicted_target,
            "pooled_target": pooled_target,
        }

    @torch.no_grad()
    def encode_pair(self, input_grid: np.ndarray, output_grid: np.ndarray, device: Optional[str] = None) -> np.ndarray:
        use_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.to(use_device)
        input_latent, _, _ = self.context_encoder.encode_numpy([np.asarray(input_grid, dtype=int)], device=use_device)
        output_latent, _, _ = self.context_encoder.encode_numpy([np.asarray(output_grid, dtype=int)], device=use_device)
        inp = input_latent[0].detach().cpu().numpy()
        out = output_latent[0].detach().cpu().numpy()
        return np.concatenate([inp, out, out - inp, np.abs(out - inp)], axis=0)

    @torch.no_grad()
    def encode_task_context(
        self,
        pairs: Sequence[Tuple[np.ndarray, np.ndarray]],
        device: Optional[str] = None,
    ) -> np.ndarray:
        if not pairs:
            return np.zeros(self.hidden_dim * 4, dtype=float)
        latents = [self.encode_pair(inp, out, device=device) for inp, out in pairs]
        return np.mean(np.asarray(latents, dtype=float), axis=0)


def load_grid_jepa_checkpoint(path: str | Path, device: Optional[str] = None) -> GridJEPA:
    if not torch_available():  # pragma: no cover
        raise RuntimeError("GridJEPA checkpoint loading requires torch")
    checkpoint_path = Path(path)
    package = torch.load(checkpoint_path, map_location=device or "cpu")
    config = dict(package.get("model_config", {}))
    model = GridJEPA(**config)
    model.load_state_dict(package["model_state"])
    model.eval()
    return model
