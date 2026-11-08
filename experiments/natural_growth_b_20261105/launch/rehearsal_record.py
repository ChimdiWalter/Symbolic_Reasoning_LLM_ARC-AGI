"""Record of the Kaggle rehearsal (amendment 3, section B): what each rehearsal kernel ran and how it ended.

    python3 -I launch/rehearsal_record.py N        (rehearsal N; from anywhere; paths are the study's)

Reads, under checks/kaggle_rehearsal/rehearsal_<N>/: REHEARSAL_GO and FREEZE_CANDIDATE.json (copies of that
rehearsal's GO and candidate freeze), pushed_*_utc.txt, poll.log, STATUS_<K>.txt, download/<K>/ (the files Kaggle
returned: the kernel log and <K>_outputs.tar.gz), extracted/<K>/ (that archive extracted), the package manifests
(PACKAGE_MANIFEST_*.json) and the Athe report's files in extracted/RC/ (RESULTS.json, REPORT.md), with the claim
markers in checks/kaggle_rehearsal/. Writes checks/kaggle_rehearsal/REHEARSAL_<N>_RECORD.json. Checks made here, in addition to the kernels' own gates and the build's
verification of RA and RB: every output manifest verifies under rehearsal/REHEARSAL_GO; every task id in every row
file is a source-half id of the real split (no held task ran); the kernel logs hold no traceback. It scores nothing.
"""
import collections
import hashlib
import json
import os
import re
import sys

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDY)
from ngb import kaggle_build as KB                                        # noqa: E402

N = int(sys.argv[1])
TOP = os.path.join(STUDY, "checks", "kaggle_rehearsal")
REC = os.path.join(TOP, f"rehearsal_{N}")
GO = os.path.join(REC, "REHEARSAL_GO")
SLUG = {"RA": "cora-library-transfer-rehearsal-a", "RB": "cora-library-transfer-rehearsal-b",
        "RC": "cora-library-transfer-rehearsal-c"}
PREFIX = {"co": "concept_arc", "mi": "mini_arc", "1d": "1d_arc"}


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def source_ids():
    sp = json.load(open(os.path.join(KB.REPO, KB.STUDY_A_REL, "split", "SPLIT.json"), encoding="utf-8"))
    return {b: {t for f in v["families"].values() for t in f["source"]} for b, v in sp["benchmarks"].items()}


def kernel_log(k):
    """The kernel's stdout/stderr as Kaggle returned it (a JSON list of stream records, or plain text)."""
    d = os.path.join(REC, "download", k)
    p = os.path.join(d, SLUG[k] + ".log")
    if not os.path.exists(p):
        return {"present": False}
    raw = open(p, encoding="utf-8", errors="replace").read()
    try:
        text = "".join(r.get("data", "") for r in json.loads(raw))
    except (ValueError, AttributeError):
        text = raw
    lines = text.splitlines()
    pick = [x for x in lines if x.startswith(("package ", "return code", "/kaggle/working/"))]
    return {"present": True, "sha256": sha(p), "lines": len(lines), "key_lines": pick,
            "traceback_lines": sum("Traceback" in x for x in lines),
            "final_status_line": next((x for x in reversed(lines) if x.startswith('{"status"')), None)}


def rows_summary(path, src):
    stops, fits, cpu, child, bad, n = collections.Counter(), 0, 0.0, 0.0, [], 0
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        n += 1
        stops[str(r.get("stop"))] += 1
        fits += bool(r.get("fit"))
        cpu += float(r.get("cpu_s") or 0)
        child += float(r.get("child_cpu_measured_s") or 0)
        b = r.get("bench") if r.get("bench") in src else PREFIX.get(str(r.get("task"))[:2])
        if b not in src or r.get("task") not in src[b]:
            bad.append(r.get("task"))
    return {"rows": n, "stops": dict(sorted(stops.items())), "fit_on_demonstrations": fits,
            "cpu_s": round(cpu, 1), "child_cpu_measured_s": round(child, 1), "ids_outside_source_half": bad}


def verify(d):
    """KB.verify_kernel_output, except that the Athe report's own two files (written into RC after its
    verification) are not counted as unlisted."""
    man_p = os.path.join(d, "OUTPUT_MANIFEST.json")
    man = json.load(open(man_p, encoding="utf-8"))
    have = {r: h for r, h in KB.run_manifest(d).items() if r not in ("RESULTS.json", "REPORT.md")}
    bad = sorted(r for r, h in man.items() if have.get(r) != h)
    extra = sorted(r for r in have if r not in man)
    st = json.load(open(os.path.join(d, "STAGES.json"), encoding="utf-8"))
    primary = open(GO, encoding="utf-8").read().splitlines()[2].split(" ", 1)[1]
    ok = not bad and not extra and st.get("go_sha256") == sha(GO) and st.get("primary") == primary \
        and st.get("status") == "complete"
    return {"ok": ok, "output_manifest_sha256": sha(man_p), "files_listed": len(man), "changed_or_missing": bad,
            "unlisted": extra}


