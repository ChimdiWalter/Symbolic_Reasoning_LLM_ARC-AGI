"""Entry point of the library-rivals test: python3 -I run.py <command> [args] (see PROTOCOL.md section 9)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        from lr import libraries as LB
        import json
        out = LB.build()
        print(json.dumps({b: {k: (v if not isinstance(v, list) else len(v)) for k, v in d.items()}
                          for b, d in out["benchmarks"].items()}, indent=1))
    else:
        import importlib
        mod = importlib.import_module("lr." + cmd)
        mod.main(*sys.argv[2:])
