"""Coverage audit of a NEURAL_TTT_BASELINE committed run.

  python kaggle/neural_v1/audit_run.py RUN_DIR TEST_CHALLENGES_JSON
      RUN_DIR holds the downloaded kernel log, submission.json and
      execution_manifest.json.

A valid submission.json is not coverage: upstream's writer fills every
unprocessed position with the default [[0]]. So the audit reports neural
inference coverage directly, from the worker log and the submission itself.
For each task:
- started: a worker logged it as finished or as timed out;
- finished: "[Rank r] finished KEY in S s";
- timed out: "[Rank r] timeout after S s for puzzle KEY". Upstream can
  still emit outputs for subkeys decoded before the timeout.

Per position:
- genuine attempt_1: not the default [[0]];
- genuine attempt_2: not the default [[0]];
- default: both attempts [[0]], so nothing was decoded.

It also reports schema validity over all positions, the runtime against the
12 h limit, per-task time quantiles and per-rank peak memory.
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = [[0]]


def main(run_dir, test_path):
    log = next(os.path.join(run_dir, f) for f in os.listdir(run_dir) if f.endswith(".log"))
    ev = json.load(open(log))
    txt = "".join(e.get("data", "") for e in ev)
    span = round(ev[-1]["time"] - ev[0]["time"], 1)
    fin = {m.group(2): float(m.group(3)) for m in re.finditer(r"\[Rank (\d)\] finished (\S+) in ([\d.]+)s", txt)}
    tout = {m.group(3): float(m.group(2)) for m in re.finditer(r"\[Rank (\d)\] timeout after ([\d.]+)s for puzzle (\S+)", txt)}
    mem = {int(m.group(1)): float(m.group(2)) for m in re.finditer(r"\[Rank (\d)\] \S+ max_memory_allocated_GB=([\d.]+)", txt)}
    ch = json.load(open(test_path))
    sub = json.load(open(os.path.join(run_dir, "submission.json")))
    spec = importlib.util.spec_from_file_location("emu", os.path.join(os.path.dirname(HERE), "native_v1", "emulate.py"))
    emu = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(emu)
    pos = [(k, i) for k in ch for i in range(len(ch[k]["test"]))]
    g1 = sum(1 for k, i in pos if sub.get(k, [{}] * 9)[i].get("attempt_1") != DEFAULT)
    g2 = sum(1 for k, i in pos if sub.get(k, [{}] * 9)[i].get("attempt_2") != DEFAULT)
    dflt = sum(1 for k, i in pos if sub.get(k, [{}] * 9)[i].get("attempt_1") == DEFAULT and sub[k][i].get("attempt_2") == DEFAULT)
    dup = sum(1 for k, i in pos if sub[k][i].get("attempt_1") == sub[k][i].get("attempt_2") and sub[k][i].get("attempt_1") != DEFAULT)
    times = sorted(fin.values())
    q = lambda p: times[min(len(times) - 1, int(p * len(times)))] if times else None
    man = json.load(open(os.path.join(run_dir, "execution_manifest.json"))) if os.path.exists(os.path.join(run_dir, "execution_manifest.json")) else {}
    out = {"tasks": len(ch), "positions": len(pos), "tasks_started": len(set(fin) | set(tout)), "tasks_finished": len(fin),
           "tasks_timed_out": len(tout), "tasks_never_started": len(set(ch) - set(fin) - set(tout)),
           "positions_genuine_attempt_1": g1, "positions_genuine_attempt_2": g2, "positions_default_only": dflt,
           "positions_identical_attempts": dup, "schema_problems": len(emu.validate(sub, ch)),
           "log_span_s": span, "log_span_h": round(span / 3600, 2), "under_12h": span < 12 * 3600,
           "per_task_s": {"median": q(0.5), "p90": q(0.9), "max": times[-1] if times else None},
           "tasks_over_1000s": sum(t > 1000 for t in times), "peak_memory_gb_by_rank": mem, "manifest": man,
           "pipeline_health_line": next((l for l in txt.splitlines() if "pipeline-health" in l), None)}
    print(json.dumps(out, indent=1))
    json.dump(out, open(os.path.join(run_dir, "coverage_audit.json"), "w"), indent=1)
    return out


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
