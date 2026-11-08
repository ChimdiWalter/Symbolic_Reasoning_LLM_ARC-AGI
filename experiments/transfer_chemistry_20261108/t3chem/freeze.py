"""Write FREEZE.json: the sha256 of the code, the configuration, the data manifest, the protocol, the derived
item pool and the raw data files, and the Python and RDKit versions. Run with the study's Python
(python3 -I). The scoring salt is not in this file: it is the sha256 of the committed bytes
of the original runs/GO, written by the coordinator after the pre-run review (PROTOCOL.md Amendment 1). Under
Amendment 2 the coordinator's runs/GO_AMENDMENT2 names this freeze for the rerun."""
import datetime, hashlib, json, os, platform

import rdkit

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = ["t3chem/__init__.py", "t3chem/chem.py", "t3chem/library.py", "t3chem/arms.py", "t3chem/stats.py",
        "t3chem/run.py", "t3chem/build_items.py", "t3chem/freeze.py", "launch/run_score.sh"]
CONFIG = ["config/T3_CONFIG.json"]
MANIFEST = ["DATA_MANIFEST.md"]
OTHER = ["PROTOCOL.md", "data/POOL.json", "data/cache/items.jsonl.gz",
         "data/raw/enzymemap/enzymemap_v2_brenda2023.csv.gz", "data/raw/enzymemap/compound_to_smiles.json",
         "data/raw/pickaxe/metacyc_generalized_rules.tsv", "data/raw/pickaxe/metacyc_coreactants.tsv"]


def sha(p):
    h = hashlib.sha256()
    with open(os.path.join(STUDY, p), "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def group(paths):
    h = hashlib.sha256()
    for p in paths:
        h.update((p + " " + sha(p) + "\n").encode())
    return h.hexdigest()


files = {p: sha(p) for p in CODE + CONFIG + MANIFEST + OTHER}
out = {"study": "transfer_chemistry_20261108", "test": "T3 chemistry",
       "label": "real data; reconstruction of known enzyme transformations on held substrates, not discovery",
       "frozen_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "code_sha256": group(CODE), "config_sha256": group(CONFIG), "manifest_sha256": group(MANIFEST),
       "protocol_sha256": files["PROTOCOL.md"], "files_sha256": files,
       "environment": {"python": platform.python_version(), "rdkit": rdkit.__version__},
       "salt_rule": "salt = sha256 of the committed bytes of the original runs/GO (Amendment 1, unchanged by "
                    "Amendment 2); runs/GO_AMENDMENT2, written and committed alone by the coordinator after the "
                    "delta review, names this freeze commit, which must be the last commit on HEAD that changed "
                    "this file; run.py refuses to score otherwise"}
json.dump(out, open(os.path.join(STUDY, "FREEZE.json"), "w"), indent=1, sort_keys=True)
print(json.dumps({k: out[k] for k in ("code_sha256", "config_sha256", "manifest_sha256", "protocol_sha256")}))
