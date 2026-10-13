"""CORA-NVG guides: given a failed native attempt, choose which cut view to
search next, or NO_CHANGE. Every guide sees only what `decision_input`
builds:
- the subset's training demonstrations;
- the task's unlabelled test inputs (the held-out INPUTS);
- the static census of the subset;
- the native failure trace on that subset, by condition.

`decision_input` has no access to any held-out output, the outcome, the
prediction hash, the task id or the family; tests/test_nvg.py checks this
with mutation tests.

Guides return a ranking of the option views (most promising first) and a
choice (a view, or None for NO_CHANGE).
"""
import hashlib
import json

import numpy as np

ORDER = ("S1", "S2", "S3", "S5", "S4", "S6", "S7")             # the native trial order
VIEW_TEXT = {
    "S1": "groups touching cells of the same colour (touching along an edge)",
    "S2": "groups touching cells of the same colour (touching along an edge or at a corner)",
    "S3": "groups touching cells of any colour (touching along an edge)",
    "S4": "groups touching cells of any colour (touching along an edge or at a corner)",
    "S5": "groups touching cells after choosing the background colour separately for each grid",
    "S6": "puts all cells of one colour into one group, even when they are far apart",
    "S7": "groups cells of any colour that are at most one empty cell apart",
}
STAGE_TEXT = {
    "segmentation": "no grouping method described the examples well enough to search",
    "matching": "objects in the inputs could not be matched to objects in the outputs",
    "selector": "no rule could select which objects change",
    "parameter": "no rule could set how the selected objects change",
    "loo": "a rule fitted all the examples, but re-deriving it with one example left out failed",
}
LABELS = "ABCDEFG"


def _grid_text(g):
    return "\n".join("".join(str(v) for v in row) for row in g)


def decision_input(train, unlabelled, census_sub, trace):
    """The complete input of a decision. `train` = the subset's
    (input, output) pairs; `unlabelled` = test inputs only; `census_sub` =
    the census record of that subset; `trace` = the native attempt's trace on
    that subset (None when the attempt is not available)."""
    options = [v for v in census_sub["cut"]]
    stats = {v: {"objects": census_sub["views"][v]["objects"], "coverage": round(census_sub["views"][v]["coverage"], 3),
                 "coherence": round(census_sub["views"][v]["coherence"], 3)} for v in census_sub["views"]}
    tr = None
    if trace is not None:
        ns, loo = trace.get("near_solve"), trace.get("loo")
        tr = {"stage": trace.get("failure_stage"), "fit_objects": trace.get("train_fit_objects"),
              "fit_pixels": trace.get("train_fit_pixels"),
              "near_view": ns["variant"] if ns else None,
              "near_fit_objects": ns["fit_objects"] if ns else None,
              "unexplained": ns["unexplained"] if ns else None,
              "conflicts": ns["conflicts"] if ns else None,
              "histogram": ns["histogram"] if ns else None,
              "loo": None if not loo else {"folds": loo["folds"], "passed": loo["passed"], "failed_pairs": loo["failed_pairs"]},
              "events": sorted(set(e.split(":")[0] for e in trace.get("events", [])))}
    return {"train": [[np.asarray(a).tolist(), np.asarray(b).tolist()] for a, b in train],
            "unlabelled": [np.asarray(a).tolist() for a in unlabelled],
            "searched": list(census_sub["kept"]), "options": options, "stats": stats, "trace": tr}


