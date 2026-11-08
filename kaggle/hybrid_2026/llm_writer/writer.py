"""Program writers: a pretrained causal language model sampled through Hugging Face transformers (inference only,
no gradient, no adapter, no training of any kind), and a scripted mock for tests.

`HFWriter.sample(messages, n, ...)` returns n replies to one chat prompt. Memory-aware sampling: the prompt is
prefilled once per chunk, in slices of `prefill_chunk` tokens so that attention memory stays bounded (only the
last position's logits are computed), its key-value cache is repeated for the
chunk's sequences, and sequences are decoded with temperature and nucleus sampling from a seeded generator;
finished sequences leave the batch. The chunk size is set from the free GPU memory and the model's per-token cache
size, so a long prompt is sampled in several chunks rather than running out of memory. A reply stops at an
end-of-turn token or once its ```cora block is closed.

Every reply records its generated tokens, the prompt tokens and the GPU seconds of its chunk (shared equally), so
arms can be compared at matched generated tokens (design requirement 5).
"""
import hashlib
import re
import time
from dataclasses import dataclass, field


@dataclass
class Reply:
    text: str
    gen_tokens: int
    prompt_tokens: int
    gpu_s: float
    finished: bool
    seed: int
    note: str = ""


def seed_of(*parts):
    """A stable 31-bit seed from any parts (task id, arm, round, parent, ...)."""
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16) & 0x7FFFFFFF


FENCE = re.compile(r"```[a-zA-Z]*\s*\n.*?```", re.S)


class MockWriter:
    """Scripted replies for tests: `script(messages, n, seed) -> [text]`. Counts tokens as whitespace words."""
    label = "MOCK"
    sep = ""

    def __init__(self, script):
        self.script = script
        self.stats = {"calls": 0, "gen_tokens": 0, "prompt_tokens": 0, "gpu_s": 0.0}

    def sample(self, messages, n, max_new_tokens=600, temperature=0.8, top_p=0.95, seed=0):
        self.stats["calls"] += 1
        texts = list(self.script(messages, n, seed))[:n]
        plen = sum(len(m["content"].split()) for m in messages)
        out = []
        for t in texts:
            g = min(max_new_tokens, len(t.split()))
            self.stats["gen_tokens"] += g
            out.append(Reply(t, g, plen, 0.0, True, seed))
        self.stats["prompt_tokens"] += plen
        return out

    def count_tokens(self, messages):
        return sum(len(m["content"].split()) for m in messages)

    def close(self):
        pass


