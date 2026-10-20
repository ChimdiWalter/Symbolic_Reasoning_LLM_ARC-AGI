"""ncv2-g2 program-class forms: typed ASTs for native CORA's ReductionProgram and GenerativeProgram.

The program classes:
- symmetry completion, pixel rules and counting: native `inducer.py` wraps each as a ReductionProgram with
  `split.kind` set to symmetry / pixel_rule / counting;
- panel reductions: `reduction.py`, separator or equal splits; select_panel, overlay_* and cellwise(_color);
- GenerativeProgram: `generative.py`, per-object generators painted onto one canvas.

Each typed form compiles to exactly the dict that native's own inducers build. It runs only through native
`render_program`. `decompile(d)` turns a native dict back into the typed form, so native-induced programs can enter
the ncv2-g2 agenda as typed hypotheses.

Refused rather than half-typed:
- the generator kinds `ray_relational` (an untyped relational payload) and `learned_generator` (it depends on the
  frozen learned-generator asset);
- any key native does not define.

Native's stringified table keys are parsed with `ast.literal_eval` (literals only, never code) and re-emitted with
`str(tuple)`, exactly as native writes them.
"""
import ast as _pyast

from cora_neural_v2.rast import ASTError, N, VIEWS

SYMMETRIES = ("d4", "4fold", "rot90", "horizontal", "vertical", "rot180")
PIXEL_MODES = ("color_swap", "neighbor_count", "neighbor_pattern")
COUNTING_MODES = ("majority_color", "unique_color", "surrounding_of_unique", "color_count_row", "color_histogram_col")
CRITERIA = ("unique_pattern", "majority_pattern", "most_nonbg", "least_nonbg", "most_colors", "least_colors")
COMBINERS = ("overlay_first", "overlay_last", "overlay_max", "overlay_min_nonbg")
CANVAS = ("over_input", "blank")
# generator kind -> (required params, optional params), read from generative._apply_generator
GEN_PARAMS = {
    "ray": (("direction",), ("color", "length")),
    "ray_until_obstacle": (("direction",), ("color", "bg")),
    "ray_through_absorbed": (("direction",), ("color", "bg")),
    "row_line": ((), ("color",)), "col_line": ((), ("color",)), "cross_line": ((), ("color",)),
    "halo": ((), ("color", "conn")), "fill_interior": ((), ("color",)),
    "mirror_edge": (("direction",), ()), "symmetry_complete": (("axis",), ()),
    "periodic_self": (("direction",), ()), "periodic_bbox": (("direction",), ()),
    "frame_minority": ((), ()), "line_periodic": ((), ("color",)), "path_two_anchor": ((), ("color",)),
    "cross_center": ((), ("color",)), "cavity_leak": ((), ("color",)), "ray_deflect": (("direction",), ("color",)),
}
NOT_EXPOSED_KINDS = {"ray_relational": "its relational target predicate is an untyped payload",
                     "learned_generator": "it depends on the frozen learned-generator asset"}
INT_PARAMS = ("color", "bg", "length", "conn")
SYMBOLS = ("up", "down", "left", "right", "horizontal", "vertical", "diag_main", "diag_anti", "both", "row", "col")
CLASS_PROGRAM_OPS = ("symmetry_completion", "pixel_rule", "counting", "panel_reduction", "generative")
CLASS_HELPER_OPS = ("entry", "key_color", "key_count", "key_pattern", "split_separator", "split_equal", "select_panel",
                    "overlay", "cellwise", "cellwise_color", "cell_row", "flags", "colors", "panel", "gen", "gsel",
                    "sel_color", "sel_min_size", "sel_not_background", "grule", "gp")
CLASS_OPS = CLASS_PROGRAM_OPS + CLASS_HELPER_OPS


def _color(x, path):
    if isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= 9:
        raise ASTError(f"{path}: expected a colour 0-9, got {x!r}")
    return x


def _nat(x, path, lo=0):
    if isinstance(x, bool) or not isinstance(x, int) or x < lo:
        raise ASTError(f"{path}: expected an integer >= {lo}, got {x!r}")
    return x


def _sym(x, allowed, path):
    if x not in allowed:
        raise ASTError(f"{path}: {x!r} is not one of {allowed}")
    return x