def run_summary(k, src):
    d = os.path.join(REC, "extracted", k)
    if not os.path.exists(os.path.join(d, "STAGES.json")):
        return {"present": False}
    st = json.load(open(os.path.join(d, "STAGES.json"), encoding="utf-8"))
    verified = verify(d)
    stages = {n: {"status": v["status"], "attempts": len(v["attempts"]), "cpu_s": v["cpu_s"],
                  "wall_s": round(sum(a["wall_s"] for a in v["attempts"]), 1),
                  "started_utc": v["attempts"][0]["started_utc"] if v["attempts"] else None}
              for n, v in st["stages"].items()}
    files = {}
    for sub in ("held", "arc2"):
        for dd, _, fs in os.walk(os.path.join(d, sub)):
            for f in sorted(fs):
                p = os.path.join(dd, f)
                rel = os.path.relpath(p, d)
                if f.endswith(".jsonl"):
                    files[rel] = rows_summary(p, src)
                elif f.startswith("ALLOWANCE_"):
                    files[rel] = json.load(open(p, encoding="utf-8"))
    keep = ("status", "go_sha256", "primary", "workers", "cpu_count", "cpu_scale", "object_growth_available")
    return {"present": True, "stages_record": {x: st.get(x) for x in keep}, "verified_under_rehearsal_go": verified,
            "stages": stages, "stage_cpu_s_total": round(sum(v["cpu_s"] for v in st["stages"].values()), 1),
            "stage_wall_s_total": round(sum(v["wall_s"] for v in stages.values()), 1), "files": files,
            "ids_outside_source_half": sorted({t for v in files.values() if isinstance(v, dict)
                                               for t in v.get("ids_outside_source_half", [])})}


def poll_times(k):
    p = os.path.join(REC, "poll.log")
    seen = [x.split()[0] for x in open(p, encoding="utf-8") if f" {k} " in x] if os.path.exists(p) else []
    done = [x.split()[0] for x in open(p, encoding="utf-8") if f" {k} " in x and
            re.search(r"COMPLETE|ERROR|CANCEL", x)] if os.path.exists(p) else []
    return {"first_poll_utc": seen[0] if seen else None, "finished_seen_utc": done[0] if done else None}


