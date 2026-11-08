"""Invented operators: parse a proposal, check it, and run it only inside the gridfn sandbox.

A proposal is a plain-text specification followed by one fenced code block:
    LEVEL / GAP / NAME / PARAMS / SEMANTICS / PRECONDITIONS / USE lines, then
    ```python
    def new_op(grid[, k]): ...          # helpers allowed
    TESTS = [(input, expected), ...]    # or (input, k, expected)
    ```
Substrate: the gridfn-1 dialect (no imports, no numpy) checked by llm_writer.gridfn.lang.check and executed only by
the isolated worker (llm_writer.gridfn.sandbox, rlimits, CPU timer, step limit). The gridfn primitive library is
refused except shape, new_grid and copy: the library already contains trim, upscale, downscale and other named
grid operations, so an invention may not call them (checked from the checker's record of names used). At most one
integer parameter with a declared range inside 0..30. Nothing here executes model text as Python.
"""
import ast
import hashlib
import re

from cgrow import paths as P

P.ensure_import_paths()
from a2 import arcdsl as D                       # noqa: E402
from llm_writer.gridfn import lang as GL         # noqa: E402
from llm_writer.gridfn import sandbox as SB      # noqa: E402

ALLOWED_PRIMS = frozenset({"shape", "new_grid", "copy"})
FIELDS = ("OBSERVATION", "LEVEL", "GAP", "NAME", "PARAMS", "SEMANTICS", "PRECONDITIONS", "USE")
LEVELS = ("representation", "interpretation", "relation", "operation", "composition", "search",
          "insufficient_evidence")
CODE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)
PARAM = re.compile(r"([A-Za-z_]\w*)\s*:\s*int\w*\s*(?:in\s*)?\[?\(?\s*(-?\d+)\s*(?:\.\.|-|,|to)\s*(-?\d+)", re.I)
CALL_CPU_S = 0.5
MAX_TEST_SIDE = 30


class Rejected(Exception):
    def __init__(self, kind, message):
        self.kind, self.message = kind, message
        super().__init__(f"{kind}: {message}")


def parse(text):
    """Header fields, code, tests and parameter declaration; raises Rejected with a typed kind."""
    m = CODE.search(text or "")
    if not m:
        raise Rejected("no_code_block", "no fenced code block (reply unfinished or malformed)")
    head = text[:m.start()]
    fields = {}
    for line in head.splitlines():
        mm = re.match(r"\s*\**\s*([A-Z]+)\s*\**\s*:\s*(.*)", line)
        if mm and mm.group(1) in FIELDS:
            fields[mm.group(1)] = mm.group(2).strip()
    code = m.group(1)
    try:
        mod = ast.parse(code)
    except SyntaxError as e:
        raise Rejected("syntax_error", str(e)[:200])
    tests, body, fn_names = [], [], set()
    for st in mod.body:
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name) \
                and st.targets[0].id == "TESTS":
            try:
                tests = ast.literal_eval(st.value)
            except (ValueError, SyntaxError):
                tests = "unparsable"
            continue
        if isinstance(st, ast.FunctionDef):
            fn_names.add(st.name)
        body.append(st)
    if "new_op" not in fn_names:
        # interface tolerance, the same in every arm: `transform`, the function named in NAME, or the only
        # top-level function is taken as the operation (and renamed; calls to it are renamed too)
        named = (fields.get("NAME") or "").strip().strip("`").lower()
        pick = "transform" if "transform" in fn_names else next(
            (n for n in fn_names if n.lower() == named), None) or (next(iter(fn_names)) if len(fn_names) == 1 else None)
        if pick is None:
            raise Rejected("no_new_op", "the code defines no new_op function")
        for node in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(node, ast.FunctionDef) and node.name == pick:
                node.name = "new_op"
            elif isinstance(node, ast.Name) and node.id == pick:
                node.id = "new_op"
        fn_names.discard(pick)
        fn_names.add("new_op")
    body = [st for st in body if not (isinstance(st, ast.FunctionDef) and st.name == "transform")]
    new_op = next(st for st in body if isinstance(st, ast.FunctionDef) and st.name == "new_op")
    decl = fields.get("PARAMS", "none")
    pm = PARAM.search(decl)
    if len(new_op.args.args) == 1 and pm:
        # interface tolerance, the same in every arm: a parameter declared in PARAMS and used as a free name in
        # new_op's body, but missing from its signature, is added as the second argument
        pname = pm.group(1)
        bound = {a.arg for a in new_op.args.args} | {n.id for n in ast.walk(new_op) if isinstance(n, ast.Name)
                                                       and isinstance(n.ctx, ast.Store)}
        used = {n.id for n in ast.walk(new_op) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        if pname in used and pname not in bound:
            new_op.args.args.append(ast.arg(arg=pname))
    n_args = len(new_op.args.args)
    params = []
    if n_args == 2:
        if pm:
            lo, hi = int(pm.group(2)), int(pm.group(3))
        else:
            lo, hi = 0, 9                     # undeclared range: colours or small counts
        lo, hi = max(0, min(lo, hi)), min(30, max(lo, hi))
        params = [{"name": new_op.args.args[1].arg, "lo": lo, "hi": hi}]
    elif n_args != 1:
        raise Rejected("bad_signature", f"new_op takes {n_args} arguments; allowed: (grid) or (grid, k)")
    src = ast.unparse(ast.Module(body=body, type_ignores=[]))
    return {"fields": fields, "code": src, "params": params, "tests": tests, "raw_code": code}


def program_text(code, ints):
    call = ", ".join(["grid"] + [str(int(v)) for v in ints])
    return f"{code}\n\n\ndef transform(grid):\n    return new_op({call})\n"


def check(prop):
    """Allowlist check of the code (with a sample binding) and the substrate restriction."""
    ints = [p["lo"] for p in prop["params"]]
    try:
        chk = GL.check(program_text(prop["code"], ints))
    except GL.GridFnError as e:
        raise Rejected("check_" + e.kind, e.message[:200])
    used = set(chk.primitives)
    bad = sorted(used - ALLOWED_PRIMS)
    if bad:
        raise Rejected("substrate_violation", "uses library primitives " + ", ".join(bad))
    return {"nodes": chk.nodes, "primitives": sorted(used), "canonical_sha256": chk.canonical_sha256,
            "src_sha256": hashlib.sha256(prop["code"].encode()).hexdigest()}


def _to_list(g):
    return [list(r) for r in g]


def _to_grid(x):
    if not isinstance(x, list) or not x or not all(isinstance(r, list) and r for r in x):
        return None
    w = len(x[0])
    if len(x) > MAX_TEST_SIDE or w > MAX_TEST_SIDE or any(len(r) != w for r in x):
        return None
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in x for v in r):
        return None
    return tuple(tuple(r) for r in x)