def _node(x, op, n, path):
    if not isinstance(x, N) or x.op != op or len(x.args) != n:
        raise ASTError(f"{path}: expected ({op} …{n} args), got {x!r}")
    return x.args


def _list(x, path):
    if not isinstance(x, tuple):
        raise ASTError(f"{path}: expected a list, got {x!r}")
    return x


# ------------------------------------------------------------------ typecheck (each returns "PROGRAM" or raises)
def _check_value(v, path):
    if isinstance(v, N):
        (i,) = _node(v, "panel", 1, path)
        _nat(i, path)
    else:
        _color(v, path)


def _check_pixel_key(mode, k, path):
    if mode == "color_swap":
        _color(_node(k, "key_color", 1, path)[0], path)
    elif mode == "neighbor_count":
        c, n = _node(k, "key_count", 2, path)
        _color(c, path)
        _nat(n, path)
    else:
        c, flags = _node(k, "key_pattern", 2, path)
        _color(c, path)
        if len(_list(flags, path)) != 4 or any(f not in (-1, 0, 1) for f in flags):
            raise ASTError(f"{path}: a neighbour pattern is four flags in {{-1, 0, 1}}")


def _check_generator(g, path):
    sel, rule = _node(g, "gen", 2, path)
    for i, cond in enumerate(_list(_node(sel, "gsel", 1, path + ".gsel")[0], path)):
        p = f"{path}.gsel[{i}]"
        if not isinstance(cond, N):
            raise ASTError(f"{p}: expected a selector condition")
        if cond.op == "sel_color":
            _color(_node(cond, "sel_color", 1, p)[0], p)
        elif cond.op == "sel_min_size":
            _nat(_node(cond, "sel_min_size", 1, p)[0], p, 1)
        else:
            _node(cond, "sel_not_background", 0, p)
    kind, params = _node(rule, "grule", 2, path + ".grule")
    if kind in NOT_EXPOSED_KINDS:
        raise ASTError(f"{path}: generator kind {kind} is not exposed: {NOT_EXPOSED_KINDS[kind]}")
    if kind not in GEN_PARAMS:
        raise ASTError(f"{path}: {kind!r} is not a native generator kind")
    req, opt = GEN_PARAMS[kind]
    seen = set()
    for j, gp in enumerate(_list(params, path)):
        name, val = _node(gp, "gp", 2, f"{path}.gp[{j}]")
        if name not in req + opt or name in seen:
            raise ASTError(f"{path}: parameter {name!r} is not allowed (or repeated) for {kind}")
        seen.add(name)
        if name in INT_PARAMS:
            if val == "none" and name in opt:                       # native stores an explicit None (e.g. length)
                continue
            (_color if name in ("color", "bg") else _nat)(val, f"{path}.{name}")
        else:
            _sym(val, SYMBOLS, f"{path}.{name}")
    if not set(req) <= seen:
        raise ASTError(f"{path}: {kind} needs {req}")