def input_sha(inp):
    return hashlib.sha256(json.dumps(inp, sort_keys=True).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- symbolic guides
def guide_B1(inp, **_):
    """Fixed-order failure fallback (KAAR/GPAR/ARGA-style; the PROMOTE rule)."""
    r = sorted(inp["options"], key=ORDER.index)
    return r, (r[0] if r else None)


def guide_B2(inp, **_):
    """Demonstrations only: the coarsest grouping first (fewest objects over the
    training inputs), ties in native order."""
    r = sorted(inp["options"], key=lambda v: (sum(inp["stats"][v]["objects"][:len(inp["train"])]), ORDER.index(v)))
    return r, (r[0] if r else None)


def guide_B3(inp, **_):
    """ARGA-style tabu: searched views are excluded (they are not options); the
    rest are ranked by training-only coverage x coherence, ties in native order."""
    r = sorted(inp["options"], key=lambda v: (-inp["stats"][v]["coverage"] * inp["stats"][v]["coherence"], ORDER.index(v)))
    return r, (r[0] if r else None)


def guide_R(inp, seed=0, **_):
    rng = np.random.default_rng(int(input_sha(inp), 16) % (2 ** 32) + seed)
    r = list(inp["options"])
    rng.shuffle(r)
    return r, (r[0] if r else None)


# ---------------------------------------------------------------- language-model guide
def prompt(inp, condition, perm_seed, shuffled_trace=None):
    """The preregistered prompt. Option labels are a fresh random permutation per
    decision (seeded by the input and perm_seed). View names never appear.
    Returns (text, label -> view)."""
    rng = np.random.default_rng(int(input_sha(inp), 16) % (2 ** 32) + 1000 * perm_seed)
    opts = list(inp["options"])
    rng.shuffle(opts)
    lab = {LABELS[i]: v for i, v in enumerate(opts)}
    n = len(inp["train"])
    lines = ["You are helping a program-search engine that solves grid puzzles. Each puzzle gives example input grids "
             "and their output grids; the engine looks for one rule that turns every input into its output. Before "
             "searching, the engine splits each grid into objects with a grouping method, and it can search only a few "
             "grouping methods.", "", "Digits are colours; 0 is the background."]
    for i, (a, b) in enumerate(inp["train"], 1):
        lines += ["", f"Example {i} input:", _grid_text(a), f"Example {i} output:", _grid_text(b)]
    for i, a in enumerate(inp["unlabelled"], 1):
        lines += ["", f"New input {i} (its output is unknown):", _grid_text(a)]
    lines += ["", "The engine already searched these grouping methods: "
              + "; ".join(VIEW_TEXT[v] for v in inp["searched"]) + ".",
              "It has not searched these candidate grouping methods:"]
    for L, v in lab.items():
        lines.append(f"{L}: {VIEW_TEXT[v]}. Objects per example input: "
                     + ", ".join(str(x) for x in inp["stats"][v]["objects"][:n]) + ".")
    tr = inp["trace"] if condition == "D" else (shuffled_trace if condition == "E" else None)
    if condition in ("D", "E") and tr is not None:
        lines += ["", "What happened when the engine searched (its failure record):",
                  "- outcome: " + STAGE_TEXT.get(tr["stage"], str(tr["stage"])) + "."]
        if tr["near_view"]:
            lines.append(f"- its best partial rule used the method that {VIEW_TEXT.get(tr['near_view'], 'is unknown')} and explained "
                         f"{round(100 * (tr['near_fit_objects'] or 0))}% of the objects; unexplained changes: {tr['unexplained']}.")
        if tr["conflicts"]:
            lines.append(f"- conflicting object selections: {tr['conflicts'].get('selector_conflicts', 0)}; conflicting "
                         f"change parameters: {tr['conflicts'].get('parameter_conflicts', 0)}.")
        if tr["histogram"]:
            lines.append("- kinds of change it saw: " + ", ".join(f"{k} {v}" for k, v in sorted(tr["histogram"].items())) + ".")
        if tr["loo"]:
            lines.append(f"- leave-one-out check: {tr['loo']['passed']} of {tr['loo']['folds']} re-derivations reproduced the "
                         "left-out example" + (f"; it failed when example(s) {', '.join(str(j + 1) for j in tr['loo']['failed_pairs'])} "
                                               "were left out" if tr["loo"]["failed_pairs"] else "") + ".")
    if condition == "F":
        lines += ["", "Diagnosis of the failure: a useful grouping method may have been excluded by the search limit "
                  "(status: suspected)."]
    lines += ["", "Which candidate grouping method should the engine search next? If none of them is likely to reveal "
              "the rule, answer N. Answer with a single letter."]
    return "\n".join(lines), lab


class LLMGuide:
    """Frozen causal LM; the choice is the highest-scoring answer token among the
    option labels and N (no sampling)."""

    def __init__(self, path, device="cuda:0"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.float16).to(device).eval()
        self.device = device
        self.label_ids = {}
        for L in LABELS + "N":
            ids = self.tok.encode(" " + L, add_special_tokens=False)
            assert len(ids) == 1, (L, ids)
            self.label_ids[L] = ids[0]

    #: Qwen2.5's own chat template, rendered for one user turn with its default
    #: system message. It was checked equal to tokenizer_config.json's template on
    #: 2026-10-13; it is written out because the shared environment's jinja2
    #: (3.0.3) is older than transformers requires, and no package of another
    #: project's environment is changed.
    TEMPLATE = ("<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n"
                "<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\nAnswer:")

    def score(self, text, labels):
        s = self.TEMPLATE.format(text=text)
        ids = self.tok(s, return_tensors="pt").input_ids.to(self.device)
        with self.torch.no_grad():
            logits = self.model(ids).logits[0, -1].float()
        lp = self.torch.log_softmax(logits, -1)
        return {L: float(lp[self.label_ids[L]]) for L in labels}, int(ids.shape[1])

    def __call__(self, inp, condition, perm_seed=0, shuffled_trace=None):
        text, lab = prompt(inp, condition, perm_seed, shuffled_trace)
        scores, n_tokens = self.score(text, list(lab) + ["N"])
        ranked = sorted(lab, key=lambda L: -scores[L])
        best = max(scores, key=scores.get)
        return [lab[L] for L in ranked], (None if best == "N" else lab[best]), \
            {"scores": scores, "tokens": n_tokens, "labels": lab, "prompt_sha": hashlib.sha256(text.encode()).hexdigest()[:16]}


# ---------------------------------------------------------------- counterfactual-transition form
CF_QUESTION = ("If the engine searched candidate {L} next, what would most likely happen? "
               "a: it would find a rule that fits all the examples and also works on new inputs; "
               "b: it would find nothing new; "
               "c: it would find a rule that fits these examples but fails on new inputs. "
               "Answer with a single letter: a, b or c.")


def cf_prompt(inp, condition, perm_seed, label, shuffled_trace=None):
    base, lab = prompt(inp, condition, perm_seed, shuffled_trace)
    head = base[:base.rindex("Which candidate grouping method")]
    return head + CF_QUESTION.format(L=label), lab


def cf_call(llm, inp, condition, perm_seed=0, shuffled_trace=None):
    """Per option, the predicted transition; views ranked by P(a) normalized
    over a/b/c. The top view is chosen only if a is its most likely answer,
    otherwise NO_CHANGE. Only the engine's own run (the reference) decides
    what actually happens."""
    _, lab = prompt(inp, condition[0], perm_seed, shuffled_trace)
    ids = {}
    for x in "abc":
        t = llm.tok.encode(" " + x, add_special_tokens=False)
        assert len(t) == 1, (x, t)
        ids[x] = t[0]
    pa, tokens, best = {}, 0, {}
    for L, v in lab.items():
        text, _ = cf_prompt(inp, condition[0], perm_seed, L, shuffled_trace)
        s = llm.TEMPLATE.format(text=text)
        enc = llm.tok(s, return_tensors="pt").input_ids.to(llm.device)
        with llm.torch.no_grad():
            lp = llm.torch.log_softmax(llm.model(enc).logits[0, -1].float(), -1)
        p = np.exp(np.array([float(lp[ids[x]]) for x in "abc"]))
        p = p / p.sum()
        pa[v], best[v], tokens = float(p[0]), "abc"[int(np.argmax(p))], tokens + int(enc.shape[1])
    r = sorted(lab.values(), key=lambda v: -pa[v])
    choice = r[0] if r and best[r[0]] == "a" else None
    return r, choice, {"p_a": pa, "argmax": best, "tokens": tokens}
