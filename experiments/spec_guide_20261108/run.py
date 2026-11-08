"""Entry point of the specification-reading guide test (PYTHONHASHSEED=0; python -s -B; the study folder is put on
sys.path here).

    python -s -B run.py <module> [args...]            run sgd.<module>.main(*args)
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    if os.environ.get("PYTHONHASHSEED") != "0" or sys.flags.ignore_environment:
        raise SystemExit("run with PYTHONHASHSEED=0 and without -I or -E")
    mod = importlib.import_module("sgd." + sys.argv[1])
    mod.main(*sys.argv[2:])