def typecheck(node, path="root"):
    o, a = node.op, node.args
    if o == "symmetry_completion":
        _sym(_node(node, o, 1, path)[0], SYMMETRIES, path)
    elif o == "counting":
        _sym(_node(node, o, 1, path)[0], COUNTING_MODES, path)
    elif o == "pixel_rule":
        mode, entries = _node(node, o, 2, path)
        _sym(mode, PIXEL_MODES, path)
        if not _list(entries, path):
            raise ASTError(f"{path}: an empty pixel table")
        for i, e in enumerate(entries):
            k, v = _node(e, "entry", 2, f"{path}[{i}]")
            _check_pixel_key(mode, k, f"{path}[{i}]")
            _color(v, f"{path}[{i}]")
    elif o == "panel_reduction":
        split, comb = _node(node, o, 2, path)
        if isinstance(split, N) and split.op == "split_separator":
            _color(_node(split, "split_separator", 1, path)[0], path)
        else:
            r, c = _node(split, "split_equal", 2, path)
            _nat(r, path, 1)
            _nat(c, path, 1)
        if not isinstance(comb, N):
            raise ASTError(f"{path}: expected a combiner")
        if comb.op == "select_panel":
            _sym(_node(comb, "select_panel", 1, path)[0], CRITERIA, path)
        elif comb.op == "overlay":
            _sym(_node(comb, "overlay", 1, path)[0], COMBINERS, path)
        elif comb.op in ("cellwise", "cellwise_color"):
            rows = _list(_node(comb, comb.op, 1, path)[0], path)
            for i, row in enumerate(rows):
                k, v = _node(row, "cell_row", 2, f"{path}[{i}]")
                if comb.op == "cellwise":
                    if not isinstance(k, N) or k.op != "flags" or not k.args or any(not isinstance(b, bool) for b in k.args):
                        raise ASTError(f"{path}[{i}]: cellwise keys are (flags #t #f …)")
                else:
                    if not isinstance(k, N) or k.op != "colors" or not k.args:
                        raise ASTError(f"{path}[{i}]: cellwise_color keys are (colors c …)")
                    for c in k.args:
                        _color(c, f"{path}[{i}]")
                _check_value(v, f"{path}[{i}]")
        else:
            raise ASTError(f"{path}: {comb.op} is not a panel combiner")
    elif o == "generative":
        view, gens, canvas, bg, delsrc, ic = _node(node, o, 6, path)
        _sym(view, VIEWS, path)
        if not _list(gens, path):
            raise ASTError(f"{path}: a generative program needs at least one generator")
        for i, g in enumerate(gens):
            _check_generator(g, f"{path}.gen[{i}]")
        _sym(canvas, CANVAS, path)
        _color(bg, path)
        if not isinstance(delsrc, bool):
            raise ASTError(f"{path}: delete_source is #t or #f")
        if ic != "none":
            _color(ic, path)
    else:
        raise ASTError(f"{path}: {o} is not an ncv2-g2 program-class form")
    return "PROGRAM"


# ------------------------------------------------------------------ compile: typed form -> the native dict
def _value_out(v):
    return f"@panel{v.args[0]}" if isinstance(v, N) else int(v)


def _pixel_key_out(mode, k):
    if mode == "color_swap":
        return str(int(k.args[0]))
    if mode == "neighbor_count":
        return str((int(k.args[0]), int(k.args[1])))
    return str((int(k.args[0]), tuple(int(f) for f in k.args[1])))


def compile_class(node):
    typecheck(node)
    o, a = node.op, node.args
    if o == "symmetry_completion":
        return {"program_class": "reduction", "split": {"kind": "symmetry"}, "mode": a[0],
                "params": {"mode": "symmetry_completion", "symmetry": a[0]}}
    if o == "counting":
        return {"program_class": "reduction", "split": {"kind": "counting"}, "mode": a[0], "params": {"mode": a[0]}}
    if o == "pixel_rule":
        table = {_pixel_key_out(a[0], e.args[0]): int(e.args[1]) for e in a[1]}
        return {"program_class": "reduction", "split": {"kind": "pixel_rule"}, "mode": a[0],
                "params": {"mode": a[0], "table": table}}
    if o == "panel_reduction":
        split, comb = a
        spec = {"kind": "separator", "color": int(split.args[0])} if split.op == "split_separator" else \
            {"kind": "equal", "rows": int(split.args[0]), "cols": int(split.args[1])}
        if comb.op == "select_panel":
            return {"program_class": "reduction", "split": spec, "mode": "select_panel",
                    "params": {"criterion": comb.args[0]}}
        if comb.op == "overlay":
            return {"program_class": "reduction", "split": spec, "mode": comb.args[0], "params": {}}
        table = {}
        for row in comb.args[0]:
            k, v = row.args
            table[str(tuple(bool(b) for b in k.args) if comb.op == "cellwise" else tuple(int(c) for c in k.args))] = _value_out(v)
        return {"program_class": "reduction", "split": spec, "mode": comb.op, "params": {"table": table}}
    view, gens, canvas, bg, delsrc, ic = a
    out = []
    for g in gens:
        sel, rule = g.args
        sd = {}
        for cond in sel.args[0]:
            if cond.op == "sel_color":
                sd["color"] = int(cond.args[0])
            elif cond.op == "sel_min_size":
                sd["min_size"] = int(cond.args[0])
            else:
                sd["not_background"] = True
        rd = {"kind": rule.args[0]}
        for gp in rule.args[1]:
            rd[gp.args[0]] = None if gp.args[1] == "none" else gp.args[1]
        out.append({"selector": sd, "rule": rd})
    d = {"program_class": "generative", "seg_variant": view, "generators": out, "canvas_policy": canvas,
         "background": int(bg)}
    if delsrc:
        d["delete_source"] = True
    if ic != "none":
        d["intersection_color"] = int(ic)
    return d


