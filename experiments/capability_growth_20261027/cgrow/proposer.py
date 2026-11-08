"""The neural proposer: one local pretrained model (inference only), the same in every arm.

Model: Qwen3-4B-Instruct-2507 (local copy, fp16, GPU 0 only, under outputs/locks/gpu0.lock; never GPU 1).
Sampling goes through the hybrid's HFWriter (kaggle/hybrid_2026/llm_writer/writer.py, imported read-only): seeded
nucleus sampling, a reply stops at end of turn or once one fenced block is closed, and every reply records its
generated tokens, prompt tokens and GPU seconds.

    python -m cgrow.proposer bench                       # load + one timed batch (GPU lock held by the caller)
    python -m cgrow.proposer generate JOBS.jsonl OUT.jsonl   # resumable: jobs already in OUT are skipped

A job is {"job_id", "messages", "n", "max_new", "temperature", "top_p", "seed"}; each output row carries the
replies with their token counts and the sha256 of the exact prompt.
"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P          # noqa: E402

P.ensure_import_paths()


def _writer():
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    if os.environ["CUDA_VISIBLE_DEVICES"] != "0":
        raise RuntimeError("GPU 0 only")
    from llm_writer import writer as W
    return W.HFWriter(P.MODEL_DIR, label="qwen3_4b_instruct_2507", device=0, dtype="float16", max_context=16384)


def prompt_sha(messages):
    return hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()


def bench():
    w = _writer()
    msgs = [{"role": "user", "content": "Write a Python function new_op(grid) that removes every row whose cells "
             "all have the same value. Reply with a short description, then one ```python block."}]
    t0 = time.time()
    reps = w.sample(msgs, 6, max_new_tokens=500, temperature=0.8, top_p=0.95, seed=1)
    dt = time.time() - t0
    toks = sum(r.gen_tokens for r in reps)
    print(json.dumps({"load_s": w.load_s, "batch_s": round(dt, 1), "gen_tokens": toks,
                      "tok_per_s_summed": round(toks / dt, 1), "finished": sum(r.finished for r in reps),
                      "peak_mem_gb": w.stats["peak_mem_gb"], "sample0": reps[0].text[:600]}, indent=1))


def generate(jobs_path, out_path):
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            done = {json.loads(x)["job_id"] for x in f if x.strip()}
    with open(jobs_path, encoding="utf-8") as f:
        jobs = [json.loads(x) for x in f if x.strip()]
    todo = [j for j in jobs if j["job_id"] not in done]
    print(json.dumps({"jobs": len(jobs), "done": len(done), "todo": len(todo)}), flush=True)
    if not todo:
        return
    w = _writer()
    t_start = time.time()
    for j in todo:
        t0 = time.time()
        reps = w.sample(j["messages"], j["n"], max_new_tokens=j["max_new"], temperature=j["temperature"],
                        top_p=j["top_p"], seed=j["seed"])
        row = {"job_id": j["job_id"], "prompt_sha256": prompt_sha(j["messages"]), "wall_s": round(time.time() - t0, 2),
               "replies": [{"text": r.text, "gen_tokens": r.gen_tokens, "prompt_tokens": r.prompt_tokens,
                            "gpu_s": round(r.gpu_s, 3), "finished": r.finished, "seed": r.seed, "note": r.note}
                           for r in reps]}
        P.check_write(out_path)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        print(json.dumps({"job": j["job_id"], "wall_s": row["wall_s"],
                          "gen": sum(r.gen_tokens for r in reps)}), flush=True)
    print(json.dumps({"total_wall_s": round(time.time() - t_start, 1), "stats": w.stats}), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "bench":
        bench()
    elif sys.argv[1] == "generate":
        generate(sys.argv[2], sys.argv[3])
