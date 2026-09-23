"""Variable-size grid encoders with optional torch-backed transformer layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..parsing import parse_objects, symmetry_indicators
from .dataset import pad_grids

try:
    import torch
    from torch import Tensor, nn

    _TORCH_AVAILABLE = True
except Exception:  # pragma: no cover - exercised via fallback path
    torch = None
    Tensor = Any
    nn = object
    _TORCH_AVAILABLE = False


def torch_available() -> bool:
    return bool(_TORCH_AVAILABLE)


@dataclass
class GridEncoding:
    grid_latent: np.ndarray
    object_latents: List[np.ndarray]
    token_latents: Optional[np.ndarray]
    valid_mask: np.ndarray


def _handcrafted_grid_features(grid: np.ndarray) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    h, w = arr.shape
    total = float(max(1, h * w))
    histogram = np.bincount(arr.reshape(-1), minlength=10).astype(float) / total
    non_background = arr > 0
    occupied = float(np.mean(non_background))
    objects = parse_objects(arr)
    sizes = [obj.size for obj in objects]
    holes = [obj.holes for obj in objects]
    border = [int(obj.touches_border) for obj in objects]
    symmetry = symmetry_indicators(arr)
    feature_parts = [
        np.asarray(
            [
                float(h) / 30.0,
                float(w) / 30.0,
                occupied,
                float(len(objects)) / total,
                float(max(sizes) if sizes else 0) / total,
                float(np.mean(sizes) if sizes else 0.0) / total,
                float(sum(holes)),
                float(sum(border)),
                float(symmetry["horizontal"]),
                float(symmetry["vertical"]),
                float(symmetry["rotational_180"]),
                float(len([c for c in np.unique(arr) if c != 0])) / 9.0,
            ],
            dtype=float,
        ),
        histogram,
    ]
    return np.concatenate(feature_parts, axis=0)


def _object_feature_vector(grid: np.ndarray) -> List[np.ndarray]:
    arr = np.asarray(grid, dtype=int)
    total = float(max(1, arr.shape[0] * arr.shape[1]))
    features: List[np.ndarray] = []
    for obj in parse_objects(arr):
        min_r, min_c, max_r, max_c = obj.bbox
        features.append(
            np.asarray(
                [
                    float(obj.color) / 9.0,
                    float(obj.size) / total,
                    float(min_r) / max(1.0, float(arr.shape[0] - 1)),
                    float(min_c) / max(1.0, float(arr.shape[1] - 1)),
                    float(max_r) / max(1.0, float(arr.shape[0] - 1)),
                    float(max_c) / max(1.0, float(arr.shape[1] - 1)),
                    float(obj.centroid[0]) / max(1.0, float(arr.shape[0] - 1)),
                    float(obj.centroid[1]) / max(1.0, float(arr.shape[1] - 1)),
                    float(obj.touches_border),
                    float(obj.holes),
                ],
                dtype=float,
            )
        )
    return features


class HandcraftedGridEncoder:
    """Fallback encoder when torch is unavailable."""

    name = "handcrafted_grid_encoder"

    def encode_grid(self, grid: np.ndarray) -> GridEncoding:
        arr = np.asarray(grid, dtype=int)
        return GridEncoding(
            grid_latent=_handcrafted_grid_features(arr),
            object_latents=_object_feature_vector(arr),
            token_latents=None,
            valid_mask=np.ones_like(arr, dtype=bool),
        )

    def encode_pair(self, input_grid: np.ndarray, output_grid: np.ndarray) -> np.ndarray:
        input_features = _handcrafted_grid_features(np.asarray(input_grid, dtype=int))
        output_features = _handcrafted_grid_features(np.asarray(output_grid, dtype=int))
        return np.concatenate(
            [input_features, output_features, output_features - input_features, np.abs(output_features - input_features)],
            axis=0,
        )

    def encode_task_context(self, pairs: Sequence[Tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
        if not pairs:
            return np.zeros(88, dtype=float)
        encodings = [self.encode_pair(inp, out) for inp, out in pairs]
        return np.mean(np.asarray(encodings, dtype=float), axis=0)


class TorchGridEncoder(nn.Module):
    """Small transformer encoder for variable-size ARC-style color grids."""

    name = "torch_grid_encoder"

    def __init__(
        self,
        hidden_dim: int = 64,
        num_layers: int = 2,
        num_heads: int = 4,
        dropout: float = 0.1,
        max_grid_size: int = 30,
    ) -> None:
        if not _TORCH_AVAILABLE:  # pragma: no cover - exercised on no-torch systems
            raise RuntimeError("TorchGridEncoder requires torch")
        super().__init__()
        self.hidden_dim = int(hidden_dim)
        self.max_grid_size = int(max_grid_size)
        self.color_embedding = nn.Embedding(11, self.hidden_dim)
        self.row_embedding = nn.Embedding(self.max_grid_size + 1, self.hidden_dim)
        self.col_embedding = nn.Embedding(self.max_grid_size + 1, self.hidden_dim)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, self.hidden_dim))
        layer = nn.TransformerEncoderLayer(
            d_model=self.hidden_dim,
            nhead=int(num_heads),
            dim_feedforward=self.hidden_dim * 4,
            dropout=float(dropout),
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=int(num_layers))
        self.output_norm = nn.LayerNorm(self.hidden_dim)

    def forward(self, color_grids: Tensor, valid_mask: Tensor) -> Tuple[Tensor, Tensor]:
        batch_size, height, width = color_grids.shape
        rows = torch.arange(height, device=color_grids.device)
        cols = torch.arange(width, device=color_grids.device)
        row_embed = self.row_embedding(rows).unsqueeze(1)
        col_embed = self.col_embedding(cols).unsqueeze(0)
        token_embed = self.color_embedding(color_grids.clamp(min=0, max=10)) + row_embed + col_embed
        flat_tokens = token_embed.view(batch_size, height * width, self.hidden_dim)
        flat_mask = valid_mask.view(batch_size, height * width)
        cls = self.cls_token.expand(batch_size, -1, -1)
        tokens = torch.cat([cls, flat_tokens], dim=1)
        cls_mask = torch.ones((batch_size, 1), dtype=torch.bool, device=color_grids.device)
        key_padding_mask = ~torch.cat([cls_mask, flat_mask], dim=1)
        encoded = self.encoder(tokens, src_key_padding_mask=key_padding_mask)
        encoded = self.output_norm(encoded)
        grid_latent = encoded[:, 0, :]
        token_latents = encoded[:, 1:, :].view(batch_size, height, width, self.hidden_dim)
        return grid_latent, token_latents

    def encode_numpy(self, grids: Sequence[np.ndarray], device: Optional[str] = None) -> Tuple[Tensor, Tensor, Tensor]:
        padded, mask = pad_grids(grids)
        use_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        color_grids = torch.as_tensor(padded, dtype=torch.long, device=use_device)
        valid_mask = torch.as_tensor(mask, dtype=torch.bool, device=use_device)
        grid_latent, token_latents = self.forward(color_grids, valid_mask)
        return grid_latent, token_latents, valid_mask

    def _pool_object_latents(self, grid: np.ndarray, token_latents: Tensor) -> List[np.ndarray]:
        pooled: List[np.ndarray] = []
        for obj in parse_objects(np.asarray(grid, dtype=int)):
            pixel_vectors = [token_latents[r, c] for r, c in obj.pixels]
            if not pixel_vectors:
                continue
            pooled.append(torch.stack(pixel_vectors, dim=0).mean(dim=0).detach().cpu().numpy())
        return pooled

    @torch.no_grad()
    def encode_grid(self, grid: np.ndarray, device: Optional[str] = None) -> GridEncoding:
        arr = np.asarray(grid, dtype=int)
        grid_latent, token_latents, valid_mask = self.encode_numpy([arr], device=device)
        return GridEncoding(
            grid_latent=grid_latent[0].detach().cpu().numpy(),
            object_latents=self._pool_object_latents(arr, token_latents[0]),
            token_latents=token_latents[0].detach().cpu().numpy(),
            valid_mask=valid_mask[0].detach().cpu().numpy(),
        )

    @torch.no_grad()
    def encode_pair(self, input_grid: np.ndarray, output_grid: np.ndarray, device: Optional[str] = None) -> np.ndarray:
        input_encoding = self.encode_grid(input_grid, device=device)
        output_encoding = self.encode_grid(output_grid, device=device)
        return np.concatenate(
            [
                input_encoding.grid_latent,
                output_encoding.grid_latent,
                output_encoding.grid_latent - input_encoding.grid_latent,
                np.abs(output_encoding.grid_latent - input_encoding.grid_latent),
            ],
            axis=0,
        )

    @torch.no_grad()
    def encode_task_context(self, pairs: Sequence[Tuple[np.ndarray, np.ndarray]], device: Optional[str] = None) -> np.ndarray:
        if not pairs:
            return np.zeros(self.hidden_dim * 4, dtype=float)
        pair_latents = [self.encode_pair(inp, out, device=device) for inp, out in pairs]
        return np.mean(np.asarray(pair_latents, dtype=float), axis=0)


def build_grid_encoder(
    *,
    use_torch: bool = True,
    hidden_dim: int = 64,
    num_layers: int = 2,
    num_heads: int = 4,
    dropout: float = 0.1,
    max_grid_size: int = 30,
) -> Any:
    if use_torch and _TORCH_AVAILABLE:
        return TorchGridEncoder(
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            dropout=dropout,
            max_grid_size=max_grid_size,
        )
    return HandcraftedGridEncoder()
