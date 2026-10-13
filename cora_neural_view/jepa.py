"""CORA-NVG frozen I-JEPA guide (exploratory arm; licence CC-BY-NC-4.0, research only).

Each grid is rendered with exactly one 14 x 14 px patch per cell (ViT-H/14 at
224 px, so up to 16 x 16 cells), so the patch tokens are aligned with cells.

Score of a view V: the mean cosine similarity between
- the embedding of V's object partition of a training input (each object
  painted one fixed palette colour by object index); and
- the embedding of that pair's output grid.

Embeddings are the mean of the patch tokens. Views are ranked by this score,
highest first. The design is perceptual: does how a view groups the input
look like what the output is?

Conditions:
- J-C: averaged over all training pairs;
- J-D: averaged over the pairs whose leave-one-out re-derivation failed in
  the authentic native trace (all pairs if none failed or there is no
  trace);
- J-E: the same, with another decision's failed-pair set.

A J arm always tries its top view. Abstention needs a threshold, and none is
tuned.
"""
import numpy as np

PALETTE = np.array([[0, 0, 0], [0, 116, 217], [255, 65, 54], [46, 204, 64], [255, 220, 0], [170, 170, 170],
                    [240, 18, 190], [255, 133, 27], [127, 219, 255], [135, 12, 37]], dtype=np.float32)
PART = np.array([[230, 25, 75], [60, 180, 75], [255, 225, 25], [0, 130, 200], [245, 130, 48], [145, 30, 180],
                 [70, 240, 240], [240, 50, 230], [210, 245, 60]], dtype=np.float32)


def render(grid, part=None):
    g = np.asarray(grid)
    img = np.zeros((224, 224, 3), np.float32)
    for r in range(min(16, g.shape[0])):
        for c in range(min(16, g.shape[1])):
            col = PALETTE[g[r, c]] if part is None else (PART[part[r, c] % len(PART)] if part[r, c] >= 0 else PALETTE[0])
            img[14 * r:14 * r + 14, 14 * c:14 * c + 14] = col
    return img / 255.0


def partition(grid, view):
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import SegmentationVariant as SV, to_grid_pairs
    g = np.asarray(grid)
    V = next(x for x in SV if x.value == view)
    gp = to_grid_pairs([(g, g)])[0][0]
    objs = S.segment(gp, V, S.background_for(gp, V))
    lab = -np.ones(g.shape, int)
    for k, o in enumerate(sorted(objs, key=lambda o: min(o.cells))):
        for (r, c) in o.cells:
            lab[r, c] = k
    return lab


class JEPAGuide:
    def __init__(self, path, device="cuda:0"):
        import torch
        from transformers import AutoModel
        self.torch = torch
        self.model = AutoModel.from_pretrained(path, dtype=torch.float16).to(device).eval()
        self.device = device
        self.mean = torch.tensor([0.485, 0.456, 0.406], device=device).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225], device=device).view(1, 3, 1, 1)
        self.cache = {}

    def embed(self, imgs):
        t = self.torch.tensor(np.stack(imgs), device=self.device).permute(0, 3, 1, 2)
        t = ((t - self.mean) / self.std).half()
        with self.torch.no_grad():
            h = self.model(pixel_values=t).last_hidden_state.float()
        v = h.mean(1)
        return (v / v.norm(dim=-1, keepdim=True)).cpu().numpy()

    def scores(self, inp, pairs=None):
        idx = list(range(len(inp["train"]))) if not pairs else [j for j in pairs if j < len(inp["train"])]
        out = {}
        outs = self.embed([render(inp["train"][j][1]) for j in idx])
        for v in inp["options"]:
            parts = self.embed([render(inp["train"][j][0], partition(inp["train"][j][0], v)) for j in idx])
            out[v] = float(np.mean(np.sum(parts * outs, axis=1)))
        return out

    def __call__(self, inp, condition, shuffled_trace=None):
        tr = inp["trace"] if condition == "J-D" else (shuffled_trace if condition == "J-E" else None)
        pairs = (tr or {}).get("loo", {}) or {}
        sc = self.scores(inp, pairs.get("failed_pairs") if condition != "J-C" else None)
        r = sorted(inp["options"], key=lambda v: -sc[v])
        return r, (r[0] if r else None), {"scores": sc}
