"""Test harness: run the scorer on a synthetic world's Config and log every open of a "*solutions*" path, with
whether runs/SCORE_CLAIM.json existed at that moment.

    python -I run_scorer.py CONFIG.json REVIEW OPEN_LOG.json"""
import json
import os
import sys

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import common as C              # noqa: E402
from testb import driver as DR             # noqa: E402
from testb import scorer as SC             # noqa: E402

cfg = DR.Config(**C.load_json(sys.argv[1]))
CLAIM = os.path.join(cfg.runs, "SCORE_CLAIM.json")
LOG = []


def hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.fsdecode(args[0])
        if C.ANSWER_NAME.search(os.path.basename(p)):
            LOG.append({"path": p, "claim_existed": os.path.exists(CLAIM)})


sys.addaudithook(hook)
code, msg, training = 0, None, None
try:
    SC.score(cfg, sys.argv[2])
except SystemExit as e:
    code, msg = 1, str(e)
finally:
    try:                                   # training answers must stay unreadable in the scorer
        with open(os.path.join(os.path.dirname(next(iter(C.load_json(cfg.protocol_freeze)["answers_scorer_only"]))),
                               "synthetic_training_solutions.json"), "rb") as f:
            f.read(1)
        training = "read"
    except PermissionError:
        training = "refused"
    with open(sys.argv[3], "w") as f:
        json.dump({"opens": LOG, "exit": msg, "training_answers": training}, f)
if msg:
    print(msg, file=sys.stderr)
sys.exit(code)
