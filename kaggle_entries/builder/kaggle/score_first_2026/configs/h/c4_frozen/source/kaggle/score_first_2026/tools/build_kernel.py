#!/usr/bin/env python3
"""Build a private, internet-off Kaggle notebook folder for the score-first pipeline. The `sf` package is embedded
in the first cell (its files are written to /kaggle/working/sf_code), so the notebook is self-contained; the
checkpoint is attached as a Kaggle Model source.

  python3 build_kernel.py OUT_DIR SLUG TITLE [--mode dev|submit] [--env K=V ...]

Modes: dev = solve the public evaluation challenges (or a subset) and keep every candidate pool;
submit = solve arc-agi_test_challenges.json; when that file is the public placeholder (all of its task ids are
training ids, i.e. a commit run, not the hidden rerun), only the first SF_COMMIT_TASKS tasks are solved and the rest
get fallbacks. Never used to submit.
"""
import argparse
import hashlib
import json
import os

OWNER = "chimdiwalter"
COMP = "arc-prize-2026-arc-agi-2"
MODEL = "sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1"
PEFT_DS = "chimdiwalter/sf-peft-wheel-0212"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["sf/__init__.py", "sf/grids.py", "sf/textfmt.py", "sf/lm.py", "sf/predict.py", "sf/select.py",
         "sf/runner.py", "sf/ttt.py", "sf/pilot.py"]
WHEEL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "outputs", "score_first", "wheels",
                     "peft-0.21.2-py3-none-any.whl")

DRIVER_PILOT = r'''
import glob, json, os, subprocess, sys, time
T0 = time.time()
MODE = os.environ["SF_MODE"]
whl = [p for p in glob.glob("/kaggle/input/**/peft-0.21.2-py3-none-any.whl", recursive=True) if os.path.isfile(p)]
if whl:                                     # the tested peft version, imported from the wheel (pure Python)
    sys.path.insert(0, whl[0])
    os.environ["PYTHONPATH"] = whl[0] + os.pathsep + os.environ.get("PYTHONPATH", "")
import peft, torch, transformers
def find_model():
    for cfg in sorted(glob.glob("/kaggle/input/**/config.json", recursive=True)):
        try:
            c = json.load(open(cfg))
        except Exception:
            continue
        if c.get("model_type") == "qwen3" and c.get("vocab_size") == 16:
            return os.path.dirname(cfg)
    raise SystemExit("checkpoint not found")
MODEL_DIR = find_model()
COMP = [d for d in ("/kaggle/input/competitions/arc-prize-2026-arc-agi-2", "/kaggle/input/arc-prize-2026-arc-agi-2") if os.path.isdir(d)][0]
CH = os.path.join(COMP, "arc-agi_evaluation_challenges.json")
OUT = "/kaggle/working/run"
os.makedirs(OUT, exist_ok=True)
info = {"mode": MODE, "model_dir": MODEL_DIR, "code_sha256": CODE_SHA, "peft": peft.__version__,
        "peft_file": peft.__file__,
        "torch": torch.__version__, "transformers": transformers.__version__, "python": sys.version.split()[0]}
json.dump(info, open("/kaggle/working/run_info.json", "w"), indent=1)
print(json.dumps(info), flush=True)
cfgs = json.loads(os.environ["SF_CFGS"])
tasks = json.loads(os.environ.get("SF_TASK_SPLIT", "[[], [], [], []]"))
procs = []
for r in range(4):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(r), PYTHONUNBUFFERED="1")
    cmd = [sys.executable, "-m", "sf.pilot", MODE, "--rank", str(r), "--challenges", CH, "--model", MODEL_DIR,
           "--out", OUT, "--tasks", ",".join(tasks[r]), "--cfg", json.dumps(cfgs[r])]
    f = open(os.path.join(OUT, f"worker_{r}.log"), "w")
    procs.append(subprocess.Popen(cmd, env=env, stdout=f, stderr=f, cwd=CODE_DIR))
limit = T0 + float(os.environ.get("SF_DEADLINE_S", "3600"))
while any(p.poll() is None for p in procs) and time.time() < limit:
    time.sleep(15)
for p in procs:
    if p.poll() is None:
        p.kill()
print("returncodes", [p.returncode for p in procs], "wall_s", round(time.time() - T0, 1), flush=True)
json.dump({"returncodes": [p.returncode for p in procs], "wall_s": round(time.time() - T0, 1)},
          open(os.path.join(OUT, "done.json"), "w"))
'''

