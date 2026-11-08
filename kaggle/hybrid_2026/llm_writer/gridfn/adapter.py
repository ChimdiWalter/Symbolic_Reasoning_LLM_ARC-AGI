"""The grid-function language as a second program language of the LLM-writer hybrid (versioned arm "gridfn-1").

Interface required by the LLM-writer agent (its PROGRESS.md, 26 Oct, 02:12Z):
- `extract(text) -> str | None`: the program source in a model reply;
- `parse(src) -> Program`, raising GridFnError (a ValueError subclass) whose message is shown to the model, with a
  closest-name hint for unknown names; parsing never executes anything;
- `Program`: hashable, `key()` (canonical text, for de-duplication), `render()` (shown in revision prompts),
  `run(grid) -> list[list[int]] | None` (isolated worker; bounded in steps, CPU, wall-clock time and memory; never
  raises its own errors; None on any failure or limit; output 1..30 x 1..30, values 0..9), `size()` (node count);
- `ablations(program) -> [(label, Program)]`: drop one statement of transform, or replace one call of a grid-to-grid
  primitive by its first argument (at most 8; each variant passes the check);
- `CARD` (the language card) and `FEWSHOT` (prompts.FEWSHOT format; public TRAINING puzzles; checked by `run`).

Also here: `execute(program, task)` returns the same `cora_neural_hybrid.execute.Execution` record that
`llm_writer.cora_exec.run` builds for a CORA program (statuses INVALID / ERROR / INCOMPLETE / FITS with the same
reasons, per-demonstration rows with shape, wrong, fixed, broken, remaining, changed, precision and recall,
`cora_neural_v2g3.delta.DemoDelta` masks, `outs`, test predictions for fits), so CORA's diagnosis
(`llm_writer.diagnose`) reads a wrong grid-function program exactly as it reads a wrong CORA program. Each record
also carries `provenance` (language version, source and canonical sha256, the parse result, card sha256, limits)
and `grid_errors` (the typed error of every grid that failed). `causal_check` mirrors `llm_writer.ablate.check`.
Expected test outputs are never read here.
"""
import ast
import copy as _copy
import re

from . import card as C
from . import interp as I
from . import lang as L
from . import prims as P
from . import sandbox as SB

VERSION = L.VERSION
GridFnError = L.GridFnError
CARD = C.CARD
FEWSHOT = C.FEWSHOT
CARD_SHA256 = L.sha256(CARD)
REVISION_OPS = ("CHANGE_VIEW", "GROUP_OBJECTS", "REVISE_SELECTOR", "REVISE_BINDING", "REVISE_ACTION", "ADD_RULE",
                "CHANGE_OUTPUT_FRAME", "MORE_SEARCH", "KEEP_ALTERNATIVES")

SYSTEM = ("You write programs in a small, safe subset of Python for grid puzzles. A puzzle gives example input and "
          "output grids; the same hidden rule maps every input to its output. Write one function transform(grid) "
          "that implements the rule. CORA runs it on every example and on the test input. Use only the Python "
          "subset and the functions in the language card.")
FORMAT = ("Use only the Python subset and the functions of the language card (no imports). Answer in this format:\n"
          "Rule: one or two sentences describing the transformation.\n```python\ndef transform(grid):\n    ...\n```")
REVISION_FORMAT = ("Answer in this format, program first, no long explanation:\nRevision: one of "
                   + ", ".join(REVISION_OPS) + "\n```python\n(the complete corrected program)\n```\n"
                   "Rule: one sentence.")
CACHE_MAX = 256


