"""Test harness: run a driver command on a synthetic world's Config, recording every attempt to open an answer file.

    python -I run_driver.py CONFIG.json run|close|check-inputs [OPEN_LOG.json]

The recording audit hook is added before the driver's answer guard, so it sees refused attempts too."""
import json
import os
import sys

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import common as C              # noqa: E402
from testb import driver as DR             # noqa: E402

cfg = DR.Config(**C.load_json(sys.argv[1]))
WATCH = {os.path.realpath(p) for p in C.load_json(cfg.protocol_freeze)["answers_scorer_only"]}
LOG = []


def hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.fsdecode(args[0])
        if C.ANSWER_NAME.search(os.path.basename(p)) or os.path.realpath(p) in WATCH:
            LOG.append(p)


sys.addaudithook(hook)
code, msg = 0, None
try:
    {"run": DR.run, "close": DR.close, "check-inputs": DR.check_inputs}[sys.argv[2]](cfg)
except SystemExit as e:
    code, msg = 1, str(e)
finally:
    if len(sys.argv) > 3:
        with open(sys.argv[3], "w") as f:
            json.dump({"answer_open_attempts": LOG, "exit": msg}, f)
if msg:
    print(msg, file=sys.stderr)
sys.exit(code)