DRIVER = '\nimport glob, json, os, subprocess, sys, time\nKROOT = os.environ.get("SF_KAGGLE_ROOT", "/kaggle")   # a local dress rehearsal sets another root\nT0 = time.time()\nMODE = os.environ.get("SF_MODE", "submit")\ndef find_model():\n    for cfg in sorted(glob.glob(KROOT + "/input/**/config.json", recursive=True)):\n        try:\n            c = json.load(open(cfg))\n        except Exception:\n            continue\n        if c.get("model_type") == "qwen3" and c.get("vocab_size") == 16:\n            return os.path.dirname(cfg)\n    raise SystemExit("checkpoint not found under /kaggle/input")\ndef find_comp():\n    for d in (KROOT + "/input/competitions/arc-prize-2026-arc-agi-2", KROOT + "/input/arc-prize-2026-arc-agi-2"):\n        if os.path.isdir(d):\n            return d\n    hits = glob.glob(KROOT + "/input/**/arc-agi_test_challenges.json", recursive=True)\n    return os.path.dirname(hits[0])\nMODEL_DIR, COMP_DIR = find_model(), find_comp()\nOUT = os.environ.get("SF_RUN_DIR", KROOT + "/working/run")\nos.makedirs(OUT, exist_ok=True)\nSUB = os.environ.get("SF_CHILD_SUBMISSION", KROOT + "/working/submission.json")\nargs = ["--model", MODEL_DIR, "--out", OUT, "--submission", SUB, "--gpus", os.environ.get("SF_GPUS", "4"),\n        "--deadline-s", os.environ.get("SF_DEADLINE_S", str(11.5 * 3600)),\n        "--n-gen", os.environ.get("SF_N_GEN", "8"), "--n-score", os.environ.get("SF_N_SCORE", "16"),\n        "--task-cap-s", os.environ.get("SF_TASK_CAP_S", "900"), "--code-dir", CODE_DIR,\n        "--ttt-steps", os.environ.get("SF_TTT_STEPS", "0"), "--ttt-rank", os.environ.get("SF_TTT_RANK", "64"),\n        "--ttt-alpha", os.environ.get("SF_TTT_ALPHA", "64"), "--ttt-lr", os.environ.get("SF_TTT_LR", "1e-4"),\n        "--ttt-max-tokens", os.environ.get("SF_TTT_MAX_TOKENS", "8192"),\n        "--ttt-frac", os.environ.get("SF_TTT_FRAC", "0.7"), "--method", os.environ.get("SF_METHOD", "vote_score")]\nif int(os.environ.get("SF_TTT_STEPS", "0")) > 0:\n    whl = [p for p in glob.glob(KROOT + "/input/**/peft-0.21.2-py3-none-any.whl", recursive=True) if os.path.isfile(p)]\n    if whl:\n        os.environ["PYTHONPATH"] = whl[0] + os.pathsep + os.environ.get("PYTHONPATH", "")\ninfo = {"mode": MODE, "model_dir": MODEL_DIR, "comp_dir": COMP_DIR, "code_sha256": CODE_SHA,\n        "rerun_env": os.environ.get("KAGGLE_IS_COMPETITION_RERUN"), "python": sys.version.split()[0]}\nfor mod in ("torch", "transformers", "accelerate", "peft", "numpy", "scipy"):\n    try:\n        info[mod] = __import__(mod).__version__\n    except Exception as e:\n        info[mod] = None\ninfo["model_files"] = {f: os.path.getsize(os.path.join(MODEL_DIR, f)) for f in sorted(os.listdir(MODEL_DIR))}\nif MODE == "dev":\n    ch_path = os.path.join(COMP_DIR, "arc-agi_evaluation_challenges.json")\n    if os.environ.get("SF_TASK_IDS"):\n        args += ["--task-ids", os.environ["SF_TASK_IDS"]]\n    elif os.environ.get("SF_LIMIT"):\n        args += ["--limit", os.environ["SF_LIMIT"]]\nelif os.environ.get("SF_REHEARSE_ON") == "evaluation":\n    # timed rehearsal: the submit path end to end, on the public evaluation challenges in place of the test file\n    ch_path = os.path.join(COMP_DIR, "arc-agi_evaluation_challenges.json")\n    info["placeholder_test_file"] = False\n    info["rehearsal"] = "public evaluation challenges (CONTAMINATED for this checkpoint)"\nelse:\n    ch_path = os.path.join(COMP_DIR, "arc-agi_test_challenges.json")\n    with open(ch_path) as f:\n        test_ids = set(json.load(f))\n    try:                                    # a missing or unreadable training file means "not the placeholder"\n        with open(os.path.join(COMP_DIR, "arc-agi_training_challenges.json")) as f:\n            train_ids = set(json.load(f))\n    except (OSError, ValueError):\n        train_ids = set()\n    placeholder = bool(test_ids) and test_ids <= train_ids\n    info["placeholder_test_file"] = placeholder\n    if placeholder:\n        n = os.environ.get("SF_COMMIT_TASKS", "8")\n        ch_full = json.load(open(ch_path))\n        keep = sorted(ch_full)[:int(n)]\n        args += ["--task-ids", ",".join(keep)]\ninfo["challenges"] = ch_path\nwith open(KROOT + "/working/run_info.json", "w") as f:\n    json.dump(info, f, indent=1)\nprint(json.dumps(info), flush=True)\ntry:\n    subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv"])\nexcept OSError:\n    pass\nr = subprocess.run([sys.executable, "-m", "sf.runner", "orchestrate", "--challenges", ch_path] + args, cwd=CODE_DIR)\nif MODE != "dev":\n    # the runner wrote a file for the tasks it ran; complete it for every task of the official file\n    sys.path.insert(0, CODE_DIR)\n    from sf import select as S\n    ch_all = json.load(open(ch_path))\n    try:\n        sub = json.load(open(SUB))\n    except Exception:\n        sub = {}\n    for tid, t in ch_all.items():\n        if tid not in sub or len(sub[tid]) != len(t["test"]):\n            sub[tid] = [S.two_attempts([], x["input"], []) for x in t["test"]]\n    tmp = SUB + ".tmp"\n    with open(tmp, "w") as f:\n        json.dump(sub, f)\n        f.flush()\n        os.fsync(f.fileno())\n    os.replace(tmp, SUB)\n    problems = S.check_submission(sub, ch_all)\n    print("schema problems:", len(problems), problems[:5])\nprint("returncode", r.returncode, "wall_s", round(time.time() - T0, 1))\n'


