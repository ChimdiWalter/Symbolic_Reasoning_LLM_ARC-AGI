import math
import json
import random
import argparse
import copy
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam

# --- VISUALIZATION SETUP ---
import matplotlib
# Force non-interactive backend (Saves to file only, no popup windows)
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# ==========================================
# 0. Visualization Utils
# ==========================================

ARC_COLORS = [
    '#000000', # 0: Black
    '#0074D9', # 1: Blue
    '#FF4136', # 2: Red
    '#2ECC40', # 3: Green
    '#FFDC00', # 4: Yellow
    '#AAAAAA', # 5: Grey
    '#F012BE', # 6: Pink
    '#FF851B', # 7: Orange
    '#7FDBFF', # 8: Cyan
    '#870C25', # 9: Maroon
    '#222222', # 10: Canvas BG
]
CMAP = mcolors.ListedColormap(ARC_COLORS)
NORM = mcolors.Normalize(vmin=0, vmax=10)

def visualize_prediction(task_id, index, inp, tgt, pred, status, save_dir="results"):
    os.makedirs(save_dir, exist_ok=True)
    
    fig, axs = plt.subplots(1, 3, figsize=(12, 4))
    
    # 1. Input
    axs[0].imshow(inp, cmap=CMAP, norm=NORM)
    axs[0].set_title(f"Input {inp.shape}")
    axs[0].axis('off')
    
    # 2. Target
    axs[1].imshow(tgt, cmap=CMAP, norm=NORM)
    axs[1].set_title(f"Target {tgt.shape}")
    axs[1].axis('off')
    
    # 3. Prediction
    axs[2].imshow(pred, cmap=CMAP, norm=NORM)
    axs[2].set_title(f"Pred {pred.shape} ({status})")
    axs[2].axis('off')
    
    plt.tight_layout()
    filename = f"{save_dir}/{status}_{task_id}_{index}.png"
    plt.savefig(filename)
    plt.close(fig)

# ==========================================
# 1. VARC Canvas Engine
# ==========================================

CANVAS_SIZE = 64
BG_COLOR = 10  
NUM_COLORS = 11

def prepare_canvas(grid: np.ndarray, augment: bool = False, max_scale_limit: Optional[int] = None) -> Tuple[torch.Tensor, int, int, int]:
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

def recover_from_canvas(canvas_logits: torch.Tensor, original_H: int, original_W: int, 
                        scale: int, top: int, left: int) -> torch.Tensor:
    """
    Robust Recovery with BG Cleaning.
    """
    preds = canvas_logits.argmax(0) # [64, 64]
    
    # --- CRITICAL FIX: Map Canvas BG (10) to Grid BG (0) ---
    # But we do this AFTER finding the bounding box, so we can distinguish
    # "Empty Canvas" from "Black Pixel".
    
    # 1. Check Expected Location first
    scaled_H = original_H * scale
    scaled_W = original_W * scale
    r_end = min(CANVAS_SIZE, top + scaled_H)
    c_end = min(CANVAS_SIZE, left + scaled_W)
    
    expected_crop = preds[top:r_end, left:c_end]
    
    # If Expected Crop has content (>5% non-BG), assume it's correct
    # (Most ARC tasks preserve grid size/location)
    num_pixels = expected_crop.numel()
    num_bg = (expected_crop == BG_COLOR).sum().item()
    
    final_crop = None
    
    if num_pixels > 0 and (num_bg / num_pixels) < 0.95:
        final_crop = expected_crop
    else:
        # 2. Dynamic Search (Fallback)
        non_bg_mask = (preds != BG_COLOR)
        coords = torch.nonzero(non_bg_mask)
        
        if coords.size(0) == 0:
             final_crop = torch.full((original_H * scale, original_W * scale), BG_COLOR, 
                              device=canvas_logits.device, dtype=torch.long)
        else:
            min_y, min_x = coords.min(dim=0).values
            max_y, max_x = coords.max(dim=0).values
            final_crop = preds[min_y : max_y+1, min_x : max_x+1]

    # 3. Downsample
    if scale > 1:
        final_crop = final_crop[::scale, ::scale]
        
    # 4. FINAL CLEANUP: Convert 10 -> 0
    # This is necessary because GT grids use 0 for black/background.
    final_crop = torch.where(final_crop == BG_COLOR, torch.tensor(0, device=final_crop.device), final_crop)
    
    return final_crop

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
    H, W = grid.shape
    visited = np.zeros((H, W), dtype=bool)
    comps = []
    dirs = [(1,0), (-1,0), (0,1), (0,-1)]
    
    for i in range(H):
        for j in range(W):
            if not visited[i,j]:
                c = grid[i,j]
                q = [(i,j)]; visited[i,j] = True; px = [(i,j)]
                while q:
                    ci, cj = q.pop()
                    for di, dj in dirs:
                        ni, nj = ci+di, cj+dj
                        if 0<=ni<H and 0<=nj<W and not visited[ni,nj] and grid[ni,nj]==c:
                            visited[ni,nj]=True
                            q.append((ni,nj))
                            px.append((ni,nj))
                comps.append({"c": c, "px": px})

    N = len(comps)
    if N == 0:
        return GraphData(torch.zeros(0, num_colors+2), torch.zeros(0,0), [], 0)

    feats = []
    for comp in comps:
        c_vec = np.zeros(num_colors, dtype=np.float32)
        c_vec[comp['c']] = 1.0
        sz = len(comp['px']) / (H*W + 1e-5)
        ys = [p[0] for p in comp['px']]; xs = [p[1] for p in comp['px']]
        bbox_area = (max(ys)-min(ys)+1)*(max(xs)-min(xs)+1)
        compact = sz / (bbox_area/(H*W) + 1e-5)
        feats.append(np.concatenate([c_vec, [sz, compact]]))
        
    node_feats = torch.tensor(np.stack(feats), dtype=torch.float32)
    adj = torch.eye(N) 
    return GraphData(node_feats, adj, [c['px'] for c in comps], N)

