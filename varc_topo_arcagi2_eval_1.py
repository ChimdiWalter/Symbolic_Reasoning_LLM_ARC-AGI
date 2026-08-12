import math
import json
import random
import argparse
import copy
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

# ==========================================
# 1. VARC Canvas Engine
# ==========================================

CANVAS_SIZE = 64
BG_COLOR = 10  # 0-9 are colors, 10 is background (special "empty" class)


def prepare_canvas(
    grid: np.ndarray,
    augment: bool = False,
    max_scale_limit: Optional[int] = None,
) -> Tuple[torch.Tensor, int, int, int]:
    """
    Place grid on a fixed 64x64 canvas with optional scale/translation augmentation.

    Returns:
        canvas: [64, 64] tensor of ints in [0..10]
        scale: int (integer scaling factor)
        top, left: placement offsets on the 64x64 canvas
    """
    H, W = grid.shape
    h_safe = max(1, H)
    w_safe = max(1, W)

    max_scale = min(CANVAS_SIZE // h_safe, CANVAS_SIZE // w_safe)
    if max_scale_limit is not None:
        max_scale = min(max_scale, max_scale_limit)
    max_scale = max(1, max_scale)

    # Scale
    if augment and max_scale > 1:
        scale = random.randint(1, max_scale)
    else:
        scale = max_scale

    scaled_grid = grid.repeat(scale, axis=0).repeat(scale, axis=1)
    SH, SW = scaled_grid.shape

    # Translation
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
    left: int,
) -> torch.Tensor:
    """
    Inverse of prepare_canvas: crop the relevant region, downsample back
    to original (H, W).

    canvas_logits: [NumColors, 64, 64]
    Returns: [NumColors, H, W]
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
        # pad: (left, right, top, bottom)
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
    Very simple component graph:
      - nodes = connected components of equal color
      - features = [one-hot color (11), normalized size, compactness]
      - adjacency = identity (can be extended to neighbor graph)
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
                        if (
                            0 <= ni < H
                            and 0 <= nj < W
                            and not visited[ni, nj]
                            and grid[ni, nj] == c
                        ):
                            visited[ni, nj] = True
                            q.append((ni, nj))
                            px.append((ni, nj))
                comps.append({"c": c, "px": px})

    N = len(comps)
    if N == 0:
        return GraphData(torch.zeros(0, num_colors + 2), torch.zeros(0, 0), [], 0)

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
    Simple ViT-like encoder on the 64x64 canvas.

    - Input: one-hot canvas [B, 64, 64, 11]
    - Patchify into 2x2 patches
    - Transformer encoder
    - Output: feature map [B, Dim, 32, 32]
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
        # canvas_onehot: [B, 64, 64, 11]
        B, H, W, C = canvas_onehot.shape
        patches = canvas_onehot.view(
            B, self.H_patches, self.patch_size, self.W_patches, self.patch_size, C
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
    Very simple MLP-based encoder for component node features.
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
    U-Net-like fusion decoder:

      Inputs:
        - vis_map:   [B, vis_dim, 32, 32]
        - geo_canvas:[B, geo_dim, 64, 64]
        - task_emb:  [B, task_dim]
        - coords:    [2, 64, 64] (registered buffer)

      Output:
        - logits_canvas: [B, out_dim(=11), 64, 64]
    """

    def __init__(self, vis_dim: int, geo_dim: int, task_dim: int, out_dim: int = 11):
        super().__init__()
        total_in = vis_dim + geo_dim + task_dim + 2

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
            torch.linspace(-1, 1, 64),
            torch.linspace(-1, 1, 64),
            indexing="ij",
        )
        self.register_buffer("coords", torch.stack([yy, xx], dim=0).unsqueeze(0))

    def forward(
        self, vis_map: torch.Tensor, geo_canvas: torch.Tensor, task_emb: torch.Tensor
    ) -> torch.Tensor:
        B = vis_map.size(0)

        vis_up = F.interpolate(
            vis_map, size=(64, 64), mode="bilinear", align_corners=False
        )

        task_plane = task_emb.view(B, -1, 1, 1).expand(-1, -1, 64, 64)

        x = torch.cat(
            [vis_up, geo_canvas, task_plane, self.coords.expand(B, -1, -1, -1)], dim=1
        )

        x = self.conv1(x)
        x = self.conv2(x)
        return self.final(x)