# ------------------------------------------------------------------ extraction
_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+.-]*)[ \t]*\n(.*?)```", re.S)
_OPEN_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+.-]*)[ \t]*\n")
_TRANSFORM = re.compile(r"^[ \t]*def[ \t]+transform[ \t]*\(", re.M)
_TYPING = re.compile(r"^[ \t]*(from[ \t]+typing[ \t]+import[^\n]*|import[ \t]+typing[^\n]*)\n?", re.M)
_MAIN = re.compile(r"^if[ \t]+__name__[ \t]*==[^\n]*:[ \t]*\n.*\Z", re.M | re.S)


def _clean(code):
    import textwrap
    code = textwrap.dedent(code.replace("\r\n", "\n").replace("\t", "    "))
    code = _TYPING.sub("", code)
    code = _MAIN.sub("", code)
    return code.strip("\n") + "\n"


def extract(text):
    """The program in a model reply: the last fenced block that defines transform (an unclosed last fence counts);
    else the code from the first top-level `def` on. `from typing import ...` lines and a trailing
    `if __name__ == "__main__":` block are dropped. None if no transform is defined."""
    if not isinstance(text, str):
        return None
    for _, body in reversed(_FENCE.findall(text)):
        if _TRANSFORM.search(body):
            return _clean(body)
    opens = list(_OPEN_FENCE.finditer(text))
    if opens and text.count("```") % 2 == 1:
        tail = text[opens[-1].end():]
        if _TRANSFORM.search(tail):
            return _clean(tail)
    m = re.search(r"^def[ \t]+\w+[ \t]*\(", text, re.M)
    if m and _TRANSFORM.search(text[m.start():]):
        lines, keep = text[m.start():].replace("\r\n", "\n").split("\n"), []
        for ln in lines:
            if ln.strip() and not ln[0].isspace() and not re.match(r"(def |[A-Za-z_]\w*\s*=|#|@)", ln):
                break
            keep.append(ln)
        return _clean("\n".join(keep))
    return None


# ------------------------------------------------------------------ programs
class Program:
    """A checked grid-function program. Equality and hash follow the canonical text. `last_error` holds the typed
    error of the last `run` that returned None (for example "RuntimeFault: index 9 is out of range for a list of
    length 9 (line 7)"), else None."""
    __slots__ = ("src", "checked", "_cache", "last_error", "dialect")

    def __init__(self, src, checked, dialect="gridfn-1"):
        self.src, self.checked, self._cache, self.last_error = src, checked, {}, None
        self.dialect = dialect

    def key(self):
        return self.checked.canonical if self.dialect == "gridfn-1" else f"#{self.dialect}\n" + self.checked.canonical

    def render(self):
        return self.checked.canonical

    def size(self):
        return self.checked.nodes

    @property
    def sha256(self):
        return self.checked.src_sha256

    @property
    def canonical_sha256(self):
        return self.checked.canonical_sha256

    def info(self):
        return dict(self.checked.info(), card_sha256=CARD_SHA256)

    def __eq__(self, other):
        return isinstance(other, Program) and other.key() == self.key()

    def __hash__(self):
        return hash(("gridfn", self.key()))

    def __repr__(self):
        return f"Program({self.checked.canonical_sha256[:12]}, {self.size()} nodes)"

    def execute_grid(self, grid, sandbox=None, limits=None, cpu_s=None):
        """The worker's reply for one grid: {ok, out, kind, message, line, steps, cpu}; cached per grid."""
        g = _plain(grid)
        if g is None:
            return {"ok": False, "out": None, "kind": "ValueError", "message": "bad input grid", "line": None,
                    "steps": 0, "cpu": 0.0}
        k = (tuple(tuple(r) for r in g), None if limits is None else tuple(limits.as_dict().values()), cpu_s)
        hit = self._cache.get(k)
        if hit is not None:
            return hit
        text = self.checked.canonical if self.dialect == "gridfn-1" else DIALECT_PREFIX + self.checked.canonical
        rep = (sandbox or SB.default()).run(text, g, limits, cpu_s)
        if rep.get("ok"):
            try:
                rep["out"] = I.validate_output(rep["out"])
            except I.OutputError as e:
                rep = dict(rep, ok=False, out=None, kind=e.kind, message=e.message)
        if len(self._cache) >= CACHE_MAX:
            self._cache.pop(next(iter(self._cache)))
        self._cache[k] = rep
        return rep

    def run(self, grid):
        """Output grid (a new list of lists of ints) or None, with the reason in `last_error`. Never raises its own
        errors; an exception raised into the wait by the caller's own signal handler (for example cora_exec's
        time guard) propagates after the worker is stopped."""
        self.last_error = None
        try:
            rep = self.execute_grid(grid)
        except (OSError, ValueError, TypeError) as e:
            self.last_error = f"RuntimeFault: {type(e).__name__}"
            return None
        if not rep.get("ok"):
            self.last_error = error_text(rep)
            return None
        return [list(row) for row in rep["out"]]

    def ablations(self, limit=8):
        """[(label, Program)]: see the module function `ablations`."""
        return ablations(self, limit)


