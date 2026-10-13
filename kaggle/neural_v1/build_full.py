"""Build NEURAL_TTT_BASELINE neural_v1: the public NVARC Qwen3-4B
test-time-training pipeline, reproduced for ARC Prize 2026 with
compatibility changes only.

  python kaggle/neural_v1/build_full.py   -> kaggle/neural_v1/kernel/

Upstream: sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue, version 10, in
kaggle/neural_v1_smoke/upstream/ (sha256 recorded in the build output). The
smoke test (chimdiwalter/nvarc-qwen3-4b-smoke-v1, version 2) passed with the
same compatibility changes.

The label is NEURAL_TTT_BASELINE: not FULL_CORA and not capability invention.

Changes, each an asserted exact-string patch:
1. paths: the competition directory and the model directory are found
   under /kaggle/input (the 2026 mount layout);
2. committed run: all tasks of the visible stand-in file (ARC-AGI-2
   training tasks) instead of upstream's 4 self-test evaluation tasks. The
   hidden re-run processes every task, as upstream does. No evaluation file
   is opened;
3. committed-run check: against arc-agi_training_solutions.json, for all
   stand-in tasks. NVARC trained on these tasks, so this is a pipeline-health
   figure, never a score;
4. logging: peak GPU memory per worker;
5. a light identity cell: sha256 of the small model files and the task
   file, plus shard sizes. The full 44,151-file hash is recorded from smoke
   run 2; answer and evaluation files are never opened;
6. a final cell: schema validation and repair of submission.json (an
   invalid or missing entry becomes the test input), and
   execution_manifest.json.

The 12 h guard (12 x 3600 - 600 s), the 20-min per-task cap, the 540-s DFS
cap, LoRA TTT, augmentation, decoding and selection are untouched.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
UP = os.path.join(os.path.dirname(HERE), "neural_v1_smoke", "upstream", "arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb")
OUT = os.path.join(HERE, "kernel")
FIND = ("next(d for d, _, fs in __import__('os').walk('/kaggle/input') "
        "if 'arc-agi_test_challenges.json' in fs)")
MODEL = ('next(d for d, _, fs in os.walk("/kaggle/input") if "model.safetensors.index.json" in fs '
         'and "qwen3_4b_grids15_sft139" in d)')
IDENT = """# NEURAL_TTT_BASELINE neural_v1: environment and light asset identity (logging only)
import hashlib, json, os, subprocess, sys
print(subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout)
print("NEURAL_V1 python", sys.version.split()[0], "| cpus", os.cpu_count(), "| inputs", sorted(os.listdir("/kaggle/input")))
ident = {}
for d, _, fs in os.walk("/kaggle/input"):
    for f in sorted(fs):
        p = os.path.join(d, f)
        if "solution" in f.lower() or "evaluation" in f.lower():
            continue                                   # never opened
        size = os.path.getsize(p)
        if size <= 50_000_000:
            ident[os.path.relpath(p, "/kaggle/input")] = [size, hashlib.sha256(open(p, "rb").read()).hexdigest()]
        else:
            ident[os.path.relpath(p, "/kaggle/input")] = [size, None]   # shards: sha256 recorded by smoke run 2
json.dump(ident, open("/kaggle/working/asset_identity_light.json", "w"), indent=1)
print("NEURAL_V1 identity files", len(ident))
"""
FINAL = """# NEURAL_TTT_BASELINE neural_v1: schema validation, repair and execution manifest
import json, os, time
def _ok(g):
    return (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) for r in g) and 1 <= len(g[0]) <= 30
            and all(len(r) == len(g[0]) for r in g) and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))
_comp = """ + FIND + """
_ch = json.load(open(os.path.join(_comp, "arc-agi_test_challenges.json")))
try:
    _sub = json.load(open("submission.json"))
except Exception:
    _sub = {}
_fixed, _rep = {}, 0
for _k, _t in _ch.items():
    _e = _sub.get(_k) if isinstance(_sub.get(_k), list) else []
    _row = []
    for _i, _case in enumerate(_t["test"]):
        _x = _e[_i] if _i < len(_e) and isinstance(_e[_i], dict) else {}
        _a1, _a2 = _x.get("attempt_1"), _x.get("attempt_2")
        _o1, _o2 = _ok(_a1), _ok(_a2)
        _rep += (not _o1) + (not _o2)
        _a1 = _a1 if _o1 else (_a2 if _o2 else _case["input"])
        _row.append({"attempt_1": _a1, "attempt_2": _a2 if _o2 else _a1})
    _fixed[_k] = _row
json.dump(_fixed, open("submission.json", "w"))
_outs = os.listdir("/kaggle/inference_outputs") if os.path.isdir("/kaggle/inference_outputs") else []
_man = {"label": "NEURAL_TTT_BASELINE", "version": "neural_v1", "upstream": "sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue v10",
        "model": "sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1", "rerun_mode": bool(os.getenv("KAGGLE_IS_COMPETITION_RERUN")),
        "tasks": len(_fixed), "positions": sum(len(v) for v in _fixed.values()), "repaired_attempts": _rep,
        "decoded_output_files": len(_outs), "tasks_with_outputs": len({o.split("_")[0] for o in _outs}),
        "elapsed_s": round(time.time() - (global_end_time - 12 * 3600 + 600), 1)}