# ==========================================
# 4. Main NeuroSymbolic Model
# ==========================================

class NeuroSymbolic_VARC(nn.Module):
    def __init__(self, device: torch.device, num_train_tasks: int):
        super().__init__()
        self.device = device
        self.vis_dim = 128
        self.geo_dim = 64
        self.task_dim = 64

        self.visual_encoder = VisionTransformerEncoder(hidden_dim=self.vis_dim)
        self.geo_encoder = GraphEncoder(in_dim=13, hidden_dim=self.geo_dim)
        self.task_embedding = nn.Embedding(num_train_tasks, self.task_dim)
        self.decoder = FusionDecoder(self.vis_dim, self.geo_dim, self.task_dim)

        # Test-time training token
        self.ttt_token = nn.Parameter(torch.randn(1, self.task_dim))

        # Class weights for cross-entropy (foreground > background)
        w = torch.ones(11, dtype=torch.float32)
        w[BG_COLOR] = 0.2   # background less important
        w[:BG_COLOR] = 2.0  # colors 0..9 more important
        self.register_buffer("ce_weights", w)

    def paint_graph_to_canvas(
        self,
        graph: GraphData,
        node_embs: torch.Tensor,
        scale: int,
        top: int,
        left: int,
    ) -> torch.Tensor:
        """
        Project graph node embeddings to the same 64x64 canvas (using same
        scale/top/left as visual canvas).
        """
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

    def forward_pair(
        self,
        input_grid: np.ndarray,
        task_idx: Optional[int] = None,
        augment: bool = True,
        output_grid: Optional[np.ndarray] = None,
    ):
        """
        One input-output pair forward:
          - builds augmented canvas + graph
          - encodes visual + geometric
          - decodes to 64x64 logits
          - if output_grid is given, returns loss (cross-entropy with weights)
          - else returns [NumColors, H, W] logits in original grid size
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
        geo_canvas = self.paint_graph_to_canvas(graph, node_embs, scale, top, left)

        if task_idx is not None:
            t_emb = self.task_embedding(torch.tensor([task_idx], device=self.device))
        else:
            t_emb = self.ttt_token

        logits_canvas = self.decoder(vis_map, geo_canvas, t_emb)  # [1, 11, 64, 64]

        if output_grid is not None:
            # Build target canvas with same augmentation
            target_canvas = torch.full(
                (CANVAS_SIZE, CANVAS_SIZE), BG_COLOR, dtype=torch.long
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
            # weighted cross-entropy
            loss = F.cross_entropy(logits_canvas, target_gpu, weight=self.ce_weights)
            return loss

        # Inference: recover in original grid size
        logits_crop = recover_from_canvas(
            logits_canvas[0], h_in, w_in, scale, top, left
        )
        return logits_crop


# ==========================================
# 5. Training & TTT
# ==========================================

def train_offline(model: NeuroSymbolic_VARC, tasks: List[Dict[str, Any]], epochs: int = 10):
    """
    Offline pretraining on all training tasks (uses task embeddings).
    """
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

        print(f"[Offline] Epoch {ep+1}/{epochs} | Loss: {total_loss / max(1, steps):.4f}")


def test_time_training(
    model: NeuroSymbolic_VARC,
    task: Dict[str, Any],
    steps: int = 50,
    ttt_views: int = 3,
    infer_views: int = 5,
) -> List[np.ndarray]:
    """
    TTT on a single task:

      1. Re-init ttt_token.
      2. Optimize ttt_token + decoder on train pairs, with multiple
         augmentations per pair per step (ttt_views).
      3. Multi-view inference on test pairs (infer_views) returning
         averaged logits -> argmax.
    """
    nn.init.normal_(model.ttt_token, std=0.02)

    params = [model.ttt_token] + list(model.decoder.parameters())
    opt = Adam(params, lr=1e-3)

    # TTT phase
    model.train()
    for _ in range(steps):
        for pair in task["train"]:
            loss_sum = 0.0
            for _ in range(ttt_views):
                loss_sum = loss_sum + model.forward_pair(
                    pair["input"],
                    task_idx=None,
                    augment=True,
                    output_grid=pair["output"],
                )
            loss = loss_sum / float(ttt_views)
            opt.zero_grad()
            loss.backward()
            opt.step()

    # Multi-view inference
    model.eval()
    preds: List[np.ndarray] = []
    with torch.no_grad():
        for test_pair in task["test"]:
            grid = test_pair["input"]
            acc_logits = None
            for _ in range(infer_views):
                logits = model.forward_pair(
                    grid, task_idx=None, augment=True, output_grid=None
                )  # [11, H, W]
                if acc_logits is None:
                    acc_logits = logits
                else:
                    acc_logits = acc_logits + logits
            acc_logits = acc_logits / float(infer_views)
            pred_grid = acc_logits.argmax(0).cpu().numpy()
            preds.append(pred_grid)

    return preds


# ==========================================
# 6. Visualization Helpers
# ==========================================

def make_arc_cmap():
    # 11 discrete colors (0-9 + BG 10)
    colors = [
        "#000000",  # 0 black
        "#0074D9",  # 1 blue
        "#FF4136",  # 2 red
        "#2ECC40",  # 3 green
        "#FFDC00",  # 4 yellow
        "#AAAAAA",  # 5 gray
        "#F012BE",  # 6 magenta
        "#FF851B",  # 7 orange
        "#7FDBFF",  # 8 light blue
        "#870C25",  # 9 dark red
        "#FFFFFF",  # 10 white background
    ]
    return ListedColormap(colors)


def save_task_visuals(
    task: Dict[str, Any],
    preds: List[np.ndarray],
    split_tag: str,
    out_dir: Path,
):
    """
    Save PNG + TXT for a single task.

    Layout: for each test pair, show (Input, GT, Pred) as 3 columns.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cmap = make_arc_cmap()

    base = f"{split_tag}_{task['id']}"
    png_path = out_dir / f"{base}.png"
    txt_path = out_dir / f"{base}.txt"

    num_tests = len(task["test"])
    fig, axes = plt.subplots(
        num_tests, 3, figsize=(9, 3 * num_tests), squeeze=False
    )

    with open(txt_path, "w") as f:
        f.write(f"Task ID: {task['id']}\n")
        f.write(f"Split: {split_tag}\n\n")

        for idx, (pair, pred) in enumerate(zip(task["test"], preds)):
            inp = pair["input"]
            gt = pair.get("output", None)

            # --- Text dump ---
            f.write(f"=== Test #{idx} ===\n")
            f.write("INPUT:\n")
            f.write(str(inp) + "\n")
            if gt is not None:
                f.write("GT:\n")
                f.write(str(gt) + "\n")
            f.write("PRED:\n")
            f.write(str(pred) + "\n\n")

            # --- PNG tiles ---
            ax_input = axes[idx, 0]
            ax_gt = axes[idx, 1]
            ax_pred = axes[idx, 2]

            ax_input.imshow(inp, interpolation="nearest", vmin=0, vmax=10, cmap=cmap)
            ax_input.set_title("INPUT")
            ax_input.axis("off")

            if gt is not None:
                ax_gt.imshow(gt, interpolation="nearest", vmin=0, vmax=10, cmap=cmap)
                ax_gt.set_title("GT")
            else:
                ax_gt.imshow(
                    np.zeros_like(inp), interpolation="nearest", vmin=0, vmax=10, cmap=cmap
                )
                ax_gt.set_title("GT (missing)")
            ax_gt.axis("off")

            ax_pred.imshow(pred, interpolation="nearest", vmin=0, vmax=10, cmap=cmap)
            ax_pred.set_title("PRED")
            ax_pred.axis("off")

    plt.tight_layout()
    fig.savefig(png_path, dpi=120)
    plt.close(fig)


