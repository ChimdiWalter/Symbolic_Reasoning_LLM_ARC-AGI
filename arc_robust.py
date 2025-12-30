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

# =============================
# 1. Graph Data Structure & Utils
# =============================

@dataclass
class Graph:
    node_feats: torch.Tensor     # [N, F]
    adj: torch.Tensor            # [N, N] (0/1 or weighted)
    pixels: List[List[Tuple[int, int]]]  # per-node list of (row, col)
    H: int
    W: int

def extract_components(grid: np.ndarray) -> List[Dict[str, Any]]:
    """
    Flood-fill to extract connected components of equal color.
    """
    H, W = grid.shape
    visited = np.zeros((H, W), dtype=bool)
    comps = []
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]  # 4-connected

    for i in range(H):
        for j in range(W):
            if visited[i, j]:
                continue
            color = int(grid[i, j])
            queue = [(i, j)]
            visited[i, j] = True
            pixels = [(i, j)]
            while queue:
                ci, cj = queue.pop()
                for di, dj in directions:
                    ni, nj = ci + di, cj + dj
                    if 0 <= ni < H and 0 <= nj < W and not visited[ni, nj]:
                        if int(grid[ni, nj]) == color:
                            visited[ni, nj] = True
                            queue.append((ni, nj))
                            pixels.append((ni, nj))
            comps.append({"color": color, "pixels": pixels})
    return comps

def are_adjacent(pixels_a: List[Tuple[int, int]],
                 pixels_b: List[Tuple[int, int]],
                 max_cheb_dist: int = 1) -> bool:
    # Simple O(N*M) check. For ARC (small grids), this is acceptable.
    # Optimization: Check bounding box overlap first.
    for (i1, j1) in pixels_a:
        for (i2, j2) in pixels_b:
            if max(abs(i1 - i2), abs(j1 - j2)) <= max_cheb_dist:
                return True
    return False

def grid_to_graph(grid: np.ndarray, num_colors: int = 10) -> Graph:
    """
    Convert grid to graph. 
    Features: Size, Color (OneHot), Centroids, BBox.
    """
    H, W = grid.shape
    comps = extract_components(grid)
    num_nodes = len(comps)
    
    node_feats_list = []
    pixels_lists = []

    for comp in comps:
        color = comp["color"]
        pixels = comp["pixels"]
        pixels_lists.append(pixels)

        size = len(pixels)
        ys = np.array([p[0] for p in pixels], dtype=np.float32)
        xs = np.array([p[1] for p in pixels], dtype=np.float32)

        # Normalized spatial features
        centroid_y = ys.mean() / max(1, H)
        centroid_x = xs.mean() / max(1, W)
        y_min, y_max = ys.min(), ys.max()
        x_min, x_max = xs.min(), xs.max()
        bbox_h = (y_max - y_min + 1) / max(1, H)
        bbox_w = (x_max - x_min + 1) / max(1, W)
        size_norm = size / (H * W + 1e-5)

        # Color One-Hot
        color_oh = np.zeros(num_colors, dtype=np.float32)
        if 0 <= color < num_colors:
            color_oh[color] = 1.0
        
        # Feature Vector
        # [Size, CentroidY, CentroidX, BBoxH, BBoxW, Color(10)]
        feats = np.concatenate([
            np.array([size_norm, centroid_y, centroid_x, bbox_h, bbox_w], dtype=np.float32),
            color_oh
        ])
        node_feats_list.append(feats)

    if num_nodes > 0:
        node_feats_np = np.stack(node_feats_list, axis=0)
    else:
        # Handle completely empty grid case
        feat_dim = 5 + num_colors
        node_feats_np = np.zeros((0, feat_dim), dtype=np.float32)

    # Adjacency
    adj_np = np.zeros((num_nodes, num_nodes), dtype=np.float32)
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if are_adjacent(pixels_lists[i], pixels_lists[j]):
                adj_np[i, j] = 1.0
                adj_np[j, i] = 1.0 # Undirected

    return Graph(
        node_feats=torch.from_numpy(node_feats_np),
        adj=torch.from_numpy(adj_np),
        pixels=pixels_lists,
        H=H, W=W
    )

# =============================
# 2. Neural Modules
# =============================