json.dump(_man, open("execution_manifest.json", "w"), indent=1)
print("NEURAL_V1 manifest:", json.dumps(_man))
"""


def patch(src, old, new, count=1):
    n = src.count(old)
    assert n == count, (old[:70], n)
    return src.replace(old, new)


def main(probe=None):
    """probe: a list of stand-in task ids. The committed run then processes only
    those tasks (a cheap pre-check of multi-output and 30x30 handling, as
    version 3 of the smoke kernel). Without it, the full package is built."""
    raw = open(UP, "rb").read()
    nb = json.loads(raw)
    code = [i for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code"]
    src = {i: ("".join(nb["cells"][i]["source"]) if isinstance(nb["cells"][i]["source"], list) else nb["cells"][i]["source"])
           for i in code}
    c4, c5, c7 = code[4], code[5], code[7]
    src[c4] = patch(src[c4], 'model_name="/kaggle/input/qwen3_4b_grids15_sft139/transformers/bfloat16/1",',
                    f'model_name={MODEL},  # NEURAL_V1: mount-layout independent')
    src[c4] = patch(src[c4], '''    if rerun_mode:
        test_path = "/kaggle/input/arc-prize-2025/arc-agi_test_challenges.json"
    else:
        test_path = "/kaggle/input/arc-prize-2025/arc-agi_evaluation_challenges.json"''',
                    f'''    test_path = os.path.join({FIND}, "arc-agi_test_challenges.json")  # NEURAL_V1: never an evaluation file''')
    src[c5] = patch(src[c5], '''    if rerun_mode:
        test_path = "/kaggle/input/arc-prize-2025/arc-agi_test_challenges.json"
    else:
        test_path = "/kaggle/input/arc-prize-2025/arc-agi_evaluation_challenges.json"''',
                    f'''    test_path = os.path.join({FIND}, "arc-agi_test_challenges.json")  # NEURAL_V1''')
    src[c5] = patch(src[c5], '''        if not rerun_mode:
            if key not in ["0934a4d8", "36a08778", "981571dc", "aa4ec2a5"]:
                continue
''', '''        # NEURAL_V1: every task in both modes (upstream self-tested 4 evaluation tasks when not re-running)
''' + (f'''        if not rerun_mode and key not in {sorted(probe)!r}:  # PROBE (smoke v3): committed-run pre-check only
            continue
''' if probe else ''))
    src[c5] = patch(src[c5], '''    worker(rank, queue, end_time)
    ''', '''    worker(rank, queue, end_time)
    print(f"[Rank {rank}] NEURAL_V1 max_memory_allocated_GB={torch.cuda.max_memory_allocated() / 1e9:.2f}")
    ''')
    src[c7] = patch(src[c7], '''if rerun_mode:
    data = ArcDataset.from_file("/kaggle/input/arc-prize-2025/arc-agi_test_challenges.json")
else:
    data = ArcDataset.from_file("/kaggle/input/arc-prize-2025/arc-agi_evaluation_challenges.json")
    data = data.load_replies("/kaggle/input/arc-prize-2025/arc-agi_evaluation_solutions.json")''',
                    f'''COMP = {FIND}
data = ArcDataset.from_file(os.path.join(COMP, "arc-agi_test_challenges.json"))
if not rerun_mode:  # NEURAL_V1: training solutions only (pipeline health on tasks the model was trained on; not a score)
    data = data.load_replies(os.path.join(COMP, "arc-agi_training_solutions.json"))''')
    src[c7] = patch(src[c7], '''    print("*** Reload score:", data.validate_submission(reload_submission))''',
                    '''    print("*** NEURAL_V1 pipeline-health check on the TRAINING stand-in tasks (contaminated; not a score):",
          data.validate_submission(reload_submission))''')
    for i in code:
        nb["cells"][i]["source"] = src[i]
    nb["cells"].insert(code[0] + 1, {"cell_type": "code", "metadata": {}, "outputs": [], "execution_count": None, "source": IDENT})
    nb["cells"].append({"cell_type": "code", "metadata": {}, "outputs": [], "execution_count": None, "source": FINAL})
    nb["metadata"].pop("kaggle", None)
    out = os.path.join(os.path.dirname(HERE), "neural_v1_smoke", "kernel_probe") if probe else OUT
    os.makedirs(out, exist_ok=True)
    json.dump(nb, open(os.path.join(out, "notebook.ipynb"), "w"), indent=1)
    up_meta = json.load(open(os.path.join(os.path.dirname(UP), "kernel-metadata.json")))
    meta = {"id": "chimdiwalter/nvarc-qwen3-4b-smoke-v1" if probe else "chimdiwalter/cora-neural-ttt-baseline-v1",
            "title": "NVARC Qwen3-4B smoke v1" if probe else "CORA Neural TTT Baseline v1", "code_file": "notebook.ipynb",
            "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_tpu": False,
            "enable_internet": False, "machine_shape": up_meta["machine_shape"], "dataset_sources": [],
            "competition_sources": ["arc-prize-2026-arc-agi-2"], "kernel_sources": up_meta["kernel_sources"],
            "model_sources": up_meta["model_sources"], "docker_image": up_meta["docker_image"], "keywords": []}
    json.dump(meta, open(os.path.join(out, "kernel-metadata.json"), "w"), indent=2)
    txt = "\n".join(nb["cells"][i]["source"] if isinstance(nb["cells"][i]["source"], str) else "".join(nb["cells"][i]["source"])
                    for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code")
    assert "arc-prize-2025" not in txt and "evaluation_challenges" not in txt and "evaluation_solutions" not in txt
    assert "12 * 3600 - 600" in txt and "1200" in txt and "540" in txt
    print(json.dumps({"upstream_sha256": hashlib.sha256(raw).hexdigest(),
                      "notebook_sha256": hashlib.sha256(open(os.path.join(out, "notebook.ipynb"), "rb").read()).hexdigest(),
                      "probe": probe,
                      "cells": len(nb["cells"])}))


if __name__ == "__main__":
    import sys
    main(json.load(open(os.path.join(HERE, "probe_ids.json"))) if sys.argv[1:2] == ["--probe"] else None)
