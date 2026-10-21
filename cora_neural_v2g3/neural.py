"""ncv2-g3 neural interfaces (Phase 4): how pretrained grid representations may enter executable program search.
INTERFACES AND CONTROLS ONLY. Nothing here loads or trains a model; tests use synthetic hidden states.

The source of representations is the Apache-2.0 Qwen3-4B checkpoint used by the v1 pilot. Its vocabulary is 16 grid
symbols (records/NEURAL_CORA_V2_LICENSE_AND_PRETRAINING_AUDIT.md section 2): it cannot emit CORA program tokens, so
programs come from a separate structured decoder whose every output is typechecked, compiled and executed.

A. **Alignment and pooling.** `serialize` is v1's `prior.task_text` (NVARC's format). Every grid digit is one token
   whose id equals the colour, so `align` maps each cell (grid, row, column) to a token position exactly, and checks
   it. `pool` averages (or max-pools) the hidden states of an object's cells into an OBJECT SLOT. The model is causal:
   a demonstration's states never see later grids, so `serialize(task, reread=True)` appends a second copy of every
   demonstration input after the test input. Which segment pools better must be measured, not assumed.
B. **Joint rule scoring.** `rule_features` describes a whole conditional rule (selector, action, binding) in its task:
   the C+H prior, the coupling bonus, its execution delta when probed, one-hot selector and action kinds, and the mean
   object slot over the objects the selector actually picks (scene.selections). A `RuleScorer` maps it to a residual.
C. **Typed sketch decoding.** `GrammarAutomaton` is built from `rast.SIGNATURES`. At every step it lists the legal
   next tokens (an op of the expected type, a literal of the expected kind, or a typed hole), so any decoded sequence
   is a well-typed sketch. Holes are filled by symbolic completion (`complete_sketch`), as the joint proposer spec
   (docs/NEURAL_CORA_JOINT_RULE_PROPOSER_SPEC.md) describes.
D. **Residual ranking.** `residual_rescore(scorer)` plugs into `JointConfig.rescore`: score = C+H prior + r_theta.
   With `ZeroScorer` the order is exactly C+H.
E. **Neural evidence is untrusted.** `Proposal`s from any decoder enter the shared evaluator like every other
   candidate (`search(..., proposals=...)`): ill-typed ones are counted and dropped, and only execution decides a fit.

`ARMS` names the comparison arms for a future, separately frozen experiment, at equal candidate and CPU budgets.
"""
import random
from dataclasses import dataclass, field

import numpy as np

from cora_neural_v2 import rast as R
from cora_neural_v2.rast import ASTError, N

DIGITS = tuple(range(10))

ARMS = {
    "ch": "C+H alone: the ncv2-g3 joint stream and the ncv2-g2 stream, zero residual",
    "ch_hand": "C+H + a residual learned from hand features only (rule_features without slots)",
    "ch_qwen": "C+H + a residual learned from hand features and Qwen object slots",
    "qwen_sketch": "joint Qwen sketch proposals + symbolic completion, alongside C+H",
    "shuffled_qwen": "ch_qwen with object slots taken from another task (ShuffledSlots)",
    "untrained": "the same heads, randomly initialised and never trained (UntrainedScorer / UntrainedSketchDecoder)",
}


# ------------------------------------------------------------------ A. alignment and pooling
def g2s(g):
    return "\n".join("".join(str(int(v)) for v in row) for row in g)


def grids(task, reread=False):
    """[(role, index, grid)] in serialization order."""
    out = []
    for i, (a, b) in enumerate(task["train"]):
        out += [("demo_in", i, a), ("demo_out", i, b)]
    out.append(("test_in", 0, task["test_inputs"][0]))
    if reread:
        out += [("reread_in", i, a) for i, (a, _) in enumerate(task["train"])]
    return out


def serialize(task, reread=False):
    """v1's prior.task_text (rows of digits joined by newlines, in chat turns), optionally plus a re-read block."""
    t = "".join(f"<|im_start|>user\n{g2s(a)}<|im_end|><|im_start|>assistant\n{g2s(b)}<|im_end|>" for a, b in task["train"])
    t += f"<|im_start|>user\n{g2s(task['test_inputs'][0])}<|im_end|>"
    if reread:
        t += "".join(f"<|im_start|>user\n{g2s(a)}<|im_end|>" for a, _ in task["train"])
    return t