class MessagePassingLayer(nn.Module):
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(2 * hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim), # Added depth
            nn.LayerNorm(hidden_dim)           # Added normalization
        )

    def forward(self, h: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        if h.size(0) == 0: return h
        
        # D^-1 A H formulation
        deg = adj.sum(dim=1, keepdim=True).clamp(min=1.0)
        m = (adj @ h) / deg
        
        h_cat = torch.cat([h, m], dim=-1)
        return F.relu(h + self.mlp(h_cat)) # Residual connection

class GraphEncoder(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int = 64, num_layers: int = 3):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.input_proj = nn.Linear(in_dim, hidden_dim)
        self.layers = nn.ModuleList([
            MessagePassingLayer(hidden_dim) for _ in range(num_layers)
        ])

    def forward(self, node_feats: torch.Tensor, adj: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if node_feats.size(0) == 0:
            # Handle empty graph
            device = next(self.parameters()).device
            return (torch.zeros((0, self.hidden_dim), device=device), 
                    torch.zeros(self.hidden_dim, device=device))

        h = F.relu(self.input_proj(node_feats))
        for layer in self.layers:
            h = layer(h, adj)
        
        # Global embedding: Mean + Max pooling for robustness
        global_mean = h.mean(dim=0)
        global_max = h.max(dim=0)[0]
        global_emb = (global_mean + global_max) / 2.0
        
        return h, global_emb

class TaskEncoder(nn.Module):
    def __init__(self, graph_encoder: GraphEncoder, hidden_dim: int, task_dim: int):
        super().__init__()
        self.graph_encoder = graph_encoder
        self.task_dim = task_dim
        
        # Relation Network style MLP
        self.pair_mlp = nn.Sequential(
            nn.Linear(3 * hidden_dim, 2 * hidden_dim),
            nn.ReLU(),
            nn.Linear(2 * hidden_dim, task_dim),
            nn.LayerNorm(task_dim)
        )

    def forward(self, graphs_in: List[Graph], graphs_out: List[Graph]) -> torch.Tensor:
        # Compute embeddings for all pairs
        pair_embs = []
        device = next(self.parameters()).device
        
        for Gin, Gout in zip(graphs_in, graphs_out):
            _, g_in = self.graph_encoder(Gin.node_feats, Gin.adj)
            _, g_out = self.graph_encoder(Gout.node_feats, Gout.adj)
            
            # Represent transformation as concatenation + difference
            diff = g_out - g_in
            pair_vec = torch.cat([g_in, g_out, diff], dim=-1)
            pair_embs.append(self.pair_mlp(pair_vec))

        if not pair_embs:
            return torch.zeros(self.task_dim, device=device)

        # Aggregate pairs (Mean pooling) represents the "Task Rule"
        pair_embs = torch.stack(pair_embs, dim=0)
        z_task = pair_embs.mean(dim=0)
        return z_task

# =============================
# 3. Hybrid Decoder (Graph -> Canvas -> CNN)
# =============================

class ResidualBlock(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.conv1 = nn.Conv2d(dim, dim, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(dim)
        self.conv2 = nn.Conv2d(dim, dim, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(dim)

    def forward(self, x):
        residual = x
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += residual
        return F.relu(out)

class HybridDecoder(nn.Module):
    def __init__(self, graph_encoder: GraphEncoder, hidden_dim: int, task_dim: int, num_colors: int = 10):
        super().__init__()
        self.graph_encoder = graph_encoder # <--- FIX: Store the encoder
        self.hidden_dim = hidden_dim
        self.max_h = 30
        self.max_w = 30
        
        # Input: NodeEmb + GlobalEmb + TaskEmb
        in_dim = hidden_dim + hidden_dim + task_dim
        self.node_to_pixel_mlp = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim)
        )
        
        # Coordinate embeddings (2 channels: y, x)
        self.coord_proj = nn.Conv2d(2, 16, kernel_size=1)
        
        cnn_in_dim = hidden_dim + 16 # Features + Coords
        
        self.cnn_stem = nn.Sequential(
            nn.Conv2d(cnn_in_dim, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU()
        )
        
        # Residual blocks for deep spatial reasoning
        self.res_layers = nn.ModuleList([ResidualBlock(hidden_dim) for _ in range(3)])
        
        self.final_conv = nn.Conv2d(hidden_dim, num_colors, kernel_size=1)

        # Register coordinate grid buffer
        y_grid, x_grid = torch.meshgrid(torch.linspace(-1, 1, 30), torch.linspace(-1, 1, 30), indexing='ij')
        self.register_buffer('coords', torch.stack([y_grid, x_grid], dim=0).unsqueeze(0)) # [1, 2, 30, 30]

    def forward(self, G_in: Graph, z_task: torch.Tensor, H_out: int, W_out: int) -> torch.Tensor:
        device = z_task.device
        
        # 1. Encode Input Graph
        node_embs, g_emb = self.graph_encoder(G_in.node_feats, G_in.adj)
        N = node_embs.size(0)
        
        # 2. Create Canvas [Batch=1, Hidden, 30, 30]
        canvas = torch.zeros((1, self.hidden_dim, self.max_h, self.max_w), device=device)
        
        # 3. Paint Nodes
        if N > 0:
            z_expand = z_task.unsqueeze(0).expand(N, -1)
            g_expand = g_emb.unsqueeze(0).expand(N, -1)
            
            # Combine info: "I am this node, in this graph context, solving this task"
            combined = torch.cat([node_embs, g_expand, z_expand], dim=1)
            pixel_feats = self.node_to_pixel_mlp(combined) # [N, Hidden]
            
            # Scatter to canvas
            # We iterate because N is small (usually < 20)
            for idx in range(N):
                feat = pixel_feats[idx]
                pixels = G_in.pixels[idx]
                for (r, c) in pixels:
                    if r < self.max_h and c < self.max_w:
                        # Summation allows handling overlapping semantic components
                        canvas[0, :, r, c] += feat

        # 4. Append Coordinate Info (Crucial for Symmetry/Pattern tasks)
        # coords shape: [1, 2, 30, 30]
        coord_feats = self.coord_proj(self.coords) # [1, 16, 30, 30]
        canvas = torch.cat([canvas, coord_feats], dim=1) # [1, Hidden+16, 30, 30]
        
        # 5. CNN Refinement
        x = self.cnn_stem(canvas)
        for res_block in self.res_layers:
            x = res_block(x)
            
        # 6. Prediction [1, NumColors, 30, 30]
        logits = self.final_conv(x)
        
        # 7. Crop to target size
        # ARC output sizes vary. Ideally we predict size, but for training we use GT size.
        out_h_clamped = min(H_out, self.max_h)
        out_w_clamped = min(W_out, self.max_w)
        
        logits = logits[0, :, :out_h_clamped, :out_w_clamped] # [NumColors, H_out, W_out]
        
        return logits

# =============================
# 4. Full Model Wrapper
# =============================

class ARCGeomModel(nn.Module):
    def __init__(self, num_colors: int = 10, hidden_dim: int = 128, task_dim: int = 128):
        super().__init__()
        self.num_colors = num_colors
        
        # Instantiate sub-modules
        # Using a larger hidden_dim helps ARC
        dummy_in_dim = 5 + num_colors # Size(1)+Centroid(2)+BBox(2)+Color(10)
        
        self.graph_encoder = GraphEncoder(in_dim=dummy_in_dim, hidden_dim=hidden_dim)
        self.task_encoder = TaskEncoder(self.graph_encoder, hidden_dim, task_dim)
        self.decoder = HybridDecoder(self.graph_encoder, hidden_dim, task_dim, num_colors)

    def forward_task(self, task: Dict[str, Any], device: torch.device) -> torch.Tensor:
        """
        Train step: 
        1. Infer Z_task from Train Pairs.
        2. Compute Reconstruction Loss on Train Pairs.
        3. Compute Prediction Loss on Test Pairs (if output exists).
        """
        
        # 1. Prepare Graphs
        train_pairs = task["train"]
        if not train_pairs: return torch.tensor(0.0, device=device)

        graphs_in_train = [grid_to_graph(p["input"], self.num_colors) for p in train_pairs]
        graphs_out_train = [grid_to_graph(p["output"], self.num_colors) for p in train_pairs]
        
        # Move to device
        for g in graphs_in_train + graphs_out_train:
            g.node_feats = g.node_feats.to(device)
            g.adj = g.adj.to(device)
            
        # 2. Get Task Embedding (Rule)
        z_task = self.task_encoder(graphs_in_train, graphs_out_train)
        
        # 3. Compute Losses
        # We calculate loss on ALL available pairs (Train + Test with labels)
        # This ensures the model learns to reproduce the train examples given the rule it just extracted.
        all_pairs = train_pairs + [p for p in task.get("test", []) if "output" in p]
        
        losses = []
        for pair in all_pairs:
            G_in = grid_to_graph(pair["input"], self.num_colors)
            G_in.node_feats = G_in.node_feats.to(device)
            G_in.adj = G_in.adj.to(device)
            
            target = torch.from_numpy(pair["output"].astype(np.int64)).to(device)
            H_out, W_out = target.shape
            
            logits = self.decoder(G_in, z_task, H_out, W_out)
            
            # Flatten for CrossEntropy
            loss = F.cross_entropy(logits.reshape(self.num_colors, -1).T, target.flatten())
            losses.append(loss)
            
        if not losses:
            return torch.tensor(0.0, device=device)
            
        return sum(losses) / len(losses)

# =============================
# 5. Data Loading & Main
# =============================

def load_arcagi2_split(data_root: str, split: str = "train") -> List[Dict[str, Any]]:
    root = Path(data_root)
    
    # Map splits to filenames
    files = {
        "train": ("arc-agi_training_challenges.json", "arc-agi_training_solutions.json"),
        "eval": ("arc-agi_evaluation_challenges.json", "arc-agi_evaluation_solutions.json"),
        "test": ("arc-agi_test_challenges.json", None)
    }
    
    if split not in files: raise ValueError(f"Unknown split: {split}")
    
    chall_name, sol_name = files[split]
    
    with (root / chall_name).open("r") as f:
        challenges = json.load(f)
    
    solutions = None
    if sol_name and (root / sol_name).exists():
        with (root / sol_name).open("r") as f:
            solutions = json.load(f)
            
    tasks = []
    for tid, spec in challenges.items():
        train_pairs = []
        for ex in spec["train"]:
            train_pairs.append({
                "input": np.array(ex["input"], dtype=np.int64),
                "output": np.array(ex["output"], dtype=np.int64)
            })
            
        test_pairs = []
        if solutions and tid in solutions:
            # Train/Eval split
            sols = solutions[tid]
            for ex, sol in zip(spec["test"], sols):
                test_pairs.append({
                    "input": np.array(ex["input"], dtype=np.int64),
                    "output": np.array(sol, dtype=np.int64)
                })
        else:
            # Test split (no solutions available publicly)
            for ex in spec["test"]:
                test_pairs.append({
                    "input": np.array(ex["input"], dtype=np.int64)
                })
                
        tasks.append({"task_id": tid, "train": train_pairs, "test": test_pairs})
        
    return tasks

def evaluate(model, tasks, device):
    model.eval()
    correct_pixels = 0
    total_pixels = 0
    solved_grids = 0
    total_grids = 0
    
    with torch.no_grad():
        for task in tasks:
            # Encode Train Pairs
            graphs_in = [grid_to_graph(p["input"], 10) for p in task["train"]]
            graphs_out = [grid_to_graph(p["output"], 10) for p in task["train"]]
            for g in graphs_in + graphs_out:
                g.node_feats = g.node_feats.to(device)
                g.adj = g.adj.to(device)
            
            z_task = model.task_encoder(graphs_in, graphs_out)
            
            # Predict Test Pairs
            for pair in task["test"]:
                if "output" not in pair: continue
                total_grids += 1
                
                G_in = grid_to_graph(pair["input"], 10)
                G_in.node_feats = G_in.node_feats.to(device)
                G_in.adj = G_in.adj.to(device)
                
                tgt = torch.from_numpy(pair["output"].astype(np.int64)).to(device)
                H, W = tgt.shape
                
                logits = model.decoder(G_in, z_task, H, W)
                pred = logits.argmax(0)
                
                if pred.shape == tgt.shape:
                    if torch.equal(pred, tgt):
                        solved_grids += 1
                    correct_pixels += (pred == tgt).sum().item()
                    total_pixels += tgt.numel()
                    
    print(f"  Grids Solved: {solved_grids}/{total_grids} ({solved_grids/max(1, total_grids)*100:.2f}%)")
    print(f"  Pixel Acc:    {correct_pixels/max(1, total_pixels)*100:.2f}%")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_root", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()
    
    device = torch.device(args.device)
    
    print("Loading Data...")
    train_tasks = load_arcagi2_split(args.data_root, "train")
    eval_tasks = load_arcagi2_split(args.data_root, "eval")
    
    model = ARCGeomModel(hidden_dim=128, task_dim=128).to(device)
    optimizer = Adam(model.parameters(), lr=args.lr)
    
    print("Starting Training (Hybrid Graph-CNN)...")
    
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0
        random.shuffle(train_tasks)
        
        for i, task in enumerate(train_tasks):
            optimizer.zero_grad()
            try:
                loss = model.forward_task(task, device)
                loss.backward()
                
                # Gradient clipping for stability
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                
                optimizer.step()
                total_loss += loss.item()
            except Exception as e:
                # Robustness: Skip tasks that cause graph errors (rare)
                print(f"Skipping task {task['task_id']} due to error: {e}")
                continue
                
        avg_loss = total_loss / len(train_tasks)
        print(f"Epoch {epoch+1}/{args.epochs} | Loss: {avg_loss:.4f}")
        
        # Evaluate every 5 epochs
        if (epoch + 1) % 5 == 0:
            print(f"--- Evaluation @ Epoch {epoch+1} ---")
            evaluate(model, eval_tasks, device)

if __name__ == "__main__":
    main()