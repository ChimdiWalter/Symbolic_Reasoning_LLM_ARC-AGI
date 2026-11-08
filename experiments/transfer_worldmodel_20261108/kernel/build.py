"""Build the kernel script from kernel/probe_template.py by embedding the study's own analysis code (wm/*.py).

    python3 -I kernel/build.py          -> kernel/probe.py       (MODE = "dev": development games)
    python3 -I kernel/build.py held     -> kernel/probe_held.py  (MODE = "held": held games; push only after the GO)

To push, copy the built file as probe.py next to kernel-metadata.json in an empty folder.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ST = os.path.dirname(HERE)
FILES = ("__init__.py", "envs.py", "model.py", "induce.py", "arc3.py")
mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
assert mode in ("dev", "held")
src = {f: open(os.path.join(ST, "wm", f)).read() for f in FILES}
tpl = open(os.path.join(HERE, "probe_template.py")).read()
assert tpl.count("WM_SOURCES = {}") == 1 and tpl.count('MODE = "dev"') == 1
out = tpl.replace("WM_SOURCES = {}", "WM_SOURCES = " + json.dumps(src)).replace('MODE = "dev"', f'MODE = "{mode}"')
name = "probe.py" if mode == "dev" else "probe_held.py"
open(os.path.join(HERE, name), "w").write(out)
print("built", name, "mode", mode)
