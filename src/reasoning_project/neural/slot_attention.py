"""Slot Attention for object-centric decomposition of ARC-style grids.

Learns to decompose grids into K object slots without supervision.
Each slot captures one object's color, shape, and position.

Reference: Locatello et al. 2020, "Object-Centric Learning with Slot Attention"
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .grid_encoder import torch_available

if torch_available():
    import torch
    import torch.nn.functional as F
    from torch import Tensor, nn
else:  # pragma: no cover
    torch = None
    Tensor = Any
    nn = object
    F = None


class SlotAttentionModule(nn.Module):
    """Iterative slot attention: compete K slots for pixel tokens."""

    def __init__(
        self,
        num_slots: int = 8,
        slot_dim: int = 64,
        input_dim: int = 64,
        hidden_dim: int = 128,
        num_iterations: int = 3,
        epsilon: float = 1e-8,
    ) -> None:
        super().__init__()
        self.num_slots = num_slots
        self.slot_dim = slot_dim
        self.num_iterations = num_iterations
        self.epsilon = epsilon

        self.norm_input = nn.LayerNorm(input_dim)
        self.norm_slots = nn.LayerNorm(slot_dim)
        self.norm_mlp = nn.LayerNorm(slot_dim)

        self.project_q = nn.Linear(slot_dim, slot_dim, bias=False)
        self.project_k = nn.Linear(input_dim, slot_dim, bias=False)
        self.project_v = nn.Linear(input_dim, slot_dim, bias=False)

        self.gru = nn.GRUCell(slot_dim, slot_dim)
        self.mlp = nn.Sequential(
            nn.Linear(slot_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, slot_dim),
        )

        self.slot_mu = nn.Parameter(torch.randn(1, 1, slot_dim) * 0.02)
        self.slot_log_sigma = nn.Parameter(torch.zeros(1, 1, slot_dim))

    def _init_slots(self, batch_size: int, device) -> Tensor:
        mu = self.slot_mu.expand(batch_size, self.num_slots, -1)
        sigma = self.slot_log_sigma.exp().expand(batch_size, self.num_slots, -1)
        return mu + sigma * torch.randn_like(mu)

    def forward(self, inputs: Tensor, valid_mask: Optional[Tensor] = None) -> Tuple[Tensor, Tensor]:
        """
        Args:
            inputs: (B, N, D) pixel/token features
            valid_mask: (B, N) bool mask for valid tokens
        Returns:
            slots: (B, K, slot_dim) refined slot features
            attn_weights: (B, K, N) attention weights (soft assignment)
        """
        B, N, D = inputs.shape
        inputs = self.norm_input(inputs)
        k = self.project_k(inputs)
        v = self.project_v(inputs)
        scale = self.slot_dim ** -0.5

        slots = self._init_slots(B, inputs.device)
        attn_weights = None

        for _ in range(self.num_iterations):
            slots_prev = slots
            slots = self.norm_slots(slots)
            q = self.project_q(slots)

            attn_logits = torch.bmm(q, k.transpose(1, 2)) * scale  # (B, K, N)

            if valid_mask is not None:
                attn_logits = attn_logits.masked_fill(~valid_mask.unsqueeze(1), -1e4)

            attn_weights = F.softmax(attn_logits, dim=1)  # normalize over slots
            attn_weights = attn_weights / (attn_weights.sum(dim=-1, keepdim=True) + self.epsilon)

            if valid_mask is not None:
                attn_weights = attn_weights * valid_mask.unsqueeze(1).float()

            updates = torch.bmm(attn_weights, v)  # (B, K, slot_dim)
            slots = self.gru(
                updates.reshape(-1, self.slot_dim),
                slots_prev.reshape(-1, self.slot_dim),
            ).reshape(B, self.num_slots, self.slot_dim)
            slots = slots + self.mlp(self.norm_mlp(slots))

        return slots, attn_weights


class SlotDecoder(nn.Module):
    """Broadcast decoder: each slot decodes to a full spatial map, then combine."""

    def __init__(self, slot_dim: int = 64, hidden_dim: int = 64, max_grid_size: int = 30, num_colors: int = 11):
        super().__init__()
        self.max_grid_size = max_grid_size
        self.slot_dim = slot_dim

        self.pos_embed_row = nn.Embedding(max_grid_size, hidden_dim)
        self.pos_embed_col = nn.Embedding(max_grid_size, hidden_dim)

        self.decoder = nn.Sequential(
            nn.Linear(slot_dim + hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_colors + 1),  # +1 for alpha/mask channel
        )

    def forward(self, slots: Tensor, height: int, width: int) -> Tuple[Tensor, Tensor]:
        """
        Args:
            slots: (B, K, slot_dim)
        Returns:
            recon: (B, H, W, num_colors) reconstructed color logits
            masks: (B, K, H, W) per-slot spatial masks
        """
        B, K, _ = slots.shape
        rows = torch.arange(height, device=slots.device)
        cols = torch.arange(width, device=slots.device)
        row_embed = self.pos_embed_row(rows)  # (H, hidden)
        col_embed = self.pos_embed_col(cols)  # (W, hidden)
        pos = (row_embed.unsqueeze(1) + col_embed.unsqueeze(0)).reshape(1, height * width, -1)
        pos = pos.expand(B, -1, -1)  # (B, H*W, hidden)

        slot_broadcast = slots.unsqueeze(2).expand(-1, -1, height * width, -1)  # (B, K, H*W, slot_dim)
        pos_broadcast = pos.unsqueeze(1).expand(-1, K, -1, -1)  # (B, K, H*W, hidden)

        decoder_input = torch.cat([slot_broadcast, pos_broadcast], dim=-1)  # (B, K, H*W, slot_dim+hidden)
        decoded = self.decoder(decoder_input)  # (B, K, H*W, num_colors+1)

        color_logits = decoded[..., :-1]  # (B, K, H*W, num_colors)
        alpha_logits = decoded[..., -1]   # (B, K, H*W)

        masks = F.softmax(alpha_logits, dim=1)  # (B, K, H*W) — compete over slots
        masks_4d = masks.unsqueeze(-1)  # (B, K, H*W, 1)

        recon = (masks_4d * color_logits).sum(dim=1)  # (B, H*W, num_colors)
        recon = recon.reshape(B, height, width, -1)
        masks = masks.reshape(B, K, height, width)

        return recon, masks


class GridSlotModel(nn.Module):
    """Full Slot Attention model for ARC grids: encode → slot attention → decode."""

    def __init__(
        self,
        num_slots: int = 8,
        slot_dim: int = 64,
        hidden_dim: int = 128,
        num_iterations: int = 3,
        max_grid_size: int = 30,
        num_colors: int = 11,
    ):
        super().__init__()
        self.num_colors = num_colors
        self.max_grid_size = max_grid_size

        self.color_embed = nn.Embedding(num_colors, hidden_dim)
        self.pos_embed_row = nn.Embedding(max_grid_size, hidden_dim)
        self.pos_embed_col = nn.Embedding(max_grid_size, hidden_dim)
        self.input_proj = nn.Linear(hidden_dim, hidden_dim)

        self.slot_attention = SlotAttentionModule(
            num_slots=num_slots,
            slot_dim=slot_dim,
            input_dim=hidden_dim,
            hidden_dim=hidden_dim,
            num_iterations=num_iterations,
        )
        self.decoder = SlotDecoder(
            slot_dim=slot_dim,
            hidden_dim=hidden_dim,
            max_grid_size=max_grid_size,
            num_colors=num_colors,
        )

    def encode_grid(self, grids: Tensor, valid_mask: Tensor) -> Tensor:
        """Encode grid pixels to token features."""
        B, H, W = grids.shape
        color_emb = self.color_embed(grids.clamp(0, self.num_colors - 1))
        rows = torch.arange(H, device=grids.device)
        cols = torch.arange(W, device=grids.device)
        pos = self.pos_embed_row(rows).unsqueeze(1) + self.pos_embed_col(cols).unsqueeze(0)
        tokens = color_emb + pos.unsqueeze(0)
        tokens = self.input_proj(tokens.reshape(B, H * W, -1))
        flat_mask = valid_mask.reshape(B, H * W)
        return tokens, flat_mask, H, W

    def forward(self, grids: Tensor, valid_mask: Tensor) -> Dict[str, Tensor]:
        tokens, flat_mask, H, W = self.encode_grid(grids, valid_mask)

        slots, attn_weights = self.slot_attention(tokens, flat_mask)
        recon_logits, slot_masks = self.decoder(slots, H, W)

        target = grids.clamp(0, self.num_colors - 1).long()
        flat_logits = recon_logits.reshape(-1, self.num_colors)
        flat_logits = torch.where(
            torch.isnan(flat_logits), torch.zeros_like(flat_logits), flat_logits
        )
        recon_loss = F.cross_entropy(
            flat_logits,
            target.reshape(-1),
            reduction="none",
        ).reshape(grids.shape[0], H, W)
        recon_loss = (recon_loss * valid_mask.float()).sum() / valid_mask.float().sum().clamp(min=1)

        return {
            "loss": recon_loss,
            "recon_logits": recon_logits,
            "slots": slots,
            "attn_weights": attn_weights,
            "slot_masks": slot_masks,
        }

    @torch.no_grad()
    def extract_slots(self, grid: np.ndarray, device: Optional[str] = None) -> Dict[str, np.ndarray]:
        """Extract object slots from a single grid."""
        dev = device or "cpu"
        self.to(dev)
        self.eval()

        arr = np.asarray(grid, dtype=int)
        H, W = arr.shape
        grids_t = torch.tensor(arr, dtype=torch.long, device=dev).unsqueeze(0)
        valid = torch.ones(1, H, W, dtype=torch.bool, device=dev)

        result = self.forward(grids_t, valid)

        return {
            "slots": result["slots"][0].cpu().numpy(),             # (K, slot_dim)
            "slot_masks": result["slot_masks"][0].cpu().numpy(),   # (K, H, W)
            "attn_weights": result["attn_weights"][0].cpu().numpy(),  # (K, H*W)
            "recon": result["recon_logits"][0].argmax(dim=-1).cpu().numpy(),  # (H, W)
        }


def load_slot_model_checkpoint(path, device=None):
    if not torch_available():
        raise RuntimeError("Requires torch")
    package = torch.load(path, map_location=device or "cpu")
    config = package.get("model_config", {})
    model = GridSlotModel(**config)
    model.load_state_dict(package["model_state"])
    model.eval()
    return model
