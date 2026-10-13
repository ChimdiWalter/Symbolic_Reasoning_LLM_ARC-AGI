"""Build the NVARC compatibility smoke-test kernel from the public upstream
notebook (sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue, pulled
2026-10-13 into upstream/).

  python kaggle/neural_v1_smoke/build_smoke.py   -> kaggle/neural_v1_smoke/kernel/

A separate artifact from native_v1, under the leader-method audit (section
15). It is a compatibility smoke test, never submitted.

Patches are exact-string replacements, each asserted to match exactly once
where it is meant to apply:
1. paths: the competition directory is the one under /kaggle/input that
   holds arc-agi_test_challenges.json, instead of the hard-coded
   arc-prize-2025 path;
2. self-test: outside a competition re-run, the first 4 task ids (sorted) of
   the visible stand-in file. That file is ARC-AGI-2 training data. No
   evaluation file of any kind is opened;
3. functional check: compared only with arc-agi_training_solutions.json, for
   those 4 tasks. NVARC trained on these tasks, so this is a contaminated
   pipeline check, not a score;
4. time cap: 90 min overall instead of 12 h, to protect the GPU quota;
5. logging: peak GPU memory per worker;
6. a logging-only first cell: nvidia-smi, the Python version, and the size
   and sha256 of every attached input file (asset_identity.json).

Model, LoRA test-time training, decoding and selection code are untouched.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
UP = os.path.join(HERE, "upstream", "arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb")
OUT = os.path.join(HERE, "kernel")
IDENT = """# SMOKE: environment and asset identity (logging only; no algorithm change)
import hashlib, json, os, subprocess, sys
print(subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout)
print("SMOKE python", sys.version.split()[0], "| cpus", os.cpu_count(), "| inputs", sorted(os.listdir("/kaggle/input")))
ident = {}
for d, _, fs in os.walk("/kaggle/input"):
    for f in sorted(fs):
        p = os.path.join(d, f)
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 24), b""):
                h.update(chunk)
        ident[os.path.relpath(p, "/kaggle/input")] = [os.path.getsize(p), h.hexdigest()]
