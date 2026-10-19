"""The typed hypothesis language of Neural-CORA v1 (grammar ncv1-g0) and its compiler to native CORA programs.

A hypothesis is

    Segment(variant) -> [Select(selector) -> Action(params)] x 1..2 -> default action -> render (same size)

with first-match rule semantics, exactly native CORA's `ObjectProgram`. `compile_native` lowers a hypothesis to the
native JSON dict, and native `render_program` executes it unchanged. This module defines no new operator.

Typed components:
- **representation**: one of native's 7 segmentation views (S1-S7);
- **select**: an applicability predicate over native object features (colour, size, size rank, border, shape tests);
- **program**: one native action per rule.
  - Identity: keep.
  - Non-additive: delete, recolour, translate by a constant vector, slide until blocked, reflect.
  - Additive: fill_line, a line through the object's centroid to the border. Native's inducer never proposes it.
- **colour**: a typed constant inside recolour and fill_line;
- **default**: keep or delete the objects no rule selects;
- **assumptions**: output grid size equals input size.

`Hypothesis` also carries provenance (origin), demonstration evidence, uncertainty and cost. These bookkeeping fields
never change what the hypothesis computes. No task id, answer or lookup table can enter a hypothesis.
"""
import hashlib
import json
from dataclasses import dataclass, field

GRAMMAR_VERSION = "ncv1-g0"
VARIANTS = ("S1", "S2", "S3", "S5", "S4", "S6", "S7")        # native trial order
COLOURS = tuple(range(1, 10))
SELECTORS = ((("true", None),)
             + tuple(("color", c) for c in COLOURS)
             + tuple(("size", k) for k in range(1, 13))
             + (("size_rank", 0), ("size_rank_reversed", 0), ("touches_border", True), ("touches_border", False),
                ("is_line", True), ("is_rectangle", True), ("has_hole", True), ("is_unique_color", True),
                ("is_unique_size", True)))
VECTORS = tuple((dr, dc) for dr in range(-3, 4) for dc in range(-3, 4) if (dr, dc) != (0, 0))
DIRECTIONS = ("up", "down", "left", "right")
LINE_AXES = ("horizontal", "vertical", "both")
REFLECT_AXES = ("horizontal", "vertical")
ACTIONS = ((("keep",), ("delete",))
           + tuple(("recolor", c) for c in COLOURS)
           + tuple(("translate", dr, dc) for dr, dc in VECTORS)
           + tuple(("slide", d) for d in DIRECTIONS)
           + tuple(("fill_line", a, c) for a in LINE_AXES for c in COLOURS)
           + tuple(("reflect", a) for a in REFLECT_AXES))
DEFAULTS = ("keep", "delete")
ADDITIVE = frozenset({"fill_line"})
NON_ADDITIVE = frozenset({"delete", "recolor", "translate", "slide", "reflect"})
IDENTITY = frozenset({"keep"})
SEL_INDEX = {s: i for i, s in enumerate(SELECTORS)}
ACT_INDEX = {a: i for i, a in enumerate(ACTIONS)}
VAR_INDEX = {v: i for i, v in enumerate(VARIANTS)}


@dataclass(frozen=True)
class Rule:
    selector: tuple
    action: tuple

    def __post_init__(self):
        assert self.selector in SEL_INDEX, f"selector not in {GRAMMAR_VERSION}: {self.selector}"
        assert self.action in ACT_INDEX, f"action not in {GRAMMAR_VERSION}: {self.action}"


