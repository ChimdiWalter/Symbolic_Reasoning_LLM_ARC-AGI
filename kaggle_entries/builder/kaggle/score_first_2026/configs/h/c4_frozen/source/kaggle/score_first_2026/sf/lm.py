"""The grid language model: loading, prompt prefill, batched constrained greedy decoding and teacher-forced scoring.

Own implementation on transformers' public model API (Apache-2.0). Prompts are prefilled one at a time (no padding,
so the causal attention kernels apply), then their key/value caches are left-padded into one batch for decoding.
"""
import time

import torch
from transformers import AutoModelForCausalLM, DynamicCache, StaticCache

from . import textfmt as F

PREFILL_CHUNK = 4096                 # tokens per prefill forward (1024 on pre-Ampere GPUs, see LM)


def make_cache(kv):
    """A DynamicCache holding the given per-layer (keys, values)."""
    try:
        return DynamicCache(ddp_cache_data=kv)
    except TypeError:
        cache = DynamicCache()
        for i, (k, v) in enumerate(kv):
            cache.update(k, v, i)
        return cache


class LM:
    def __init__(self, path, device="cuda:0", dtype=None, attn="sdpa"):
        self.device = torch.device(device)
        if dtype is None:
            if self.device.type != "cuda":
                dtype = torch.float32
            else:
                major = torch.cuda.get_device_capability(self.device)[0]
                dtype = torch.bfloat16 if major >= 8 else torch.float16
        self.dtype = dtype
        self.chunk = PREFILL_CHUNK
        self.use_static = True
        if self.device.type == "cuda" and torch.cuda.get_device_capability(self.device)[0] < 8:
            self.chunk = 1024
        t0 = time.time()
        self.model = AutoModelForCausalLM.from_pretrained(path, dtype=dtype, device_map={"": str(self.device)},
                                                          attn_implementation=attn)
        self.model.eval()
        self.load_s = time.time() - t0
        self.stats = {"prefill_tokens": 0, "decode_steps": 0, "decode_seq_steps": 0, "score_tokens": 0,
                      "prefill_s": 0.0, "decode_s": 0.0, "score_s": 0.0}

    # ----- prefill -------------------------------------------------------------------------------------------
    @torch.no_grad()
    def prefill(self, ids):
        """Run a prompt (batch 1); return (cache, log-probs of the next token)."""
        t0 = time.time()
        cache = DynamicCache()
        out = None
        for s in range(0, len(ids), self.chunk):
            chunk = torch.tensor([ids[s:s + self.chunk]], device=self.device)
            out = self.model(input_ids=chunk, past_key_values=cache, use_cache=True, logits_to_keep=1)
            cache = out.past_key_values
        lp = torch.log_softmax(out.logits[0, -1].float(), -1)
        self.stats["prefill_tokens"] += len(ids)
        self.stats["prefill_s"] += time.time() - t0
        return cache, lp

    # ----- constrained greedy decoding -----------------------------------------------------------------------
    @torch.no_grad()
    def _static_batch(self, prompts, max_len):
        """Prefill each prompt alone and copy its keys/values, left-padded, into one preallocated static cache
        (decoding then writes in place instead of re-concatenating the whole cache at every step)."""
        cfg = self.model.config
        B, lens = len(prompts), [len(p) for p in prompts]
        L = max(lens)
        cache = StaticCache(config=cfg, max_cache_len=max_len)
        cache.early_initialization(B, cfg.num_key_value_heads, cfg.head_dim, self.dtype, self.device)
        first = []
        for b, p in enumerate(prompts):
            c, lp = self.prefill(p)
            for dst, src in zip(cache.layers, c.layers):
                dst.keys[b, :, L - lens[b]:L].copy_(src.keys[0])
                dst.values[b, :, L - lens[b]:L].copy_(src.values[0])
            first.append(lp)
            del c
        for layer in cache.layers:
            if torch.is_tensor(layer.cumulative_length):
                layer.cumulative_length.fill_(L)
            else:
                layer.cumulative_length = L
        return cache, torch.stack(first), lens, L

    @torch.no_grad()
    def _dynamic_batch(self, prompts):
        """Fallback when the static cache API is unavailable: left-padded concatenation into a DynamicCache."""
        caches, first = [], []
        for p in prompts:
            c, lp = self.prefill(p)
            caches.append(c)
            first.append(lp)
        lens = [len(p) for p in prompts]
        L = max(lens)
        merged = []
        for li in range(len(caches[0].layers)):
            ks, vs = [], []
            for b, c in enumerate(caches):
                pad = L - lens[b]
                ks.append(torch.nn.functional.pad(c.layers[li].keys, (0, 0, pad, 0)))
                vs.append(torch.nn.functional.pad(c.layers[li].values, (0, 0, pad, 0)))
            merged.append((torch.cat(ks, 0), torch.cat(vs, 0)))
        del caches
        return make_cache(merged), torch.stack(first), lens, L

    @torch.no_grad()
    def greedy(self, prompts, max_new=F.MAX_OUT_TOKENS):
        """Constrained greedy decoding of a batch of prompts. Returns, per prompt, (tokens incl. end, sum logp)."""
        B = len(prompts)
        L0 = max(len(p) for p in prompts)
        static = self.use_static
        if static:
            try:
                cache, lp, lens, L = self._static_batch(prompts, L0 + max_new)
            except (TypeError, AttributeError, NotImplementedError):
                self.use_static = static = False
        if not static:
            cache, lp, lens, L = self._dynamic_batch(prompts)
        t0 = time.time()
        mask = torch.zeros((B, L + max_new), dtype=torch.long, device=self.device)
        for b in range(B):
            mask[b, L - lens[b]:L] = 1
        cons = [F.GridConstraint() for _ in range(B)]
        toks = [[] for _ in range(B)]
        score = [0.0] * B
        pos = torch.tensor(lens, device=self.device)
        V = lp.shape[-1]
        for step in range(max_new):
            allow = torch.zeros((B, V), dtype=torch.bool)
            live = []
            for b in range(B):
                a = cons[b].allowed()
                if a:
                    allow[b, list(a)] = True
                    live.append(b)
            if not live:
                break
            allow = allow.to(self.device, non_blocking=True)
            nxt = lp.masked_fill(~allow, float("-inf")).argmax(-1)
            chosen = lp.gather(1, nxt[:, None])[:, 0]
            both = torch.stack([nxt.float(), chosen]).tolist()
            nl = [int(v) for v in both[0]]
            for b in live:
                toks[b].append(nl[b])
                score[b] += both[1][b]
                cons[b].step(nl[b])
            if all(c.done for c in cons):
                break
            mask[:, L + step] = 1
            if static:
                out = self.model(input_ids=nxt[:, None], attention_mask=mask, position_ids=pos[:, None],
                                 past_key_values=cache, use_cache=True,
                                 cache_position=torch.tensor([L + step], device=self.device))
            else:
                out = self.model(input_ids=nxt[:, None], attention_mask=mask[:, :L + step + 1],
                                 position_ids=pos[:, None], past_key_values=cache, use_cache=True)
                cache = out.past_key_values
            pos = pos + 1
            lp = torch.log_softmax(out.logits[:, -1].float(), -1)
            self.stats["decode_steps"] += 1
            self.stats["decode_seq_steps"] += len(live)
        del cache
        self.stats["decode_s"] += time.time() - t0
        return [(toks[b], score[b]) for b in range(B)]

    # ----- teacher-forced scoring ----------------------------------------------------------------------------
    @torch.no_grad()
    def score(self, prompt, targets, cache=None, first_lp=None):
        """Sum of log-probs of each target token sequence after the prompt (prompt cache reused, cropped back)."""
        if cache is None:
            cache, first_lp = self.prefill(prompt)
        t0 = time.time()
        L = len(prompt)
        res = []
        for tg in targets:
            total = float(first_lp[tg[0]])
            if len(tg) > 1:
                x = torch.tensor([tg[:-1]], device=self.device)
                out = self.model(input_ids=x, past_key_values=cache, use_cache=True,
                                 position_ids=torch.arange(L, L + len(tg) - 1, device=self.device)[None])
                lps = torch.log_softmax(out.logits[0].float(), -1)
                total += float(lps.gather(1, torch.tensor(tg[1:], device=self.device)[:, None]).sum())
                cache = out.past_key_values
                cache.crop(-(len(tg) - 1))          # drop the target tokens again
            self.stats["score_tokens"] += len(tg)
            res.append(total)
        self.stats["score_s"] += time.time() - t0
        return res
