"""Entry point of the natural-task growth test (run with python -I; the study folder is put on sys.path here).

    python -I run.py split-write                   write split/SPLIT.json once (task identities only)
    python -I run.py <module> [args...]            run ngrow.<module>.main(*args)
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    if sys.argv[1] == "split-write":
        sys.argv = [sys.argv[0], "write"]
        import runpy
        runpy.run_module("ngrow.data", run_name="__main__")
    else:
        mod = importlib.import_module("ngrow." + sys.argv[1])
        mod.main(*sys.argv[2:])
