"""Exact read-only CORA dependencies inside this isolated worktree."""
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPRINT = ROOT / 'experiments' / 'independent_synthesis_20261029'
PINS = {
    'E25': ('round25/diagnosis_constructor/engine.py', '009788d7071929240a5231032eaeb3e783b1313e92aea14a9a81043dccb56559'),
    'G': ('round25/capability_growth/library.py', '974dab6c9e98df7f024081c7c4599e7b9242be39cc5f0763987fe5e60ea83dc6'),
    'E': ('round26/coverage_constructor/engine.py', '0e513986bd94565fa0c572f4dbd6dfd5a698a8fa87188f2f876e27f607919a82'),
    'M': ('round27/learned_local_rules/model.py', '110bcb0c19801d22fc27de7f38b34d1c7e7aca65afdbcb7d0b10980b00a3fbd6'),
}

def _load(name):
    relative, sha = PINS[name]
    path = SPRINT / relative
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise RuntimeError('FROZEN_DEPENDENCY_CHANGED:' + name)
    spec = importlib.util.spec_from_file_location('_cage_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

E25, G, E, M = (_load(name) for name in ('E25', 'G', 'E', 'M'))
