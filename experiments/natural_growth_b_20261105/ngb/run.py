"""Entry point of study B (run with python -I from anywhere; the study folder and study A go on sys.path here).

    python -I ngb/run.py <module> [args...]        run ngb.<module>.main(*args)
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    mod = importlib.import_module("ngb." + sys.argv[1])
    mod.main(*sys.argv[2:])