@dataclass
class HFWriter:
    model_dir: str
    label: str
    device: object = 0                     # a GPU index, "auto" (with max_memory), or "map" (explicit device_map)
    dtype: str = "bfloat16"
    max_context: int = 32768
    sep: str = ""                          # grid cell separator suited to the tokenizer
    max_memory: dict = None
    kv_margin_gb: float = 1.0
    prefill_chunk: int = 1024              # prompt tokens per prefill step (bounds attention memory)
    device_map: dict = None                # explicit module -> GPU placement when device == "map"
    stats: dict = field(default_factory=lambda: {"calls": 0, "gen_tokens": 0, "prompt_tokens": 0, "gpu_s": 0.0,
                                                 "chunks": 0, "too_long": 0, "peak_mem_gb": 0.0,
                                                 "deadline_stops": 0})
    deadline: float = None                 # absolute time.time(): decoding stops there (replies marked unfinished)

    def __post_init__(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        t0 = time.time()
        self.tok = AutoTokenizer.from_pretrained(self.model_dir)
        dt = {"bfloat16": torch.bfloat16, "float16": torch.float16}[self.dtype]
        kw = {"dtype": dt} if _accepts_dtype() else {"torch_dtype": dt}
        if self.device == "auto":
            kw["device_map"] = "auto"
            if self.max_memory:
                kw["max_memory"] = self.max_memory
        elif self.device == "map":
            kw["device_map"] = self.device_map
        else:
            kw["device_map"] = {"": int(self.device)}
        try:
            self.model = AutoModelForCausalLM.from_pretrained(self.model_dir, **kw)
        except ValueError as e:                            # no accelerate installed: load, then move to one GPU
            if "accelerate" not in str(e) or self.device in ("auto", "map"):
                raise
            kw.pop("device_map")
            self.model = AutoModelForCausalLM.from_pretrained(self.model_dir, **kw).to(f"cuda:{int(self.device)}")
        self.model.eval()
        self.load_s = round(time.time() - t0, 1)
        cfg = self.model.config
        cfg = getattr(cfg, "text_config", cfg)
        layers = cfg.num_hidden_layers
        kvh = getattr(cfg, "num_key_value_heads", None) or cfg.num_attention_heads
        hd = getattr(cfg, "head_dim", None) or cfg.hidden_size // cfg.num_attention_heads
        self.kv_bytes = layers * kvh * hd * 2 * (2 if self.dtype in ("bfloat16", "float16") else 4)
        eos = set()
        gc = getattr(self.model, "generation_config", None)
        for x in (getattr(gc, "eos_token_id", None), self.tok.eos_token_id):
            if isinstance(x, int):
                eos.add(x)
            elif isinstance(x, (list, tuple)):
                eos.update(int(v) for v in x)
        for name in ("<|im_end|>", "<|endoftext|>", "<|eot_id|>"):
            i = self.tok.convert_tokens_to_ids(name)
            if isinstance(i, int) and i >= 0 and i != self.tok.unk_token_id:
                eos.add(i)
        self.eos = eos
        self.first_device = next(self.model.parameters()).device

    # ------------------------------------------------------------------ prompts
    def prompt_ids(self, messages):
        try:
            text = self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                enable_thinking=False)
        except TypeError:
            text = self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return self.tok(text, return_tensors="pt", add_special_tokens=False)["input_ids"]

    def count_tokens(self, messages):
        return int(self.prompt_ids(messages).shape[1])

    def _free_bytes(self):
        torch = self.torch
        if self.device in ("auto", "map"):
            # the cache of every layer lives on that layer's GPU: the binding constraint is the GPU with the least
            # free memory per layer it holds, so use the minimum free memory times the number of GPUs, divided
            # evenly (layers are split evenly by explicit_map)
            free = min(torch.cuda.mem_get_info(d)[0] for d in range(torch.cuda.device_count())) * \
                torch.cuda.device_count()
        else:
            free = torch.cuda.mem_get_info(int(self.device))[0]
        n = torch.cuda.device_count() if self.device in ("auto", "map") else 1
        return max(0, free - int(n * self.kv_margin_gb * 1e9))

    # ------------------------------------------------------------------ sampling
    def sample(self, messages, n, max_new_tokens=600, temperature=0.8, top_p=0.95, seed=0):
        torch = self.torch
        self.stats["calls"] += 1
        ids = self.prompt_ids(messages)
        plen = int(ids.shape[1])
        if plen + max_new_tokens > self.max_context:
            self.stats["too_long"] += 1
            return [Reply("", 0, plen, 0.0, False, seed, "prompt_too_long")]
        # the prompt's cache exists once before it is repeated for the chunk (m + 1 copies at the peak), and each
        # sequence then grows by up to max_new tokens
        free = self._free_bytes() - plen * self.kv_bytes
        per_seq = (plen + max_new_tokens) * self.kv_bytes
        fit = max(1, int(free // max(1, per_seq)))
        out, k = [], 0
        while k < n:
            if self.deadline is not None and time.time() >= self.deadline:
                self.stats["deadline_stops"] += 1
                break
            m = min(n - k, fit)
            got = None
            while got is None:
                try:
                    got = self._chunk(ids, m, max_new_tokens, temperature, top_p, seed + 7919 * k)
                except torch.OutOfMemoryError:
                    self.stats["oom_retries"] = self.stats.get("oom_retries", 0) + 1
                    torch.cuda.empty_cache()
                    if m == 1:
                        got = [Reply("", 0, plen, 0.0, False, seed + 7919 * k, "out_of_memory")]
                    else:
                        m = max(1, m // 2)
                        fit = min(fit, m)
            out += got
            k += len(got) if got and got[0].note != "out_of_memory" else m
        return out

    def _chunk(self, ids, m, max_new, temperature, top_p, seed):
        torch = self.torch
        dev = self.first_device
        t0 = time.time()
        g = torch.Generator(device=dev)
        g.manual_seed(int(seed))
        self.stats["chunks"] += 1
        replies = [None] * m
        try:
            with torch.no_grad():
                ids = ids.to(dev)
                cache = None
                for i in range(0, ids.shape[1], self.prefill_chunk):
                    o = self.model(input_ids=ids[:, i:i + self.prefill_chunk], past_key_values=cache, use_cache=True,
                                   logits_to_keep=1)
                    cache = o.past_key_values
                logits = o.logits[:, -1, :].float()
                del o
                if m > 1:
                    try:
                        cache.batch_repeat_interleave(m)
                    except (AttributeError, NotImplementedError):
                        # caches without batch repetition (for example linear-attention layers): prefill the
                        # prompt once per sequence instead
                        cache = None
                        rep = ids.repeat(m, 1)
                        for i in range(0, rep.shape[1], self.prefill_chunk):
                            o = self.model(input_ids=rep[:, i:i + self.prefill_chunk], past_key_values=cache,
                                           use_cache=True, logits_to_keep=1)
                            cache = o.past_key_values
                        del o
                    logits = logits.repeat(m, 1)
                alive = list(range(m))
                gen = [[] for _ in range(m)]
                done = [False] * m
                for step in range(max_new):
                    if self.deadline is not None and time.time() >= self.deadline:
                        self.stats["deadline_stops"] += 1
                        break
                    nxt = _sample(torch, logits, temperature, top_p, g)
                    keep = []
                    for row, sidx in enumerate(alive):
                        if sidx < 0:
                            continue
                        t = int(nxt[row])
                        if t in self.eos:
                            done[sidx] = True
                            continue
                        gen[sidx].append(t)
                        keep.append(row)
                    if step % 8 == 7:
                        for row in list(keep):
                            sidx = alive[row]
                            if sidx < 0:
                                continue
                            txt = self.tok.decode(gen[sidx][-80:], skip_special_tokens=True)
                            if "```" in txt and _closed(self.tok.decode(gen[sidx], skip_special_tokens=True)):
                                done[sidx] = True
                                keep.remove(row)
                    if not keep:
                        break
                    if len(keep) < len(alive):
                        try:
                            # indices on the CPU: each layer's cache may live on a different GPU
                            cache.batch_select_indices(torch.tensor(keep, dtype=torch.long))
                            nxt = nxt[keep]
                            alive = [alive[r] for r in keep]
                        except (AttributeError, NotImplementedError):
                            # a cache that cannot drop rows: finished rows keep decoding and their tokens are
                            # discarded (their sequences are already complete)
                            alive = [a if r in keep else -1 for r, a in enumerate(alive)]
                    o = self.model(input_ids=nxt.view(-1, 1), past_key_values=cache, use_cache=True)
                    cache = o.past_key_values
                    logits = o.logits[:, -1, :].float()
                    del o
                del cache
            peak = torch.cuda.max_memory_allocated(dev) / 1e9 if torch.cuda.is_available() else 0.0
            self.stats["peak_mem_gb"] = max(self.stats["peak_mem_gb"], round(peak, 2))
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        dt = time.time() - t0
        self.stats["gpu_s"] += dt
        plen = int(ids.shape[1])
        self.stats["prompt_tokens"] += plen
        for i in range(m):
            text = self.tok.decode(gen[i], skip_special_tokens=True)
            self.stats["gen_tokens"] += len(gen[i])
            replies[i] = Reply(text, len(gen[i]), plen, dt / m, done[i], seed)
        return replies

    def close(self):
        torch = self.torch
        try:
            del self.model
        except AttributeError:
            pass
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def explicit_map(n_layers, gpus, prefix="model"):
    """A device_map that splits the decoder layers evenly over `gpus` (a list of GPU indices), embeddings on the
    first GPU, final norm and output head on the last; written out explicitly so the placement can be checked."""
    m = {f"{prefix}.embed_tokens": gpus[0], f"{prefix}.rotary_emb": gpus[0]}
    per = -(-n_layers // len(gpus))
    for i in range(n_layers):
        m[f"{prefix}.layers.{i}"] = gpus[min(len(gpus) - 1, i // per)]
    m[f"{prefix}.norm"] = gpus[-1]
    m["lm_head"] = gpus[-1]
    return m


def _closed(text):
    """True once a fenced block has been opened and closed."""
    return bool(FENCE.search(text))


def _sample(torch, logits, temperature, top_p, g):
    if temperature <= 0:
        return logits.argmax(dim=-1)
    probs = torch.softmax(logits / temperature, dim=-1)
    if top_p < 1.0:
        sp, si = torch.sort(probs, descending=True, dim=-1)
        cum = sp.cumsum(dim=-1)
        sp[(cum - sp) > top_p] = 0.0
        sp = sp / sp.sum(dim=-1, keepdim=True)
        pick = torch.multinomial(sp, 1, generator=g).squeeze(-1)
        return si.gather(-1, pick.view(-1, 1)).squeeze(-1)
    return torch.multinomial(probs, 1, generator=g).squeeze(-1)


def _accepts_dtype():
    """transformers 5 takes `dtype`; 4.x takes `torch_dtype`."""
    import transformers
    try:
        return int(transformers.__version__.split(".")[0]) >= 5
    except ValueError:
        return False
