"""Write FREEZE.json: sha256 of the code, the configuration, the data manifest, the protocol and the exact kernel file
for the held run.

    python3 -I freeze.py DEV_KERNEL_VERSION
"""
import hashlib
import json
import os
import sys

ST = os.path.dirname(os.path.abspath(__file__))
FILES = ["wm/__init__.py", "wm/envs.py", "wm/model.py", "wm/induce.py", "wm/arc3.py", "kernel/probe_template.py",
         "kernel/build.py", "kernel/kernel-metadata.json", "kernel/probe.py", "kernel/probe_held.py",
         "config/STUDY_CONFIG.json", "DATA_MANIFEST.md", "PROTOCOL.md", "DESIGN_NOTE.md", "ADAPTER_CARD.md"]


def sha(p):
    return hashlib.sha256(open(os.path.join(ST, p), "rb").read()).hexdigest()


v = sys.argv[1]
dev = os.path.join("data", "kernel_output", f"v{v}", "t4_out", "analysis.json")
out = {"study": "transfer_worldmodel_20261108",
       "label": "probe on public ARC-AGI-3 games; world-model induction; not a score",
       "kernel": "chimdiwalter/t4-arc-agi-3-world-model-probe",
       "held_run_file": "kernel/probe_held.py (push as probe.py with kernel/kernel-metadata.json, only after the GO)",
       "salt_design_note_commit": "989cb0ca9c21811144356d83955cae5ca76ec6c6",
       "protocol_sha256": sha("PROTOCOL.md"), "config_sha256": sha("config/STUDY_CONFIG.json"),
       "data_manifest_sha256": sha("DATA_MANIFEST.md"), "held_run_file_sha256": sha("kernel/probe_held.py"),
       "files_sha256": {p: sha(p) for p in FILES},
       "development_evidence": {"kernel_version": int(v), "analysis_json_sha256": sha(dev),
                                "note": "development games only; the file itself is git-ignored data"}}
json.dump(out, open(os.path.join(ST, "FREEZE.json"), "w"), indent=1)
print(json.dumps({k: out[k] for k in ("protocol_sha256", "held_run_file_sha256")}),
      "FREEZE.json sha256", sha("FREEZE.json"))