# ==========================================
# 3. Neural Modules
# ==========================================

class VisionTransformerEncoder(nn.Module):
    def __init__(self, canvas_size=64, patch_size=2, hidden_dim=128, layers=4):
        super().__init__()
        self.patch_size = patch_size
        self.H_patches = canvas_size // patch_size
        self.W_patches = canvas_size // patch_size
        num_patches = self.H_patches * self.W_patches
        
        pixels_per_patch = patch_size * patch_size
        self.patch_embed = nn.Linear(pixels_per_patch * 11, hidden_dim)
        self.pos_embed = nn.Parameter(torch.randn(1, num_patches, hidden_dim) * 0.02)
        
        enc_layer = nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=4, dim_feedforward=256, 
                                               activation='gelu', batch_first=True)
        self.blocks = nn.TransformerEncoder(enc_layer, num_layers=layers)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, canvas_onehot):
        B, H, W, C = canvas_onehot.shape
        patches = canvas_onehot.view(B, self.H_patches, self.patch_size, self.W_patches, self.patch_size, C)
        patches = patches.permute(0, 1, 3, 2, 4, 5).contiguous()
        patches_flat = patches.view(B, self.H_patches * self.W_patches, -1)
        x = self.patch_embed(patches_flat) + self.pos_embed
        x = self.blocks(x)
        x = self.norm(x)
        x = x.permute(0, 2, 1).view(B, -1, self.H_patches, self.W_patches)
        return x

class GraphEncoder(nn.Module):
    def __init__(self, in_dim, hidden_dim):
        super().__init__()
        self.mlp1 = nn.Linear(in_dim, hidden_dim)
        self.mlp2 = nn.Linear(hidden_dim, hidden_dim)
        
    def forward(self, node_feats):
        if node_feats.size(0) == 0: return node_feats
        x = F.relu(self.mlp1(node_feats))
        x = F.relu(self.mlp2(x))
        return x

