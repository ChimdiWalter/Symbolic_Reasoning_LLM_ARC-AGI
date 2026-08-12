"""GuideNet — search-guidance recognition model (Play B step 2).

DreamCoder-recognition style (docs/BREAKTHROUGH_RESEARCH_2026_07.md):
per train pair, embed input and output grids, compute a DIFFERENCE
feature (output minus input in feature space), pass through dilated
convs, pool to a fixed vector; average across the task's train pairs.
Heads: multi-label action kinds (sigmoid) + family (softmax).

The guide only ORDERS induction search downstream; it never touches
acceptance (LOO gate unchanged) — the guidance-without-contamination
contract in paper/DRAFT.md related work.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

CANVAS = 30
NCOLORS = 11          # 0-9 + pad/background sentinel 10


class GridEncoder(nn.Module):
    def __init__(self, d=64):
        super().__init__()
        self.emb = nn.Embedding(NCOLORS, 16)
        self.conv = nn.Sequential(
            nn.Conv2d(16, d, 3, padding=1), nn.ReLU(),
            nn.Conv2d(d, d, 3, padding=2, dilation=2), nn.ReLU(),
            nn.Conv2d(d, d, 3, padding=4, dilation=4), nn.ReLU(),
        )

    def forward(self, g):
        # g: [B, 30, 30] long -> [B, d, 30, 30]
        return self.conv(self.emb(g).permute(0, 3, 1, 2))


class GuideNet(nn.Module):
    def __init__(self, n_kinds, n_families, d=64, feat=256):
        super().__init__()
        self.enc = GridEncoder(d)
        self.mix = nn.Sequential(
            nn.Conv2d(3 * d, d, 3, padding=1), nn.ReLU(),
            nn.Conv2d(d, d, 3, padding=2, dilation=2), nn.ReLU(),
        )
        self.pool = nn.AdaptiveAvgPool2d(3)
        self.proj = nn.Linear(d * 9, feat)
        self.kind_head = nn.Linear(feat, n_kinds)
        self.family_head = nn.Linear(feat, n_families)

    def pair_feat(self, gin, gout):
        a, b = self.enc(gin), self.enc(gout)
        h = self.mix(torch.cat([a, b, b - a], dim=1))
        return self.proj(self.pool(h).flatten(1))       # [B, feat]

    def forward(self, gins, gouts, npairs):
        """gins/gouts: [B, P, 30, 30] padded pair stacks; npairs: [B]."""
        B, P = gins.shape[:2]
        f = self.pair_feat(gins.reshape(B * P, CANVAS, CANVAS),
                           gouts.reshape(B * P, CANVAS, CANVAS))
        f = f.view(B, P, -1)
        mask = (torch.arange(P, device=f.device)[None, :]
                < npairs[:, None]).float().unsqueeze(-1)
        f = (f * mask).sum(1) / mask.sum(1).clamp(min=1)
        f = F.relu(f)
        return self.kind_head(f), self.family_head(f)


def count_params(m):
    return sum(p.numel() for p in m.parameters())
