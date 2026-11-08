"""The typed hypothesis that enters CORA from any proposer, and the structured-head format a neural decoder emits.

A `Hypothesis` is untrusted. Its `source` says what produced it:
- MOCK: a fixed test proposer (interface verification only; never a result);
- UNTRAINED_NEURAL: a neural head with random or no weights (a control);
- TRAINED_NEURAL: a neural head with trained weights (its `weights` field holds the weights' sha256);
- EXTRACTED_FROM_NEURAL_GRID: a CORA program constructed to reproduce a neural model's predicted grid (route A);
- SYMBOLIC: CORA's own search.
Only execution (execute.py) decides whether a hypothesis fits; `confidence` only orders proposals.

**Structured-head format** (what a program decoder outputs; `from_structured` turns it into CORA's own typed AST, so
there is no second interpreter):

    {"view": "S2",
     "rules": [{"selector": {"test": ["color", "==", 2]},
                "action": {"ray": ["NW"], "stop": "through", "color": "own"}}]}

Selectors: {"true": true} | {"test": [feature, cmp, value]} | {"and": [sel, sel]} | {"exists": [relation, sel]}.
Native actions: {"recolor": c} | {"translate": [dr, dc]} | {"delete": true}. Representation-aware actions (the
version 4 layer): {"part": kind, "color": c or "own"} | {"ray": [direction names], "stop": "obstacle" or "through",
"color": c or "own"}. Native rules run first (first match per object), then part and ray rules, in order.
Programs may also be given as {"sexpr": "(program S1 ...)"} in CORA's S-expression syntax.
"""
from dataclasses import dataclass

from cora_neural_v2.rast import N, to_sexpr
from cora_neural_v2g4 import parts as PT
from cora_neural_v2g4 import program as PG

SOURCES = ("MOCK", "UNTRAINED_NEURAL", "TRAINED_NEURAL", "EXTRACTED_FROM_NEURAL_GRID", "SYMBOLIC")
KINDS = ("program", "sketch", "representation", "revision")
DIR_NAMES = {"E": (0, 1), "W": (0, -1), "S": (1, 0), "N": (-1, 0), "SE": (1, 1), "SW": (1, -1), "NE": (-1, 1),
             "NW": (-1, -1)}
DIR_OF = {v: k for k, v in DIR_NAMES.items()}
VIEWS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")


class SchemaError(ValueError):
    pass


@dataclass
class Hypothesis:
    kind: str
    payload: object                  # program: an AST (rast N) or a G4Program; sketch: an AST with holes
    source: str
    proposer: str = ""
    confidence: float = 0.0
    weights: str = ""                # sha256 of trained weights (TRAINED_NEURAL only)
    note: str = ""

    def __post_init__(self):
        if self.kind not in KINDS or self.source not in SOURCES:
            raise SchemaError(f"bad kind or source: {self.kind}, {self.source}")
        if self.source == "TRAINED_NEURAL" and not self.weights:
            raise SchemaError("a TRAINED_NEURAL hypothesis must name its weights")

    def key(self):
        return (self.kind, render(self.payload))


def render(program):
    """One S-expression for a native program or a G4 program (for provenance and equality)."""
    if isinstance(program, PG.G4Program):
        from cora_neural_v2g4 import construct as C
        return C.sexpr(program)
    return to_sexpr(program)


# ------------------------------------------------------------------ structured head -> typed AST
def _selector(d):
    if not isinstance(d, dict) or len(d) != 1:
        raise SchemaError(f"selector must be a one-key object: {d!r}")
    (k, v), = d.items()
    if k == "true":
        return N("true", ())
    if k == "test":
        f, cmp, val = v
        return N("test", (f, cmp, val))
    if k == "and":
        a, b = v
        return N("and", (_selector(a), _selector(b)))
    if k == "exists":
        rel, inner = v
        return N("exists", (rel, _selector(inner)))
    raise SchemaError(f"unknown selector {k}")


def _native_action(d):
    if "recolor" in d:
        return N("recolor", (N("color", (int(d["recolor"]),)),))
    if "translate" in d:
        dr, dc = d["translate"]
        return N("translate", (N("vec", (int(dr), int(dc))),))
    if "delete" in d:
        return N("delete", ())
    return None


def _colour(c):
    if c == "own":
        return "own"
    c = int(c)
    if not 0 <= c <= 9:
        raise SchemaError(f"colour out of range: {c}")
    return c


def from_structured(d):
    """Structured-head output (dict) -> a native program AST, or a G4Program when part or ray rules are present."""
    if "sexpr" in d:
        from cora_neural_v2g2 import grammar as G
        return G.parse(d["sexpr"])
    view = d.get("view", "S1")
    if view not in VIEWS:
        raise SchemaError(f"unknown view {view}")
    native, layer = [], []
    for r in d.get("rules", ()):
        sel = _selector(r["selector"])
        act = r["action"]
        nat = _native_action(act)
        if nat is not None:
            native.append(N("rule", (sel, nat)))
        elif "part" in act:
            if act["part"] not in PT.KINDS:
                raise SchemaError(f"unknown part kind {act['part']}")
            layer.append(PG.PartRule(sel, act["part"], _colour(act.get("color", "own"))))
        elif "ray" in act:
            dirs = tuple(sorted(DIR_NAMES[x] for x in act["ray"]))
            if act.get("stop", "obstacle") not in ("obstacle", "through"):
                raise SchemaError("stop must be obstacle or through")
            layer.append(PG.RayRule(sel, dirs, act.get("stop", "obstacle"), _colour(act.get("color", "own"))))
        else:
            raise SchemaError(f"unknown action {act!r}")
    if not native and not layer:
        raise SchemaError("a program needs at least one rule")
    base = N("program", (view, tuple(native), "keep", N("same_as_input", ()))) if native else None
    return base if not layer else PG.make(view, base, layer)


def to_structured(program):
    """The inverse of from_structured for the supported subset (used to build training targets); None otherwise."""
    def sel(s):
        if s.op == "true":
            return {"true": True}
        if s.op == "test":
            return {"test": list(s.args)}
        if s.op == "and":
            return {"and": [sel(s.args[0]), sel(s.args[1])]}
        if s.op == "exists":
            return {"exists": [s.args[0], sel(s.args[1])]}
        raise SchemaError(s.op)

    def nat(a):
        if a.op == "recolor" and a.args[0].op == "color":
            return {"recolor": a.args[0].args[0]}
        if a.op == "translate" and a.args[0].op == "vec":
            return {"translate": list(a.args[0].args)}
        if a.op == "delete":
            return {"delete": True}
        raise SchemaError(a.op)
    try:
        if isinstance(program, PG.G4Program):
            out = to_structured(program.base) if program.base is not None else {"view": program.view, "rules": []}
            out["view"] = program.view
            for r in program.rules:
                if isinstance(r, PG.PartRule):
                    out["rules"].append({"selector": sel(r.sel), "action": {"part": r.kind, "color": r.colour}})
                else:
                    out["rules"].append({"selector": sel(r.sel), "action": {"ray": [DIR_OF[x] for x in r.dirs],
                                                                            "stop": r.stop, "color": r.colour}})
            return out
        if program.op != "program" or program.args[2] != "keep" or program.args[3] != N("same_as_input", ()):
            return None
        return {"view": program.args[0],
                "rules": [{"selector": sel(r.args[0]), "action": nat(r.args[1])} for r in program.args[1]]}
    except (SchemaError, AttributeError, IndexError, TypeError):
        return None
