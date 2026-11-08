"""Environment of the construction test at scale: imports of the frozen construction-test (S1) code, read-only,
and the write guard of this study.

The study reuses the S1 code in `experiments/capability_growth_20261027/cgrow/` without changing any of its files.
That code reads its folders from module constants of `cgrow.paths` (HERE, RUNS, PARTITIONS, EVALUATOR_DIR, ...).
`use_world(dir)` points those constants at one world folder of this study, so the frozen gates, controller and
search read and write there and nowhere else. `check_write` refuses any write outside this study's folder.

Root folders come from the environment variable CAS_ROOT (a package copy on Kaggle) or default to the repository.
"""
import hashlib
import json
import os
import sys

REPO = os.environ.get("CAS_REPO", "/path/to/repository")
STUDY = os.environ.get("CAS_STUDY", os.path.join(REPO, "experiments", "construction_at_scale_20261105"))
S1_DIR = os.path.join(REPO, "experiments", "capability_growth_20261027")
SWEEP = os.path.join(REPO, "experiments", "architecture_sweep_20261026")

PACKAGE = os.environ.get("CAS_PACKAGE") == "1"
PROJECT_PACKAGES = ("cgrow", "a2", "harness", "cast", "cas", "llm_writer")


def _stub_sandbox():
    """The sandbox for model-written code (llm_writer.gridfn) is imported by cgrow.invent but used only by S1's
    neural methods, none of which runs in this study. It is replaced, everywhere and always (on Athe as in the
    kernel package, as in the S1 replay), by a stub that raises if anything calls it."""
    import types
    if "llm_writer" in sys.modules:
        return

    def refuse(*a, **k):
        raise RuntimeError("model-written code is never executed in this study")

    class GridFnError(Exception):
        pass
    pkg, gridfn = types.ModuleType("llm_writer"), types.ModuleType("llm_writer.gridfn")
    lang, sandbox = types.ModuleType("llm_writer.gridfn.lang"), types.ModuleType("llm_writer.gridfn.sandbox")
    pkg.__path__, gridfn.__path__ = [], []
    pkg.__cas_stub__ = gridfn.__cas_stub__ = lang.__cas_stub__ = sandbox.__cas_stub__ = True
    lang.GridFnError, lang.check, sandbox.default = GridFnError, refuse, refuse
    pkg.gridfn, gridfn.lang, gridfn.sandbox = gridfn, lang, sandbox
    sys.modules.update({"llm_writer": pkg, "llm_writer.gridfn": gridfn, "llm_writer.gridfn.lang": lang,
                        "llm_writer.gridfn.sandbox": sandbox})


def _package_setup():
    """In a package copy (Kaggle): the S1 replay shim's steps. The package's own experiment folders go first on
    sys.path and its a2 and harness are imported before cgrow.paths; the constants the frozen code reads
    (cgrow.paths and a2.arcdsl.DSL_DIR) point at the package's copies."""
    for p in (S1_DIR, SWEEP):
        if p not in sys.path:
            sys.path.insert(0, p)
    import a2                                                                   # noqa: F401
    import harness                                                              # noqa: F401
    from a2 import arcdsl
    arcdsl.DSL_DIR = os.path.join(REPO, "outputs", "search_components", "resources_20261026", "github", "arc-dsl")


_stub_sandbox()
if PACKAGE:
    _package_setup()
if S1_DIR not in sys.path:
    sys.path.insert(0, S1_DIR)
from cgrow import paths as P                                                    # noqa: E402

if PACKAGE:
    P.REPO, P.SWEEP = REPO, SWEEP
    P.HYBRID = os.path.join(REPO, "kaggle", "hybrid_2026")
P.ensure_import_paths()


def loaded_modules():
    """Every loaded module of the project's packages: {name: (path relative to REPO or 'stub', sha256 or None)}."""
    out = {}
    for name, mod in sorted(sys.modules.items()):
        if name == "__main__" and getattr(mod, "__file__", None):
            # the entry module (python -m cas.x runs it as __main__): pinned under its path
            rp = os.path.realpath(mod.__file__)
            if rp.startswith(os.path.realpath(REPO) + os.sep):
                rel = os.path.relpath(rp, os.path.realpath(REPO))
                out["__main__ (" + rel + ")"] = (rel, sha256(rp))
            continue
        if name.split(".")[0] not in PROJECT_PACKAGES:
            continue
        if getattr(mod, "__cas_stub__", False):
            out[name] = ("stub", None)
            continue
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        rp = os.path.realpath(f)
        rel = os.path.relpath(rp, os.path.realpath(REPO))
        out[name] = (rel, sha256(rp) if os.path.exists(rp) else None)
    return out


def pin_record(path):
    """Write the executed project modules with their digests and check them against FREEZE.json (files_sha256 for
    this study's code, dependencies_sha256 for the rest). Records the result; never raises, so that a phase 1 check
    can run against unfrozen code. Phase 2's analysis requires ok == true in every record."""
    mods = loaded_modules()
    fz_path = os.path.join(STUDY, "FREEZE.json")
    pins = {}
    if os.path.exists(fz_path):
        fz = load(fz_path)
        pins.update({os.path.join("experiments", "construction_at_scale_20261105", k): v
                     for k, v in fz.get("files_sha256", {}).items()})
        pins.update(fz.get("dependencies_sha256", {}))
    mism = {}
    for name, (rel, h) in mods.items():
        if rel == "stub":
            continue
        if rel not in pins:
            mism[name] = "executed module not pinned: " + rel
        elif pins[rel] != h:
            mism[name] = "digest differs from the freeze: " + rel
    rec = {"modules": {n: {"path": r, "sha256": h} for n, (r, h) in mods.items()}, "mismatches": mism,
           "ok": not mism and bool(pins), "freeze_present": bool(pins)}
    dump(path, rec)
    return rec


class WriteRefused(PermissionError):
    pass


def check_write(path):
    rp = os.path.realpath(path)
    if not rp.startswith(os.path.realpath(STUDY) + os.sep) or P.DENY.search(rp):
        raise WriteRefused(f"write outside the study folder: {path}")
    return rp


def open_write(path, mode="w"):
    check_write(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return open(path, mode, encoding="utf-8")


def dump(path, obj, indent=1):
    with open_write(path) as f:
        json.dump(obj, f, indent=indent, sort_keys=True, default=list)
        f.write("\n")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def use_world(world_dir):
    """Point the frozen S1 code's folder constants at one world folder of this study (all its reads and writes)."""
    wd = os.path.realpath(world_dir)
    check_write(os.path.join(wd, "x"))
    P.HERE = wd
    P.RUNS = os.path.join(wd, "runs")
    P.PARTITIONS = os.path.join(wd, "partitions")
    P.REGISTRY_DIR = os.path.join(wd, "registry")
    P.REPORTS = os.path.join(wd, "reports")
    P.EVALUATOR_DIR = os.path.join(wd, "evaluator_only")
    P.LEDGER = os.path.join(wd, "runs", "LOCAL_LEDGER.jsonl")
    return P