json.dump(ident, open("/kaggle/working/asset_identity.json", "w"), indent=1)
print("SMOKE asset files", len(ident), "bytes", sum(v[0] for v in ident.values()))
"""
FIND = ("next(d for d, _, fs in __import__('os').walk('/kaggle/input') "
        "if 'arc-agi_test_challenges.json' in fs)")


def patch(src, old, new, count=1):
    n = src.count(old)
    assert n == count, (old[:60], n)
    return src.replace(old, new)


def main():
    raw = open(UP, "rb").read()
    nb = json.loads(raw)
    code = [i for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code"]
    src = {i: ("".join(nb["cells"][i]["source"]) if isinstance(nb["cells"][i]["source"], list) else nb["cells"][i]["source"])
           for i in code}
    c0, c4, c5, c7 = code[0], code[4], code[5], code[7]
    # 4: time cap
    src[c0] = patch(src[c0], "global_end_time = time.time() + 12 * 3600 - 600",
                    "global_end_time = time.time() + 90 * 60  # SMOKE: 90-min cap (upstream: 12 * 3600 - 600)")
    # 1+2: worker test path
    src[c4] = patch(src[c4], '''    if rerun_mode:
        test_path = "/kaggle/input/arc-prize-2025/arc-agi_test_challenges.json"
    else:
        test_path = "/kaggle/input/arc-prize-2025/arc-agi_evaluation_challenges.json"''',
                    f'''    test_path = os.path.join({FIND}, "arc-agi_test_challenges.json")  # SMOKE: 2026 data; never an evaluation file''')
    # 1+2+5: starter
    src[c5] = patch(src[c5], '''    if rerun_mode:
        test_path = "/kaggle/input/arc-prize-2025/arc-agi_test_challenges.json"
    else:
        test_path = "/kaggle/input/arc-prize-2025/arc-agi_evaluation_challenges.json"''',
                    f'''    test_path = os.path.join({FIND}, "arc-agi_test_challenges.json")  # SMOKE: 2026 data''')
    src[c5] = patch(src[c5], '''        if not rerun_mode:
            if key not in ["0934a4d8", "36a08778", "981571dc", "aa4ec2a5"]:
                continue''', '''        if not rerun_mode:
            if key not in sorted(data.keys())[:4]:  # SMOKE: first 4 stand-in (training) tasks; upstream used 4 evaluation tasks
                continue''')
    src[c5] = patch(src[c5], '''    worker(rank, queue, end_time)
    ''', '''    worker(rank, queue, end_time)
    print(f"[Rank {rank}] SMOKE max_memory_allocated_GB={torch.cuda.max_memory_allocated() / 1e9:.2f}")
    ''')
    # 1+2+3: submission and check
    src[c7] = patch(src[c7], '''if rerun_mode:
    data = ArcDataset.from_file("/kaggle/input/arc-prize-2025/arc-agi_test_challenges.json")
else:
    data = ArcDataset.from_file("/kaggle/input/arc-prize-2025/arc-agi_evaluation_challenges.json")
    data = data.load_replies("/kaggle/input/arc-prize-2025/arc-agi_evaluation_solutions.json")''',
                    f'''COMP = {FIND}
data = ArcDataset.from_file(os.path.join(COMP, "arc-agi_test_challenges.json"))
if not rerun_mode:  # SMOKE: training solutions only (contaminated functional check); no evaluation file is opened
    data = data.change_keys(sorted(data.keys)[:4], keep_flags=True)
    data = data.load_replies(os.path.join(COMP, "arc-agi_training_solutions.json"))''')
    src[c7] = patch(src[c7], '''    print("*** Reload score:", data.validate_submission(reload_submission))''',
                    '''    print("*** SMOKE functional check on 4 TRAINING tasks the model was trained on (not a score):",
          data.validate_submission(reload_submission))
    print("SMOKE schema:", {k: [sorted(e) for e in v] for k, v in reload_submission.items()})''')
    for i in code:
        nb["cells"][i]["source"] = src[i]
    # 6: environment and asset identity, logging only, inserted after the first code cell
    ident_cell = {"cell_type": "code", "metadata": {}, "outputs": [], "execution_count": None, "source": IDENT}
    nb["cells"].insert(code[0] + 1, ident_cell)
    nb["metadata"].pop("kaggle", None)   # the upstream's embedded data-source ids; kernel-metadata.json defines the inputs
    os.makedirs(OUT, exist_ok=True)
    json.dump(nb, open(os.path.join(OUT, "notebook.ipynb"), "w"), indent=1)
    meta = {"id": "chimdiwalter/nvarc-qwen3-4b-smoke-v1", "title": "NVARC Qwen3-4B smoke v1", "code_file": "notebook.ipynb",
            "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_tpu": False,
            "enable_internet": False, "machine_shape": "NvidiaL4", "dataset_sources": [],
            "competition_sources": ["arc-prize-2026-arc-agi-2"],
            "kernel_sources": ["sorokin/pip-install-unsloth-flash-patch"],
            "model_sources": ["sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1"],
            "docker_image": json.load(open(os.path.join(HERE, "upstream", "kernel-metadata.json")))["docker_image"],
            "keywords": []}
    json.dump(meta, open(os.path.join(OUT, "kernel-metadata.json"), "w"), indent=2)
    print(json.dumps({"upstream_sha256": hashlib.sha256(raw).hexdigest(),
                      "notebook_sha256": hashlib.sha256(open(os.path.join(OUT, "notebook.ipynb"), "rb").read()).hexdigest(),
                      "patched_cells": [c0, c4, c5, c7]}))


if __name__ == "__main__":
    main()
