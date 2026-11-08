"""The surface syntax a language model writes, and its parser into CORA's own typed program objects.

Nothing the model writes is executed as Python. Its text is only ever tokenized and parsed into CORA data:
- native object programs, `seq` programs and the program classes (pixel_rule, symmetry_completion, counting,
  panel_reduction, generative) are CORA's S-expressions, parsed by CORA's own parser
  (`cora_neural_v2g2.grammar.parse`) and type-checked by CORA (`cora_neural_hybrid.execute.check`);
- programs with part and ray rules (CORA's version 4 layer) are written as

      (g4program VIEW BASE (list RULE ...))
      BASE := (identity) | a native object program
      RULE := (part_rule SELECTOR KIND COLOUR) | (ray_rule SELECTOR (list DIR ...) STOP COLOUR)

  exactly the form CORA prints for them (`cora_neural_v2g4.construct.sexpr`), except that a direction may also be
  written by name (up, down, left, right, up_left, up_right, down_left, down_right) instead of as `(dr dc)`. The
  S-expression is tokenized by CORA's parser; this module only maps the parsed tuple onto CORA's constructors
  (`PG.make`, `PG.PartRule`, `PG.RayRule`), one surface form per AST, and validates every literal.

`extract(text)` finds the program in a model reply (the last ```cora fenced block, else the last balanced
S-expression that starts with a program head). `parse(src)` returns the program or raises SurfaceError with a
message that the diagnosis returns to the model. `render(prog)` prints the canonical surface form.
"""
import re

from cora_neural_v2.rast import ASTError, N
from cora_neural_v2g2 import grammar as G
from cora_neural_v2g2 import classes as GC
from cora_neural_v2g4 import parts as PT
from cora_neural_v2g4 import program as PG
from cora_neural_hybrid import execute as EX

DIR_NAMES = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1), "up_left": (-1, -1),
             "up_right": (-1, 1), "down_left": (1, -1), "down_right": (1, 1)}
NAME_OF = {v: k for k, v in DIR_NAMES.items()}
VIEWS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")
STOPS = ("obstacle", "through")
PROGRAM_HEADS = ("program", "seq", "g4program") + GC.CLASS_PROGRAM_OPS
MAX_CHARS = 6000


class SurfaceError(ValueError):
    pass


def extract(text):
    """The program source in a model reply, or None."""
    if not isinstance(text, str):
        return None
    blocks = re.findall(r"```(?:cora|lisp|scheme|clojure|sexp|text)?\s*\n(.*?)```", text, flags=re.S)
    for b in reversed(blocks):
        s = _last_program(b) or b.strip()
        if s.startswith("("):
            return s
    found = _last_program(text)
    if found is None:                              # unbalanced: hand the tail to parse, which reports it
        m = list(re.finditer(r"\((" + "|".join(map(re.escape, PROGRAM_HEADS)) + r")\b", text))
        if m:
            return text[m[-1].start():].strip()
    return found


def _last_program(text):
    """The last OUTERMOST balanced S-expression whose head is a program head (a program nested inside another, such
    as the base of a g4program or a stage of a seq, is part of its parent, not a program of its own)."""
    spans = []
    for m in re.finditer(r"\((" + "|".join(map(re.escape, PROGRAM_HEADS)) + r")\b", text):
        depth, i = 0, m.start()
        for j in range(i, len(text)):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    spans.append((i, j + 1))
                    break
    outer = [a for a in spans if not any(b[0] < a[0] and a[1] <= b[1] for b in spans)]
    return text[outer[-1][0]:outer[-1][1]] if outer else None


def _colour(x, where):
    if x == "own":
        return "own"
    if isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= 9:
        raise SurfaceError(f"{where}: a colour is 0-9 or own, got {x!r}")
    return x


def _dir(x, where):
    if isinstance(x, str) and x in DIR_NAMES:
        return DIR_NAMES[x]
    if isinstance(x, tuple) and len(x) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in x):
        if x in NAME_OF:
            return x
    raise SurfaceError(f"{where}: a ray direction is one of {sorted(DIR_NAMES)}, got {x!r}")