class FusionDecoder(nn.Module):
    def __init__(self, vis_dim, geo_dim, task_dim, out_dim=11):
        super().__init__()
        total_in = vis_dim + geo_dim + task_dim + 2 
        self.conv1 = nn.Sequential(
            nn.Conv2d(total_in, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
            nn.Conv2d(128, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU()
        )
        self.conv2 = nn.Sequential(
            nn.Conv2d(128, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU()
        )
        self.final = nn.Conv2d(64, out_dim, 1)
        yy, xx = torch.meshgrid(torch.linspace(-1,1,64), torch.linspace(-1,1,64), indexing='ij')
        self.register_buffer('coords', torch.stack([yy, xx], dim=0).unsqueeze(0))

    def forward(self, vis_map, geo_canvas, task_emb):
        B = vis_map.size(0)
        vis_up = F.interpolate(vis_map, size=(64, 64), mode='bilinear', align_corners=False)
        task_plane = task_emb.view(B, -1, 1, 1).expand(-1, -1, 64, 64)
        x = torch.cat([vis_up, geo_canvas, task_plane, self.coords.expand(B,-1,-1,-1)], dim=1)
        x = self.conv1(x)
        x = self.conv2(x)
        return self.final(x)

# ==========================================
# 4. The Main NeuroSymbolic Model
# ==========================================

class NeuroSymbolic_VARC(nn.Module):
    def __init__(self, device, num_train_tasks):
        super().__init__()
        self.device = device
        self.vis_dim = 128
        self.geo_dim = 64
        self.task_dim = 64
        
        self.visual_encoder = VisionTransformerEncoder(hidden_dim=self.vis_dim)
        self.geo_encoder = GraphEncoder(in_dim=13, hidden_dim=self.geo_dim) 
        self.task_embedding = nn.Embedding(num_train_tasks, self.task_dim)
        self.decoder = FusionDecoder(self.vis_dim, self.geo_dim, self.task_dim)
        self.ttt_token = nn.Parameter(torch.randn(1, self.task_dim)) 

    def paint_graph_to_canvas(self, graph: GraphData, node_embs: torch.Tensor, 
                              scale: int, top: int, left: int) -> torch.Tensor:
        canvas = torch.zeros((1, self.geo_dim, CANVAS_SIZE, CANVAS_SIZE), device=self.device)
        if graph.num_nodes == 0: return canvas
        for i in range(graph.num_nodes):
            emb = node_embs[i]
            pixels = graph.pixels[i]
            for r, c in pixels:
                r_start, r_end = r*scale + top, (r+1)*scale + top
                c_start, c_end = c*scale + left, (c+1)*scale + left
                r_start = max(0, min(CANVAS_SIZE, r_start))
                r_end = max(0, min(CANVAS_SIZE, r_end))
                c_start = max(0, min(CANVAS_SIZE, c_start))
                c_end = max(0, min(CANVAS_SIZE, c_end))
                if r_end > r_start and c_end > c_start:
                    canvas[0, :, r_start:r_end, c_start:c_end] += emb.view(-1, 1, 1)
        return canvas

    def forward_pair(self, input_grid: np.ndarray, task_idx: Optional[int] = None, 
                     augment: bool = True, output_grid: Optional[np.ndarray] = None):
        
        h_in, w_in = input_grid.shape
        max_s_in = min(CANVAS_SIZE // max(1, h_in), CANVAS_SIZE // max(1, w_in))
        max_limit = max_s_in
        
        if output_grid is not None:
            h_out, w_out = output_grid.shape
            max_s_out = min(CANVAS_SIZE // max(1, h_out), CANVAS_SIZE // max(1, w_out))
            max_limit = min(max_s_in, max_s_out)
        
        canvas, scale, top, left = prepare_canvas(input_grid, augment=augment, max_scale_limit=max_limit)
        
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
            
        logits_canvas = self.decoder(vis_map, geo_canvas, t_emb)
        
        if output_grid is not None:
            target_canvas = torch.full((CANVAS_SIZE, CANVAS_SIZE), BG_COLOR, dtype=torch.long)
            tgt_np = output_grid.repeat(scale, 0).repeat(scale, 1)
            tSH, tSW = tgt_np.shape
            r_end = min(CANVAS_SIZE, top + tSH)
            c_end = min(CANVAS_SIZE, left + tSW)
            place_h = r_end - top
            place_w = c_end - left
            if place_h > 0 and place_w > 0:
                target_canvas[top:r_end, left:c_end] = torch.from_numpy(tgt_np[:place_h, :place_w])
            target_gpu = target_canvas.to(self.device).unsqueeze(0)
            
            loss = F.cross_entropy(logits_canvas, target_gpu)
            return loss
        else:
            return recover_from_canvas(logits_canvas[0], input_grid.shape[0], input_grid.shape[1], 
                                     scale, top, left)

# ==========================================
# 5. Training Loops
# ==========================================

def train_offline(model, tasks, epochs=10):
    opt = Adam(model.parameters(), lr=3e-4)
    model.train()
    
    for ep in range(epochs):
        total_loss = 0
        random.shuffle(tasks)
        steps = 0
        
        for t_idx, task in enumerate(tasks):
            for pair in task['train']:
                opt.zero_grad()
                loss = model.forward_pair(pair['input'], task_idx=t_idx, 
                                          augment=True, output_grid=pair['output'])
                loss.backward()
                opt.step()
                total_loss += loss.item()
                steps += 1
        
        print(f"Offline Epoch {ep+1}: Loss {total_loss/max(1, steps):.4f}")

def test_time_training(model, task, steps=50) -> List[np.ndarray]:
    nn.init.normal_(model.ttt_token, std=0.02)
    params = [model.ttt_token] + list(model.decoder.parameters())
    opt = Adam(params, lr=1e-3)
    
    model.train()
    for _ in range(steps):
        for pair in task['train']:
            opt.zero_grad()
            loss = model.forward_pair(pair['input'], task_idx=None, augment=True, output_grid=pair['output'])
            loss.backward()
            opt.step()
    
    model.eval()
    predictions = []
    with torch.no_grad():
        for test_pair in task['test']:
            # Inference
            pred_grid_tensor = model.forward_pair(test_pair['input'], task_idx=None, augment=False)
            
            # Convert to numpy. NO argmax here (recover_from_canvas already does it)
            pred_grid = pred_grid_tensor.cpu().numpy()
            predictions.append(pred_grid)
    return predictions

# ==========================================
# 6. Data Loading & CLI
# ==========================================

def load_file_pair(root, challenge_file, solution_file=None):
    root_path = Path(root)
    c_path = root_path / challenge_file
    print(f"Loading challenges: {c_path}")
    with open(c_path) as f: challenges = json.load(f)
    
    solutions = {}
    if solution_file and (root_path / solution_file).exists():
        print(f"Loading solutions:  {root_path / solution_file}")
        with open(root_path / solution_file) as f: solutions = json.load(f)
    
    tasks = []
    for tid, content in challenges.items():
        test_pairs = [{"input": np.array(x['input'])} for x in content['test']]
        if tid in solutions:
            for i, sol_grid in enumerate(solutions[tid]):
                if i < len(test_pairs):
                    test_pairs[i]["output"] = np.array(sol_grid)
        tasks.append({
            "id": tid,
            "train": [{"input": np.array(x['input']), "output": np.array(x['output'])} for x in content['train']],
            "test": test_pairs
        })
    return tasks

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_root", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    print("\n--- DATASET 1: TRAINING ---")
    train_tasks = load_file_pair(args.data_root, "arc-agi_training_challenges.json", "arc-agi_training_solutions.json")
    
    print("\n--- DATASET 2: EVALUATION ---")
    eval_tasks = load_file_pair(args.data_root, "arc-agi_evaluation_challenges.json", "arc-agi_evaluation_solutions.json")
    
    model = NeuroSymbolic_VARC(device, num_train_tasks=len(train_tasks)).to(device)
    
    print(f"\n1. Starting Offline Training on {len(train_tasks)} Training Tasks...")
    train_offline(model, train_tasks, epochs=args.epochs)
    
    print(f"\n2. Starting TTT Evaluation on {len(eval_tasks)} Evaluation Tasks...")
    solved_count = 0
    total_tasks = 0
    
    for i, task in enumerate(eval_tasks):
        if "output" not in task['test'][0]:
            print(f"Skipping Task {task['id']} (No Solution)")
            continue
            
        total_tasks += 1
        preds = test_time_training(model, task, steps=100)
        
        correct = True
        for idx, (pred, pair) in enumerate(zip(preds, task['test'])):
            gt = pair['output']
            if pred.shape != gt.shape or not np.array_equal(pred, gt):
                correct = False
            
            status = "SOLVED" if (correct and idx == len(preds)-1) else "FAILED" if not correct else "PARTIAL"
            try:
                visualize_prediction(task['id'], idx, pair['input'], gt, pred, status)
            except Exception as e:
                print(f"Viz Error: {e}")

        if correct: solved_count += 1
        print(f"Task {task['id']} [{i+1}/{len(eval_tasks)}]: {'SOLVED' if correct else 'Failed'}")
        
    print(f"\nFinal Score: {solved_count} / {total_tasks} ({(solved_count/max(1,total_tasks))*100:.2f}%)")
    print("Check 'results/' folder for images.")