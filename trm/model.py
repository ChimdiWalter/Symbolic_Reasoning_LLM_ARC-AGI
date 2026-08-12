"""Tiny Recursion Model (TRM) — per 2510.04871, self-attention variant.

Single tiny network recursing on (x=question, y=answer, z=latent):
  latent_recursion: n times  z <- net(x + y + z)
  answer update:             y <- net(y + z)
Deep supervision: T-1 recursion processes without grad, then one with
grad; up to N_sup outer improvement steps at train time (halting head).
~7M params at D=256, 2 layers.  30x30 canvas, 11 tokens (0-9 + PAD).
"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

CANVAS = 30
VOCAB = 11           # colors 0-9 + PAD(10)
MASK = 11            # corruption token (DRM objective; input-side only)
SEQ = CANVAS * CANVAS


class Block(nn.Module):
    def __init__(self, d, heads=8):
        super().__init__()
        self.norm1 = nn.RMSNorm(d)
        self.attn = nn.MultiheadAttention(d, heads, batch_first=True,
                                          bias=False)
        self.norm2 = nn.RMSNorm(d)
        self.mlp = nn.Sequential(nn.Linear(d, 4 * d, bias=False),
                                 nn.SiLU(),
                                 nn.Linear(4 * d, d, bias=False))

    def forward(self, h):
        a, _ = self.attn(self.norm1(h), self.norm1(h), self.norm1(h),
                         need_weights=False)
        h = h + a
        return h + self.mlp(self.norm2(h))


class TRM(nn.Module):
    def __init__(self, d=256, layers=2, n_latent=6, demos=3):
        super().__init__()
        self.d = d
        self.n_latent = n_latent
        # x: 7 channels (3 demo in/out pairs + query input)
        self.cell_emb = nn.Embedding(VOCAB + 1, d)   # +1 = MASK (input only)
        self.chan_emb = nn.Embedding(2 * demos + 1, d)
        self.pos_emb = nn.Parameter(torch.randn(1, SEQ, d) * 0.02)
        self.net = nn.ModuleList([Block(d) for _ in range(layers)])
        self.in_norm = nn.RMSNorm(d)   # tames the recursion's additive drift
        self.out_head = nn.Linear(d, VOCAB, bias=False)
        self.halt_head = nn.Linear(d, 1, bias=False)

    def embed_x(self, x):
        # x: [B, C, 30, 30] long -> [B, SEQ, D] (channels summed)
        B, C, H, W = x.shape
        e = self.cell_emb(x.view(B, C, SEQ))              # [B,C,SEQ,D]
        e = e + self.chan_emb.weight[:C].view(1, C, 1, -1)
        return e.sum(1) + self.pos_emb                     # [B,SEQ,D]

    def _pass(self, h):
        h = self.in_norm(h)
        for blk in self.net:
            h = blk(h)
        return h

    def latent_recursion(self, xe, y, z):
        for _ in range(self.n_latent):
            z = self._pass(xe + y + z)
        y = self._pass(y + z)
        return y, z

    def forward(self, x, y=None, z=None, T=3):
        """One deep-supervision step: T-1 recursions no-grad, 1 with grad.
        Returns (logits [B,SEQ,VOCAB], y, z, halt_logit [B])."""
        xe = self.embed_x(x)
        B = x.shape[0]
        if y is None:
            y = torch.zeros(B, SEQ, self.d, device=x.device)
        if z is None:
            z = torch.zeros(B, SEQ, self.d, device=x.device)
        with torch.no_grad():
            for _ in range(T - 1):
                y, z = self.latent_recursion(xe, y, z)
        y, z = self.latent_recursion(xe, y, z)
        logits = self.out_head(y)
        halt = self.halt_head(y.mean(1)).squeeze(-1)
        return logits, y.detach(), z.detach(), halt


def count_params(m):
    return sum(p.numel() for p in m.parameters())


if __name__ == "__main__":
    m = TRM()
    print(f"TRM params: {count_params(m)/1e6:.1f}M")