def cell(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("slug")
    ap.add_argument("title")
    ap.add_argument("--mode", default="dev", choices=["dev", "submit", "smoke", "pilot"])
    ap.add_argument("--env", action="append", default=[])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    files = {f: open(os.path.join(HERE, f), encoding="utf-8").read() for f in FILES}
    blob = json.dumps(files, sort_keys=True)
    sha = hashlib.sha256(blob.encode()).hexdigest()
    env = dict(x.split("=", 1) for x in a.env)
    env["SF_MODE"] = a.mode
    c0 = ("import json, os\n" + "".join(f"os.environ[{k!r}] = {v!r}\n" for k, v in sorted(env.items())) +
          "CODE_DIR = os.environ.get('SF_KAGGLE_ROOT', '/kaggle') + '/working/sf_code'\n"
          f"CODE_SHA = {sha!r}\n"
          f"FILES = json.loads({blob!r})\n"
          "for name, text in FILES.items():\n"
          "    p = os.path.join(CODE_DIR, name)\n"
          "    os.makedirs(os.path.dirname(p), exist_ok=True)\n"
          "    open(p, 'w', encoding='utf-8').write(text)\n"
          "print('code written', CODE_SHA, len(FILES))\n")
    nb = {"cells": [cell(c0), cell(DRIVER_PILOT if a.mode in ("smoke", "pilot") else DRIVER)],
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    json.dump(nb, open(os.path.join(a.out, "notebook.ipynb"), "w"), indent=1)
    meta = {"id": f"{OWNER}/{a.slug}", "title": a.title, "code_file": "notebook.ipynb", "language": "python",
            "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_tpu": False,
            "enable_internet": False,
            "dataset_sources": [PEFT_DS] if a.mode in ("smoke", "pilot") or int(env.get("SF_TTT_STEPS", "0")) else [],
            "competition_sources": [COMP],
            "kernel_sources": [], "model_sources": [MODEL], "machine_shape": "NvidiaL4"}
    json.dump(meta, open(os.path.join(a.out, "kernel-metadata.json"), "w"), indent=1)
    manifest = {"code_sha256": sha, "files": {f: hashlib.sha256(t.encode()).hexdigest() for f, t in files.items()},
                "env": env, "model": MODEL, "mode": a.mode}
    json.dump(manifest, open(os.path.join(a.out, "build_manifest.json"), "w"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
