"""Graph Network Simulator (GNS) for object-level dynamics prediction.

Operates on object graphs (from slot attention or hand-coded extraction)
to predict how objects transform from input to output grids.

Reference: Sanchez-Gonzalez et al. 2020, "Learning to Simulate Complex
Physics with Graph Networks"
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


class EdgeModel(nn.Module):
    """Computes updated edge features from sender/receiver nodes + edge features."""

    def __init__(self, node_dim: int, edge_dim: int, hidden_dim: int):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(2 * node_dim + edge_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, edge_dim),
        )

    def forward(self, src: Tensor, dst: Tensor, edge_attr: Tensor) -> Tensor:
        return self.mlp(torch.cat([src, dst, edge_attr], dim=-1))


class NodeModel(nn.Module):
    """Updates node features from aggregated edge messages + node features."""

    def __init__(self, node_dim: int, edge_dim: int, hidden_dim: int):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(node_dim + edge_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, node_dim),
        )

    def forward(self, x: Tensor, agg_messages: Tensor) -> Tensor:
        return self.mlp(torch.cat([x, agg_messages], dim=-1))


class GraphNetworkBlock(nn.Module):
    """One message-passing step: update edges, aggregate, update nodes."""

    def __init__(self, node_dim: int, edge_dim: int, hidden_dim: int):
        super().__init__()
        self.edge_model = EdgeModel(node_dim, edge_dim, hidden_dim)
        self.node_model = NodeModel(node_dim, edge_dim, hidden_dim)

    def forward(
        self,
        node_features: Tensor,
        edge_index: Tensor,
        edge_attr: Tensor,
    ) -> Tuple[Tensor, Tensor]:
        """
        Args:
            node_features: (N, node_dim)
            edge_index: (2, E) source/target indices
            edge_attr: (E, edge_dim)
        Returns:
            updated_nodes: (N, node_dim)
            updated_edges: (E, edge_dim)
        """
        src_idx, dst_idx = edge_index[0], edge_index[1]
        src_features = node_features[src_idx]
        dst_features = node_features[dst_idx]

        updated_edges = self.edge_model(src_features, dst_features, edge_attr)

        N = node_features.shape[0]
        agg = torch.zeros(N, updated_edges.shape[-1], device=node_features.device)
        agg.scatter_add_(0, dst_idx.unsqueeze(-1).expand_as(updated_edges), updated_edges)

        updated_nodes = self.node_model(node_features, agg)
        updated_nodes = node_features + updated_nodes  # residual

        return updated_nodes, updated_edges


class GraphNetworkSimulator(nn.Module):
    """Multi-step GNS: encode → message-pass × L → decode."""

    def __init__(
        self,
        input_node_dim: int = 16,
        input_edge_dim: int = 8,
        node_dim: int = 64,
        edge_dim: int = 32,
        hidden_dim: int = 128,
        num_layers: int = 3,
        output_node_dim: int = 16,
    ):
        super().__init__()
        self.node_encoder = nn.Sequential(
            nn.Linear(input_node_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, node_dim),
        )
        self.edge_encoder = nn.Sequential(
            nn.Linear(input_edge_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, edge_dim),
        )
        self.blocks = nn.ModuleList([
            GraphNetworkBlock(node_dim, edge_dim, hidden_dim)
            for _ in range(num_layers)
        ])
        self.node_decoder = nn.Sequential(
            nn.Linear(node_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_node_dim),
        )

    def forward(
        self,
        node_features: Tensor,
        edge_index: Tensor,
        edge_attr: Tensor,
    ) -> Tensor:
        x = self.node_encoder(node_features)
        e = self.edge_encoder(edge_attr)

        for block in self.blocks:
            x, e = block(x, edge_index, e)

        return self.node_decoder(x)


def objects_to_graph_tensors(
    objects: List[Dict[str, Any]],
    grid_shape: Tuple[int, int],
    device: str = "cpu",
) -> Tuple[Tensor, Tensor, Tensor]:
    """Convert object list to graph tensors for GNS.

    Each object dict should have: color, size, bbox, centroid, is_rectangular.
    """
    N = len(objects)
    H, W = grid_shape
    norm_h = max(1.0, float(H))
    norm_w = max(1.0, float(W))
    total = max(1.0, float(H * W))

    node_features = []
    for obj in objects:
        color_onehot = [0.0] * 10
        c = int(obj.get("color", 0))
        if 0 <= c < 10:
            color_onehot[c] = 1.0

        feat = color_onehot + [
            float(obj.get("size", 0)) / total,
            float(obj.get("centroid", (0, 0))[0]) / norm_h,
            float(obj.get("centroid", (0, 0))[1]) / norm_w,
            float(obj.get("is_rectangular", False)),
            float(obj.get("bbox", (0, 0, 0, 0))[2] - obj.get("bbox", (0, 0, 0, 0))[0] + 1) / norm_h,
            float(obj.get("bbox", (0, 0, 0, 0))[3] - obj.get("bbox", (0, 0, 0, 0))[1] + 1) / norm_w,
        ]
        node_features.append(feat)

    if N == 0:
        return (
            torch.zeros(0, 16, device=device),
            torch.zeros(2, 0, dtype=torch.long, device=device),
            torch.zeros(0, 8, device=device),
        )

    node_t = torch.tensor(node_features, dtype=torch.float32, device=device)

    src_list, dst_list, edge_feats = [], [], []
    for i in range(N):
        for j in range(N):
            if i == j:
                continue
            src_list.append(i)
            dst_list.append(j)

            ci = objects[i].get("centroid", (0, 0))
            cj = objects[j].get("centroid", (0, 0))
            dr = (cj[0] - ci[0]) / norm_h
            dc = (cj[1] - ci[1]) / norm_w
            dist = (dr**2 + dc**2) ** 0.5

            same_color = float(objects[i].get("color", -1) == objects[j].get("color", -2))
            size_ratio = float(objects[j].get("size", 1)) / max(float(objects[i].get("size", 1)), 1.0)

            bi = objects[i].get("bbox", (0, 0, 0, 0))
            bj = objects[j].get("bbox", (0, 0, 0, 0))
            h_overlap = max(0, min(bi[3], bj[3]) - max(bi[1], bj[1]))
            v_overlap = max(0, min(bi[2], bj[2]) - max(bi[0], bj[0]))
            adjacent = float(h_overlap >= 0 and v_overlap >= 0 and
                           (max(bj[1] - bi[3], bi[1] - bj[3], 0) <= 1) and
                           (max(bj[0] - bi[2], bi[0] - bj[2], 0) <= 1))

            edge_feats.append([dr, dc, dist, same_color, size_ratio, adjacent,
                             float(h_overlap > 0), float(v_overlap > 0)])

    if not src_list:
        edge_index = torch.zeros(2, 0, dtype=torch.long, device=device)
        edge_attr = torch.zeros(0, 8, device=device)
    else:
        edge_index = torch.tensor([src_list, dst_list], dtype=torch.long, device=device)
        edge_attr = torch.tensor(edge_feats, dtype=torch.float32, device=device)

    return node_t, edge_index, edge_attr


def grid_objects_to_dicts(grid: np.ndarray, background: int = 0) -> List[Dict[str, Any]]:
    """Extract objects from grid as dicts for graph construction."""
    from scipy import ndimage

    arr = np.asarray(grid, dtype=int)
    objects = []
    for color in sorted(set(arr.flatten().tolist())):
        if color == background:
            continue
        mask = arr == color
        labeled, n = ndimage.label(mask)
        for comp_id in range(1, n + 1):
            pixels = list(zip(*np.where(labeled == comp_id)))
            if not pixels:
                continue
            rows = [p[0] for p in pixels]
            cols = [p[1] for p in pixels]
            bbox = (min(rows), min(cols), max(rows), max(cols))
            h = bbox[2] - bbox[0] + 1
            w = bbox[3] - bbox[1] + 1
            objects.append({
                "color": int(color),
                "size": len(pixels),
                "bbox": bbox,
                "centroid": (float(np.mean(rows)), float(np.mean(cols))),
                "is_rectangular": len(pixels) == h * w,
                "pixels": pixels,
            })
    return objects


class TaskContextEncoder(nn.Module):
    """Encodes a set of (input, output) demonstration pairs into a task embedding.

    Uses per-pair slot encoding + cross-pair attention to produce a fixed-size
    task vector that conditions the GNS dynamics.
    """

    def __init__(self, slot_dim: int = 64, hidden_dim: int = 128, max_demos: int = 8):
        super().__init__()
        self.pair_encoder = nn.Sequential(
            nn.Linear(slot_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, slot_dim),
        )
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=slot_dim, num_heads=4, batch_first=True
        )
        self.norm = nn.LayerNorm(slot_dim)
        self.max_demos = max_demos

    def forward(self, input_slot_means: Tensor, output_slot_means: Tensor) -> Tensor:
        """
        Args:
            input_slot_means: (N_demos, slot_dim) mean slot per demo input
            output_slot_means: (N_demos, slot_dim) mean slot per demo output
        Returns:
            task_embedding: (slot_dim,) conditioning vector
        """
        pair_feats = self.pair_encoder(
            torch.cat([input_slot_means, output_slot_means], dim=-1)
        )
        pair_feats = pair_feats.unsqueeze(0)
        attn_out, _ = self.cross_attn(pair_feats, pair_feats, pair_feats)
        attn_out = self.norm(attn_out + pair_feats)
        return attn_out.squeeze(0).mean(dim=0)


class WorldModel(nn.Module):
    """Task-conditioned Slot Attention + GNS world model for ARC tasks.

    Pipeline:
        Training demos → TaskContextEncoder → task_embedding
        Input grid → Slot Attention (object discovery) →
        [slots + task_embedding] → GNS (conditioned dynamics prediction) →
        Output slot features → reconstruct output grid
    """

    def __init__(
        self,
        num_slots: int = 8,
        slot_dim: int = 64,
        hidden_dim: int = 128,
        gns_layers: int = 3,
        max_grid_size: int = 30,
        num_colors: int = 11,
    ):
        super().__init__()
        self.num_slots = num_slots
        self.slot_dim = slot_dim
        self.hidden_dim = hidden_dim

        from .slot_attention import GridSlotModel, SlotDecoder
        self.slot_model = GridSlotModel(
            num_slots=num_slots,
            slot_dim=slot_dim,
            hidden_dim=hidden_dim,
            num_iterations=3,
            max_grid_size=max_grid_size,
            num_colors=num_colors,
        )

        self.context_encoder = TaskContextEncoder(
            slot_dim=slot_dim, hidden_dim=hidden_dim
        )

        self.conditioning_proj = nn.Sequential(
            nn.Linear(slot_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, slot_dim),
        )

        self.gns = GraphNetworkSimulator(
            input_node_dim=slot_dim,
            input_edge_dim=8,
            node_dim=slot_dim,
            edge_dim=32,
            hidden_dim=hidden_dim,
            num_layers=gns_layers,
            output_node_dim=slot_dim,
        )

        self.output_decoder = SlotDecoder(
            slot_dim=slot_dim,
            hidden_dim=hidden_dim,
            max_grid_size=max_grid_size,
            num_colors=num_colors,
        )

    def _build_slot_edges(self, slots: Tensor) -> Tuple[Tensor, Tensor]:
        """Build fully-connected edges between slots."""
        if slots.dim() == 3:
            K = slots.shape[1]
        else:
            K = slots.shape[0]
        src, dst = [], []
        for i in range(K):
            for j in range(K):
                if i != j:
                    src.append(i)
                    dst.append(j)
        if not src:
            device = slots.device
            return (
                torch.zeros(2, 0, dtype=torch.long, device=device),
                torch.zeros(0, 8, device=device),
            )
        edge_index = torch.tensor([src, dst], dtype=torch.long, device=slots.device)
        E = edge_index.shape[1]
        edge_attr = torch.zeros(E, 8, device=slots.device)
        return edge_index, edge_attr

    def _encode_grid_to_slots(self, grid_t: Tensor, valid_t: Tensor) -> Tensor:
        result = self.slot_model(grid_t, valid_t)
        return result["slots"]

    def _get_slot_mean(self, grid: np.ndarray, device: str) -> Tensor:
        arr = np.asarray(grid, dtype=int)
        H, W = arr.shape
        g_t = torch.tensor(arr, dtype=torch.long, device=device).unsqueeze(0)
        v_t = torch.ones(1, H, W, dtype=torch.bool, device=device)
        slots = self._encode_grid_to_slots(g_t, v_t)
        return slots[0].mean(dim=0)

    def _compute_task_embedding(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]], device: str
    ) -> Tensor:
        input_means = []
        output_means = []
        for inp, out in train_pairs[:8]:
            if inp.shape[0] > 30 or inp.shape[1] > 30:
                continue
            if out.shape[0] > 30 or out.shape[1] > 30:
                continue
            input_means.append(self._get_slot_mean(inp, device))
            output_means.append(self._get_slot_mean(out, device))
        if not input_means:
            return torch.zeros(self.slot_dim, device=device)
        inp_stack = torch.stack(input_means)
        out_stack = torch.stack(output_means)
        return self.context_encoder(inp_stack, out_stack)

    def _condition_slots(self, slots: Tensor, task_emb: Tensor) -> Tensor:
        """Condition input slots with task embedding via concatenation + projection."""
        K = slots.shape[0]
        expanded = task_emb.unsqueeze(0).expand(K, -1)
        combined = torch.cat([slots, expanded], dim=-1)
        return self.conditioning_proj(combined)

    def forward(
        self,
        input_grids: Tensor,
        input_valid: Tensor,
        output_grids: Tensor,
        output_valid: Tensor,
        task_embedding: Optional[Tensor] = None,
    ) -> Dict[str, Tensor]:
        B, H_in, W_in = input_grids.shape
        _, H_out, W_out = output_grids.shape

        input_result = self.slot_model(input_grids, input_valid)
        input_slots = input_result["slots"]

        edge_index, edge_attr = self._build_slot_edges(input_slots)
        predicted_output_slots_list = []
        for b in range(B):
            slots_b = input_slots[b]
            if task_embedding is not None:
                te = task_embedding if task_embedding.dim() == 1 else task_embedding[b]
                slots_b = self._condition_slots(slots_b, te)
            pred_nodes = self.gns(slots_b, edge_index, edge_attr)
            predicted_output_slots_list.append(pred_nodes)
        predicted_output_slots = torch.stack(predicted_output_slots_list)

        output_recon, output_masks = self.output_decoder(predicted_output_slots, H_out, W_out)

        target = output_grids.clamp(0, self.slot_model.num_colors - 1).long()
        flat_logits = output_recon.reshape(-1, self.slot_model.num_colors)
        flat_logits = torch.where(
            torch.isnan(flat_logits), torch.zeros_like(flat_logits), flat_logits
        )
        recon_loss = F.cross_entropy(
            flat_logits,
            target.reshape(-1),
            reduction="none",
        ).reshape(B, H_out, W_out)
        recon_loss = (recon_loss * output_valid.float()).sum() / output_valid.float().sum().clamp(min=1)

        input_recon_loss = input_result["loss"]
        total_loss = recon_loss + 0.5 * input_recon_loss

        return {
            "loss": total_loss,
            "output_recon_loss": recon_loss,
            "input_recon_loss": input_recon_loss,
            "input_slots": input_slots,
            "predicted_output_slots": predicted_output_slots,
            "output_recon_logits": output_recon,
            "output_slot_masks": output_masks,
        }

    @torch.no_grad()
    def predict(
        self,
        input_grid: np.ndarray,
        output_shape: Tuple[int, int],
        device: str = "cpu",
        train_pairs: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None,
    ) -> np.ndarray:
        """Predict output grid, optionally conditioned on training demonstrations."""
        self.to(device)
        self.eval()

        arr = np.asarray(input_grid, dtype=int)
        H_in, W_in = arr.shape
        H_out, W_out = output_shape

        task_emb = None
        if train_pairs:
            task_emb = self._compute_task_embedding(train_pairs, device)

        grids_t = torch.tensor(arr, dtype=torch.long, device=device).unsqueeze(0)
        valid = torch.ones(1, H_in, W_in, dtype=torch.bool, device=device)

        input_result = self.slot_model(grids_t, valid)
        input_slots = input_result["slots"]

        edge_index, edge_attr = self._build_slot_edges(input_slots)
        slots_0 = input_slots[0]
        if task_emb is not None:
            slots_0 = self._condition_slots(slots_0, task_emb)
        pred_slots = self.gns(slots_0, edge_index, edge_attr).unsqueeze(0)

        output_recon, _ = self.output_decoder(pred_slots, H_out, W_out)
        return output_recon[0].argmax(dim=-1).cpu().numpy()

    @torch.no_grad()
    def score_candidate(
        self,
        input_grid: np.ndarray,
        candidate_output: np.ndarray,
        device: str = "cpu",
        train_pairs: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None,
    ) -> float:
        """Score candidate via task-conditioned prediction agreement + log-likelihood."""
        self.to(device)
        self.eval()

        H_out, W_out = candidate_output.shape

        task_emb = None
        if train_pairs:
            task_emb = self._compute_task_embedding(train_pairs, device)

        arr = np.asarray(input_grid, dtype=int)
        H_in, W_in = arr.shape
        grids_t = torch.tensor(arr, dtype=torch.long, device=device).unsqueeze(0)
        valid = torch.ones(1, H_in, W_in, dtype=torch.bool, device=device)

        input_result = self.slot_model(grids_t, valid)
        input_slots = input_result["slots"]

        edge_index, edge_attr = self._build_slot_edges(input_slots)
        slots_0 = input_slots[0]
        if task_emb is not None:
            slots_0 = self._condition_slots(slots_0, task_emb)
        pred_slots = self.gns(slots_0, edge_index, edge_attr).unsqueeze(0)

        output_recon, _ = self.output_decoder(pred_slots, H_out, W_out)
        logits = output_recon[0]
        log_probs = F.log_softmax(logits, dim=-1)

        target = torch.tensor(candidate_output, dtype=torch.long, device=device)
        target = target.clamp(0, log_probs.shape[-1] - 1)
        per_pixel_ll = log_probs.gather(-1, target.unsqueeze(-1)).squeeze(-1)
        mean_ll = per_pixel_ll.mean().item()

        predicted = logits.argmax(dim=-1).cpu().numpy()
        pixel_agreement = float(np.mean(predicted == candidate_output))

        return 0.5 * pixel_agreement + 0.5 * (1.0 / (1.0 + np.exp(-mean_ll)))


def load_world_model_checkpoint(path, device=None):
    if not torch_available():
        raise RuntimeError("Requires torch")
    package = torch.load(path, map_location=device or "cpu", weights_only=False)
    config = package.get("model_config", {})
    model = WorldModel(**config)
    state = package["model_state"]
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        for key in missing:
            parts = key.split(".")
            param = model
            for p in parts[:-1]:
                param = getattr(param, p)
            tensor = getattr(param, parts[-1])
            if isinstance(tensor, torch.nn.Parameter):
                pass
    model.eval()
    return model