def align(task, ids, reread=False):
    """{(role, index, row, col): token position}. Digit tokens have ids 0-9 equal to the colour and no other token
    does (the audited property), so the k-th digit token is the k-th cell in serialization order. Raises ValueError
    on any disagreement."""
    pos = [p for p, t in enumerate(ids) if int(t) in DIGITS]
    cells = [(role, i, r, c, int(v)) for role, i, g in grids(task, reread) for r, row in enumerate(g) for c, v in enumerate(row)]
    if len(pos) != len(cells):
        raise ValueError(f"{len(pos)} digit tokens for {len(cells)} cells")
    out = {}
    for p, (role, i, r, c, v) in zip(pos, cells):
        if int(ids[p]) != v:
            raise ValueError(f"token {p} is {ids[p]}, cell {(role, i, r, c)} is {v}")
        out[(role, i, r, c)] = p
    return out


def pool(states, amap, role, index, cells, how="mean"):
    """An object slot: the pooled hidden states of `cells` of grid (role, index)."""
    rows = states[[amap[(role, index, r, c)] for r, c in sorted(cells)]]
    return rows.mean(0) if how == "mean" else rows.max(0)


def object_slots(task, states, ids, view="S1", role="demo_in", reread=False, how="mean"):
    """{(demo index, object index): slot} over the demonstration inputs' native objects (or their re-read copies)."""
    from cora_neural_v2g3.scene import native_objects
    amap = align(task, ids, reread)
    out = {}
    for i, (a, _) in enumerate(task["train"]):
        for j, o in enumerate(native_objects(a, view)[0]):
            out[(i, j)] = pool(states, amap, role, i, o.cells, how)
    return out


# ------------------------------------------------------------------ B. joint rule features and scorers
SEL_KINDS = ("true", "color", "size", "size_rank", "bool", "exists", "other")
ACT_KINDS = ("keep", "delete", "recolour", "move", "copy", "line", "geometry", "bind", "other")


def _sel_kind(sel):
    if sel.op == "true":
        return "true"
    if sel.op == "exists":
        return "exists"
    if sel.op == "test":
        f = sel.args[0]
        return "color" if f == "color" else "size" if f == "size" else "size_rank" if f.startswith("size_rank") else "bool"
    return "other"


def _act_kind(kind):
    k = kind[0] if isinstance(kind, tuple) else kind
    for name, members in (("recolour", ("recolour", "recolour_ref", "recolour_map", "recolour_rel", "recolour_freq",
                                        "recolour_featmap", "paint")),
                          ("move", ("move_vec", "move_rel", "move_rel2", "move_to", "geometry_shift")),
                          ("copy", ("copy_off", "copy", "copy2", "extract")), ("line", ("line", "connect", "connect2"))):
        if k in members:
            return name
    return k if k in ACT_KINDS else "other"


def rule_features(rule, prior, key, picks=None, slots=None, totals=None, slot_dim=0):
    """A fixed-length vector for one whole conditional rule. `picks` (per demonstration object indices the selector
    picks) and `slots` ({(demo, object): vector}) add the mean slot of the selected objects; `totals` (fixed, broken,
    remaining) adds its probe delta when it has been executed."""
    sel = rule.args[1] if rule.op == "rule_with" else rule.args[0]
    v = [prior, float(rule.op == "rule_with")]
    v += [float(_sel_kind(sel) == k) for k in SEL_KINDS]
    v += [float(_act_kind(key[1]) == k) for k in ACT_KINDS]
    t = totals or (0, 0, 0)
    tot = max(1, sum(t))
    v += [t[0] / tot, t[1] / tot, t[2] / tot, float(totals is not None)]
    if slot_dim:
        chosen = [slots[(i, j)] for i, p in enumerate(picks or []) if p for j in p if (i, j) in (slots or {})]
        v += list(np.mean(chosen, 0)) if chosen else [0.0] * slot_dim
    return np.asarray(v, dtype=np.float64)


class ZeroScorer:
    """r_theta = 0: the C+H order, unchanged."""

    def __call__(self, x):
        return 0.0