def error_text(rep):
    """'Kind: message (line n)' for a failed grid reply, else None."""
    if rep is None or rep.get("ok"):
        return None
    line = f" (line {rep['line']})" if rep.get("line") else ""
    return f"{rep.get('kind')}: {rep.get('message')}{line}"


def _plain(grid):
    if hasattr(grid, "tolist"):
        grid = grid.tolist()
    try:
        return I.check_input(grid)
    except (ValueError, TypeError):
        return None


DIALECT_PREFIX = "#dialect:gridfn-2\n"


def parse(src, dialect="gridfn-1"):
    """Program, or GridFnError (kinds SyntaxError, DisallowedNode, UnknownName; CompatibilityGap in gridfn-2).
    Never executes anything."""
    return Program(src, L.check(src, dialect), dialect)


def parse2(src):
    """gridfn-2: the same language plus the audited numpy subset (SOAR-style programs)."""
    return parse(src, "gridfn-2")


def parse_record(src):
    """Provenance of one parse: {"ok", "src_sha256", ...} with the error kind and message if it failed."""
    sha = L.sha256(src) if isinstance(src, str) else None
    try:
        return dict(parse(src).info(), src_sha256=sha)
    except GridFnError as e:
        return {"ok": False, "language": VERSION, "src_sha256": sha, "kind": e.kind, "message": e.message,
                "line": e.line}


# ------------------------------------------------------------------ ablations
def _transform_def(tree):
    defs = [s for s in tree.body if isinstance(s, ast.FunctionDef) and s.name == "transform"]
    return defs[-1] if defs else None


def _module_names(tree):
    names = set()
    for s in tree.body:
        if isinstance(s, ast.FunctionDef):
            names.add(s.name)
        elif isinstance(s, ast.Assign):
            for t in s.targets:
                names |= L._target_names(t)
    return names


def _local_names(tree):
    out = set()
    for s in ast.walk(tree):
        if isinstance(s, ast.FunctionDef):
            out |= {a.arg for a in s.args.args} | L._bound_names(s.body)
        elif isinstance(s, ast.comprehension):
            out |= L._target_names(s.target)
    return out


def _grid_calls(tree):
    """Calls of grid-to-grid primitives (not shadowed by the program's own names) with a first argument, in a
    fixed traversal order."""
    shadow = _module_names(tree) | _local_names(tree)
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.args and n.func.id in P.REGISTRY \
                and P.REGISTRY[n.func.id].grid_op and n.func.id not in shadow:
            out.append(n)
    return out


def _replace_nth_call(tree, k):
    """Copy of tree with the k-th call of _grid_calls replaced by its first argument."""
    new = _copy.deepcopy(tree)
    target = _grid_calls(new)[k]
    for parent in ast.walk(new):
        for field, value in ast.iter_fields(parent):
            if value is target:
                setattr(parent, field, target.args[0])
                return new
            if isinstance(value, list):
                for j, v in enumerate(value):
                    if v is target:
                        value[j] = target.args[0]
                        return new
    return None


def ablations(program, limit=8):
    """[(label, Program)]: transform's statements dropped one at a time (not its returns), then grid-to-grid
    primitive calls replaced by their first argument, in source order; only variants that pass the check and differ
    from the program; at most `limit`."""
    tree = program.checked.tree
    cands = []
    tf = _transform_def(tree)
    if tf is not None:
        for j, s in enumerate(tf.body):
            if isinstance(s, ast.Return):
                continue
            new = _copy.deepcopy(tree)
            body = _transform_def(new).body
            del body[j]
            if not body:
                body.append(ast.Pass())
            text = ast.unparse(s).split("\n")[0][:50]
            cands.append(((getattr(s, "lineno", 0), 0), f"drop statement {j + 1} of transform ({text})", new))
    for k, call in enumerate(_grid_calls(tree)):
        new = _replace_nth_call(tree, k)
        if new is not None:
            cands.append(((getattr(call, "lineno", 0), 1), f"{call.func.id}(...) on line {call.lineno} replaced by "
                          "its first argument", new))
    cands.sort(key=lambda t: t[0])
    out, seen = [], {program.key()}
    for _, label, new in cands:
        try:
            v = parse(ast.unparse(ast.fix_missing_locations(new)), getattr(program, "dialect", "gridfn-1"))
        except (GridFnError, ValueError, RecursionError):
            continue
        if v.key() in seen:
            continue
        seen.add(v.key())
        out.append((label, v))
        if len(out) == limit:
            break
    return out


