"""Build kaggle/cora_fhr_v1/notebook.py and notebook.ipynb from the sealed native_v1 notebook.

The native notebook is copied verbatim and changed only by the asserted exact-string patches below:
- P1 the docstring;
- P2 the label;
- P3, P4 the data and package resolution for two attached datasets;
- P5 the FHR helpers;
- P6 the phase itself, after the native submission is written.
The native harness keeps native_v1's 11.25 h budget.

The native reasoning (harness command, flags, assets and writer) is untouched.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
NATIVE = os.path.join(HERE, "..", "native_v1", "notebook.py")

DOC = '''#!/usr/bin/env python3
"""ARC Prize 2026 (ARC-AGI-2) submission notebook, CORA_FHR_V1 (single cell).

LABEL: CORA_FHR_V1. The unchanged native CORA v23 solver, followed by CORA-FHR: failure-driven construction
of a typed executable growth operator, verified before use. No neural model and no third-party predictions.

Datasets:
- arc_native_baseline_v1.tar.gz (chimdiwalter/arc-native-baseline-v1, unchanged): geocat_arc/ harness/
  src/ scripts/ library.json learned_verbs.json MANIFEST.json;
- arc_cora_fhr_v1.tar.gz (chimdiwalter/arc-cora-fhr-v1): cora_fhr/ cora_funnel/ cora_pilot/ cora_reach/
  fhr_phase.py MANIFEST.json (kaggle/cora_fhr_v1/build_dataset.sh).

Per task:
1. NATIVE: the sealed unified harness, exactly as in native_v1 (flags, assets, writer, 11.25 h budget);
   the native_v1 committed run needed 4.03 h of it.
2. FHR (fhr_phase.py), on growth-shaped tasks that native's object layer did not certify:
   - read native's own memorized-growth record (the failure evidence);
   - construct a G-grow operator;
   - install it reversibly into the same engine;
   - require native's gate, use of the operator, no tie and adaptive leave-one-out that rebuilds
     everything per fold.
   This is cora_fhr.measure.job with arm E, the code path of the development runs. It uses the remaining
   time: tasks start until 10.75 h, and the phase stops at 11.4 h.
3. ANSWERS:
   - where FHR certifies, attempt_1 is its prediction and attempt_2 is native's attempt_1;
   - everywhere else native's answers are kept unchanged (the fallback policy);
   - every output's origin is in provenance.json (native:<layer>, fhr:<operator>, or fallback);
   - the operator counts are in execution_manifest.json.

