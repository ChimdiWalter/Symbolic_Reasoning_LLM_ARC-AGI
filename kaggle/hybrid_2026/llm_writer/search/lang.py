"""The two program languages, behind one small interface: parse, key, render, size, check and execute.

- "cora": typed CORA programs (rast N, version 4 G4Program), parsed by `llm_writer.surface`, type-checked by
  `cora_neural_hybrid.execute.check`, executed by `llm_writer.cora_exec.run` (native CORA's interpreters).
- "gridfn": the bounded grid-function language, parsed and allowlist-checked by `llm_writer.gridfn.adapter.parse`,
  executed by `llm_writer.gridfn.adapter.execute` in its isolated worker (the record of `cora_exec.run`).
Parsing never executes anything, and nothing a model wrote is ever run as Python.
"""


class Cora:
    name = "cora"

    @staticmethod
    def parse(src):
        from llm_writer import surface as SF
        return SF.parse(src)

    @staticmethod
    def key(prog):
        from llm_writer import surface as SF
        return SF.key(prog)

    @staticmethod
    def render(prog):
        from llm_writer import surface as SF
        return SF.render(prog)

    @staticmethod
    def size(prog):
        from cora_neural_v2.rast import N
        from cora_neural_v2g4 import program as PG
        n = 0

        def walk(x):
            nonlocal n
            if isinstance(x, N):
                n += 1
                for a in x.args:
                    walk(a)
            elif isinstance(x, tuple):
                for a in x:
                    walk(a)
            elif isinstance(x, PG.PartRule) or isinstance(x, PG.RayRule):
                n += 1
                walk(x.sel)
            else:
                n += 1
        if isinstance(prog, PG.G4Program):
            n += 1
            if prog.base is not None:
                walk(prog.base)
            for r in prog.rules:
                walk(r)
        else:
            walk(prog)
        return n

    @staticmethod
    def check(prog):
        from cora_neural_hybrid import execute as EX
        try:
            return EX.check(prog)[0]
        except Exception:                                  # noqa: BLE001 (an ill-formed mutant is simply invalid)
            return False

    @staticmethod
    def execute(prog, task, guard_s=5.0, gridfn_steps=None):   # noqa: ARG004
        from llm_writer import cora_exec as CX
        return CX.run(prog, task, guard_s)


class GridFn:
    name = "gridfn"

    @staticmethod
    def parse(src):
        from llm_writer.gridfn import adapter as GA
        return GA.parse(src)

    @staticmethod
    def key(prog):
        return prog.key()

    @staticmethod
    def render(prog):
        return prog.render()

    @staticmethod
    def size(prog):
        return prog.size()

    @staticmethod
    def check(prog):
        return prog is not None

    @staticmethod
    def execute(prog, task, guard_s=5.0, gridfn_steps=2_000_000):
        from llm_writer.gridfn import adapter as GA
        from llm_writer.gridfn import interp as I
        limits = I.Limits(max_steps=int(gridfn_steps)) if gridfn_steps else None
        return GA.execute(prog, task, guard_s=min(float(guard_s), 2.0), limits=limits)


LANGUAGES = {"cora": Cora, "gridfn": GridFn}


def get(name):
    if name not in LANGUAGES:
        raise ValueError(f"unknown language {name!r}")
    return LANGUAGES[name]