@dataclass
class Hypothesis:
    variant: str
    rules: tuple
    default: str = "keep"
    origin: dict = field(default_factory=dict)        # proposer, model/adapter hash, grammar version, fold
    evidence: dict = field(default_factory=dict)      # demonstration fit, fold observations
    uncertainty: dict = field(default_factory=dict)   # alternative consistent predictions, missing evidence
    cost: dict = field(default_factory=dict)          # executions, cpu seconds, model seconds

    def __post_init__(self):
        assert self.variant in VAR_INDEX and self.default in DEFAULTS and 1 <= len(self.rules) <= 2
        self.rules = tuple(r if isinstance(r, Rule) else Rule(tuple(r[0]), tuple(r[1])) for r in self.rules)

    def key(self):
        """The semantic identity: two hypotheses with equal keys compute the same function."""
        return (self.variant, tuple((r.selector, r.action) for r in self.rules), self.default)

    def program_sha(self):
        return hashlib.sha256(json.dumps(compile_native(self), sort_keys=True).encode()).hexdigest()[:16]

    def to_dict(self):
        return {"grammar": GRAMMAR_VERSION, "variant": self.variant,
                "rules": [[list(r.selector), list(r.action)] for r in self.rules], "default": self.default,
                "origin": self.origin, "evidence": self.evidence, "uncertainty": self.uncertainty, "cost": self.cost}

    @staticmethod
    def from_dict(d):
        assert d["grammar"] == GRAMMAR_VERSION
        rules = tuple(Rule(_tup(s), _tup(a)) for s, a in d["rules"])
        return Hypothesis(d["variant"], rules, d["default"], dict(d.get("origin", {})), dict(d.get("evidence", {})),
                          dict(d.get("uncertainty", {})), dict(d.get("cost", {})))

    def kinds(self):
        return tuple(r.action[0] for r in self.rules)

    def describe(self):
        parts = [f"view {self.variant}"]
        for r in self.rules:
            parts.append(f"if {_sel_text(r.selector)}: {_act_text(r.action)}")
        parts.append(f"otherwise {self.default}")
        return "; ".join(parts)


def _tup(x):
    return tuple(None if v is None else v for v in x)


def _sel_text(s):
    k, v = s
    return "always" if k == "true" else f"{k} == {v}"


def _act_text(a):
    return " ".join(str(x) for x in a)


def _pred(sel):
    kind, val = sel
    if kind == "true":
        return {"expr_class": "PredExpr", "op": "true", "args": []}, 0
    return {"expr_class": "PredExpr", "op": "test", "args": [kind, "==", val]}, 1


def _colour(c):
    return {"expr_class": "ColorExpr", "op": "const", "args": [int(c)]}


def _axis(a):
    return {"expr_class": "AxisExpr", "op": "const", "args": [a]}


def _action(act):
    t = act[0]
    if t == "keep":
        return {"delta_type": "keep", "params": {}, "parameter_class": "constant"}
    if t == "delete":
        return {"delta_type": "delete", "params": {}, "parameter_class": "constant"}
    if t == "recolor":
        return {"delta_type": "recolor", "params": {"color": _colour(act[1])}, "parameter_class": "constant"}
    if t == "translate":
        return {"delta_type": "translate", "parameter_class": "constant",
                "params": {"vector": {"expr_class": "VecExpr", "op": "const", "args": [int(act[1]), int(act[2])]}}}
    if t == "slide":
        return {"delta_type": "translate", "parameter_class": "relational",
                "params": {"vector": {"expr_class": "VecExpr", "op": "slide_vector", "args": [act[1]]}}}
    if t == "fill_line":
        return {"delta_type": "fill_line", "parameter_class": "constant",
                "params": {"axis": _axis(act[1]), "color": _colour(act[2]), "extent": _axis("to_border")}}
    if t == "reflect":
        return {"delta_type": "reflect", "params": {"axis": _axis(act[1])}, "parameter_class": "constant"}
    raise ValueError(f"unknown action {act}")


def compile_native(h):
    """The native ObjectProgram dict for `h` (deterministic; reads only the hypothesis)."""
    rules = []
    for r in h.rules:
        pred, lit = _pred(r.selector)
        rules.append({"selector": {"predicate": pred, "literals": lit}, "action": _action(r.action)})
    return {"segmentation_variant": h.variant, "rules": rules,
            "default_action": {"delta_type": h.default, "params": {}, "parameter_class": "constant"},
            "output_spec": {"mode": "same_as_input", "region": None, "height": None, "width": None,
                            "background": None, "fill": None},
            "library_operators_used": []}
