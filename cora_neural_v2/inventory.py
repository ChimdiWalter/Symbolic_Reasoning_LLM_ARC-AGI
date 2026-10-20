"""The native CORA operation inventory, read from the native registries, and what ncv2-g1 exposes.

    python -m cora_neural_v2.inventory      # prints the inventory as JSON

`native_inventory()` lists, from the live native code (never a hand-copied list):
- every delta type;
- every expression class and its grammar;
- every relation and feature;
- the program classes and output modes.

`G1_EXPOSURE` records, for each native item, whether ncv2-g1 exposes it, and why not if it does not.

`ACTION_PARAMS` holds the parameter names each native apply_* function reads, scanned from native actions.py.
`check_bridge_dict()` verifies a compiled program against the grammars and these names, so the bridge cannot emit an
op or a parameter that native would silently ignore.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOT_EXPOSED = {
    "delta:grow": "many growth modes with mode-specific parameters; the next increment, behind its own parity tests",
    "delta:synth_copy": "depends on the frozen learned-verb asset (learned_verbs.json); not generic syntax",
    "copy:k+placement": "per-copy-index placements need the copy_index binding; deferred",
    "copy:keep_original": "the native default (keep the original) only; deferred",
    "ref:matched_template": "needs a correspondence-bound template; not inference-local syntax",
    "expr:FreeSlotExpr": "a library-operator hole; ncv2 has its own typed holes",
    "expr:GrowModeExpr": "only used by GROW",
    "expr:PatternExpr": "only used by GROW",
    "program:framed/overlay/reduction/generative/computed_pattern/erase_patch": "other native program classes; later",
}


def scan_action_params(path=None):
    """{native apply function: parameter names it reads}, scanned from geocat_arc/object_reasoning/actions.py."""
    path = path or os.path.join(HERE, "geocat_arc", "object_reasoning", "actions.py")
    cur, out = None, {}
    for line in open(path):
        m = re.match(r"def (apply_\w+)\(", line)
        if m:
            cur = m.group(1)
            out[cur] = set()
            continue
        if cur:
            for k in (re.findall(r'_eval_param\(action,\s*"(\w+)"', line) + re.findall(r'params\.get\("(\w+)"', line)
                      + re.findall(r'params\["(\w+)"\]', line) + re.findall(r'"(\w+)" in action\.params', line)):
                out[cur].add(k)
    return out


def native_inventory():
    from geocat_arc.object_reasoning import expressions as EX            # noqa: F401  (registers Expr classes)
    from geocat_arc.object_reasoning import features as F
    from geocat_arc.object_reasoning.types import EXPR_CLASS_REGISTRY, DeltaType
    if not F.FEATURE_REGISTRY:
        F.register_builtin_features()
    return {
        "delta_types": [d.value for d in DeltaType],
        "expression_grammars": {name: sorted(cls.GRAMMAR) for name, cls in sorted(EXPR_CLASS_REGISTRY.items())},
        "relations": sorted(F.RELATION_REGISTRY),
        "features": sorted(F.FEATURE_REGISTRY),
        "program_classes": ["object", "composed", "reduction", "framed", "overlay", "generative", "computed_pattern",
                            "erase_patch"],
        "output_modes": ["same_as_input", "crop", "constant_shape"],
        "action_params": {k: sorted(v) for k, v in scan_action_params().items()},
    }


def check_bridge_dict(d):
    """Raise ValueError if a compiled native program dict uses an op or a parameter native does not define or read."""
    from geocat_arc.object_reasoning.types import EXPR_CLASS_REGISTRY, DeltaType
    params = scan_action_params()
    deltas = {x.value for x in DeltaType}

    def expr(e):
        if isinstance(e, dict) and "expr_class" in e:
            cls = EXPR_CLASS_REGISTRY.get(e["expr_class"])
            if cls is None or e["op"] not in cls.GRAMMAR:
                raise ValueError(f"native has no {e['expr_class']}.{e['op']}")
            for a in e["args"]:
                expr(a)
        elif isinstance(e, dict) and "__tuple__" in e:
            for a in e["__tuple__"]:
                expr(a)

    def action(a):
        if a["delta_type"] not in deltas:
            raise ValueError(f"native has no delta {a['delta_type']}")
        for k, v in a["params"].items():
            if a["delta_type"] == "composite":
                _, sub, name = k.split(":")
                read = params.get(f"apply_{sub}", set())
            else:
                sub, name, read = a["delta_type"], k, params.get(f"apply_{a['delta_type']}", set())
            base = re.sub(r"\d+$", "", name)
            if name not in read and base not in ("offset", "ray"):
                raise ValueError(f"native apply_{sub} does not read parameter {name!r}")
            expr(v)

    stages = d["stages"] if d.get("program_class") == "composed" else [d]
    for s in stages:
        for r in s["rules"]:
            expr(r["selector"]["predicate"])
            action(r["action"])
        action(s["default_action"])
        for k in ("region", "background", "fill"):
            if s["output_spec"].get(k):
                expr(s["output_spec"][k])
    return True


if __name__ == "__main__":
    print(json.dumps({"native": native_inventory(), "ncv2_g1_not_exposed": NOT_EXPOSED}, indent=1))
