"""Fixture test of the strict analysis verification (run after the freeze; not part of it).

    python checks/strict_fixture.py SCRATCH_DIR OUT.json

Everything runs in a scratch mirror of the repository (the kernel package's files at their repository paths, plus
this study's code, configuration, freeze and the plumbing check's world), with CAS_PACKAGE=1 and CAS_REPO and
CAS_STUDY pointing at the mirror, so that every import and every write stays in the mirror; nothing is written in
the real study. The mirror's configuration names one world, "s1_world", built from the plumbing check's outputs
(S1's own tasks; never a pilot or main task), with the kernel-side records the plumbing check does not make (stage
record, benchmarks, module pins written by the real pin writer from the mirror's frozen code, output manifest,
package manifest). The complete fixture must pass the strict verification; each single defect, applied to a fresh
copy of the mirror, must make the analysis return INCOMPLETE or INVALID before any statistic. No arm runs.

The defects: those of revisions 3 and 4 (pins, manifests, endpoints, rows, commitments, stages, directories) and of
the reviews of revision 3 (a duplicated row, a missing seed, transfer predictions removed, an extra malformed
per-structure key, three committed predictions, absent matched-search predictions, a fit with an explicit empty
prediction list, an invalid colour, a controller summary lacking a task, a flipped endpoint, an excluded task's
matched search without a failure flag, and a motivating source shared with another world).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # the real study (read only)
REPO = os.path.dirname(os.path.dirname(SRC))
STUDY_REL = os.path.relpath(SRC, REPO)
PY = "python3"
PIN_RECORDS = ("controller", "spec", "enum_0", "enum_1", "enum_2", "c7m_E", "c7m_M", "c7m_rerun", "commit", "evaluate")
STAGES = ("controller", "spec_and_c7m_E", "enum_and_c7m_M_first", "c7m_M_rest", "c7m_rerun", "commit", "evaluate")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def manifest(wd):
    out = {}
    for d, _, files in os.walk(os.path.join(wd, "runs")):
        for f in files:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, wd)
            if not rel.endswith(".tmp") and rel != "runs/OUTPUT_MANIFEST.json":
                out[rel] = sha(p)
    with open(os.path.join(wd, "runs", "OUTPUT_MANIFEST.json"), "w") as f:
        json.dump(dict(sorted(out.items())), f, indent=1)


def env_for(mirror):
    e = dict(os.environ, PYTHONHASHSEED="0", CAS_PACKAGE="1", CAS_REPO=mirror,
             CAS_STUDY=os.path.join(mirror, STUDY_REL))
    return e


def build_mirror(mirror):
    shutil.rmtree(mirror, ignore_errors=True)
    sys.path.insert(0, os.path.join(SRC, "cas"))
    import kaggle_build as KB                                                  # its FILES list only
    for rel in KB.FILES:
        src = os.path.join(REPO, rel)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(os.path.join(mirror, rel)), exist_ok=True)
            shutil.copy2(src, os.path.join(mirror, rel))
    study = os.path.join(mirror, STUDY_REL)
    shutil.copytree(os.path.join(SRC, "cas"), os.path.join(study, "cas"), dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(os.path.join(SRC, "config"), os.path.join(study, "config"), dirs_exist_ok=True)
    shutil.copy(os.path.join(SRC, "FREEZE.json"), study)
    cfg = json.load(open(os.path.join(study, "config", "STUDY_CONFIG.json")))
    rem = json.load(open(os.path.join(SRC, "checks", "s1_world", "evaluator_only", "REMOVED.json")))
    man = json.load(open(os.path.join(SRC, "checks", "s1_world", "partitions", "PARTITIONS_MANIFEST.json")))
    cfg["world_order"] = ["s1_world"]
    cfg["worlds"] = {"s1_world": {"removed": rem["removed"], "families": rem["families"], "salt": man.get("salt"),
                                  "params": {}}}
    json.dump(cfg, open(os.path.join(study, "config", "STUDY_CONFIG.json"), "w"), indent=1)
    wd = os.path.join(study, "runs", "generated", "s1_world")
    shutil.copytree(os.path.join(SRC, "checks", "s1_world"), wd)
    pins_dir = os.path.join(wd, "runs", "module_pins")
    os.makedirs(pins_dir, exist_ok=True)
    code = ("import os, sys\nfrom cas import env as E\nimport cas.run_world\nfrom cgrow import s1\n"
            "sys.modules['__main__'].__file__ = os.path.join(E.STUDY, 'cas', 'run_world.py')\n"
            "E.pin_record(sys.argv[1])\n")
    for r in PIN_RECORDS:
        subprocess.run([PY, "-c", code, os.path.join(pins_dir, r + ".json")], cwd=study, env=env_for(mirror), check=True)
    for b in ("BENCH_start.json", "BENCH_end.json"):
        json.dump({"concurrent": {"median_cpu_s": 1.5}, "lone": {"median_cpu_s": 1.3}}, open(os.path.join(wd, "runs", b), "w"))
    write_stages(wd, "s1_world")
    os.makedirs(os.path.join(study, "runs", "kaggle"), exist_ok=True)
    json.dump({"archive_sha256": "ab" * 32, "analysis_world_dirs": ["runs/generated/s1_world"]},
              open(os.path.join(study, "runs", "kaggle", "PACKAGE_MANIFEST.json"), "w"))
    manifest(wd)


def write_stages(wd, world):
    stages = {"world": world, "status": "complete", "cpu_scale": 1.17,
              "stages": {s: {"status": "done", "cpu_s": 1.0, "wall_s": 1.0} for s in STAGES},
              "task_manifest_sha256": sha(os.path.join(wd, "partitions", "PARTITIONS_MANIFEST.json")),
              "archive_sha256": "ab" * 32}
    json.dump(stages, open(os.path.join(wd, "runs", "STAGES.json"), "w"), indent=1)


def analyse(mirror, dirs):
    study = os.path.join(mirror, STUDY_REL)
    out = os.path.join(study, "runs", "analysis")
    os.makedirs(out, exist_ok=True)
    code = "import sys\nfrom cas import analysis as AN\nAN.main(sys.argv[1], sys.argv[2:], strict=True)\n"
    p = subprocess.run([PY, "-c", code, out] + dirs, cwd=study, env=env_for(mirror), capture_output=True, text=True)
    inc = os.path.join(out, "INCOMPLETE.json")
    doc = json.load(open(inc)) if os.path.exists(inc) else {}
    probs = doc.get("problems", [])
    return {"returncode": p.returncode, "incomplete": os.path.exists(inc), "status": doc.get("status"),
            "analysis_written": os.path.exists(os.path.join(out, "ANALYSIS.json")), "problems": probs[:4],
            "n_problems": len(probs), "stderr_tail": p.stderr[-300:] if p.returncode not in (0, 2) else ""}


def _rw(path, fn):
    d = json.load(open(path))
    fn(d)
    json.dump(d, open(path, "w"))


def _first_kept_unit(c):
    return next(k for k in sorted(c["units"]) if c["units"][k].get("kind") in ("promoted", "quarantined"))


def main(scratch, out_json):
    base = os.path.join(scratch, "base")
    build_mirror(base)
    W = os.path.join(STUDY_REL, "runs", "generated", "s1_world")

    def wr(w):
        return os.path.join(w, "runs", "cas_eval", "world_results.json")

    def cp(w):
        return os.path.join(w, "runs", "cas_commit", "COMMITTED_PREDICTIONS.json")

    def recommit(w):
        open(os.path.join(w, "runs", "cas_commit", "COMMITTED_SHA256"), "w").write(sha(cp(w)) + "\n")
        _rw(wr(w), lambda r: r.__setitem__("committed_sha256", sha(cp(w))))

    def three(c):
        v = c["units"][_first_kept_unit(c)]
        v["preds"] = [v["preds"][0]] * 3

    def fit_empty(c):
        k = next(k for k in sorted(c["grown"]) if c["grown"][k].get("fit"))
        c["grown"][k]["preds"] = []

    def bad_colour(c):
        c["units"][_first_kept_unit(c)]["preds"] = [[[[10]]]]

    def drop_from_summary(w):
        r = json.load(open(wr(w)))
        t = r["units"][-1]["task"]
        _rw(os.path.join(w, "runs", "prep_v4", "controller_summary.json"), lambda s_: s_.pop(t))
        _rw(wr(w), lambda r_: (r_.__setitem__("units", [u for u in r_["units"] if u["task"] != t]),
                               r_["controller"].pop(t)))
        _rw(cp(w), lambda c: (c.__setitem__("units", {k: v for k, v in c["units"].items() if k.split("|")[1] != t}),
                              c["c7m"].pop(f"M|{t}")))
        recommit(w)

    def flip(w):
        def f(r):
            u = r["units"][0]
            for s in ("0", "1", "2"):
                a = u["seeds"][s]["S-hole"]
                a["recovered"] = not a["recovered"]
        _rw(wr(w), f)

    cases = {
        "complete fixture": None,
        "pin digest changed": lambda w: _rw(os.path.join(w, "runs", "module_pins", "spec.json"),
                                            lambda r: r["modules"]["cgrow.s1"].__setitem__("sha256", "0" * 64)),
        "unpinned module in a record": lambda w: _rw(os.path.join(w, "runs", "module_pins", "spec.json"),
                                                     lambda r: r["modules"].__setitem__("x.y", {"path": "elsewhere/x.py", "sha256": "1" * 64})),
        "pin record missing": lambda w: os.remove(os.path.join(w, "runs", "module_pins", "commit.json")),
        "empty output manifest": "empty_manifest",
        "file not in the output manifest": "stray",
        "missing S-hole endpoint": lambda w: _rw(wr(w), lambda r: r["units"][0]["seeds"]["0"]["S-hole"].__setitem__("recovered", None)),
        "missing transfer result": lambda w: _rw(wr(w), lambda r: r["e_tasks"][sorted(r["e_tasks"])[0]].pop("transfer")),
        "dropped motivating task": lambda w: _rw(wr(w), lambda r: r["units"].pop()),
        "dropped committed grown key": lambda w: (_rw(cp(w), lambda c: c["grown"].pop(sorted(k for k in c["grown"] if k.startswith("transfer|"))[0])),
                                                  recommit(w)),
        "stage not done": lambda w: _rw(os.path.join(w, "runs", "STAGES.json"),
                                        lambda st: st["stages"]["commit"].__setitem__("status", "failed [1]")),
        "world given twice": "twice",
        "unpackaged directory": "other",
        "duplicate motivating row": lambda w: _rw(wr(w), lambda r: r["units"].append(dict(r["units"][0]))),
        "seed missing in a row": lambda w: _rw(wr(w), lambda r: r["units"][0]["seeds"].pop("2")),
        "transfer predictions removed": lambda w: (_rw(cp(w), lambda c: c["grown"][sorted(k for k in c["grown"] if k.startswith("transfer|"))[0]].pop("preds")),
                                                   recommit(w)),
        "extra malformed struct key": lambda w: (_rw(cp(w), lambda c: c["grown"].__setitem__("struct|unregistered|e", {"structures": ["x"]})),
                                                 recommit(w)),
        "unit commits three predictions": lambda w: (_rw(cp(w), three), recommit(w)),
        "matched-search predictions absent": lambda w: (_rw(cp(w), lambda c: c["c7m"][sorted(c["c7m"])[0]].pop("preds")),
                                                        recommit(w)),
        "fit with an explicit empty prediction list": lambda w: (_rw(cp(w), fit_empty), recommit(w)),
        "invalid colour in a committed grid": lambda w: (_rw(cp(w), bad_colour), recommit(w)),
        "controller summary lacks a task": drop_from_summary,
        "flipped endpoint": flip,
        "excluded matched search without failure flag": lambda w: _rw(wr(w), lambda r: r["e_tasks"][sorted(r["e_tasks"])[0]]["C7m"].pop("failed")),
        "motivating source shared with another world": "second_world",
    }
    res = {}
    for label, mut in cases.items():
        mirror = os.path.join(scratch, "case_" + "".join(ch if ch.isalnum() else "_" for ch in label))
        shutil.rmtree(mirror, ignore_errors=True)
        shutil.copytree(base, mirror)
        study = os.path.join(mirror, STUDY_REL)
        wd = os.path.join(mirror, W)
        dirs = [wd]
        if mut == "empty_manifest":
            json.dump({}, open(os.path.join(wd, "runs", "OUTPUT_MANIFEST.json"), "w"))
        elif mut == "stray":
            open(os.path.join(wd, "runs", "stray.txt"), "w").write("x")
        elif mut == "twice":
            dirs = [wd, wd]
        elif mut == "other":
            other = os.path.join(study, "runs", "elsewhere", "s1_world")
            shutil.copytree(wd, other)
            dirs = [other]
        elif mut == "second_world":
            wd2 = os.path.join(study, "runs", "generated", "s1_copy")
            shutil.copytree(wd, wd2)
            _rw(os.path.join(wd2, "partitions", "PARTITIONS_MANIFEST.json"), lambda m: m.__setitem__("world", "s1_copy"))
            _rw(os.path.join(wd2, "runs", "cas_eval", "world_results.json"), lambda r: r.__setitem__("world", "s1_copy"))
            write_stages(wd2, "s1_copy")
            manifest(wd2)
            _rw(os.path.join(study, "config", "STUDY_CONFIG.json"),
                lambda c: (c["world_order"].append("s1_copy"), c["worlds"].__setitem__("s1_copy", dict(c["worlds"]["s1_world"]))))
            _rw(os.path.join(study, "runs", "kaggle", "PACKAGE_MANIFEST.json"),
                lambda p: p["analysis_world_dirs"].append("runs/generated/s1_copy"))
            dirs = [wd, wd2]
        elif mut is not None:
            mut(wd)
            manifest(wd)
        res[label] = analyse(mirror, dirs)
        print(json.dumps({"case": label, "status": res[label]["status"], "analysis_written": res[label]["analysis_written"],
                          "first": res[label]["problems"][:1]}), flush=True)
    ok = (not res["complete fixture"]["incomplete"] and res["complete fixture"]["analysis_written"] and
          all(v["incomplete"] and v["status"] in ("INCOMPLETE", "INVALID") and not v["analysis_written"]
              for k, v in res.items() if k != "complete fixture"))
    doc = {"note": "strict verification fixture on S1's own world (revision 4, after the freeze), in a scratch "
                   "mirror with CAS_PACKAGE=1; no arm runs; nothing written in the real study",
           "freeze_sha256": sha(os.path.join(SRC, "FREEZE.json")), "analysis_sha256": sha(os.path.join(SRC, "cas", "analysis.py")),
           "all_cases_as_expected": ok, "cases": res}
    json.dump(doc, open(out_json, "w"), indent=1)
    print(json.dumps({"all_cases_as_expected": ok}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