# ==========================================
# 7. Evaluation with TTT (now saving MORE visuals)
# ==========================================

def evaluate_with_ttt(
    model: NeuroSymbolic_VARC,
    heldout_train: List[Dict[str, Any]],
    eval_tasks: List[Dict[str, Any]],
    ttt_steps: int,
    ttt_views: int,
    infer_views: int,
    num_vis_train: int,
    num_vis_eval: int,
    save_dir: str = "vis_examples",
):
    out_dir = Path(save_dir)
    out_dir.mkdir(exist_ok=True)

    # ---------- Held-out TRAIN ----------
    if heldout_train:
        print("\n=== TTT Evaluation on held-out TRAIN ===")
        num_tasks = len(heldout_train)

        total_tasks = 0
        solved_tasks = 0
        total_grids = 0
        solved_grids = 0
        correct_pixels = 0
        total_pixels = 0

        # store all unsolved with their metrics
        unsolved_records_train = []

        for idx, task in enumerate(heldout_train, 1):
            has_gt = all("output" in p for p in task["test"])
            if not has_gt:
                print(
                    f"[held-out TRAIN] Task {idx}/{num_tasks} ({task['id']}): skipping (no GT)"
                )
                continue

            total_tasks += 1

            preds = test_time_training(
                model,
                task,
                steps=ttt_steps,
                ttt_views=ttt_views,
                infer_views=infer_views,
            )

            task_correct = 0
            task_total = 0
            grids_solved_this = 0
            all_grids_solved = True

            for pred, pair in zip(preds, task["test"]):
                gt = pair["output"]
                if pred.shape == gt.shape and np.array_equal(pred, gt):
                    grids_solved_this += 1
                else:
                    all_grids_solved = False

                if pred.shape == gt.shape:
                    eq = (pred == gt)
                    task_correct += int(eq.sum())
                    task_total += eq.size

            solved_grids += grids_solved_this
            total_grids += len(task["test"])
            correct_pixels += task_correct
            total_pixels += task_total

            task_pix_acc = task_correct / max(1, task_total)

            status = "SOLVED" if all_grids_solved else "not solved"
            if all_grids_solved:
                solved_tasks += 1
            else:
                unsolved_records_train.append(
                    {
                        "task": task,
                        "preds": preds,
                        "pixel_acc": task_pix_acc,
                    }
                )

            print(
                f"[held-out TRAIN] Task {idx}/{num_tasks} ({task['id']}): {status} "
                f"(grids {grids_solved_this}/{len(task['test'])}, pixel_acc={task_pix_acc:.4f})"
            )

        task_success_rate = solved_tasks / max(1, total_tasks)
        grid_success_rate = solved_grids / max(1, total_grids)
        avg_pix_acc = correct_pixels / max(1, total_pixels)

        print("\n[held-out TRAIN] Detailed metrics:")
        print(f"  num_tasks:            {total_tasks}")
        print(f"  num_tasks_solved:     {solved_tasks}")
        print(f"  task_success_rate:    {task_success_rate:.4f}")
        print(f"  num_test_grids:       {total_grids}")
        print(f"  num_test_grids_solved:{solved_grids}")
        print(f"  grid_success_rate:    {grid_success_rate:.4f}")
        print(f"  avg_pixel_accuracy:   {avg_pix_acc:.4f}")

        # sort unsolved by pixel_acc descending
        if unsolved_records_train:
            unsolved_records_train.sort(key=lambda x: x["pixel_acc"], reverse=True)
            top_k = unsolved_records_train[: max(1, num_vis_train)]

            # First one: keep original naming (train_eval_<taskid>.png/txt)
            best = top_k[0]
            print(
                f"\n[held-out TRAIN] Saving BEST unsolved task "
                f"{best['task']['id']} with pixel_acc={best['pixel_acc']:.4f}"
            )
            save_task_visuals(
                best["task"],
                best["preds"],
                split_tag="train_eval",
                out_dir=out_dir,
            )

            # Others: add extra index in tag
            for rank, rec in enumerate(top_k[1:], start=2):
                tag = f"train_eval_extra{rank}"
                print(
                    f"[held-out TRAIN] Saving EXTRA unsolved task "
                    f"{rec['task']['id']} with pixel_acc={rec['pixel_acc']:.4f} "
                    f"as {tag}_<taskid>.png/txt"
                )
                save_task_visuals(
                    rec["task"],
                    rec["preds"],
                    split_tag=tag,
                    out_dir=out_dir,
                )

    # ---------- EVAL split ----------
    if eval_tasks:
        print("\n=== TTT Evaluation on EVAL ===")
        num_tasks = len(eval_tasks)

        total_tasks = 0
        solved_tasks = 0
        total_grids = 0
        solved_grids = 0
        correct_pixels = 0
        total_pixels = 0

        unsolved_records_eval = []

        for idx, task in enumerate(eval_tasks, 1):
            has_gt = all("output" in p for p in task["test"])
            if not has_gt:
                print(
                    f"[EVAL] Task {idx}/{num_tasks} ({task['id']}): skipping (no GT)"
                )
                continue

            total_tasks += 1

            preds = test_time_training(
                model,
                task,
                steps=ttt_steps,
                ttt_views=ttt_views,
                infer_views=infer_views,
            )

            task_correct = 0
            task_total = 0
            grids_solved_this = 0
            all_grids_solved = True

            for pred, pair in zip(preds, task["test"]):
                gt = pair["output"]
                if pred.shape == gt.shape and np.array_equal(pred, gt):
                    grids_solved_this += 1
                else:
                    all_grids_solved = False

                if pred.shape == gt.shape:
                    eq = (pred == gt)
                    task_correct += int(eq.sum())
                    task_total += eq.size

            solved_grids += grids_solved_this
            total_grids += len(task["test"])
            correct_pixels += task_correct
            total_pixels += task_total

            task_pix_acc = task_correct / max(1, task_total)

            status = "SOLVED" if all_grids_solved else "not solved"
            if all_grids_solved:
                solved_tasks += 1
            else:
                unsolved_records_eval.append(
                    {
                        "task": task,
                        "preds": preds,
                        "pixel_acc": task_pix_acc,
                    }
                )

            print(
                f"[EVAL] Task {idx}/{num_tasks} ({task['id']}): {status} "
                f"(grids {grids_solved_this}/{len(task['test'])}, pixel_acc={task_pix_acc:.4f})"
            )

        task_success_rate = solved_tasks / max(1, total_tasks)
        grid_success_rate = solved_grids / max(1, total_grids)
        avg_pix_acc = correct_pixels / max(1, total_pixels)

        print("\n[EVAL] Detailed metrics:")
        print(f"  num_tasks:            {total_tasks}")
        print(f"  num_tasks_solved:     {solved_tasks}")
        print(f"  task_success_rate:    {task_success_rate:.4f}")
        print(f"  num_test_grids:       {total_grids}")
        print(f"  num_test_grids_solved:{solved_grids}")
        print(f"  grid_success_rate:    {grid_success_rate:.4f}")
        print(f"  avg_pixel_accuracy:   {avg_pix_acc:.4f}")

        if unsolved_records_eval:
            unsolved_records_eval.sort(key=lambda x: x["pixel_acc"], reverse=True)
            top_k = unsolved_records_eval[: max(1, num_vis_eval)]

            best = top_k[0]
            print(
                f"\n[EVAL] Saving BEST unsolved task "
                f"{best['task']['id']} with pixel_acc={best['pixel_acc']:.4f}"
            )
            save_task_visuals(
                best["task"],
                best["preds"],
                split_tag="eval_split",
                out_dir=out_dir,
            )

            for rank, rec in enumerate(top_k[1:], start=2):
                tag = f"eval_split_extra{rank}"
                print(
                    f"[EVAL] Saving EXTRA unsolved task "
                    f"{rec['task']['id']} with pixel_acc={rec['pixel_acc']:.4f} "
                    f"as {tag}_<taskid>.png/txt"
                )
                save_task_visuals(
                    rec["task"],
                    rec["preds"],
                    split_tag=tag,
                    out_dir=out_dir,
                )


