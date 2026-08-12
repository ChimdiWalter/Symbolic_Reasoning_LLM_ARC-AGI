import math
import json
import random
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam
import matplotlib.pyplot as plt

# ==========================================
# 0. Global Config
# ==========================================

CANVAS_SIZE = 64
BG_COLOR = 10  # 0-9 are colors, 10 is background

VIS_EXAMPLES_DIR = Path("vis_examples")
VIS_EXAMPLES_DIR.mkdir(exist_ok=True)


# ==========================================
# 1. VARC Canvas Engine
# ==========================================

def prepare_canvas(
    grid: np.ndarray,
    augment: bool = False,
    max_scale_limit: Optional[int] = None
) -> Tuple[torch.Tensor, int, int, int]:
    """
    Place grid on a fixed 64x64 canvas with integer scaling + translation.

    Returns:
        canvas: [64, 64] LongTensor with values in [0..10]
        scale:  integer scale factor
        top:    top offset on canvas
        left:   left offset on canvas
    """
    H, W = grid.shape
    h_safe = max(1, H)
    w_safe = max(1, W)

    max_scale = min(CANVAS_SIZE // h_safe, CANVAS_SIZE // w_safe)
    if max_scale_limit is not None:
        max_scale = min(max_scale, max_scale_limit)
    max_scale = max(1, max_scale)

    if augment and max_scale > 1:
        scale = random.randint(1, max_scale)
    else:
        scale = max_scale

    scaled_grid = grid.repeat(scale, axis=0).repeat(scale, axis=1)
    SH, SW = scaled_grid.shape

    max_y = max(0, CANVAS_SIZE - SH)
    max_x = max(0, CANVAS_SIZE - SW)

    if augment:
        top = random.randint(0, max_y)
        left = random.randint(0, max_x)
    else:
        top = max_y // 2
        left = max_x // 2

    canvas_np = np.full((CANVAS_SIZE, CANVAS_SIZE), BG_COLOR, dtype=np.int64)
    r_end = min(CANVAS_SIZE, top + SH)
    c_end = min(CANVAS_SIZE, left + SW)

    place_h = r_end - top
    place_w = c_end - left

    if place_h > 0 and place_w > 0:
        canvas_np[top:r_end, left:c_end] = scaled_grid[:place_h, :place_w]

    return torch.from_numpy(canvas_np), scale, top, left


def recover_from_canvas(
    canvas_logits: torch.Tensor,
    original_H: int,
    original_W: int,
    scale: int,
    top: int,
    left: int
) -> torch.Tensor:
    """
    Crop logits back to original output size.

    canvas_logits: [NumColors, 64, 64]
    Returns: [NumColors, original_H, original_W]
    """
    scaled_H = original_H * scale
    scaled_W = original_W * scale

    r_end = min(CANVAS_SIZE, top + scaled_H)
    c_end = min(CANVAS_SIZE, left + scaled_W)
    crop = canvas_logits[:, top:r_end, left:c_end]

    curr_h, curr_w = crop.shape[1], crop.shape[2]
    if curr_h < scaled_H or curr_w < scaled_W:
        pad_h = scaled_H - curr_h
        pad_w = scaled_W - curr_w
        crop = F.pad(crop, (0, pad_w, 0, pad_h), value=-1e9)

    output = F.adaptive_avg_pool2d(crop.unsqueeze(0), (original_H, original_W)).squeeze(0)
    return output


# ==========================================
# 2. Graph Construction
# ==========================================

@dataclass
class GraphData:
    node_feats: torch.Tensor
    adj: torch.Tensor
    pixels: List[List[Tuple[int, int]]]
    num_nodes: int


def grid_to_graph(grid: np.ndarray, num_colors: int = 11) -> GraphData:
    """
    Simple component graph:
      - One node per connected component of equal color.
      - Features: [11 color one-hot, size_norm, compactness].
      - Adjacency: identity (self-loops only) — GNN can be extended later.
    """
    H, W = grid.shape
    visited = np.zeros((H, W), dtype=bool)
    comps = []
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    for i in range(H):
        for j in range(W):
            if not visited[i, j]:
                c = grid[i, j]
                q = [(i, j)]
                visited[i, j] = True
                px = [(i, j)]

                while q:
                    ci, cj = q.pop()
                    for di, dj in dirs:
                        ni, nj = ci + di, cj + dj
                        if 0 <= ni < H and 0 <= nj < W and not visited[ni, nj] and grid[ni, nj] == c:
                            visited[ni, nj] = True
                            q.append((ni, nj))
                            px.append((ni, nj))

                comps.append({"c": c, "px": px})

    N = len(comps)
    if N == 0:
        return GraphData(
            node_feats=torch.zeros(0, num_colors + 2),
            adj=torch.zeros(0, 0),
            pixels=[],
            num_nodes=0
        )

    feats = []
    for comp in comps:
        c_vec = np.zeros(num_colors, dtype=np.float32)
        c_vec[comp["c"]] = 1.0

        sz = len(comp["px"]) / (H * W + 1e-5)
        ys = [p[0] for p in comp["px"]]
        xs = [p[1] for p in comp["px"]]
        bbox_area = (max(ys) - min(ys) + 1) * (max(xs) - min(xs) + 1)
        compact = sz / (bbox_area / (H * W) + 1e-5)

        feats.append(np.concatenate([c_vec, [sz, compact]]))

    node_feats = torch.tensor(np.stack(feats), dtype=torch.float32)
    adj = torch.eye(N)

    return GraphData(node_feats, adj, [c["px"] for c in comps], N)


# ==========================================
# 3. Neural Modules
# ==========================================

class VisionTransformerEncoder(nn.Module):
    """
    VARC-style ViT over 64x64 canvas, patchified into 2x2 patches.
    """

    def __init__(self, canvas_size=64, patch_size=2, hidden_dim=128, layers=4):
        super().__init__()
        self.patch_size = patch_size
        self.H_patches = canvas_size // patch_size
        self.W_patches = canvas_size // patch_size
        num_patches = self.H_patches * self.W_patches

        pixels_per_patch = patch_size * patch_size
        self.patch_embed = nn.Linear(pixels_per_patch * 11, hidden_dim)
        self.pos_embed = nn.Parameter(torch.randn(1, num_patches, hidden_dim) * 0.02)

        enc_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=4,
            dim_feedforward=256,
            activation="gelu",
            batch_first=True,
        )
        self.blocks = nn.TransformerEncoder(enc_layer, num_layers=layers)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, canvas_onehot: torch.Tensor) -> torch.Tensor:
        """
        canvas_onehot: [B, 64, 64, 11]
        Returns: [B, hidden_dim, H_patches, W_patches]
        """
        B, H, W, C = canvas_onehot.shape
        patches = canvas_onehot.view(
            B,
            self.H_patches,
            self.patch_size,
            self.W_patches,
            self.patch_size,
            C,
        )
        patches = patches.permute(0, 1, 3, 2, 4, 5).contiguous()
        patches_flat = patches.view(B, self.H_patches * self.W_patches, -1)

        x = self.patch_embed(patches_flat) + self.pos_embed
        x = self.blocks(x)
        x = self.norm(x)

        x = x.permute(0, 2, 1).view(B, -1, self.H_patches, self.W_patches)
        return x