@dataclass
class LinearScorer:
    weights: np.ndarray
    bias: float = 0.0

    def __call__(self, x):
        return float(np.dot(self.weights[:len(x)], x) + self.bias)


@dataclass
class UntrainedScorer:
    """A one-hidden-layer MLP with a fixed random initialisation, never trained (the untrained control)."""
    in_dim: int
    hidden: int = 32
    seed: int = 0
    w1: np.ndarray = field(init=False)
    w2: np.ndarray = field(init=False)

    def __post_init__(self):
        rng = np.random.default_rng(self.seed)
        self.w1 = rng.normal(0, 1 / np.sqrt(self.in_dim), (self.hidden, self.in_dim))
        self.w2 = rng.normal(0, 1 / np.sqrt(self.hidden), self.hidden)

    def __call__(self, x):
        return float(self.w2 @ np.tanh(self.w1 @ x))


@dataclass
class ShuffledSlots:
    """The shuffled-representation control: each task receives the slots of another task in a fixed derangement of
    the task list, so slots keep their distribution but lose their task."""
    task_ids: list
    seed: int = 0

    def partner(self, task_id):
        s = sorted(self.task_ids)
        if len(s) < 2:
            return task_id
        random.Random(self.seed).shuffle(s)
        return s[(s.index(task_id) + 1) % len(s)]         # the next task in a shuffled cycle: never itself


def residual_rescore(scorer, features_fn):
    """A `JointConfig.rescore` hook: prior + scorer(features_fn(rule, prior, key))."""
    def rescore(view, pool):
        return [prior + scorer(features_fn(rule, prior, key)) for rule, prior, key in pool]
    return rescore


# ------------------------------------------------------------------ C. the grammar automaton
@dataclass
class Vocab:
    """The literals a decoder may emit, e.g. copied from the task's evidence (colours, vectors, sizes)."""
    ints: tuple = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
    features: tuple = ("color", "size", "is_line", "is_rectangle", "has_hole", "touches_border")
    relations: tuple = ("adjacent", "inside", "contains")
    values: tuple = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, True, False)
    max_list: int = 2
    allow_holes: bool = True


class GrammarAutomaton:
    """Pre-order decoding of a typed AST. State: a stack of pending slots, each a TYPE or a literal kind. Tokens:
    ("op", name), ("hole", TYPE), ("lit", value), ("len", k). Ops with argument kinds the automaton does not decode
    (bindings, var, pairs, fpairs, values) are not offered, so every finished sequence typechecks."""

    UNSUPPORTED = ("bindings", "var", "pairs", "fpairs", "values")

    def __init__(self, vocab=None, root="PROGRAM"):
        self.vocab = vocab or Vocab()
        self.ops = {}
        for op, (rtype, kinds) in R.SIGNATURES.items():
            if op == "hole" or rtype is None or any(k in self.UNSUPPORTED for k in kinds):
                continue
            self.ops.setdefault(rtype, []).append(op)
        self.root = root

    def start(self):
        return [("slot", self.root)], []                 # (pending stack, output tokens)

    def legal(self, state):
        stack, _ = state
        if not stack:
            return []
        kind = stack[-1][1]
        v = self.vocab
        if kind in R.TYPES:
            toks = [("op", o) for o in self.ops.get(kind, [])]
            return toks + ([("hole", kind)] if v.allow_holes and kind != self.root else [])
        if kind.startswith("list"):
            lo = 1 if kind.startswith("list+") else 0
            return [("len", k) for k in range(lo, v.max_list + 1)]
        if kind == "int":
            return [("lit", i) for i in v.ints]
        if kind.startswith("sym:"):
            return [("lit", s) for s in R.SYMBOL_SETS[kind[4:]]]
        if kind == "feature":
            return [("lit", f) for f in v.features]
        if kind == "relation":
            return [("lit", r) for r in v.relations]
        if kind == "cmp":
            return [("lit", c) for c in R.CMPS]
        if kind == "value":
            return [("lit", x) for x in v.values]
        raise ASTError(f"no tokens for kind {kind}")

    def step(self, state, tok):
        if tok not in self.legal(state):
            raise ASTError(f"illegal token {tok}")
        stack, out = list(state[0]), list(state[1]) + [tok]
        _, kind = stack.pop()
        if tok[0] == "op":
            stack += [("slot", k) for k in reversed(R.SIGNATURES[tok[1]][1])]
        elif tok[0] == "len":
            stack += [("slot", kind.split(":", 1)[1])] * tok[1]
        return stack, out

    def done(self, state):
        return not state[0]

    def build(self, tokens):
        """Tokens -> AST (the inverse of pre-order decoding)."""
        it = iter(tokens)

        def read(kind):
            tok = next(it)
            if tok[0] == "hole":
                return N("hole", (tok[1],))
            if tok[0] == "op":
                return N(tok[1], tuple(read(k) for k in R.SIGNATURES[tok[1]][1]))
            if tok[0] == "len":
                return tuple(read(kind.split(":", 1)[1]) for _ in range(tok[1]))
            return tok[1]
        return read(self.root)