# ==========================================
# 8. Data Loading
# ==========================================

def load_file_pair(root: str, challenge_file: str, solution_file: Optional[str] = None):
    """
    Explicitly load a (challenges, solutions) pair from the ARC-AGI 2 JSON files.

    Returns a list of tasks with:
      {
        "id": <task_id>,
        "train": [{"input": np.array, "output": np.array}, ...],
        "test": [{"input": np.array, "output": np.array_if_available}, ...]
      }
    """
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
        # Build test pairs
        test_pairs = [{"input": np.array(x["input"])} for x in content["test"]]

        # Attach solutions if available
        if tid in solutions:
            sols = solutions[tid]
            for i, sol_grid in enumerate(sols):
                if i < len(test_pairs):
                    test_pairs[i]["output"] = np.array(sol_grid)

        tasks.append(
            {
                "id": tid,
                "train": [
                    {
                        "input": np.array(x["input"]),
                        "output": np.array(x["output"]),
                    }
                    for x in content["train"]
                ],
                "test": test_pairs,
            }
        )
    return tasks


# ==========================================
# 9. CLI
# ==========================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_root", type=str, required=True)
    parser.add_argument("--epochs_offline", type=int, default=10)
    parser.add_argument("--ttt_steps", type=int, default=50)
    parser.add_argument("--ttt_views", type=int, default=3)
    parser.add_argument("--infer_views", type=int, default=5)
    parser.add_argument("--num_vis_train", type=int, default=3,
                        help="How many held-out train tasks to visualize (top unsolved).")
    parser.add_argument("--num_vis_eval", type=int, default=3,
                        help="How many eval tasks to visualize (top unsolved).")
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

    device = torch.device(args.device)
    print(f"Using device: {device}")

    # 1. Load training set
    train_tasks = load_file_pair(
        args.data_root,
        "arc-agi_training_challenges.json",
        "arc-agi_training_solutions.json",
    )
    print(f"\nLoaded {len(train_tasks)} train tasks.")

    # 2. Split into offline + held-out for TTT
    if len(train_tasks) > 50:
        offline_set = train_tasks[:-50]
        heldout_train = train_tasks[-50:]
    else:
        offline_set = train_tasks
        heldout_train = []

    print(f"Using {len(offline_set)} tasks for offline training.")
    print(f"Using {len(heldout_train)} held-out train tasks for TTT evaluation.")

    # 3. Load eval set
    eval_tasks = load_file_pair(
        args.data_root,
        "arc-agi_evaluation_challenges.json",
        "arc-agi_evaluation_solutions.json",
    )
    print(f"\nLoaded {len(eval_tasks)} eval tasks.")

    # Init model
    model = NeuroSymbolic_VARC(device, num_train_tasks=len(train_tasks)).to(device)

    # Offline training
    print("\n=== Offline Training ===")
    train_offline(model, offline_set, epochs=args.epochs_offline)

    # TTT evaluation on held-out train + eval
    evaluate_with_ttt(
        model,
        heldout_train,
        eval_tasks,
        ttt_steps=args.ttt_steps,
        ttt_views=args.ttt_views,
        infer_views=args.infer_views,
        num_vis_train=args.num_vis_train,
        num_vis_eval=args.num_vis_eval,
        save_dir="vis_examples",
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