def _selector(x, where):
    if not isinstance(x, N):
        raise SurfaceError(f"{where}: expected a selector such as (true) or (test color == 2), got {x!r}")
    return x


def _g4(t):
    if len(t) != 4:
        raise SurfaceError("g4program takes 3 arguments: VIEW BASE (list RULE ...)")
    _, view, base, rules = t
    if view not in VIEWS:
        raise SurfaceError(f"g4program: unknown view {view!r} (one of {VIEWS})")
    if base == ("identity",):
        base = None
    elif not (isinstance(base, N) and base.op in ("program", "seq")):
        raise SurfaceError("g4program: BASE is (identity) or a (program ...)")
    if not isinstance(rules, tuple) or not rules:
        raise SurfaceError("g4program: expected a non-empty (list RULE ...)")
    out = []
    for k, r in enumerate(rules):
        where = f"g4program rule {k + 1}"
        if not isinstance(r, tuple) or not r or r[0] not in ("part_rule", "ray_rule"):
            raise SurfaceError(f"{where}: expected (part_rule ...) or (ray_rule ...), got {r!r}"[:300])
        if r[0] == "part_rule":
            if len(r) != 4:
                raise SurfaceError(f"{where}: (part_rule SELECTOR KIND COLOUR)")
            if r[2] not in PT.KINDS:
                raise SurfaceError(f"{where}: part kind {r[2]!r} is not one of {PT.KINDS}")
            out.append(PG.PartRule(_selector(r[1], where), r[2], _colour(r[3], where)))
        else:
            if len(r) != 5:
                raise SurfaceError(f"{where}: (ray_rule SELECTOR (list DIR ...) STOP COLOUR)")
            dirs = r[2] if isinstance(r[2], tuple) else (r[2],)
            if not dirs:
                raise SurfaceError(f"{where}: at least one direction")
            dirs = tuple(sorted({_dir(d, where) for d in dirs}))
            if r[3] not in STOPS:
                raise SurfaceError(f"{where}: STOP is obstacle or through, got {r[3]!r}")
            out.append(PG.RayRule(_selector(r[1], where), dirs, r[3], _colour(r[4], where)))
    return PG.make(view, base, out)


def _known_heads():
    from cora_neural_v2 import rast as R1
    return set(R1.SIGNATURES) | set(GC.CLASS_OPS) | {"g4program", "part_rule", "ray_rule", "identity", "list"}


def _unknown_heads(src):
    """Heads of parenthesized forms in the source text that are not CORA operations (list literals, number pairs
    and bindings such as (?t REF) have no operation head)."""
    known = _known_heads()
    return [h for h in re.findall(r"\(\s*([A-Za-z_]\w*)", src) if h not in known]


RENDER_OPS = ("same_as_input", "crop", "crop_by_action", "constant_shape")
REF_OPS = ("self", "var", "nearest", "nearest_of_color", "container", "contained", "largest", "unique", "shape_twin")
#: COLOR argument positions: op -> index of its COLOR argument
COLOR_ARGS = {"recolor": 0, "connect": 1, "fill_line": 1, "constant_shape": 2}


def _sugar(x):
    """Documented shorthands, each standing for exactly one CORA AST (applied bottom-up, before type-checking):
    (test F) = (test F == #t); (test F V) = (test F == V); (recolor 3) = (recolor (color 3)); a REF where a COLOR
    is expected = (color_of REF); a program without DEFAULT and RENDER = ... keep (same_as_input); a program
    without RENDER = ... DEFAULT (same_as_input)."""
    if isinstance(x, tuple):
        return tuple(_sugar(a) for a in x)
    if not isinstance(x, N):
        return x
    args = tuple(_sugar(a) for a in x.args)
    if x.op == "test" and len(args) == 1 and isinstance(args[0], str):
        args = (args[0], "==", True)
    elif x.op == "test" and len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], (int, bool)) \
            and args[1] not in ("==",):
        args = (args[0], "==", args[1])
    if x.op in COLOR_ARGS and len(args) > COLOR_ARGS[x.op]:
        i = COLOR_ARGS[x.op]
        a = args[i]
        if isinstance(a, int) and not isinstance(a, bool):
            args = args[:i] + (N("color", (a,)),) + args[i + 1:]
        elif isinstance(a, N) and a.op in REF_OPS:
            args = args[:i] + (N("color_of", (a,)),) + args[i + 1:]
    if x.op == "program" and len(args) == 3 and args[2] in ("keep", "delete"):
        args = args + (N("same_as_input", ()),)
    return N(x.op, args)