class SandboxOp:
    """Callable production for A2's search: (grid[, int]) -> grid, run in the isolated worker, memoized."""

    def __init__(self, prop, cap_calls=6000):
        self.code, self.params = prop["code"], prop["params"]
        self.n_params = len(self.params)
        self.cap, self.calls, self.capped, self.errors = cap_calls, 0, False, {}
        self.cache, self.src = {}, {}
        self.sb = SB.default()
        self.worker_cpu = 0.0

    def reset_cap(self, cap_calls):
        self.cap, self.calls, self.capped = cap_calls, 0, False

    def __call__(self, grid, *ints):
        if D.tag(grid) != "G" or len(ints) != self.n_params:
            raise D.Bad("type")
        for v, p in zip(ints, self.params):
            if type(v) is not int or not p["lo"] <= v <= p["hi"]:
                raise D.Bad("param range")
        key = (grid, ints)
        if key in self.cache:
            v = self.cache[key]
            if v is None:
                raise D.Bad("op error")
            return v
        if self.calls >= self.cap:
            self.capped = True
            raise D.Bad("call cap")
        self.calls += 1
        if ints not in self.src:
            self.src[ints] = program_text(self.code, ints)
        rep = self.sb.run(self.src[ints], _to_list(grid), cpu_s=CALL_CPU_S)
        self.worker_cpu += rep.get("cpu") or 0.0
        out = _to_grid(rep["out"]) if rep.get("ok") else None
        if out is None:
            k = rep.get("kind") or "bad_output"
            self.errors[k] = self.errors.get(k, 0) + 1
        self.cache[key] = out
        if out is None:
            raise D.Bad("op error")
        return out

    def apply(self, grid, ints=()):
        """Value or None (no exception)."""
        try:
            return self(grid, *ints)
        except D.Bad:
            return None


def run_tests(op, tests):
    """The proposal's own tests: list of {passed, detail}; malformed tests are recorded, not run."""
    out = []
    if not isinstance(tests, (list, tuple)):
        return [{"id": "tests", "passed": None, "detail": "TESTS missing or unparsable"}]
    for i, t in enumerate(tests[:12]):
        rec = {"id": f"t{i}", "passed": None, "detail": None}
        try:
            if op.n_params == 0 and len(t) == 2:
                x, ints, y = t[0], (), t[1]
            elif op.n_params == 1 and len(t) == 3:
                x, ints, y = t[0], (int(t[1]),), t[2]
            else:
                rec["detail"] = "wrong arity"
                out.append(rec)
                continue
            gx, gy = _to_grid(x), _to_grid(y)
            if gx is None or gy is None:
                rec["detail"] = "not a grid"
                out.append(rec)
                continue
            got = op.apply(gx, ints)
            rec["passed"] = got == gy
            rec["detail"] = None if rec["passed"] else ("error" if got is None else "mismatch")
        except (TypeError, ValueError, IndexError):
            rec["detail"] = "malformed"
        out.append(rec)
    return out