# ------------------------------------------------------------------ decompile: native dict -> the typed form
def _lit(key):
    try:
        return _pyast.literal_eval(key)
    except (ValueError, SyntaxError) as e:
        raise ASTError(f"unreadable native table key {key!r}") from e


def _value_in(v):
    if isinstance(v, str):
        if not v.startswith("@panel"):
            raise ASTError(f"unknown table value {v!r}")
        return N("panel", (int(v[len("@panel"):]),))
    return int(v)


def decompile_class(d):
    pc = d.get("program_class")
    if pc == "reduction":
        split, mode, params = d["split"], d["mode"], d.get("params", {})
        kind = split.get("kind")
        if kind == "symmetry":
            node = N("symmetry_completion", (params["symmetry"],))
        elif kind == "counting":
            node = N("counting", (params["mode"],))
        elif kind == "pixel_rule":
            entries = []
            for k, v in params["table"].items():
                kv = _lit(k)
                if mode == "color_swap":
                    key = N("key_color", (int(kv),))
                elif mode == "neighbor_count":
                    key = N("key_count", (int(kv[0]), int(kv[1])))
                else:
                    key = N("key_pattern", (int(kv[0]), tuple(int(f) for f in kv[1])))
                entries.append(N("entry", (key, int(v))))
            node = N("pixel_rule", (mode, tuple(entries)))
        elif kind in ("separator", "equal"):
            if set(split) - {"kind", "color", "rows", "cols"}:
                raise ASTError(f"unknown split keys {sorted(split)}")
            sp = N("split_separator", (int(split["color"]),)) if kind == "separator" else \
                N("split_equal", (int(split["rows"]), int(split["cols"])))
            if mode == "select_panel":
                comb = N("select_panel", (params["criterion"],))
            elif mode in COMBINERS:
                comb = N("overlay", (mode,))
            elif mode in ("cellwise", "cellwise_color"):
                rows = []
                for k, v in params["table"].items():
                    kv = _lit(k)
                    key = N("flags", tuple(bool(b) for b in kv)) if mode == "cellwise" else N("colors", tuple(int(c) for c in kv))
                    rows.append(N("cell_row", (key, _value_in(v))))
                comb = N(mode, (tuple(rows),))
            else:
                raise ASTError(f"panel mode {mode!r} is not exposed")
            node = N("panel_reduction", (sp, comb))
        else:
            raise ASTError(f"reduction split kind {kind!r} is not exposed")
    elif pc == "generative":
        gens = []
        for g in d["generators"]:
            sel, rule = g["selector"], dict(g["rule"])
            if set(sel) - {"color", "min_size", "not_background"}:
                raise ASTError(f"unknown generator selector keys {sorted(sel)}")
            conds = ([N("sel_color", (int(sel["color"]),))] if "color" in sel else []) + \
                ([N("sel_min_size", (int(sel["min_size"]),))] if "min_size" in sel else []) + \
                ([N("sel_not_background", ())] if sel.get("not_background") else [])
            kind = rule.pop("kind")
            gps = tuple(N("gp", (k, "none" if v is None else v)) for k, v in rule.items())
            gens.append(N("gen", (N("gsel", (tuple(conds),)), N("grule", (kind, gps)))))
        ic = d.get("intersection_color")
        node = N("generative", (d["seg_variant"], tuple(gens), d.get("canvas_policy", "over_input"),
                                int(d.get("background", 0)), bool(d.get("delete_source", False)),
                                "none" if ic is None else int(ic)))
    else:
        raise ASTError(f"program class {pc!r} is not an ncv2-g2 class form")
    typecheck(node)
    return node