def _normalize_program(x):
    """One unambiguous surface variant: the DEFAULT and RENDER written inside the rule list,
    `(program V (list RULE ... keep (same_as_input)))`, is the same AST as `(program V (list RULE ...) keep
    (same_as_input))`. A program missing its DEFAULT and RENDER is rejected with a message saying what to add."""
    if not (isinstance(x, N) and x.op == "program" and len(x.args) == 2 and isinstance(x.args[1], tuple)):
        return x
    view, items = x.args
    if len(items) >= 2 and items[-2] in ("keep", "delete") and isinstance(items[-1], N) and items[-1].op in RENDER_OPS:
        return N("program", (view, tuple(items[:-2]), items[-2], items[-1]))
    return N("program", (view, items, "keep", N("same_as_input", ())))


def _hint(name, pool):
    import difflib
    m = difflib.get_close_matches(name, sorted(pool), n=1, cutoff=0.6)
    return f" (did you mean {m[0]!r}?)" if m else ""


def parse(src):
    """Program source -> a CORA program (rast N, or a version 4 G4Program). Raises SurfaceError."""
    if not isinstance(src, str) or not src.strip():
        raise SurfaceError("no program found: write one program inside ```cora ... ```")
    if len(src) > MAX_CHARS:
        raise SurfaceError(f"program longer than {MAX_CHARS} characters")
    if src.count("(") != src.count(")"):
        raise SurfaceError(f"unbalanced parentheses ({src.count('(')} open, {src.count(')')} close)")
    try:
        x = G.parse(src)
    except (ASTError, IndexError, ValueError, RecursionError) as e:
        raise SurfaceError(f"does not parse: {str(e)[:200]}") from None
    bad = _unknown_heads(src)
    if bad:
        raise SurfaceError(f"unknown operation {bad[0]!r}{_hint(bad[0], _known_heads())}")
    if isinstance(x, tuple) and x and x[0] == "g4program":
        prog = _g4(_sugar(x))
    elif isinstance(x, N):
        prog = _normalize_program(_sugar(x))
    else:
        head = x[0] if isinstance(x, tuple) and x else x
        raise SurfaceError(f"unknown program head {head!r}: a program starts with one of {PROGRAM_HEADS}"[:300])
    ok, why = EX.check(prog)
    if not ok:
        m = re.search(r"'(\w+)' is not a registered native (feature|relation)", why)
        if m:
            from cora_neural_v2.rast import _native_names
            feats, rels = _native_names()
            why += _hint(m.group(1), feats if m.group(2) == "feature" else rels)
        raise SurfaceError(f"does not type-check: {why}"[:400])
    if isinstance(prog, N) and prog.op not in ("program", "seq") and not G.is_class(prog):
        raise SurfaceError(f"{prog.op} is not a program")
    return prog


def render(prog):
    """The canonical surface form (directions printed by name)."""
    if isinstance(prog, PG.G4Program):
        from cora_neural_v2.rast import to_sexpr

        def rule(r):
            if isinstance(r, PG.PartRule):
                return f"(part_rule {to_sexpr(r.sel)} {r.kind} {r.colour})"
            return f"(ray_rule {to_sexpr(r.sel)} (list {' '.join(NAME_OF[d] for d in r.dirs)}) {r.stop} {r.colour})"
        base = to_sexpr(prog.base) if prog.base is not None else "(identity)"
        return f"(g4program {prog.view} {base} (list {' '.join(rule(r) for r in prog.rules)}))"
    from cora_neural_v2.rast import to_sexpr
    return to_sexpr(prog)


def key(prog):
    """A canonical identity for de-duplication (CORA's own rendering)."""
    from cora_neural_hybrid import schema as SCH
    return SCH.render(prog)
