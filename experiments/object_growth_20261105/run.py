"""Entry point of the object-level construction step (run with python -I; the study folder is put on sys.path here).

    python -I run.py <module> [args...]            run objgrow.<module>.main(*args)
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    mod = importlib.import_module("objgrow." + sys.argv[1])
    mod.main(*sys.argv[2:])