class GraphEncoder(nn.Module):
    """
    Simple MLP encoder over per-component features.
    """

    def __init__(self, in_dim: int, hidden_dim: int):
        super().__init__()
        self.mlp1 = nn.Linear(in_dim, hidden_dim)
        self.mlp2 = nn.Linear(hidden_dim, hidden_dim)

    def forward(self, node_feats: torch.Tensor) -> torch.Tensor:
        if node_feats.size(0) == 0:
            return node_feats
        x = F.relu(self.mlp1(node_feats))
        x = F.relu(self.mlp2(x))
        return x


class FusionDecoder(nn.Module):
    """
    U-Net style fusion of Visual (ViT output), Geometric canvas, Task embedding and coords.
    """

    def __init__(self, vis_dim: int, geo_dim: int, task_dim: int, out_dim: int = 11):
        super().__init__()
        total_in = vis_dim + geo_dim + task_dim + 2  # +2 for coordinates

        self.conv1 = nn.Sequential(
            nn.Conv2d(total_in, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.Conv2d(128, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
        )
        self.conv2 = nn.Sequential(
            nn.Conv2d(128, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
        )
        self.final = nn.Conv2d(64, out_dim, 1)

        yy, xx = torch.meshgrid(
            torch.linspace(-1, 1, CANVAS_SIZE),
            torch.linspace(-1, 1, CANVAS_SIZE),
            indexing="ij",
        )
        self.register_buffer("coords", torch.stack([yy, xx], dim=0).unsqueeze(0))

    def forward(
        self,
        vis_map: torch.Tensor,    # [B, vis_dim, H_p, W_p]
        geo_canvas: torch.Tensor, # [B, geo_dim, 64, 64]
        task_emb: torch.Tensor,   # [B, task_dim]
    ) -> torch.Tensor:
        B = vis_map.size(0)
        vis_up = F.interpolate(
            vis_map, size=(CANVAS_SIZE, CANVAS_SIZE),
            mode="bilinear", align_corners=False
        )
        task_plane = task_emb.view(B, -1, 1, 1).expand(-1, -1, CANVAS_SIZE, CANVAS_SIZE)

        x = torch.cat(
            [vis_up, geo_canvas, task_plane, self.coords.expand(B, -1, -1, -1)],
            dim=1,
        )
        x = self.conv1(x)
        x = self.conv2(x)
        return self.final(x)  # [B, out_dim, 64, 64]


# ==========================================
# 4. NeuroSymbolic VARC+Topo Model
# ==========================================

class NeuroSymbolic_VARC(nn.Module):
    def __init__(self, device: torch.device, num_train_tasks: int):
        super().__init__()
        self.device = device
        self.vis_dim = 128
        self.geo_dim = 64
        self.task_dim = 64

        self.visual_encoder = VisionTransformerEncoder(hidden_dim=self.vis_dim)
        self.geo_encoder = GraphEncoder(in_dim=13, hidden_dim=self.geo_dim)  # 11 color + 2 shape
        self.task_embedding = nn.Embedding(num_train_tasks, self.task_dim)
        self.decoder = FusionDecoder(self.vis_dim, self.geo_dim, self.task_dim)
        self.ttt_token = nn.Parameter(torch.randn(1, self.task_dim))

    def paint_graph_to_canvas(
        self,
        graph: GraphData,
        node_embs: torch.Tensor,
        scale: int,
        top: int,
        left: int,
    ) -> torch.Tensor:
        canvas = torch.zeros(
            (1, self.geo_dim, CANVAS_SIZE, CANVAS_SIZE), device=self.device
        )
        if graph.num_nodes == 0:
            return canvas

        for i in range(graph.num_nodes):
            emb = node_embs[i]
            pixels = graph.pixels[i]
            for r, c in pixels:
                r_start, r_end = r * scale + top, (r + 1) * scale + top
                c_start, c_end = c * scale + left, (c + 1) * scale + left

                r_start = max(0, min(CANVAS_SIZE, r_start))
                r_end = max(0, min(CANVAS_SIZE, r_end))
                c_start = max(0, min(CANVAS_SIZE, c_start))
                c_end = max(0, min(CANVAS_SIZE, c_end))

                if r_end > r_start and c_end > c_start:
                    canvas[0, :, r_start:r_end, c_start:c_end] += emb.view(-1, 1, 1)

        return canvas

    # ---------- Training forward (loss) ----------
    def forward_pair(
        self,
        input_grid: np.ndarray,
        task_idx: Optional[int] = None,
        augment: bool = True,
        output_grid: Optional[np.ndarray] = None,
    ) -> torch.Tensor:
        """
        Training mode: given input_grid and output_grid, compute CE loss
        on the canvas-space reconstruction.
        """

        h_in, w_in = input_grid.shape
        max_s_in = min(CANVAS_SIZE // max(1, h_in), CANVAS_SIZE // max(1, w_in))
        max_limit = max_s_in

        if output_grid is not None:
            h_out, w_out = output_grid.shape
            max_s_out = min(
                CANVAS_SIZE // max(1, h_out), CANVAS_SIZE // max(1, w_out)
            )
            max_limit = min(max_s_in, max_s_out)

        canvas, scale, top, left = prepare_canvas(
            input_grid, augment=augment, max_scale_limit=max_limit
        )
        canvas_gpu = canvas.to(self.device)
        canvas_oh = F.one_hot(canvas_gpu, num_classes=11).float().unsqueeze(0)

        graph = grid_to_graph(input_grid)
        g_feats = graph.node_feats.to(self.device)

        vis_map = self.visual_encoder(canvas_oh)
        node_embs = self.geo_encoder(g_feats)
        geo_canvas = self.paint_graph_to_canvas(
            graph, node_embs, scale, top, left
        )

        if task_idx is not None:
            t_emb = self.task_embedding(
                torch.tensor([task_idx], device=self.device)
            )
        else:
            t_emb = self.ttt_token

        logits_canvas = self.decoder(vis_map, geo_canvas, t_emb)

        if output_grid is not None:
            target_canvas = torch.full(
                (CANVAS_SIZE, CANVAS_SIZE),
                BG_COLOR,
                dtype=torch.long,
            )

            tgt_np = output_grid.repeat(scale, 0).repeat(scale, 1)
            tSH, tSW = tgt_np.shape
            r_end = min(CANVAS_SIZE, top + tSH)
            c_end = min(CANVAS_SIZE, left + tSW)
            place_h = r_end - top
            place_w = c_end - left
            if place_h > 0 and place_w > 0:
                target_canvas[top:r_end, left:c_end] = torch.from_numpy(
                    tgt_np[:place_h, :place_w]
                )

            target_gpu = target_canvas.to(self.device).unsqueeze(0)
            loss = F.cross_entropy(logits_canvas, target_gpu)
            return loss
        else:
            raise RuntimeError(
                "forward_pair without output_grid is training-only; "
                "use predict_pair for inference."
            )

    # ---------- Inference forward (prediction) ----------
    def predict_pair(
        self,
        input_grid: np.ndarray,
        output_shape_grid: np.ndarray,
        use_ttt_token: bool = True,
        augment: bool = False,
    ) -> np.ndarray:
        """
        Inference mode: predict output grid logits, then argmax.
        Uses the *output* shape (from GT) to ensure shapes match.
        """
        h_in, w_in = input_grid.shape
        h_out, w_out = output_shape_grid.shape

        max_s_in = min(CANVAS_SIZE // max(1, h_in), CANVAS_SIZE // max(1, w_in))
        max_s_out = min(CANVAS_SIZE // max(1, h_out), CANVAS_SIZE // max(1, w_out))
        max_limit = min(max_s_in, max_s_out)

        canvas, scale, top, left = prepare_canvas(
            input_grid, augment=augment, max_scale_limit=max_limit
        )
        canvas_gpu = canvas.to(self.device)
        canvas_oh = F.one_hot(canvas_gpu, num_classes=11).float().unsqueeze(0)

        graph = grid_to_graph(input_grid)
        g_feats = graph.node_feats.to(self.device)

        vis_map = self.visual_encoder(canvas_oh)
        node_embs = self.geo_encoder(g_feats)
        geo_canvas = self.paint_graph_to_canvas(graph, node_embs, scale, top, left)

        if use_ttt_token:
            t_emb = self.ttt_token
        else:
            t_emb = self.ttt_token

        logits_canvas = self.decoder(vis_map, geo_canvas, t_emb)[0]  # [11,64,64]

        logits_crop = recover_from_canvas(
            logits_canvas, h_out, w_out, scale, top, left
        )  # [11,h_out,w_out]

        pred_grid = logits_crop.argmax(0).cpu().numpy()
        return pred_grid


# ==========================================
# 5. Visualization helper (PNG + TXT for whole task)
# ==========================================

def save_task_examples(
    split_tag: str,
    task_id: str,
    inputs: List[np.ndarray],
    gts: List[np.ndarray],
    preds: List[np.ndarray],
):
    """
    Save a multi-row PNG and a TXT file for a single task.

    split_tag: "train_eval" or "eval_split"
    Files:
      vis_examples/<split_tag>_<taskid>.png
      vis_examples/<split_tag>_<taskid>.txt

    Each row of the PNG: [INPUT | GT | PRED] for a test grid.
    """
    assert len(inputs) == len(gts) == len(preds)
    n = len(inputs)
    if n == 0:
        return

    # ---------- PNG ----------
    fig, axes = plt.subplots(nrows=n, ncols=3, figsize=(9, 3 * n))
    if n == 1:
        axes = np.expand_dims(axes, axis=0)

    vmax = 10
    for inp, gt, pr in zip(inputs, gts, preds):
        vmax = max(vmax, int(inp.max()), int(gt.max()), int(pr.max()))
    vmin = 0

    for i in range(n):
        inp = inputs[i]
        gt = gts[i]
        pr = preds[i]

        # INPUT
        ax = axes[i, 0]
        ax.imshow(inp, interpolation="nearest", vmin=vmin, vmax=vmax)
        ax.set_title("INPUT")
        ax.axis("off")

        # GT
        ax = axes[i, 1]
        ax.imshow(gt, interpolation="nearest", vmin=vmin, vmax=vmax)
        ax.set_title("GT")
        ax.axis("off")

        # PRED
        ax = axes[i, 2]
        ax.imshow(pr, interpolation="nearest", vmin=vmin, vmax=vmax)
        ax.set_title("PRED")
        ax.axis("off")

    plt.tight_layout()
    png_path = VIS_EXAMPLES_DIR / f"{split_tag}_{task_id}.png"
    plt.savefig(png_path, dpi=150)
    plt.close()

    # ---------- TXT ----------
    txt_path = VIS_EXAMPLES_DIR / f"{split_tag}_{task_id}.txt"
    with txt_path.open("w") as f:
        for i in range(n):
            f.write(f"=== TEST GRID {i} ===\n")
            f.write("INPUT:\n")
            f.write(str(inputs[i]) + "\n\n")
            f.write("GT:\n")
            f.write(str(gts[i]) + "\n\n")
            f.write("PRED:\n")
            f.write(str(preds[i]) + "\n\n")
            f.write("=" * 40 + "\n\n")


# ==========================================
# 6. Training & TTT Loops
# ==========================================

def train_offline(model: NeuroSymbolic_VARC, tasks, epochs: int = 10):
    opt = Adam(model.parameters(), lr=3e-4)
    model.train()

    for ep in range(epochs):
        total_loss = 0.0
        steps = 0
        random.shuffle(tasks)

        for t_idx, task in enumerate(tasks):
            for pair in task["train"]:
                opt.zero_grad()
                loss = model.forward_pair(
                    pair["input"],
                    task_idx=t_idx,
                    augment=True,
                    output_grid=pair["output"],
                )
                loss.backward()
                opt.step()
                total_loss += loss.item()
                steps += 1

        avg_loss = total_loss / max(1, steps)
        print(f"[Offline] Epoch {ep+1}/{epochs} | Loss: {avg_loss:.4f}")


def test_time_training_and_eval_task(
    model: NeuroSymbolic_VARC,
    task: Dict[str, Any],
    ttt_steps: int,
) -> Tuple[Dict[str, Any], List[np.ndarray], List[np.ndarray], List[np.ndarray]]:
    """
    For a single task:
      1) Reset TTT token.
      2) Adapt on train demos.
      3) Evaluate on test grids (assuming GT available).
    Returns:
      stats dict,
      list of input grids,
      list of GT grids,
      list of predicted grids
    """
    # 1. Reset TTT token
    nn.init.normal_(model.ttt_token, std=0.02)

    # 2. Optimizer for TTT (token + decoder)
    params = [model.ttt_token] + list(model.decoder.parameters())
    opt = Adam(params, lr=1e-3)

    model.train()
    for _ in range(ttt_steps):
        for pair in task["train"]:
            opt.zero_grad()
            loss = model.forward_pair(
                pair["input"],
                task_idx=None,
                augment=True,
                output_grid=pair["output"],
            )
            loss.backward()
            opt.step()

    model.eval()
    total_pixels = 0
    correct_pixels = 0
    num_test_grids = 0
    num_test_grids_solved = 0

    inputs_all: List[np.ndarray] = []
    gts_all: List[np.ndarray] = []
    preds_all: List[np.ndarray] = []

    with torch.no_grad():
        for test_pair in task["test"]:
            if "output" not in test_pair:
                continue
            gt = test_pair["output"]
            inp = test_pair["input"]
            num_test_grids += 1

            pred = model.predict_pair(
                inp,
                gt,
                use_ttt_token=True,
                augment=False,
            )

            if pred.shape == gt.shape and np.array_equal(pred, gt):
                num_test_grids_solved += 1

            if pred.shape == gt.shape:
                correct_pixels += (pred == gt).sum()
                total_pixels += gt.size

            inputs_all.append(inp)
            gts_all.append(gt)
            preds_all.append(pred)

    task_solved = (num_test_grids > 0 and num_test_grids_solved == num_test_grids)
    pixel_acc = (
        float(correct_pixels) / float(total_pixels) if total_pixels > 0 else 0.0
    )

    stats = {
        "task_id": task["id"],
        "task_solved": task_solved,
        "num_test_grids": num_test_grids,
        "num_test_grids_solved": num_test_grids_solved,
        "correct_pixels": correct_pixels,
        "total_pixels": total_pixels,
        "pixel_acc": pixel_acc,
    }

    return stats, inputs_all, gts_all, preds_all


def evaluate_with_ttt(
    model: NeuroSymbolic_VARC,
    tasks,
    ttt_steps: int,
    split_name: str,
):
    """
    Run TTT on each task in `tasks` and compute aggregate metrics.
    Also saves ONE "best unsolved" task as PNG+TXT in vis_examples/.
    """
    print(f"\n=== TTT Evaluation on {split_name} ===")
    total_tasks = 0
    tasks_solved = 0
    total_grids = 0
    grids_solved = 0
    total_pixels = 0
    correct_pixels = 0

    # Track best unsolved task (highest pixel_acc)
    best_unsolved = None  # dict with keys: stats, inputs, gts, preds

    for idx, task in enumerate(tasks, start=1):
        has_gt = any("output" in p for p in task["test"])
        if not has_gt:
            print(
                f"[{split_name}] Task {idx}/{len(tasks)} ({task['id']}): skipped (no GT)"
            )
            continue

        stats, inputs_all, gts_all, preds_all = test_time_training_and_eval_task(
            model, task, ttt_steps
        )

        total_tasks += 1
        total_grids += stats["num_test_grids"]
        grids_solved += stats["num_test_grids_solved"]
        total_pixels += stats["total_pixels"]
        correct_pixels += stats["correct_pixels"]

        if stats["task_solved"]:
            tasks_solved += 1

        status = "SOLVED" if stats["task_solved"] else "not solved"
        print(
            f"[{split_name}] Task {idx}/{len(tasks)} ({task['id']}): {status} "
            f"(grids {stats['num_test_grids_solved']}/{stats['num_test_grids']}, "
            f"pixel_acc={stats['pixel_acc']:.4f})"
        )

        # Update best unsolved
        if (not stats["task_solved"]) and stats["num_test_grids"] > 0:
            if best_unsolved is None or stats["pixel_acc"] > best_unsolved["stats"]["pixel_acc"]:
                best_unsolved = {
                    "task_id": task["id"],
                    "stats": stats,
                    "inputs": inputs_all,
                    "gts": gts_all,
                    "preds": preds_all,
                }

    task_success_rate = (
        tasks_solved / max(1, total_tasks) if total_tasks > 0 else 0.0
    )
    grid_success_rate = (
        grids_solved / max(1, total_grids) if total_grids > 0 else 0.0
    )
    avg_pixel_accuracy = (
        correct_pixels / max(1, total_pixels) if total_pixels > 0 else 0.0
    )

    print(f"\n[{split_name}] Detailed metrics:")
    print(f"  num_tasks:            {total_tasks}")
    print(f"  num_tasks_solved:     {tasks_solved}")
    print(f"  task_success_rate:    {task_success_rate:.4f}")
    print(f"  num_test_grids:       {total_grids}")
    print(f"  num_test_grids_solved:{grids_solved}")
    print(f"  grid_success_rate:    {grid_success_rate:.4f}")
    print(f"  avg_pixel_accuracy:   {avg_pixel_accuracy:.4f}")

    # ---------- Save "best unsolved" task examples ----------
    if best_unsolved is not None:
        if "TRAIN" in split_name:
            tag = "train_eval"
        elif "EVAL" in split_name:
            tag = "eval_split"
        else:
            tag = split_name.replace(" ", "_")

        tid = best_unsolved["task_id"]
        print(
            f"\n[{split_name}] Saving best unsolved task {tid} "
            f"with pixel_acc={best_unsolved['stats']['pixel_acc']:.4f}"
        )
        save_task_examples(
            tag,
            tid,
            best_unsolved["inputs"],
            best_unsolved["gts"],
            best_unsolved["preds"],
        )
    else:
        print(f"\n[{split_name}] No unsolved tasks (or no tasks with GT) to visualize.")


# ==========================================
# 7. Data Loading (Explicit ARC-AGI-2 Files)
# ==========================================

def load_file_pair(
    root: str,
    challenge_file: str,
    solution_file: Optional[str] = None,
):
    root_path = Path(root)
    c_path = root_path / challenge_file

    print(f"Loading challenges: {c_path}")
    with open(c_path) as f:
        challenges = json.load(f)

    solutions = {}
    if solution_file and (root_path / solution_file).exists():
        s_path = root_path / solution_file
        print(f"Loading solutions:  {s_path}")
        with open(s_path) as f:
            solutions = json.load(f)

    tasks = []
    for tid, content in challenges.items():
        train_pairs = [
            {
                "input": np.array(x["input"], dtype=np.int64),
                "output": np.array(x["output"], dtype=np.int64),
            }
            for x in content["train"]
        ]

        test_pairs = [{"input": np.array(x["input"], dtype=np.int64)} for x in content["test"]]

        if tid in solutions:
            sols = solutions[tid]
            for i, sol_grid in enumerate(sols):
                if i < len(test_pairs):
                    test_pairs[i]["output"] = np.array(sol_grid, dtype=np.int64)

        tasks.append(
            {
                "id": tid,
                "train": train_pairs,
                "test": test_pairs,
            }
        )

    return tasks


# ==========================================
# 8. Main
# ==========================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_root", type=str, required=True)
    parser.add_argument("--epochs_offline", type=int, default=5)
    parser.add_argument("--ttt_steps", type=int, default=30)
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

    if args.device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, falling back to CPU.")
        device = torch.device("cpu")
    else:
        device = torch.device(args.device)

    print(f"Using device: {device}")

    # 1. Load training set
    train_tasks = load_file_pair(
        args.data_root,
        "arc-agi_training_challenges.json",
        "arc-agi_training_solutions.json",
    )

    n_total = len(train_tasks)
    n_offline = min(950, n_total)
    n_train_eval = min(50, max(0, n_total - n_offline))

    offline_set = train_tasks[:n_offline]
    train_eval_set = train_tasks[n_offline:n_offline + n_train_eval]

    print(f"\nLoaded {n_total} train tasks.")
    print(f"Using {len(offline_set)} tasks for offline training.")
    print(f"Using {len(train_eval_set)} held-out train tasks for TTT evaluation.")

    # 2. Init model
    model = NeuroSymbolic_VARC(device, num_train_tasks=len(offline_set)).to(device)

    # 3. Offline training
    print("\n=== Offline Training ===")
    train_offline(model, offline_set, epochs=args.epochs_offline)

    # 4. TTT evaluation on held-out train tasks
    if len(train_eval_set) > 0:
        evaluate_with_ttt(
            model,
            train_eval_set,
            ttt_steps=args.ttt_steps,
            split_name="held-out TRAIN",
        )

    # 5. Eval split
    eval_tasks = load_file_pair(
        args.data_root,
        "arc-agi_evaluation_challenges.json",
        "arc-agi_evaluation_solutions.json",
    )
    print(f"\nLoaded {len(eval_tasks)} eval tasks.")

    evaluate_with_ttt(
        model,
        eval_tasks,
        ttt_steps=args.ttt_steps,
        split_name="EVAL",
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
