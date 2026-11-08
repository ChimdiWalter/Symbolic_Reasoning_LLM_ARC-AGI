"""Entry point of the guided-construction test (run with PYTHONHASHSEED=0 and python -s -B; the study folder is put
on sys.path here).

    python -s -B run.py <module> [args...]            run gcon.<module>.main(*args)
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("run with PYTHONHASHSEED=0")
    mod = importlib.import_module("gcon." + sys.argv[1])
    mod.main(*sys.argv[2:])
