import math
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam

import json
from pathlib import Path

# =============================
# 1. Graph data structure
# =============================

@dataclass
class Graph:
    node_feats: torch.Tensor     # [N, F]
    adj: torch.Tensor            # [N, N] (0/1)
    pixels: List[List[Tuple[int, int]]]  # per-node list of (row, col)
    H: int
    W: int


# =============================
# 2. Grid -> component graph
# =============================

def extract_components(grid: np.ndarray) -> List[Dict[str, Any]]:
    """
    Flood-fill to extract connected components of equal color.
    Returns list of dicts with keys: 'color', 'pixels' (list of (i,j)).
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
            # BFS
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
    """
    Two components are adjacent if any pair of pixels are within given Chebyshev distance.
    This is O(n^2) but fine for small ARC grids.
    """
    for (i1, j1) in pixels_a:
        for (i2, j2) in pixels_b:
            if max(abs(i1 - i2), abs(j1 - j2)) <= max_cheb_dist:
                return True
    return False


def count_component_holes(grid: np.ndarray,
                          pixels: List[Tuple[int, int]]) -> int:
    """
    Count 'holes' in a component defined by its pixels.
    A hole = a background connected component inside the component's
    bounding box that does NOT touch the bounding box border.
    """
    if not pixels:
        return 0

    ys = np.array([p[0] for p in pixels], dtype=np.int32)
    xs = np.array([p[1] for p in pixels], dtype=np.int32)

    y_min, y_max = ys.min(), ys.max()
    x_min, x_max = xs.min(), xs.max()

    h = y_max - y_min + 1
    w = x_max - x_min + 1

    # component mask in bbox coordinates
    comp_mask = np.zeros((h, w), dtype=np.uint8)
    for (i, j) in pixels:
        comp_mask[i - y_min, j - x_min] = 1

    # background inside bbox
    bg_mask = 1 - comp_mask  # 1 where background, 0 where component

    # mark outer background: flood-fill from bbox border where bg_mask == 1
    visited = np.zeros_like(bg_mask, dtype=bool)
    from collections import deque
    q = deque()

    # add all border bg pixels
    for i in range(h):
        for j in range(w):
            if (i == 0 or i == h - 1 or j == 0 or j == w - 1) and bg_mask[i, j] == 1:
                visited[i, j] = True
                q.append((i, j))

    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while q:
        ci, cj = q.popleft()
        for di, dj in dirs:
            ni, nj = ci + di, cj + dj
            if 0 <= ni < h and 0 <= nj < w and not visited[ni, nj] and bg_mask[ni, nj] == 1:
                visited[ni, nj] = True
                q.append((ni, nj))

    # any bg pixel with bg_mask==1 and visited==False is inside a "hole"
    hole_mask = (bg_mask == 1) & (~visited)

    # count connected components in hole_mask
    hole_visited = np.zeros_like(hole_mask, dtype=bool)
    hole_count = 0

    for i in range(h):
        for j in range(w):
            if hole_mask[i, j] and not hole_visited[i, j]:
                hole_count += 1
                q = deque([(i, j)])
                hole_visited[i, j] = True
                while q:
                    ci, cj = q.popleft()
                    for di, dj in dirs:
                        ni, nj = ci + di, cj + dj
                        if (
                            0 <= ni < h and 0 <= nj < w and
                            hole_mask[ni, nj] and not hole_visited[ni, nj]
                        ):
                            hole_visited[ni, nj] = True
                            q.append((ni, nj))

    return hole_count


def grid_to_graph(
    grid: np.ndarray,
    num_colors: int = 10
) -> Graph:
    """
    Convert a grid (H,W) of integer colors into a Graph over components.

    Node features include:
      - size_norm
      - color one-hot (num_colors)
      - centroids, bbox center/size (normalized)
      - area_fraction
      - hole_count_norm
      - global_num_components_norm
      - global_total_holes_norm
    """
    H, W = grid.shape
    comps = extract_components(grid)
    num_nodes = len(comps)

    # --- first pass: compute hole counts per component ---
    hole_counts = []
    total_holes = 0
    for comp in comps:
        hc = count_component_holes(grid, comp["pixels"])
        hole_counts.append(hc)
        total_holes += hc

    # global topo stats (normalized)
    max_comps_norm = 50.0  # assume <= 50 components in typical ARC
    max_holes_norm = 20.0  # assume <= 20 holes total

    num_components_norm = min(num_nodes / max_comps_norm, 1.0)
    total_holes_norm = min(total_holes / max_holes_norm, 1.0)

    node_feats_list = []
    pixels_lists: List[List[Tuple[int, int]]] = []

    for comp, hc in zip(comps, hole_counts):
        color = comp["color"]
        pixels = comp["pixels"]
        pixels_lists.append(pixels)

        size = len(pixels)
        ys = np.array([p[0] for p in pixels], dtype=np.float32)
        xs = np.array([p[1] for p in pixels], dtype=np.float32)

        centroid_y = ys.mean() / max(1, (H - 1))
        centroid_x = xs.mean() / max(1, (W - 1))

        y_min, y_max = ys.min(), ys.max()
        x_min, x_max = xs.min(), xs.max()

        bbox_center_y = ((y_min + y_max) / 2.0) / max(1, (H - 1))
        bbox_center_x = ((x_min + x_max) / 2.0) / max(1, (W - 1))
        bbox_h = (y_max - y_min + 1) / H
        bbox_w = (x_max - x_min + 1) / W

        size_norm = size / float(H * W)
        area_fraction = size_norm

        color_oh = np.zeros(num_colors, dtype=np.float32)
        if 0 <= color < num_colors:
            color_oh[color] = 1.0
        else:
            color_oh[-1] = 1.0

        hole_count_norm = min(hc / 5.0, 1.0)  # assume most components have <=5 holes

        feats = np.concatenate([
            np.array([size_norm], dtype=np.float32),
            color_oh,
            np.array(
                [
                    centroid_y,
                    centroid_x,
                    bbox_center_y,
                    bbox_center_x,
                    bbox_h,
                    bbox_w,
                    area_fraction,
                    hole_count_norm,
                    num_components_norm,
                    total_holes_norm,
                ],
                dtype=np.float32,
            ),
        ], axis=0)

        node_feats_list.append(feats)

    if num_nodes > 0:
        node_feats_np = np.stack(node_feats_list, axis=0)
    else:
        feat_dim = 1 + num_colors + 10
        node_feats_np = np.zeros((0, feat_dim), dtype=np.float32)

    adj_np = np.zeros((num_nodes, num_nodes), dtype=np.float32)
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j:
                continue
            if are_adjacent(pixels_lists[i], pixels_lists[j], max_cheb_dist=1):
                adj_np[i, j] = 1.0

    node_feats = torch.from_numpy(node_feats_np)
    adj = torch.from_numpy(adj_np)

    return Graph(node_feats=node_feats,
                 adj=adj,
                 pixels=pixels_lists,
                 H=H,
                 W=W)


# =============================
# 3. Geometric graph encoder
# =============================

class MessagePassingLayer(nn.Module):
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(2 * hidden_dim, hidden_dim),
            nn.ReLU(),
        )

    def forward(self, h: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        deg = adj.sum(dim=1, keepdim=True)
        deg = torch.clamp(deg, min=1.0)
        m = adj @ h / deg
        h_cat = torch.cat([h, m], dim=-1)
        return self.mlp(h_cat)


class GraphEncoder(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int = 64, num_layers: int = 3):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.input_mlp = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
        )
        self.layers = nn.ModuleList([
            MessagePassingLayer(hidden_dim) for _ in range(num_layers)
        ])

    def forward(self, node_feats: torch.Tensor, adj: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if node_feats.size(0) == 0:
            H = self.hidden_dim
            node_embs = node_feats.new_zeros((0, H))
            global_emb = node_feats.new_zeros(H)
            return node_embs, global_emb

        h = self.input_mlp(node_feats)
        for layer in self.layers:
            h = layer(h, adj)
        global_emb = h.mean(dim=0)
        return h, global_emb


# =============================
# 4. Task encoder
# =============================

class TaskEncoder(nn.Module):
    def __init__(self, graph_encoder: GraphEncoder, hidden_dim: int, task_dim: int):
        super().__init__()
        self.graph_encoder = graph_encoder
        self.task_dim = task_dim
        self.pair_mlp = nn.Sequential(
            nn.Linear(3 * hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, task_dim),
            nn.ReLU(),
        )

    def forward(self,
                graphs_in: List[Graph],
                graphs_out: List[Graph]) -> torch.Tensor:
        assert len(graphs_in) == len(graphs_out)
        pair_embs = []
        for Gin, Gout in zip(graphs_in, graphs_out):
            _, g_in = self.graph_encoder(Gin.node_feats, Gin.adj)
            _, g_out = self.graph_encoder(Gout.node_feats, Gout.adj)
            diff = g_out - g_in
            pair_vec = torch.cat([g_in, g_out, diff], dim=-1)
            pair_emb = self.pair_mlp(pair_vec)
            pair_embs.append(pair_emb)
        if len(pair_embs) == 0:
            device = next(self.parameters()).device
            return torch.zeros(self.task_dim, device=device)
        pair_embs = torch.stack(pair_embs, dim=0)
        z_task = pair_embs.mean(dim=0)
        return z_task


# =============================
# 5. Task-conditioned decoder
# =============================

class HybridDecoder(nn.Module):
    def __init__(self, graph_encoder: GraphEncoder, hidden_dim: int, task_dim: int, num_colors: int = 10):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.task_dim = task_dim
        self.num_colors = num_colors
        
        # Max ARC grid size is usually 30x30. We process everything at 30x30.
        self.max_h = 30
        self.max_w = 30

        # Projection: Node features -> Canvas features
        # Input dim: hidden_dim (node emb) + hidden_dim (graph emb) + task_dim
        in_dim = hidden_dim + hidden_dim + task_dim
        
        self.canvas_mlp = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU()
        )

        # CNN Refiner: Takes the canvas and produces the output grid
        # ResNet-style blocks are better, but a simple CNN works for basic tasks
        self.cnn = nn.Sequential(
            nn.Conv2d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU(),
            nn.Conv2d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU(),
            nn.Conv2d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU(),
            # Final projection to colors
            nn.Conv2d(hidden_dim, num_colors, kernel_size=1)
        )

    def forward(self, G_in: Graph, z_task: torch.Tensor, H_out: int, W_out: int) -> torch.Tensor:
        """
        Returns logits grid of shape [num_colors, H_out, W_out]
        """
        device = z_task.device
        
        # 1. Get Node Embeddings
        node_embs, g_emb = self.graph_encoder.forward(G_in.node_feats, G_in.adj)
        # node_embs: [N, H], g_emb: [H]
        
        N = node_embs.size(0)
        
        # 2. Initialize Canvas [Batch=1, Hidden, 30, 30]
        # We use batch size 1 because we process one grid at a time in your loop
        canvas = torch.zeros((1, self.hidden_dim, self.max_h, self.max_w), device=device)
        
        # If the graph is not empty, project nodes onto canvas
        if N > 0:
            # Prepare features to paint: Node + Global + Task
            z_expand = z_task.unsqueeze(0).expand(N, -1)
            g_expand = g_emb.unsqueeze(0).expand(N, -1)
            
            # Combine features
            combined = torch.cat([node_embs, g_expand, z_expand], dim=1) # [N, In_Dim]
            paint_feats = self.canvas_mlp(combined) # [N, Hidden]
            
            # "Paint" the features back to original pixel locations
            # Note: This is a scatter operation. 
            # Optimization: In a real batch setting, use scatter_nd. 
            # Here, simple loop is fine for ARC sizes.
            
            # We need to be careful about overlapping nodes. 
            # Max pooling or summation is better than overwriting.
            # Let's use summation for overlapping pixels.
            
            for idx in range(N):
                feats = paint_feats[idx] # [Hidden]
                pixels = G_in.pixels[idx]
                for (r, c) in pixels:
                    # Clamp to max size just in case
                    if r < self.max_h and c < self.max_w:
                        canvas[0, :, r, c] += feats

        # 3. CNN Processing
        # The CNN allows features to "move" (propagate) and generate new shapes
        feat_map = self.cnn(canvas) # [1, NumColors, 30, 30]
        
        # 4. Crop to target size
        # In ARC, output size is sometimes different. 
        # For simplicity in this architecture, we crop top-left.
        # (A more advanced model would predict the output size too).
        out_h = min(H_out, self.max_h)
        out_w = min(W_out, self.max_w)
        
        logits = feat_map[0, :, :out_h, :out_w] # [NumColors, H_out, W_out]
        
        return logits


# =============================
# 6. Full model wrapper
# =============================

class ARCGeomModel(nn.Module):
    def __init__(self, graph_encoder: GraphEncoder, task_encoder: TaskEncoder,
                 decoder: HybridDecoder, num_colors: int = 10):
        super().__init__()
        self.graph_encoder = graph_encoder
        self.task_encoder = task_encoder
        self.decoder = decoder
        self.num_colors = num_colors

    def forward_task(self, task: Dict[str, Any], device: torch.device) -> torch.Tensor:
        # Build Graphs for train pairs
        graphs_in = []
        graphs_out = []
        for pair in task["train"]:
            Gi = grid_to_graph(pair["input"], num_colors=self.num_colors)
            Go = grid_to_graph(pair["output"], num_colors=self.num_colors)
            Gi.node_feats = Gi.node_feats.to(device)
            Gi.adj = Gi.adj.to(device)
            Go.node_feats = Go.node_feats.to(device)
            Go.adj = Go.adj.to(device)
            graphs_in.append(Gi)
            graphs_out.append(Go)

        # Task embedding
        z_task = self.task_encoder(graphs_in, graphs_out)
        z_task = z_task.to(device)

        losses = []
        # Training on TRAIN pairs (Self-Supervised consistency)
        # We should compute loss on the training examples too to ensure the model
        # learned the rule represented by z_task
        all_pairs = task["train"] + task.get("test", [])
        
        for pair in all_pairs:
            if "output" not in pair:
                continue

            # Input graph
            G_in = grid_to_graph(pair["input"], num_colors=self.num_colors)
            G_in.node_feats = G_in.node_feats.to(device)
            G_in.adj = G_in.adj.to(device)

            target_grid = torch.from_numpy(pair["output"].astype(np.int64)).to(device)
            H_out, W_out = target_grid.shape

            # Hybrid Decode
            logits_grid = self.decoder(G_in, z_task, H_out, W_out)

            # Compute Loss
            logits_flat = logits_grid.reshape(self.num_colors, -1).permute(1, 0) # [N, C]
            target_flat = target_grid.reshape(-1) # [N]

            loss = F.cross_entropy(logits_flat, target_flat)
            losses.append(loss)

        if not losses:
            return torch.tensor(0.0, device=device)

        return sum(losses) / len(losses)



# =============================
# 7. Training & eval loops
# =============================

def train_arc_geom_model(
    tasks: List[Dict[str, Any]],
    num_epochs: int = 10,
    hidden_dim: int = 64,
    task_dim: int = 64,
    num_colors: int = 10,
    lr: float = 1e-3,
    device: str = "cuda",
):
    device = torch.device(device)

    # Use a dummy graph to init dimensions
    sample_grid = tasks[0]["train"][0]["input"]
    sample_graph = grid_to_graph(sample_grid, num_colors=num_colors)
    feat_dim = sample_graph.node_feats.shape[1]

    graph_encoder = GraphEncoder(in_dim=feat_dim, hidden_dim=hidden_dim, num_layers=3)
    task_encoder = TaskEncoder(graph_encoder=graph_encoder, hidden_dim=hidden_dim, task_dim=task_dim)
    
    # USE THE NEW DECODER
    decoder = HybridDecoder(graph_encoder=graph_encoder, hidden_dim=hidden_dim,
                                     task_dim=task_dim, num_colors=num_colors)
    
    model = ARCGeomModel(graph_encoder, task_encoder, decoder, num_colors=num_colors)
    model.to(device)

    optimizer = Adam(model.parameters(), lr=lr)

    for epoch in range(num_epochs):
        total_loss = 0.0
        model.train()
        # Shuffle tasks for better training
        import random
        random.shuffle(tasks)
        
        for i, task in enumerate(tasks):
            optimizer.zero_grad()
            loss = model.forward_task(task, device=device)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
            # Optional: Print progress inside epoch
            # if i % 100 == 0: print(f"Step {i}, Loss: {loss.item():.4f}")

        avg_loss = total_loss / max(1, len(tasks))
        print(f"Epoch {epoch+1}/{num_epochs} - avg loss: {avg_loss:.4f}")

    return model



def evaluate_arc_geom_model_detailed(
    model: ARCGeomModel,
    tasks: List[Dict[str, Any]],
    device: str = "cpu",
) -> Dict[str, Any]:
    dev = torch.device(device)
    model.to(dev)
    model.eval()

    num_tasks = len(tasks)
    num_tasks_solved = 0
    num_test_grids = 0
    num_test_grids_solved = 0
    pixel_correct = 0
    pixel_total = 0

    with torch.no_grad():
        for task in tasks:
            task_all_correct = True

            # Build z_task
            graphs_in = []
            graphs_out = []
            for pair in task["train"]:
                Gi = grid_to_graph(pair["input"], num_colors=model.num_colors)
                Go = grid_to_graph(pair["output"], num_colors=model.num_colors)
                Gi.node_feats = Gi.node_feats.to(dev)
                Gi.adj = Gi.adj.to(dev)
                Go.node_feats = Go.node_feats.to(dev)
                Go.adj = Go.adj.to(dev)
                graphs_in.append(Gi)
                graphs_out.append(Go)
            z_task = model.task_encoder(graphs_in, graphs_out)

            for test_pair in task["test"]:
                if "output" not in test_pair:
                    continue

                num_test_grids += 1

                G_test_in = grid_to_graph(test_pair["input"], num_colors=model.num_colors)
                G_test_in.node_feats = G_test_in.node_feats.to(dev)
                G_test_in.adj = G_test_in.adj.to(dev)

                target_grid_np = test_pair["output"].astype(np.int64)
                H_out, W_out = target_grid_np.shape
                target_grid = torch.from_numpy(target_grid_np).to(dev)

                # New Decode call
                logits_grid = model.decoder(G_test_in, z_task, H_out, W_out)
                pred_grid = logits_grid.argmax(dim=0)

                # Check correctness
                if pred_grid.shape != target_grid.shape:
                    # Should not happen with this code logic
                    task_all_correct = False
                else:
                    correct_grid = torch.equal(pred_grid, target_grid)
                    if correct_grid:
                        num_test_grids_solved += 1
                    else:
                        task_all_correct = False
                    
                    pixel_correct += (pred_grid == target_grid).sum().item()
                    pixel_total += target_grid.numel()

            if task_all_correct and len(task["test"]) > 0:
                num_tasks_solved += 1

    return {
        "num_tasks": num_tasks,
        "num_tasks_solved": num_tasks_solved,
        "grid_success_rate": num_test_grids_solved / max(1, num_test_grids),
        "avg_pixel_accuracy": pixel_correct / max(1, pixel_total),
    }


# =============================
# 8. ARC-AGI-2 data loading
# =============================

def load_arcagi2_split(
    data_root: str,
    split: str = "train",
) -> List[Dict[str, Any]]:
    """
    Load ARC-AGI-2 split as a list of tasks.
    split in {"train", "eval", "test"}.
    For train/eval, attaches test outputs from solutions.
    For test, test outputs are not present.
    """
    root = Path(data_root)

    if split == "train":
        chall_path = root / "arc-agi_training_challenges.json"
        sol_path = root / "arc-agi_training_solutions.json"
        with chall_path.open("r") as f:
            challenges = json.load(f)
        with sol_path.open("r") as f:
            solutions = json.load(f)
    elif split == "eval":
        chall_path = root / "arc-agi_evaluation_challenges.json"
        sol_path = root / "arc-agi_evaluation_solutions.json"
        with chall_path.open("r") as f:
            challenges = json.load(f)
        with sol_path.open("r") as f:
            solutions = json.load(f)
    elif split == "test":
        chall_path = root / "arc-agi_test_challenges.json"
        with chall_path.open("r") as f:
            challenges = json.load(f)
        solutions = None
    else:
        raise ValueError(f"Unknown split: {split}")

    tasks: List[Dict[str, Any]] = []
    for task_id, spec in challenges.items():
        # train pairs
        train_pairs = []
        for ex in spec.get("train", []):
            train_pairs.append({
                "input": np.array(ex["input"], dtype=np.int64),
                "output": np.array(ex["output"], dtype=np.int64),
            })

        # test examples
        test_list = []
        if solutions is not None:
            sols = solutions[task_id]
            for ex, out_grid in zip(spec.get("test", []), sols):
                test_list.append({
                    "input": np.array(ex["input"], dtype=np.int64),
                    "output": np.array(out_grid, dtype=np.int64),
                })
        else:
            for ex in spec.get("test", []):
                test_list.append({
                    "input": np.array(ex["input"], dtype=np.int64),
                })

        tasks.append({
            "task_id": task_id,
            "train": train_pairs,
            "test": test_list,
        })

    if not tasks:
        raise RuntimeError(f"No tasks loaded for split='{split}' from {data_root}")
    return tasks


# =============================
# 9. CLI entrypoint
# =============================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Topology-aware geometric ARC-AGI-2 model")
    parser.add_argument("--data_root", type=str, default=".", help="Folder containing ARC-AGI-2 JSON files")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden_dim", type=int, default=64)
    parser.add_argument("--task_dim", type=int, default=64)
    parser.add_argument("--num_colors", type=int, default=10)
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--do_eval", action="store_true", help="Also evaluate on evaluation split after training")

    args = parser.parse_args()

    print(f"Loading train split from {args.data_root}")
    train_tasks = load_arcagi2_split(args.data_root, split="train")
    print(f"Loaded {len(train_tasks)} training tasks")

    model = train_arc_geom_model(
        tasks=train_tasks,
        num_epochs=args.epochs,
        hidden_dim=args.hidden_dim,
        task_dim=args.task_dim,
        num_colors=args.num_colors,
        lr=args.lr,
        device=args.device,
    )

    if args.do_eval:
        print(f"Loading eval split from {args.data_root}")
        eval_tasks = load_arcagi2_split(args.data_root, split="eval")
        print(f"Loaded {len(eval_tasks)} evaluation tasks")

        avg_eval_loss = eval_arc_geom_model(model, eval_tasks, device=args.device)
        print(f"Average eval loss: {avg_eval_loss:.4f}")

        metrics = evaluate_arc_geom_model_detailed(model, eval_tasks, device=args.device)
        print("Detailed eval metrics:")
        for k, v in metrics.items():
            print(f"  {k}: {v}")
