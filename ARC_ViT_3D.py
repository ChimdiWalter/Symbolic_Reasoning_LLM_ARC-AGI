import math
import json
import random
import argparse
import copy
import os
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam

# --- VISUALIZATION ---
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
import matplotlib.colors as mcolors

# ==========================================
# 0. Global Settings
# ==========================================
CANVAS_SIZE = 64
BG_COLOR = 10         # ARC background
NUM_COLORS = 11       # 0..10, with 10 as BG

# ViT / Evolver hyperparams
DEFAULT_HIDDEN_DIM = 192
DEFAULT_PATCH_SIZE = 2
DEFAULT_VIT_DEPTH = 6
DEFAULT_VIT_HEADS = 6
DEFAULT_VIT_MLP_RATIO = 4


# ==========================================
# 1. Canvas Engine (Dynamic Sizing)
# ==========================================

def prepare_canvas(grid: np.ndarray,
                   augment: bool = False,
                   max_scale_limit: Optional[int] = None):
    """
    Take an (H, W) grid, scale it to fit into a CANVAS_SIZE x CANVAS_SIZE
    with optional random scaling and placement.
    """
    H, W = grid.shape
    max_scale = min(CANVAS_SIZE // max(1, H),
                    CANVAS_SIZE // max(1, W))
    if max_scale_limit is not None:
        max_scale = min(max_scale, max_scale_limit)
    max_scale = max(1, max_scale)

    # Random scale for training; max scale (zoom in) for eval
    if augment and max_scale > 1:
        scale = random.randint(1, max_scale)
    else:
        scale = max_scale

    scaled = grid.repeat(scale, 0).repeat(scale, 1)
    SH, SW = scaled.shape

    max_y, max_x = max(0, CANVAS_SIZE - SH), max(0, CANVAS_SIZE - SW)
    if augment:
        top = random.randint(0, max_y) if max_y > 0 else 0
        left = random.randint(0, max_x) if max_x > 0 else 0
    else:
        top = max_y // 2
        left = max_x // 2

    canvas = np.full((CANVAS_SIZE, CANVAS_SIZE), BG_COLOR, dtype=np.int64)
    r_end, c_end = min(CANVAS_SIZE, top + SH), min(CANVAS_SIZE, left + SW)
    canvas[top:r_end, left:c_end] = scaled[:r_end - top, :c_end - left]

    return torch.from_numpy(canvas).long(), scale, top, left


def recover_from_canvas(logits: torch.Tensor,
                        H: int,
                        W: int,
                        scale: int,
                        top: int,
                        left: int) -> torch.Tensor:
    """
    Recover an (H, W) prediction from full-canvas logits.
    """
    preds = logits.argmax(0)  # [64, 64]

    # 1. Try the expected region
    r_end, c_end = min(CANVAS_SIZE, top + H * scale), min(CANVAS_SIZE, left + W * scale)
    expected = preds[top:r_end, left:c_end]

    crop = None
    if expected.numel() > 0 and (expected == BG_COLOR).float().mean() < 0.95:
        crop = expected
    else:
        # 2. Dynamic search: bounding box of non-BG predictions
        coords = torch.nonzero(preds != BG_COLOR)
        if coords.size(0) == 0:
            return torch.full((H, W),
                              0,
                              device=logits.device,
                              dtype=torch.long)
        min_y, min_x = coords.min(0).values
        max_y, max_x = coords.max(0).values
        crop = preds[min_y:max_y + 1, min_x:max_x + 1]

    if scale > 1:
        crop = crop[::scale, ::scale]

    # Optional: if crop doesn't match H,W, center-crop or pad
    ch, cw = crop.shape
    if ch != H or cw != W:
        # simple center-crop/pad to match target size
        out = torch.full((H, W),
                         BG_COLOR,
                         device=crop.device,
                         dtype=crop.dtype)
        # compute ranges
        y_start = max(0, (H - ch) // 2)
        x_start = max(0, (W - cw) // 2)
        y_end = min(H, y_start + ch)
        x_end = min(W, x_start + cw)

        cy_start = max(0, (ch - H) // 2)
        cx_start = max(0, (cw - W) // 2)
        cy_end = cy_start + (y_end - y_start)
        cx_end = cx_start + (x_end - x_start)

        out[y_start:y_end, x_start:x_end] = crop[cy_start:cy_end, cx_start:cx_end]
        crop = out

    # clean BG: 10 -> 0 for submission
    return torch.where(crop == BG_COLOR,
                       torch.tensor(0, device=crop.device),
                       crop)


# ==========================================
# 2. Strong ARC-style Augmentations
# ==========================================

def augment_pair(inp: np.ndarray,
                 out: np.ndarray,
                 enable: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply stronger augmentations that are often equivariant or helpful
    for ARC-like reasoning:
      - random color permutation (excluding BG)
      - random 0/90/180/270 rotation
      - random horizontal / vertical flips
      - random translation (pad with BG, crop off edges)
    """
    if not enable:
        return inp, out

    grid_in = inp.copy()
    grid_out = out.copy()

    # --- 1) Color permutation (same permutation for input & output) ---
    if random.random() < 0.3:
        perm = np.arange(NUM_COLORS)
        fg_colors = [c for c in range(NUM_COLORS) if c != BG_COLOR]
        shuffled = fg_colors.copy()
        random.shuffle(shuffled)
        for orig, new in zip(fg_colors, shuffled):
            perm[orig] = new
        grid_in = perm[grid_in]
        grid_out = perm[grid_out]

    # --- 2) Rotation by 0, 90, 180, 270 ---
    k = random.randint(0, 3)
    if k > 0:
        grid_in = np.rot90(grid_in, k)
        grid_out = np.rot90(grid_out, k)

    # --- 3) Horizontal / vertical flips ---
    if random.random() < 0.5:
        grid_in = np.fliplr(grid_in)
        grid_out = np.fliplr(grid_out)
    if random.random() < 0.5:
        grid_in = np.flipud(grid_in)
        grid_out = np.flipud(grid_out)

    # --- 4) Robust random translation (simple loops, no shape issues) ---
    if random.random() < 0.5:
        H, W = grid_in.shape
        max_shift_y = max(1, H // 4)
        max_shift_x = max(1, W // 4)
        dy = random.randint(-max_shift_y, max_shift_y)
        dx = random.randint(-max_shift_x, max_shift_x)

        def translate(g: np.ndarray) -> np.ndarray:
            H, W = g.shape
            new_g = np.full((H, W), BG_COLOR, dtype=g.dtype)
            for y in range(H):
                for x in range(W):
                    ys = y - dy
                    xs = x - dx
                    if 0 <= ys < H and 0 <= xs < W:
                        new_g[y, x] = g[ys, xs]
            return new_g

        grid_in = translate(grid_in)
        grid_out = translate(grid_out)

    return grid_in, grid_out



# ==========================================
# 3. 3D Visualization
# ==========================================

def save_3d_evolution(task_id,
                      idx,
                      history_logits,
                      scale,
                      top,
                      left,
                      status,
                      save_dir: str = "results_3d"):
    os.makedirs(save_dir, exist_ok=True)

    steps = len(history_logits)
    if steps == 0:
        return

    # history_logits: list of [1, 11, 64, 64]
    all_preds = torch.stack([h.argmax(1)[0] for h in history_logits])  # [T, 64, 64]
    non_bg = torch.nonzero(all_preds != BG_COLOR)

    if non_bg.size(0) == 0:
        return

    min_y, min_x = non_bg[:, 1].min().item(), non_bg[:, 2].min().item()
    max_y, max_x = non_bg[:, 1].max().item(), non_bg[:, 2].max().item()

    # Add a bit of padding
    min_y = max(0, min_y - 2)
    min_x = max(0, min_x - 2)
    max_y = min(CANVAS_SIZE, max_y + 2)
    max_x = min(CANVAS_SIZE, max_x + 2)

    crop_h = all_preds[:, min_y:max_y, min_x:max_x].cpu().numpy()
    T, H, W = crop_h.shape

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    voxels = np.zeros((T, H, W), dtype=bool)
    colors = np.zeros((T, H, W, 4), dtype=float)

    # Standard ARC color map
    cmap = [
        '#000000', '#0074D9', '#FF4136', '#2ECC40', '#FFDC00',
        '#AAAAAA', '#F012BE', '#FF851B', '#7FDBFF', '#870C25', '#222222'
    ]
    rgba_map = [mcolors.to_rgba(c) for c in cmap]

    for t in range(T):
        for r in range(H):
            for c in range(W):
                val = crop_h[t, r, c]
                if val == BG_COLOR:
                    continue
                voxels[t, H - 1 - r, c] = True
                col = list(rgba_map[val])
                # fade over time
                col[3] = 0.2 + 0.8 * (t / max(1, T - 1))
                colors[t, H - 1 - r, c] = col

    ax.voxels(voxels, facecolors=colors, edgecolors='grey', linewidth=0.2)
    ax.set_xlabel('Time')
    ax.set_ylabel('Y')
    ax.set_zlabel('X')
    ax.set_title(f"Task {task_id}: Step-by-Step Evolution ({status})")
    plt.savefig(f"{save_dir}/{task_id}_{idx}_{status}.png")
    plt.close(fig)


# ==========================================
# 4. ViT + UNet-like Evolver Model
# ==========================================

class EvolverBlock(nn.Module):
    """
    A small UNet-ish block that takes [B, H, 64, 64] state and [B, H, 64, 64] rule_map,
    and returns a delta of shape [B, H, 64, 64].
    """
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.in_conv = nn.Conv2d(hidden_dim * 2, hidden_dim, 3, padding=1)
        self.in_gn = nn.GroupNorm(8, hidden_dim)

        self.down = nn.Conv2d(hidden_dim, hidden_dim, 3, stride=2, padding=1)
        self.down_gn = nn.GroupNorm(8, hidden_dim)

        self.mid1 = nn.Conv2d(hidden_dim, hidden_dim, 3, padding=2, dilation=2)
        self.mid1_gn = nn.GroupNorm(8, hidden_dim)

        self.mid2 = nn.Conv2d(hidden_dim, hidden_dim, 3, padding=4, dilation=4)
        self.mid2_gn = nn.GroupNorm(8, hidden_dim)

        self.up = nn.ConvTranspose2d(hidden_dim, hidden_dim, 2, stride=2)
        self.up_gn = nn.GroupNorm(8, hidden_dim)

        self.out_conv = nn.Conv2d(hidden_dim * 2, hidden_dim, 3, padding=1)
        self.out_gn = nn.GroupNorm(8, hidden_dim)

    def forward(self, state: torch.Tensor, rule: torch.Tensor) -> torch.Tensor:
        # state: [B, H, 64, 64], rule: [B, H, 64, 64]
        x = torch.cat([state, rule], dim=1)   # [B, 2H, 64, 64]
        x = F.gelu(self.in_gn(self.in_conv(x)))  # [B, H, 64, 64]
        skip = x

        x = F.gelu(self.down_gn(self.down(x)))   # [B, H, 32, 32]
        x = F.gelu(self.mid1_gn(self.mid1(x)))   # [B, H, 32, 32]
        x = F.gelu(self.mid2_gn(self.mid2(x)))   # [B, H, 32, 32]
        x = F.gelu(self.up_gn(self.up(x)))       # [B, H, 64, 64]

        x = torch.cat([x, skip], dim=1)          # [B, 2H, 64, 64]
        x = F.gelu(self.out_gn(self.out_conv(x)))  # [B, H, 64, 64]
        return x


class ViT_Evolution_Model(nn.Module):
    def __init__(self,
                 device: torch.device,
                 num_tasks: int,
                 hidden_dim: int = DEFAULT_HIDDEN_DIM,
                 patch_size: int = DEFAULT_PATCH_SIZE,
                 vit_depth: int = DEFAULT_VIT_DEPTH,
                 vit_heads: int = DEFAULT_VIT_HEADS,
                 vit_mlp_ratio: int = DEFAULT_VIT_MLP_RATIO,
                 num_steps: int = 6):
        super().__init__()
        self.device = device
        self.hidden_dim = hidden_dim
        self.patch_size = patch_size
        self.num_steps = num_steps

        assert CANVAS_SIZE % patch_size == 0
        self.grid_size = CANVAS_SIZE // patch_size
        self.num_patches = self.grid_size * self.grid_size

        # A. Patch embedding (ViT)
        in_dim = patch_size * patch_size * NUM_COLORS
        self.patch_embed = nn.Linear(in_dim, hidden_dim)
        self.pos_embed = nn.Parameter(
            torch.randn(1, self.num_patches, hidden_dim) * 0.02
        )

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=vit_heads,
            dim_feedforward=hidden_dim * vit_mlp_ratio,
            activation='gelu',
            batch_first=True
        )
        self.vit_blocks = nn.TransformerEncoder(
            encoder_layer,
            num_layers=vit_depth
        )

        # B. Task memory
        self.task_emb = nn.Embedding(num_tasks, hidden_dim)
        self.ttt_token = nn.Parameter(torch.randn(1, hidden_dim))

        # C. Evolver (UNet-like)
        self.evolver = EvolverBlock(hidden_dim)

        # D. Decoder to pixels
        self.to_pixels = nn.Conv2d(hidden_dim, NUM_COLORS, 1)

    def forward(self,
                canvas_tensor: torch.Tensor,
                task_idx: Optional[torch.Tensor] = None,
                steps: Optional[int] = None):
        """
        canvas_tensor: [B, 64, 64]
        task_idx: [B] or None
        Returns:
          final_logits: [B, 11, 64, 64]
          history: list of [B, 11, 64, 64] over steps
        """
        if steps is None:
            steps = self.num_steps

        B, H, W = canvas_tensor.shape
        P = self.patch_size
        G = self.grid_size

        # 1. One-hot + patchify
        oh = F.one_hot(canvas_tensor.long(), NUM_COLORS).float()  # [B, H, W, C]
        # reshape to [B, G, P, G, P, C] -> [B, G*G, P*P*C]
        patches = oh.view(B, G, P, G, P, NUM_COLORS).permute(
            0, 1, 3, 2, 4, 5
        ).reshape(B, self.num_patches, P * P * NUM_COLORS)

        x = self.patch_embed(patches) + self.pos_embed  # [B, num_patches, hidden_dim]
        x = self.vit_blocks(x)                          # [B, num_patches, hidden_dim]

        # Reshape to feature map [B, Hdim, G, G] then upsample to 64x64
        feat_small = x.permute(0, 2, 1).view(B, self.hidden_dim, G, G)
        state = F.interpolate(feat_small,
                              size=(CANVAS_SIZE, CANVAS_SIZE),
                              mode='bilinear',
                              align_corners=False)  # [B, Hdim, 64, 64]

        # Task rule / TTT token
        if task_idx is not None:
            rule_vec = self.task_emb(task_idx)          # [B, Hdim]
        else:
            # expand single token across batch
            rule_vec = self.ttt_token.expand(B, -1)     # [B, Hdim]

        rule_map = rule_vec.view(B, self.hidden_dim, 1, 1).expand(
            -1, -1, CANVAS_SIZE, CANVAS_SIZE
        )

        history = []
        for _ in range(steps):
            delta = self.evolver(state, rule_map)
            state = state + delta   # residual update

            current_logits = self.to_pixels(state)  # [B, 11, 64, 64]
            history.append(current_logits)

        return history[-1], history


# ==========================================
# 5. Data Loading
# ==========================================

def load_file_pair(root, c_file, s_file):
    path = Path(root)
    with open(path / c_file) as f:
        challs = json.load(f)
    sols = {}
    if (path / s_file).exists():
        with open(path / s_file) as f:
            sols = json.load(f)

    tasks = []
    for tid, c in challs.items():
        test_pairs = [{"input": np.array(x['input'])} for x in c['test']]
        if tid in sols:
            for i, s in enumerate(sols[tid]):
                if i < len(test_pairs):
                    test_pairs[i]['output'] = np.array(s)
        tasks.append({"id": tid, "train": c['train'], "test": test_pairs})
    return tasks


# ==========================================
# 6. Loss (ignore BG)
# ==========================================

def masked_ce_loss(logits: torch.Tensor,
                   tgt: torch.Tensor,
                   ignore_bg: bool = True) -> torch.Tensor:
    """
    logits: [B, C, H, W], tgt: [B, H, W]
    """
    B, C, H, W = logits.shape
    logits_flat = logits.permute(0, 2, 3, 1).reshape(-1, C)
    tgt_flat = tgt.view(-1)

    if ignore_bg:
        mask = (tgt_flat != BG_COLOR)
        if mask.any():
            return F.cross_entropy(logits_flat[mask], tgt_flat[mask])
    # fallback or no foreground
    return F.cross_entropy(logits_flat, tgt_flat)


# ==========================================
# 7. Offline Training
# ==========================================

def train_offline(model: ViT_Evolution_Model,
                  tasks,
                  epochs: int = 10):
    opt = Adam(model.parameters(), lr=3e-4)
    model.train()

    for ep in range(epochs):
        random.shuffle(tasks)
        loss_sum = 0.0
        count = 0

        for t_idx, task in enumerate(tasks):
            for pair in task['train']:
                inp = np.array(pair['input'])
                out = np.array(pair['output'])

                # Strong ARC-style augmentations in grid space
                inp_aug, out_aug = augment_pair(inp, out, enable=True)

                # Robust scaling limit derived from output size (so it fits)
                h_limit = min(
                    CANVAS_SIZE // max(1, out_aug.shape[0]),
                    CANVAS_SIZE // max(1, out_aug.shape[1])
                )
                cv, scale, top, left = prepare_canvas(inp_aug,
                                                      augment=True,
                                                      max_scale_limit=h_limit)

                # Target canvas
                tgt = torch.full((CANVAS_SIZE, CANVAS_SIZE),
                                 BG_COLOR,
                                 dtype=torch.long)
                out_sc = out_aug.repeat(scale, 0).repeat(scale, 1)
                r_end = min(CANVAS_SIZE, top + out_sc.shape[0])
                c_end = min(CANVAS_SIZE, left + out_sc.shape[1])
                if r_end > top and c_end > left:
                    tgt[top:r_end, left:c_end] = torch.from_numpy(
                        out_sc[:r_end - top, :c_end - left]
                    )

                opt.zero_grad()
                logits, _ = model(
                    cv.unsqueeze(0).to(model.device),
                    task_idx=torch.tensor([t_idx], device=model.device)
                )
                tgt_batch = tgt.unsqueeze(0).to(model.device)
                loss = masked_ce_loss(logits, tgt_batch, ignore_bg=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()

                loss_sum += loss.item()
                count += 1

        avg_loss = loss_sum / max(1, count)
        print(f"[Offline] Epoch {ep + 1}/{epochs} | loss={avg_loss:.4f}")


# ==========================================
# 8. Test-Time Training (TTT) per Task
# ==========================================

def test_time_training(model: ViT_Evolution_Model,
                       task,
                       steps: int = 60):
    """
    Adapt model.ttt_token + evolver to this single task using its train pairs.
    Then generate predictions for its test pairs (no augmentation on test).
    """
    # Re-init TTT token
    with torch.no_grad():
        nn.init.normal_(model.ttt_token, std=0.02)

    # Freeze everything then unfreeze ttt_token + evolver
    for p in model.parameters():
        p.requires_grad_(False)
    model.ttt_token.requires_grad_(True)
    for p in model.evolver.parameters():
        p.requires_grad_(True)

    trainable_params = [p for p in model.parameters() if p.requires_grad]

    opt = Adam(
        [
            {'params': [model.ttt_token], 'lr': 5e-3},
            {'params': model.evolver.parameters(), 'lr': 1e-3},
        ]
    )

    model.train()
    for _ in range(steps):
        for pair in task['train']:
            inp = np.array(pair['input'])
            out = np.array(pair['output'])

            inp_aug, out_aug = augment_pair(inp, out, enable=True)

            h_limit = min(
                CANVAS_SIZE // max(1, out_aug.shape[0]),
                CANVAS_SIZE // max(1, out_aug.shape[1])
            )
            cv, scale, top, left = prepare_canvas(inp_aug,
                                                  augment=True,
                                                  max_scale_limit=h_limit)

            tgt = torch.full((CANVAS_SIZE, CANVAS_SIZE),
                             BG_COLOR,
                             dtype=torch.long)
            out_sc = out_aug.repeat(scale, 0).repeat(scale, 1)
            r_end = min(CANVAS_SIZE, top + out_sc.shape[0])
            c_end = min(CANVAS_SIZE, left + out_sc.shape[1])
            if r_end > top and c_end > left:
                tgt[top:r_end, left:c_end] = torch.from_numpy(
                    out_sc[:r_end - top, :c_end - left]
                )

            opt.zero_grad()
            logits, _ = model(
                cv.unsqueeze(0).to(model.device),
                task_idx=None   # use TTT token
            )
            tgt_batch = tgt.unsqueeze(0).to(model.device)
            loss = masked_ce_loss(logits, tgt_batch, ignore_bg=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable_params, 1.0)
            opt.step()

    # Inference
    model.eval()
    preds = []
    with torch.no_grad():
        for idx, pair in enumerate(task['test']):
            inp = np.array(pair['input'])
            cv, scale, top, left = prepare_canvas(inp, augment=False)

            logits, history = model(
                cv.unsqueeze(0).to(model.device),
                task_idx=None
            )

            pred_grid = recover_from_canvas(
                logits[0],
                inp.shape[0],
                inp.shape[1],
                scale,
                top,
                left
            )
            preds.append((pred_grid.cpu().numpy(), history, scale, top, left))
    return preds


# ==========================================
# 9. Main
# ==========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_root", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Loading Data...")
    train_set = load_file_pair(
        args.data_root,
        "arc-agi_training_challenges.json",
        "arc-agi_training_solutions.json"
    )
    eval_set = load_file_pair(
        args.data_root,
        "arc-agi_evaluation_challenges.json",
        "arc-agi_evaluation_solutions.json"
    )

    model = ViT_Evolution_Model(
        device=device,
        num_tasks=len(train_set),
        hidden_dim=DEFAULT_HIDDEN_DIM,
        patch_size=DEFAULT_PATCH_SIZE,
        vit_depth=DEFAULT_VIT_DEPTH,
        vit_heads=DEFAULT_VIT_HEADS,
        vit_mlp_ratio=DEFAULT_VIT_MLP_RATIO,
        num_steps=6
    ).to(device)

    print("1. Offline Training...")
    train_offline(model, train_set, epochs=args.epochs)

    print("2. TTT Eval & 3D Viz...")
    solved_tasks = 0
    total_tasks = 0

    for i, task in enumerate(eval_set):
        # Require at least one GT output in test to score
        if "output" not in task['test'][0]:
            continue
        total_tasks += 1

        results = test_time_training(model, task, steps=60)

        task_correct = True
        print(f"\nTask {task['id']} [{i + 1}/{len(eval_set)}]:")

        for idx, (pred, history, s, t, l) in enumerate(results):
            gt = np.array(task['test'][idx]['output'])
            grid_solved = (pred.shape == gt.shape) and np.array_equal(pred, gt)
            if not grid_solved:
                task_correct = False

            print(f"  Test grid {idx}: {'SOLVED' if grid_solved else 'failed'} "
                  f"(pred_shape={pred.shape}, gt_shape={gt.shape})")

            status = "SOLVED" if grid_solved else "FAILED"
            if i < 10:  # visualize first 10 tasks
                try:
                    save_3d_evolution(task['id'], idx, history, s, t, l, status)
                except Exception as e:
                    print(f"    Viz error: {e}")

        if task_correct:
            solved_tasks += 1
            print(f"Task {task['id']}: SOLVED")
        else:
            print(f"Task {task['id']}: FAILED")

    if total_tasks > 0:
        score = solved_tasks / total_tasks * 100.0
        print(f"\nFinal Task Score: {solved_tasks}/{total_tasks} ({score:.2f}%)")
    else:
        print("\nNo evaluable tasks with ground truth outputs in eval_set.")
