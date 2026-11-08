"""Write FREEZE.json: sha256 of the code, configuration, data manifest, data files, protocol and reused core files."""
import hashlib, json, os, platform, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(HERE))
rel = lambda p: os.path.relpath(p, REPO)
files = []
for d in ("t5", "scripts", "tests"):
    for f in sorted(os.listdir(os.path.join(HERE, d))):
        if f.endswith(".py"):
            files.append(os.path.join(HERE, d, f))
for f in ("config_held.json", "config_dev.json", "DATA_MANIFEST.md", "PROTOCOL.md", "ADAPTER_CARD.md"):
    files.append(os.path.join(HERE, f))
for f in ("ToyPKNMMB.sif", "ToyDataMMB.csv", "LiverPKNDREAM.sif", "LiverDataDREAMMIDAS.csv"):
    files.append(os.path.join(HERE, "data", "raw", f))
core = os.path.join(os.path.dirname(HERE), "universality_boolean_bbm_20261103", "u6")
for f in ("__init__.py", "bn.py", "stats.py"):
    files.append(os.path.join(core, f))
out = {"test": "T5 signalling logic models", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
       "amendment": 1,
       "salt_rule": "the sha256 of GO.json, which the coordinator commits alone after the change review; GO.json holds "
                    "freeze_commit (the last commit that changed this file), freeze_json_sha256, utc, a 64-hex nonce "
                    "from secrets.token_hex(32) and the review hashes (PROTOCOL.md section 9)",
       "python": platform.python_version(), "numpy": __import__("numpy").__version__,
       "run": "sh scripts/run_detached.sh t5_held_score --slot python3 -I "
              "experiments/transfer_signalling_20261108/scripts/score_held.py --salt <sha256 of GO.json>",
       "files": {rel(p): hashlib.sha256(open(p, "rb").read()).hexdigest() for p in files}}
json.dump(out, open(os.path.join(HERE, "FREEZE.json"), "w"), indent=1)
print(len(out["files"]), "files frozen")