def causal_check(program, preds, task):
    """llm_writer.ablate.check for a grid-function program: {"ablations": [{"variant", "test_changed"}], "causal"}.
    A fit whose prediction equals the test input is not attributed to the program."""
    import numpy as np
    rows = []
    ident_same = all(np.array_equal(np.asarray(p), np.asarray(t)) for p, t in zip(preds, task["test_inputs"]))
    rows.append({"variant": "no program (output = input)", "test_changed": not ident_same})
    for label, v in ablations(program):
        outs = [v.run(t) for t in task["test_inputs"]]
        changed = any(o is None or np.asarray(o).shape != np.asarray(p).shape or
                      not np.array_equal(np.asarray(o), np.asarray(p)) for o, p in zip(outs, preds))
        rows.append({"variant": label, "test_changed": bool(changed)})
    return {"ablations": rows, "causal": rows[0]["test_changed"] and
            (len(rows) == 1 or any(r["test_changed"] for r in rows[1:]))}


# ------------------------------------------------------------------ the execution record
LIMIT_KINDS = ("Timeout", "StepLimit")


def _err_row(rep):
    if rep is None or rep.get("ok"):
        return None
    return {"kind": rep.get("kind"), "message": rep.get("message"), "line": rep.get("line")}


def _limit_reason(rep, where, limits, cpu_s):
    if rep["kind"] == "StepLimit":
        what = f"the step limit ({limits.max_steps} steps)"
    else:
        what = f"the time limit ({cpu_s:g} s of CPU)" if "CPU" in (rep.get("message") or "") else "the time limit"
    return f"execution exceeded {what} on {where}"