def decode(automaton, choose, max_steps=200):
    """Decode one sketch; `choose(legal tokens, state)` picks the next token (a model's masked argmax or sample).
    Returns the AST, or None if `max_steps` runs out."""
    st = automaton.start()
    for _ in range(max_steps):
        if automaton.done(st):
            return automaton.build(st[1])
        st = automaton.step(st, choose(automaton.legal(st), st))
    return None


@dataclass
class UntrainedSketchDecoder:
    """The untrained control: uniform choice among legal tokens, preferring holes and leaves as depth grows."""
    seed: int = 0
    vocab: Vocab = field(default_factory=Vocab)

    def propose(self, task, k):
        rng = random.Random(self.seed)
        aut = GrammarAutomaton(self.vocab)
        out = []
        for _ in range(k * 4):
            def choose(legal, st):
                deep = len(st[1]) > 12
                leafy = [t for t in legal if t[0] in ("hole", "lit") or (t[0] == "len" and t[1] <= 1)]
                return rng.choice(leafy if deep and leafy else legal)
            s = decode(aut, choose)
            if s is not None:
                out.append(s)
            if len(out) >= k:
                break
        return out


# ------------------------------------------------------------------ E. untrusted proposals
@dataclass
class Proposal:
    program: N                                           # complete, or a sketch with holes
    source: str
    confidence: float = 0.0                              # orders proposals; never decides a fit


def admit(p):
    """Typecheck a proposal with the ncv2-g2 grammar (holes allowed). Returns (program or None, reason)."""
    from cora_neural_v2g2 import grammar as G
    try:
        G.typecheck(p.program)
    except (ASTError, AttributeError, TypeError) as e:
        return None, f"ill_typed: {e}"
    return p.program, "ok"


def complete_sketch(sketch, pool_by_view, per_hole=8):
    """Fill a program sketch's rule holes from the joint rule pools (symbolic completion), best prior first.

    Supported holes: a whole RULE, a rule's PRED (selector) or ACTION, the view, the default and the render. Other holes
    are left unfilled (such a candidate is ill-typed for execution and is counted as such)."""
    if not (isinstance(sketch, N) and sketch.op == "program"):
        yield sketch
        return
    view, rules, default, render = sketch.args
    views = [view] if not _hole(view) else list(pool_by_view)
    defaults = [default] if not _hole(default) else ["keep", "delete"]
    renders = [render] if not _hole(render) else [N("same_as_input", ())]
    for v in views:
        if v not in pool_by_view:
            continue
        pool = pool_by_view[v]
        options = []
        for r in rules:
            if _hole(r):
                options.append([p[0] for p in pool[:per_hole]])
            elif r.op == "rule" and (_hole(r.args[0]) or _hole(r.args[1])):
                sel, act = r.args
                match = [p[0] for p in pool if p[0].op == "rule" and (_hole(sel) or p[0].args[0] == sel)
                         and (_hole(act) or p[0].args[1] == act)]
                options.append(match[:per_hole])
            else:
                options.append([r])
        for combo in _product(options):
            for d in defaults:
                for rd in renders:
                    yield N("program", (v, tuple(combo), d, rd))


def _hole(x):
    return isinstance(x, N) and x.op == "hole"


def _product(options):
    if not options:
        yield ()
        return
    for head in options[0]:
        for tail in _product(options[1:]):
            yield (head,) + tail