No internet, no GPU, no solutions file. Overrides for local emulation: K_INPUT, K_SRC, K_FHR, K_COMP,
K_WORK, K_WORKERS, K_BUDGET_S, K_FHR_START_H, K_FHR_HARD_H, K_GUARD_DIR.
"""
'''

FHR_FUNCS = '''
FHR_TAR, NATIVE_TAR = "arc_cora_fhr_v1.tar.gz", "arc_native_baseline_v1.tar.gz"
FHR_PKGS = ("cora_fhr", "cora_funnel", "cora_pilot", "cora_reach", "fhr_phase.py")


def resolve_fhr():
    k = os.environ.get("K_FHR")
    if k and os.path.isdir(os.path.join(k, "cora_fhr")):
        return k
    tar_path = None
    for dirname, dirs, files in os.walk(INPUT):
        if "cora_fhr" in dirs:
            return dirname
        if FHR_TAR in files:
            tar_path = os.path.join(dirname, FHR_TAR)
    if tar_path is None:
        raise RuntimeError("CORA-FHR package not found")
    import tarfile
    dest = os.path.join(WORK, "fhr_extracted")
    if not os.path.isdir(os.path.join(dest, "cora_fhr")):
        tarfile.open(tar_path).extractall(dest)
    return dest


def run_fhr(code, progress, workers, man):
    """Stage the FHR package beside the native solver (new directories only) and run the phase."""
    out = os.path.join(WORK, "fhr_rows.jsonl")
    try:
        src = resolve_fhr()
        for name in FHR_PKGS:
            if os.path.exists(os.path.join(code, name)):
                raise RuntimeError(f"{name} would overwrite a native file")
        man["fhr_package_sha256"] = tree_sha(src)
        for name in FHR_PKGS:
            p = os.path.join(src, name)
            (shutil.copytree if os.path.isdir(p) else shutil.copy)(p, os.path.join(code, name))
        start = T0 + 3600 * float(os.environ.get("K_FHR_START_H", "10.75"))
        hard = T0 + 3600 * float(os.environ.get("K_FHR_HARD_H", "11.4"))
        cmd = [sys.executable, "fhr_phase.py", "--challenges", "data/arc/arc-agi_evaluation_challenges.json",
               "--progress", progress, "--out", out, "--start-deadline", str(start), "--hard-deadline", str(hard),
               "--workers", str(workers)]
        man["fhr_cmd"], man["fhr_deadlines_h"] = cmd[1:], [round((start - T0) / 3600, 2), round((hard - T0) / 3600, 2)]
        t = time.time()
        proc = subprocess.Popen(cmd, env=native_env(code), start_new_session=True)
        try:
            man["fhr_returncode"] = proc.wait(timeout=max(60, hard - time.time() + 300))
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            man["fhr_returncode"] = "killed"
        man["fhr_s"] = round(time.time() - t, 1)
    except Exception as e:                                       # noqa: BLE001  the native answers stand
        man["fhr_error"] = repr(e)[:400]
    rows = {}
    if os.path.exists(out):
        for line in open(out):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            rows[r.get("key")] = r
    return rows


def merge_fhr(sub, challenges, fhr, rows, repairs):
    """FHR-certified predictions become attempt_1 and native's attempt_1 moves to attempt_2; all else is native."""
    src = {r.get("task_id"): (r.get("predictions") or {}) for r in rows}
    bad = {(t, i, k) for t, i, k in repairs}
    counts = {"tasks": len(challenges), "skipped": {}, "ran": 0, "not_reached": 0, "errors": 0, "outcomes": {},
              "proposed": 0, "installed": 0, "used": 0, "verified": 0, "committed_tasks": 0,
              "restore_failures": 0, "operators": []}
    prov = {}
    for tid, task in challenges.items():
        r = fhr.get(tid) or {"fhr": "not_reached", "reason": "no_row"}
        st = r.get("fhr")
        if st == "skipped":
            counts["skipped"][r["reason"]] = counts["skipped"].get(r["reason"], 0) + 1
        elif st == "not_reached":
            counts["not_reached"] += 1
        e = (r.get("arms") or {}).get("E") or {}
        if st == "ran":
            counts["ran"] += 1
            counts["errors"] += bool(r.get("error"))
            o = str(e.get("outcome"))
            counts["outcomes"][o] = counts["outcomes"].get(o, 0) + 1
            top = e.get("top") or {}
            counts["proposed"] += bool(e.get("proposals"))
            counts["installed"] += bool(top)
            counts["used"] += bool(top.get("accepted") and top.get("uses"))
            counts["verified"] += o == "CERTIFIED_WITH_EXTENSION"
            counts["restore_failures"] += (top.get("restored") is False) + sum(
                f.get("restored") is False for f in (e.get("folds") or []) if isinstance(f, dict))
        commit = str(e.get("certified_by") or "").endswith("+extension")
        preds = e.get("committed") if commit else None
        sel = e.get("selected") or {}
        p = src.get(tid, {})
        entries, origins = [], []
        for i, case in enumerate(task["test"]):
            nat = sub[tid][i]
            has1 = bool(p.get("attempt_1") and i < len(p["attempt_1"]) and p["attempt_1"][i])
            has2 = bool(p.get("attempt_2") and i < len(p["attempt_2"]) and p["attempt_2"][i])
            o1 = "fallback:repaired" if (tid, i, "attempt_1") in bad else (
                f"native:{p.get('attempt_1_source')}" if has1 else ("native:attempt_2" if has2 else "fallback:test_input"))
            o2 = "fallback:repaired" if (tid, i, "attempt_2") in bad else ("native:attempt_2" if has2 else o1 + ":copy")
            if preds is not None and i < len(preds) and _grid_ok(preds[i]):
                keep1 = nat["attempt_1"] != preds[i]
                entries.append({"attempt_1": preds[i], "attempt_2": nat["attempt_1"] if keep1 else nat["attempt_2"]})
                origins.append({"attempt_1": f"fhr:{sel.get('name')}:{sel.get('pretty')}", "attempt_2": o1 if keep1 else o2})
            else:
                entries.append(nat)
                origins.append({"attempt_1": o1, "attempt_2": o2})
        if preds is not None:
            counts["committed_tasks"] += 1
            counts["operators"].append({"task": tid, "operator": sel.get("pretty"), "name": sel.get("name"),
                                        "novelty": (sel.get("novelty") or {}).get("class")})
        sub[tid], prov[tid] = entries, origins
    return sub, prov, counts