def execute(program, task, guard_s=5.0, sandbox=None, limits=None):
    """The Execution record of `llm_writer.cora_exec.run` for a grid-function program (a Program or its source
    text) on task {"train": [(in, out)], "test_inputs": [grid]}: the same statuses, reasons, per-demonstration rows
    (including `error`, the typed error text of a grid without output), masks, `outs` and test predictions.
    `guard_s` is the CPU-time limit per grid; the step limit (deterministic) normally stops a runaway program first.
    One deliberate difference: execution stops at the first grid that exceeds the step or time limit, with an
    "execution exceeded ..." reason (cora_exec's own time guard stops a whole program the same way), instead of
    running every remaining grid into the same limit. Test inputs run only if every demonstration is reproduced."""
    import numpy as np
    from cora_neural_hybrid import execute as EX
    from cora_neural_v2g3 import delta as D
    sb = sandbox or SB.default()
    limits = limits or sb.limits
    if not isinstance(program, Program):
        src = program
        try:
            program = parse(src)
        except GridFnError as e:
            ex = EX.Execution("INVALID", str(e))
            ex.provenance = {"language": VERSION, "parse": parse_record(src), "card_sha256": CARD_SHA256}
            ex.grid_errors, ex.test_errors = [], []
            return ex
    train = task["train"]
    prov = {"language": VERSION, "parse": program.info(), "card_sha256": CARD_SHA256, "limits": limits.as_dict(),
            "cpu_s": guard_s, "steps": [], "cpu": [], "test_steps": []}

    def attach(ex, outs, demo_reps, test_reps=()):
        ex.outs = outs
        ex.grid_errors = [_err_row(r) for r in demo_reps]
        ex.test_errors = [_err_row(r) for r in test_reps]
        ex.provenance = prov
        ex.program = program
        return ex

    reps, outs = [], []
    for i, (a, _) in enumerate(train):
        rep = program.execute_grid(a, sb, limits, guard_s)
        reps.append(rep)
        prov["steps"].append(rep.get("steps"))
        prov["cpu"].append(rep.get("cpu"))
        outs.append(np.asarray(rep["out"]) if rep.get("ok") else None)
        if rep.get("kind") in LIMIT_KINDS:
            outs += [None] * (len(train) - len(outs))
            return attach(EX.Execution("ERROR", _limit_reason(rep, f"example {i + 1}", limits, guard_s)), outs, reps)
    preds, test_reps = None, []
    if all(o is not None and o.shape == np.asarray(b).shape and np.array_equal(o, np.asarray(b))
           for o, (_, b) in zip(outs, train)):
        for j, t in enumerate(task["test_inputs"]):
            rep = program.execute_grid(t, sb, limits, guard_s)
            test_reps.append(rep)
            prov["test_steps"].append(rep.get("steps"))
            if rep.get("kind") in LIMIT_KINDS:
                return attach(EX.Execution("ERROR", _limit_reason(rep, f"test input {j + 1}", limits, guard_s)),
                              outs, reps, test_reps)
        preds = [np.asarray(r["out"]) if r.get("ok") else None for r in test_reps]
    ds, per = [], []
    for (a, b), o, rep in zip(train, outs, reps):
        A, B = np.asarray(a), np.asarray(b)
        if o is None or o.shape != B.shape:
            ds.append(D.DemoDelta(False, B.shape, None if o is None else o.shape))
            per.append({"shape_ok": False, "expected_shape": list(B.shape),
                        "got_shape": None if o is None else list(o.shape), "wrong": None, "fixed": None,
                        "broken": None, "remaining": None, "changed": None, "precision": None, "recall": None,
                        "error": error_text(rep)})
            continue
        wrong = o != B
        row = {"shape_ok": True, "wrong": int(wrong.sum()), "cells": int(wrong.size)}
        if A.shape == B.shape:
            diff = A != B
            fixed, broken, remaining = diff & ~wrong, ~diff & wrong, diff & wrong
            ds.append(D.DemoDelta(True, B.shape, o.shape, wrong, fixed, broken, remaining))
            changed = int((o != A).sum())
            row.update(fixed=int(fixed.sum()), broken=int(broken.sum()), remaining=int(remaining.sum()),
                       changed=changed, precision=(int(fixed.sum()) / changed) if changed else None,
                       recall=(int(fixed.sum()) / int(diff.sum())) if int(diff.sum()) else None)
        else:
            ds.append(D.DemoDelta(True, B.shape, o.shape, wrong))
            row.update(fixed=None, broken=None, remaining=None, changed=None, precision=None, recall=None)
        per.append(row)
    if not all(d.shape_ok for d in ds):
        return attach(EX.Execution("ERROR", "no output or wrong output shape", per_demo=per, deltas=ds), outs, reps)
    tot = {k: sum((p[k] or 0) for p in per) for k in ("wrong", "fixed", "broken", "remaining")}
    if tot["wrong"]:
        return attach(EX.Execution("INCOMPLETE", "", per_demo=per, deltas=ds, **tot), outs, reps)
    if preds is None or any(p is None for p in preds):
        bad = [(j, error_text(r)) for j, r in enumerate(test_reps) if not r.get("ok")]
        why = "; ".join(f"test input {j + 1}: {e or 'no output'}" for j, e in bad[:2])
        return attach(EX.Execution("ERROR", f"no output on a test input ({why})", per_demo=per, deltas=ds, **tot),
                      outs, reps, test_reps)
    return attach(EX.Execution("FITS", "", per_demo=per, deltas=ds, preds=preds, **tot), outs, reps, test_reps)


def predict(program, grid):
    """The program's output for one grid as a numpy array, or None (llm_writer.cora_exec.predict)."""
    import numpy as np
    out = program.run(grid)
    return None if out is None else np.asarray(out)


def error_feedback(ex, max_items=3):
    """Lines naming the typed errors of the grids that failed (for example "Example 2: RuntimeFault: index 9 is out
    of range ... (line 7)"), to append to CORA's diagnosis of a grid-function program; '' if none."""
    lines = []
    for i, e in enumerate(getattr(ex, "grid_errors", None) or []):
        if e is not None and len(lines) < max_items:
            line = f" (line {e['line']})" if e.get("line") else ""
            lines.append(f"Example {i + 1}: {e['kind']}: {e['message']}{line}")
    for j, e in enumerate(getattr(ex, "test_errors", None) or []):
        if e is not None and len(lines) < max_items:
            line = f" (line {e['line']})" if e.get("line") else ""
            lines.append(f"Test input {j + 1}: {e['kind']}: {e['message']}{line}")
    return "\n".join(lines)


def head(training, sep=""):
    """CARD followed by the worked examples, as the CORA prompt's `Prompter.head`."""
    return CARD + "\n" + C.fewshot_text(training, sep) + "\n\n"
