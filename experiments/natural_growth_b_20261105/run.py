"""Entry point of study B (run with python -I; the study folder is put on sys.path here).

    python -I run.py <module> [args...]            run ngb.<module>.main(*args)
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    if sys.argv[1] == "seed_probe":                      # one hash-seed probe (ngb/seed_check.py)
        from ngb import seed_check as SK
        SK.probe(sys.argv[2], [a.split(":") for a in sys.argv[3:]])
    elif sys.argv[1] == "seed_probe_construct":          # one construction probe (ngb/seed_check.py)
        from ngb import seed_check as SK
        SK.probe_construct([a.split(":") for a in sys.argv[2:]])
    else:
        mod = importlib.import_module("ngb." + sys.argv[1])
        mod.main(*sys.argv[2:])