def speed(out):
    """Per kernel: the benchmark copies, the measured ratio to Athe's reference, the applied (clipped) factor; and,
    per benchmark, the CPU ratio of Kaggle's G0 rows to Athe's G0 discovery rows of the same tasks (with how many of
    them agree on fit, stop, level and program)."""
    import ast
    cfg = json.load(open(os.path.join(STUDY, "config", "STUDY_CONFIG.json"), encoding="utf-8"))
    ref = cfg["cpu_speed"]["bench_reference_cpu_s"]
    disc = {}
    for i in (0, 1):
        for line in open(os.path.join(STUDY, "feasibility", f"discover_shard{i}.jsonl"), encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                disc[r["task"]] = r["base"] if isinstance(r["base"], dict) else ast.literal_eval(r["base"])
    res = {}
    for k in SLUG:
        d = os.path.join(REC, "extracted", k)
        if not os.path.exists(os.path.join(d, "STAGES.json")):
            continue
        st = json.load(open(os.path.join(d, "STAGES.json"), encoding="utf-8"))
        b0 = st.get("bench_start") or {}
        res[k] = {"workers": st.get("workers"), "bench_copies": b0.get("copies"),
                  "bench_median_cpu_s": b0.get("median_cpu_s"),
                  "measured_ratio": round(b0["median_cpu_s"] / ref, 3) if b0.get("median_cpu_s") else None,
                  "applied_factor": st.get("cpu_scale"), "g0_rows": {}}
        res[k]["clip_bound"] = res[k]["measured_ratio"] is not None and res[k]["measured_ratio"] != st.get("cpu_scale")
        for b in ("concept_arc", "mini_arc", "1d_arc"):
            p = os.path.join(d, "held", b, "G0.jsonl")
            if k == "RC" or not os.path.exists(p):
                continue
            rows = [json.loads(x) for x in open(p, encoding="utf-8") if x.strip()]
            same = sum(1 for r in rows if all(r[f] == disc[r["task"]][f] for f in ("fit", "stop", "level_complete",
                                                                                     "program")))
            res[k]["g0_rows"][b] = {"tasks": len(rows), "agree_with_athe": same,
                                    "cpu_ratio_to_athe": round(sum(r["cpu_s"] for r in rows) /
                                                               sum(disc[r["task"]]["cpu_s"] for r in rows), 3)}
    return res


def main():
    src = source_ids()
    out = {"go_file": os.path.relpath(GO, STUDY), "go_sha256": sha(GO),
           "go_lines": open(GO, encoding="utf-8").read().splitlines(), "kernels": {}}
    for k in SLUG:
        dl = os.path.join(REC, "download", k)
        tgz = os.path.join(dl, f"{k}_outputs.tar.gz")
        pushed = os.path.join(REC, f"pushed_{k}_utc.txt")
        status = os.path.join(REC, f"STATUS_{k}.txt")
        out["kernels"][k] = {
            "id": f"{KB.OWNER}/{SLUG[k]}", "benches": KB.KERNELS[k],
            "status": open(status, encoding="utf-8").read().strip() if os.path.exists(status) else None,
            **poll_times(k), "outputs_archive": {"sha256": sha(tgz), "bytes": os.path.getsize(tgz)}
            if os.path.exists(tgz) else None,
            "log": kernel_log(k), "run": run_summary(k, src)}
        if os.path.exists(pushed):
            out["kernels"][k]["pushed_utc"] = open(pushed, encoding="utf-8").read().strip()
    rc = os.path.join(REC, "extracted", "RC")
    if os.path.isdir(os.path.join(rc, "held")):              # RC's packaged copies of RA's and RB's held rows
        src_of = {"concept_arc": "RA", "mini_arc": "RA", "1d_arc": "RB"}
        same, differ, absent = 0, [], []
        for dd, _, fs in os.walk(os.path.join(rc, "held")):
            for f in fs:
                rel = os.path.relpath(os.path.join(dd, f), rc)
                orig = os.path.join(REC, "extracted", src_of[rel.split(os.sep)[1]], rel)
                if not os.path.exists(orig):
                    absent.append(rel)
                elif sha(orig) == sha(os.path.join(dd, f)):
                    same += 1
                else:
                    differ.append(rel)
        n_src = sum(1 for k in ("RA", "RB") for dd, _, fs in os.walk(os.path.join(REC, "extracted", k, "held"))
                    for f in fs if not f.endswith(".pkl"))
        out["rc_copies_of_held_rows"] = {"equal": same, "differ": differ, "absent_in_source": absent,
                                         "source_files_without_pkl": n_src}
    out["report"] = {f: sha(os.path.join(rc, f)) for f in ("RESULTS.json", "REPORT.md")
                     if os.path.exists(os.path.join(rc, f))}
    if os.path.exists(os.path.join(rc, "RESULTS.json")):
        res = json.load(open(os.path.join(rc, "RESULTS.json"), encoding="utf-8"))
        out["report"]["status"] = res.get("status")
        out["report"]["primary"] = res.get("primary")
    out["markers"] = sorted(f for f in os.listdir(TOP) if f.startswith(("SCORING_", "SCORED_")) and
                            f.endswith(out["go_sha256"]))
    for p in (os.path.join(REC, "PACKAGE_MANIFEST_rehearsal.json"),
              os.path.join(REC, "PACKAGE_MANIFEST_rehearsal_arc2.json")):
        if os.path.exists(p):
            m = json.load(open(p, encoding="utf-8"))
            out[os.path.basename(p)[:-5]] = {"sha256": sha(p), "archive_sha256": m["archive_sha256"],
                                            "archive_bytes": m["archive_bytes"],
                                            "verified_kernel_outputs": m.get("verified_kernel_outputs", {}),
                                            "kernels": m["kernels"]}
    out["candidate_freeze_sha256"] = sha(os.path.join(REC, "FREEZE_CANDIDATE.json"))
    out["speed"] = speed(out)
    with open(os.path.join(TOP, f"REHEARSAL_{N}_RECORD.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    brief = {k: (v["status"], v["run"].get("stages_record", {}).get("status"),
                 v["run"].get("verified_under_rehearsal_go", {}).get("ok"), v["run"].get("ids_outside_source_half"),
                 v["log"].get("traceback_lines")) for k, v in out["kernels"].items()}
    print(json.dumps({"kernels": brief, "report": out["report"], "markers": out["markers"]}))


if __name__ == "__main__":
    main()