'''

TAIL_OLD = '''    sub, repairs, extra = validate_and_repair(sub, challenges)
    json.dump(sub, open(out_path, "w"))
    rows = [json.loads(x) for x in open(progress)] if os.path.exists(progress) else []
    man.update(tasks_with_rows=len({r.get("task_id") for r in rows}),
               tasks_with_predictions=sum(1 for r in rows if r.get("predictions")),
               validation={"tasks": len(sub), "positions": sum(len(v) for v in sub.values()),
                           "repaired_entries": len(repairs), "extra_ids_dropped": extra},
               submission_sha256=_sha(out_path), elapsed_s=round(time.time() - T0, 1))
    json.dump(man, open(os.path.join(WORK, "execution_manifest.json"), "w"), indent=1)
    print("submission.json written:", json.dumps(man["validation"]), "| harness", man["harness_status"],
          "| elapsed", man["elapsed_s"], "s")
'''

TAIL_NEW = '''    sub, repairs, extra = validate_and_repair(sub, challenges)
    native_path = os.path.join(WORK, "submission_native.json")
    json.dump(sub, open(native_path, "w"))
    json.dump(sub, open(out_path, "w"))                  # a valid native submission exists before FHR starts
    rows = [json.loads(x) for x in open(progress)] if os.path.exists(progress) else []
    man.update(tasks_with_rows=len({r.get("task_id") for r in rows}),
               tasks_with_predictions=sum(1 for r in rows if r.get("predictions")),
               native_validation={"tasks": len(sub), "positions": sum(len(v) for v in sub.values()),
                                  "repaired_entries": len(repairs), "extra_ids_dropped": extra},
               native_submission_sha256=_sha(native_path))
    fhr = run_fhr(code, progress, workers, man)
    sub, prov, counts = merge_fhr(sub, challenges, fhr, rows, repairs)
    sub, repairs2, _extra2 = validate_and_repair(sub, challenges)
    json.dump(sub, open(out_path, "w"))
    json.dump(prov, open(os.path.join(WORK, "provenance.json"), "w"))
    man.update(fhr_counts=counts, final_repairs=len(repairs2),
               validation={"tasks": len(sub), "positions": sum(len(v) for v in sub.values()),
                           "repaired_entries": len(repairs) + len(repairs2), "extra_ids_dropped": extra},
               submission_sha256=_sha(out_path), elapsed_s=round(time.time() - T0, 1))
    json.dump(man, open(os.path.join(WORK, "execution_manifest.json"), "w"), indent=1)
    print("submission.json written:", json.dumps(man["validation"]), "| harness", man["harness_status"],
          "| FHR", json.dumps({k: counts[k] for k in ("ran", "not_reached", "verified", "committed_tasks")}),
          "| elapsed", man["elapsed_s"], "s")
'''

PATCHES = [
    ('LABEL, VERSION = "NATIVE_BASELINE", "native_v1"', 'LABEL, VERSION = "CORA_FHR_V1", "cora_fhr_v1"'),
    ('        if "geocat_arc" in dirname or any(f.endswith(".tar.gz") for f in files):',
     '        rel = os.path.relpath(dirname, INPUT)\n'
     '        if "geocat_arc" in rel or "cora_fhr" in rel or any(f.endswith(".tar.gz") for f in files):'),
    ('            if f.endswith(".tar.gz") and tar_path is None:', '            if f == NATIVE_TAR and tar_path is None:'),
    ('\n\ndef main():\n', '\n' + FHR_FUNCS + 'def main():\n'),
    (TAIL_OLD, TAIL_NEW),
]


def main():
    s = open(NATIVE).read()
    head, sep, rest = s.partition("\nimport hashlib\n")
    assert sep, "native notebook layout changed"
    s = DOC + sep.lstrip("\n") + rest
    for old, new in PATCHES:
        assert s.count(old) == 1, old[:60]
        s = s.replace(old, new)
    open(os.path.join(HERE, "notebook.py"), "w").write(s)
    nb = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                     "source": s.splitlines(keepends=True)}],
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    json.dump(nb, open(os.path.join(HERE, "notebook.ipynb"), "w"), indent=1)
    print("notebook.py and notebook.ipynb written;", len(PATCHES) + 1, "patches")


if __name__ == "__main__":
    main()
