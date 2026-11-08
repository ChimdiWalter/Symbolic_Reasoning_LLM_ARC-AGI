"""Pre-registered analysis (PROTOCOL.md sections 6 and 7), from the worlds' evaluator records only.

    python -m cas.analysis OUT_DIR WORLD_DIR [WORLD_DIR ...]          (phase 2: after the GO gate's analyse stage)

Completeness first (verify_complete, strict in phase 2). The expected sets are reconciled, not read from the
results: the world directories must be exactly the ones packaging recorded for the analysis (runs/kaggle/
PACKAGE_MANIFEST.json "analysis_world_dirs": one per configured world, no other, no duplicate), and each world's
own name, removed set and families must equal the configuration; the expected motivating tasks (partition M with
the controller's construction decision) and excluded tasks (partition E) come from the world's hashed task files and
its controller summary; the committed-predictions file must hold exactly the expected unit keys (every growth arm
x every motivating task x every seed), matched-search keys (every motivating and excluded task) and grown-grammar
keys (reuse and transfer for every excluded task), and its sha256 must equal the recorded one and the one in the
world results; the world results must hold exactly the expected tasks with a typed (true or false) "recovered"
endpoint for every arm, seed and contrast, None being permitted only for an S-shuffled unit that records why it has
no donor; the kernel record must be complete, name the committed task manifest's digest and the package digest;
the output manifest must cover every file under runs/, hold every required entry, and every digest must equal the
file; every required module-pin record must exist and is validated here against the bound FREEZE.json (recorded
paths and digests, permitted stubs only), not trusted on its own ok flag; no source may serve motivating tasks of
two worlds (section 6). The rows must be unique and exactly as many as expected, with exactly the expected seeds and
arms; every committed record (unit, matched search, grown grammar) must be complete, typed and bounded (at most two
predictions, an explicit empty list distinguished from an absent one), and the grown keys must be exactly the
expected set, including one per promoted structure per excluded task. Anything missing makes the study INCOMPLETE,
anything malformed INVALID, before any analysis: the analysis writes INCOMPLETE.json (with that status) and stops. Absent work is never substituted. A recorded method failure (a matched search
that timed out or ran out of memory; a growth unit that commits nothing) counts as not recovered.

Unit of inference: the motivating task (seeds are within-task replicates, as in S1's task-level correction). A
method recovers a task under the majority criterion when its committed outputs are right in at least 2 of its 3
seeds, under the all-3 criterion when in all 3. Matched static search is deterministic and runs once per task.

Primary: S-hole against C7m, majority criterion, all motivating tasks of all worlds. Statistics (S1's code,
testib_rest._compare): the exact two-sided McNemar test on the discordant tasks, the mean paired difference, and
percentile bootstrap 95% intervals (10,000 draws) over units (seed 1) and over clusters (seed 7). Decision, with the
dependence-aware clusters (families, with W2's four linked families as ONE cluster: 8 clusters); no source serves
motivating tasks of two worlds, by construction and verified here, so the primary has no cross-world link:
  "S-hole beats matched search"        McNemar p < 0.05 and the dependence-aware interval lies above 0;
  "matched search beats S-hole"        McNemar p < 0.05 and that interval lies below 0;
  "S1-sized advantage refuted"         neither, and that interval's upper end is below 3/11 (S1's difference);
  "inconclusive"                       otherwise.
The McNemar p-value assumes exchangeable tasks and is reported as conditional on that; the 11-family interval and a
source-input-clustered interval are reported beside the decision interval.
Secondaries (exact McNemar, Holm over the four; the dependence-aware interval must exclude 0):
  1 S-hole against S-shuffled, majority criterion (tasks with no donor are not applicable and are excluded, counted);
  2 S-hole against S-enum, all-3 criterion for both;
  3 reuse: the committed two predictions of one base search per excluded task with the family's grown grammar,
    against C7m;
  4 transfer: as 3, with the grown grammar of the other families of the same world.
Excluded tasks may share a source input across worlds, so the categorical conclusions of 3 and 4 are conditional on
no cross-world link; beside them a joint source-and-family clustered interval (connected components of the
cluster and source links) is reported, descriptive, when it has at least 4 components.
Descriptive only: oracle reach (S1's revision-1 endpoint: any retried candidate's prediction right) per method,
and reach on excluded tasks (the union over the family's structures tried alone); per-world and per-family tables;
S-hole against S-demo; S-enum against C7m; CPU accounting; S-enum's overshoot of its cap; executions per CPU-second
of every matched search.
"""
import json
import os
import sys

from cas import env as E
from cgrow import evaluate as EV, testib_rest as TR                             # noqa: E402

SEEDS = ("0", "1", "2")
S1_DIFF = 3 / 11
ARMS = ("S-hole", "S-demo", "S-shuffled", "S-enum")
STAGES = ("controller", "spec_and_c7m_E", "enum_and_c7m_M_first", "c7m_M_rest", "c7m_rerun", "commit", "evaluate")
PIN_RECORDS = ("controller", "spec", "enum_0", "enum_1", "enum_2", "c7m_E", "c7m_M", "c7m_rerun", "commit", "evaluate")
DECISIONS = ("INVENT_NEW_OPERATION", "CONTINUE_PROGRAM_SEARCH", "REQUEST_ADDITIONAL_ADMISSIBLE_EVIDENCE",
             "PRESERVE_COMPETING_HYPOTHESES", "NONE")                      # cgrow/controller.py analyze
REQUIRED_MODULES = ("cas.env", "cgrow.s1", "cgrow.search", "cgrow.schema", "cgrow.lang0", "a2.bus", "a2.arcdsl",
                    "a2.grammars")
PERMITTED_STUBS = ("llm_writer", "llm_writer.gridfn", "llm_writer.gridfn.lang", "llm_writer.gridfn.sandbox")
REQUIRED_OUTPUTS = ("runs/STAGES.json", "runs/BENCH_start.json", "runs/BENCH_end.json",
                    "runs/prep_v4/records.pkl", "runs/prep_v4/controller_summary.json",
                    "runs/cas_arms/units_spec.json", "runs/cas_arms/units_enum_s0.json",
                    "runs/cas_arms/units_enum_s1.json", "runs/cas_arms/units_enum_s2.json",
                    "runs/cas_c7m/c7m_M.json", "runs/cas_c7m/c7m_E.json",
                    "runs/cas_commit/COMMITTED_PREDICTIONS.json", "runs/cas_commit/COMMITTED_SHA256",
                    "runs/cas_eval/world_results.json", "runs/cas_eval/struct_scores.json") + \
    tuple(f"runs/module_pins/{r}.json" for r in PIN_RECORDS)
STUDY_REL = "experiments/construction_at_scale_20261105"


# ------------------------------------------------------------------ completeness and custody
def _expected(wd):
    """Expected motivating and excluded tasks from the world's hashed task metadata and its controller summary
    (partition, family, source and the decision only; no query output is read here)."""
    ev = E.load(os.path.join(wd, "evaluator_only", "TASKS_EVAL.json"))
    summ = E.load(os.path.join(wd, "runs", "prep_v4", "controller_summary.json"))
    tids = sorted(t for t, v in ev.items() if v["partition"] == "M"
                  and summ.get(t, {}).get("decision") == "INVENT_NEW_OPERATION")
    e_ids = sorted(t for t, v in ev.items() if v["partition"] == "E")
    meta = {t: {"family": v.get("family"), "source": v["source"], "template": v.get("template"),
                "n_queries": len(v.get("test_inputs") or [])}
            for t, v in ev.items()}                      # U and D tasks have no family or template
    return tids, e_ids, meta


def _typed(d, key="recovered"):
    return isinstance(d, dict) and isinstance(d.get(key), bool)


def _grid(g):
    """A grid: a non-empty rectangular list of non-empty lists of integers 0 to 9."""
    return (isinstance(g, list) and g and all(isinstance(r, list) and r and len(r) == len(g[0]) for r in g) and
            all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


def _attempts(p, n_queries, lo=0, hi=2):
    """Saved predictions: a list (an explicit empty list is allowed when lo == 0; absent is not) of lo to hi
    attempts, each a list of one grid per query input."""
    return (isinstance(p, list) and lo <= len(p) <= hi and
            all(isinstance(a, list) and len(a) == n_queries and all(_grid(g) for g in a) for a in p))


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _check_commitments(name, com, tids, e_ids, meta, problems):
    """Exact key sets and complete, typed, bounded records for every unit, matched-search and grown-grammar
    commitment. A malformed record is INVALID; a missing one INCOMPLETE."""
    units, c7m, grown = com.get("units"), com.get("c7m"), com.get("grown")
    if not (isinstance(units, dict) and isinstance(c7m, dict) and isinstance(grown, dict)):
        problems.append(f"INVALID {name}: committed predictions lack the units, c7m or grown sections")
        return
    exp_units = {f"{arm}|{t}|{s}" for arm in ARMS for t in tids for s in SEEDS}
    exp_c7m = {f"M|{t}" for t in tids} | {f"E|{t}" for t in e_ids}
    if set(units) != exp_units:
        problems.append(f"{name}: committed unit keys differ from the expected set "
                        f"(missing {sorted(exp_units - set(units))[:3]}, extra {sorted(set(units) - exp_units)[:3]})")
    if set(c7m) != exp_c7m:
        problems.append(f"{name}: committed matched-search keys differ from the expected set "
                        f"(missing {sorted(exp_c7m - set(c7m))[:3]}, extra {sorted(set(c7m) - exp_c7m)[:3]})")
    # units: not applicable (S-shuffled only), or a typed commit of 1 or 2 attempts, or an explicit nothing
    promoted = set()
    for k, v in units.items():
        t = k.split("|")[1] if k.count("|") == 2 else None
        nq = meta.get(t, {}).get("n_queries", 1)
        if not isinstance(v, dict):
            problems.append(f"INVALID {name}: committed unit {k} is not a record")
            continue
        if v.get("not_applicable"):
            if not k.startswith("S-shuffled|") or set(v) != {"not_applicable"}:
                problems.append(f"INVALID {name}: committed unit {k} marked not applicable")
            continue
        if set(v) != {"preds", "kind", "structure"}:
            problems.append(f"INVALID {name}: committed unit {k} fields {sorted(v)} are not preds, kind, structure")
            continue
        if v["kind"] is None:
            if v["preds"] is not None or v["structure"] is not None:
                problems.append(f"INVALID {name}: committed unit {k} commits nothing but carries predictions")
        elif v["kind"] in ("promoted", "quarantined"):
            if not (isinstance(v["structure"], str) and _attempts(v["preds"], nq, lo=1)):
                problems.append(f"INVALID {name}: committed unit {k} has no structure or not 1 to 2 typed predictions")
            elif v["kind"] == "promoted":
                promoted.add(v["structure"])
        else:
            problems.append(f"INVALID {name}: committed unit {k} kind {v['kind']!r}")
    # matched searches: typed, fit consistent with the predictions (explicit empty when no fit)
    for k, v in c7m.items():
        t = k.split("|", 1)[1] if "|" in k else None
        nq = meta.get(t, {}).get("n_queries", 1)
        need = {"preds", "fit", "stop", "failed", "budget_cpu_s", "cpu_s"}
        if not isinstance(v, dict) or set(v) != need:
            problems.append(f"INVALID {name}: committed matched search {k} fields are not {sorted(need)}")
            continue
        ok = isinstance(v["fit"], bool) and isinstance(v["failed"], bool) and _num(v["budget_cpu_s"]) and \
            v["budget_cpu_s"] > 0 and (v["cpu_s"] is None or _num(v["cpu_s"]))
        ok = ok and (_attempts(v["preds"], nq, lo=1) if (v["fit"] and not v["failed"]) else v["preds"] == [])
        if not ok:
            problems.append(f"INVALID {name}: committed matched search {k} malformed")
    # grown grammars: recomputed from the committed S-hole promotions (majority of seeds per task), then the exact
    # key set (reuse and transfer per excluded task, one per promoted structure per excluded task) and typed records
    gbf = {}
    for t in tids:
        cnt = {}
        for s in SEEDS:
            v = units.get(f"S-hole|{t}|{s}") or {}
            if v.get("kind") == "promoted":
                cnt[v["structure"]] = cnt.get(v["structure"], 0) + 1
        for sid, n in cnt.items():
            if n >= 2:
                gbf.setdefault(meta[t]["family"], set()).add(sid)
    gbf = {f: sorted(v) for f, v in gbf.items()}
    if com.get("grown_by_family") != gbf:
        problems.append(f"INVALID {name}: grown grammars in the commit differ from the committed S-hole promotions")
    exp_grown = {f"reuse|{t}" for t in e_ids} | {f"transfer|{t}" for t in e_ids} | \
        {f"struct|{sid}|{t}" for sid in promoted for t in e_ids}
    if set(grown) != exp_grown:
        problems.append(f"INVALID {name}: committed grown keys differ from the expected set "
                        f"(missing {sorted(exp_grown - set(grown))[:3]}, extra {sorted(set(grown) - exp_grown)[:3]})")
    for k, v in grown.items():
        parts = k.split("|")
        t = parts[-1]
        if t not in meta:
            continue                                         # an unknown task: reported by the key-set check
        nq = meta[t]["n_queries"]
        f = meta[t]["family"]
        if parts[0] == "reuse" and len(parts) == 2:
            want = gbf.get(f, [])
        elif parts[0] == "transfer" and len(parts) == 2:
            want = sorted({sid for g, ss in gbf.items() if g != f for sid in ss})
        elif parts[0] == "struct" and len(parts) == 3:
            want = [parts[1]]
        else:
            continue
        need = {"structures", "fit", "preds", "program", "cpu_s"}
        if not isinstance(v, dict) or set(v) != need:
            problems.append(f"INVALID {name}: committed grown record {k} fields are not {sorted(need)}")
            continue
        ok = v["structures"] == want and isinstance(v["fit"], bool) and _num(v["cpu_s"]) and \
            (v["program"] is None or isinstance(v["program"], str))
        ok = ok and (_attempts(v["preds"], nq, lo=1) if v["fit"] else v["preds"] == [])
        if not ok:
            problems.append(f"INVALID {name}: committed grown record {k} malformed")


def _rescore(name, wd, w, com, tids, e_ids, problems):
    """Every recorded endpoint re-derived from the committed predictions and the hashed labels (at most two
    predictions each); a disagreement is INVALID."""
    try:
        ev = E.load(os.path.join(wd, "evaluator_only", "TASKS_EVAL.json"))
    except (OSError, ValueError):
        problems.append(f"INVALID {name}: TASKS_EVAL.json unreadable for re-scoring")
        return

    def right(preds, t):
        return bool(preds) and isinstance(preds, list) and len(preds) <= 2 and EV.correct(preds, ev[t]["test_outputs"])

    units = {u.get("task"): u for u in w.get("units", []) if isinstance(u, dict)}
    cu, cc, cg = com.get("units") or {}, com.get("c7m") or {}, com.get("grown") or {}
    bad = []
    for t in tids:
        u = units.get(t) or {}
        for s in SEEDS:
            for arm in ARMS:
                rec = ((u.get("seeds") or {}).get(s) or {}).get(arm) or {}
                c = cu.get(f"{arm}|{t}|{s}") or {}
                want = None if c.get("not_applicable") else right(c.get("preds"), t)
                if rec.get("recovered") != want:
                    bad.append(f"{arm}|{t}|{s}")
        c = cc.get(f"M|{t}") or {}
        if (u.get("C7m") or {}).get("recovered") != (right(c.get("preds"), t) and not c.get("failed")):
            bad.append(f"C7m|M|{t}")
    e_tasks = w.get("e_tasks") or {}
    for t in e_ids:
        e = e_tasks.get(t) or {}
        c = cc.get(f"E|{t}") or {}
        if (e.get("C7m") or {}).get("recovered") != (right(c.get("preds"), t) and not c.get("failed")):
            bad.append(f"C7m|E|{t}")
        for k in ("reuse", "transfer"):
            g = cg.get(f"{k}|{t}") or {}
            if (e.get(k) or {}).get("recovered") != (bool(g.get("fit")) and right(g.get("preds"), t)):
                bad.append(f"{k}|{t}")
    for sid, v in (w.get("structures") or {}).items():
        for t, ok in ((v or {}).get("e_results") or {}).items():
            g = cg.get(f"struct|{sid}|{t}") or {}
            if t in ev and ok != (bool(g.get("fit")) and right(g.get("preds"), t)):
                bad.append(f"struct|{sid}|{t}")
    if bad:
        problems.append(f"INVALID {name}: {len(bad)} recorded endpoints differ from the re-scored committed "
                        f"predictions ({bad[:4]})")


def _check_pins(wd, name, freeze, problems):
    pins = {os.path.join(STUDY_REL, k): v for k, v in freeze.get("files_sha256", {}).items()}
    pins.update(freeze.get("dependencies_sha256", {}))
    entry = os.path.join(STUDY_REL, "cas", "run_world.py")
    for r in PIN_RECORDS:
        p = os.path.join(wd, "runs", "module_pins", r + ".json")
        if not os.path.exists(p):
            problems.append(f"{name}: module-pin record missing: {r}")
            continue
        rec = E.load(p)
        mods = rec.get("modules") or {}
        if not isinstance(mods, dict) or not mods or rec.get("mismatches") or rec.get("ok") is not True:
            problems.append(f"{name}: module-pin record {r} empty, not ok, or with mismatches")
        names = set(mods)
        if f"__main__ ({entry})" not in names:
            problems.append(f"{name}: module-pin record {r} lacks the entry module {entry}")
        for m in REQUIRED_MODULES:
            if m not in names:
                problems.append(f"{name}: module-pin record {r} lacks {m}")
        for mname, v in mods.items():
            path, h = (v or {}).get("path"), (v or {}).get("sha256")
            if path == "stub":
                if mname not in PERMITTED_STUBS:
                    problems.append(f"{name}: module-pin record {r}: stub not permitted: {mname}")
                continue
            if path not in pins:
                problems.append(f"{name}: module-pin record {r}: executed module not in the freeze: {path}")
            elif pins[path] != h:
                problems.append(f"{name}: module-pin record {r}: digest of {path} differs from the freeze")


def verify_complete(world_dirs, strict=True):
    """Returns (worlds, problems). With strict, every custody and reconciliation check applies (phase 2)."""
    worlds, problems = [], []
    cfg = E.load(os.path.join(E.STUDY, "config", "STUDY_CONFIG.json"))
    freeze = E.load(os.path.join(E.STUDY, "FREEZE.json")) if os.path.exists(os.path.join(E.STUDY, "FREEZE.json")) else {}
    if strict:
        pm_path = os.path.join(E.STUDY, "runs", "kaggle", "PACKAGE_MANIFEST.json")
        pm = E.load(pm_path) if os.path.exists(pm_path) else {}
        want = sorted(os.path.realpath(os.path.join(E.STUDY, d)) for d in pm.get("analysis_world_dirs", []))
        got = sorted(os.path.realpath(d) for d in world_dirs)
        if not want or got != want or len(set(got)) != len(got):
            problems.append(f"world directories {got} are not the packaged analysis set {want}")
        names = [os.path.basename(d) for d in got]
        if sorted(names) != sorted(cfg["world_order"]):
            problems.append(f"worlds {names} are not the configured {cfg['world_order']}")
        if not freeze:
            problems.append("no FREEZE.json to validate module pins against")
    m_sources = {}
    for wd in world_dirs:
        name = os.path.basename(os.path.realpath(wd))
        rpath = os.path.join(wd, "runs", "cas_eval", "world_results.json")
        if not os.path.exists(rpath):
            problems.append(f"{name}: no world_results.json")
            continue
        w = E.load(rpath)
        worlds.append(w)
        try:
            tids, e_ids, meta = _expected(wd)
        except (OSError, KeyError, ValueError) as e:
            problems.append(f"{name}: expected task sets unreadable ({type(e).__name__})")
            continue
        for u in w.get("units", []):
            m_sources.setdefault(u.get("source"), set()).add(name)
        # --- results against the expected sets, typed endpoints
        ulist = w.get("units")
        if not isinstance(ulist, list) or not all(isinstance(u, dict) for u in ulist):
            problems.append(f"INVALID {name}: the results' units are not a list of records")
            ulist = []
        ids = [u.get("task") for u in ulist]
        if len(ids) != len(set(ids)):
            problems.append(f"INVALID {name}: duplicate motivating rows in the results "
                            f"({sorted({i for i in ids if ids.count(i) > 1})})")
        if len(ulist) != len(tids):
            problems.append(f"{name}: {len(ulist)} motivating rows in the results, {len(tids)} expected")
        units = {u.get("task"): u for u in ulist}
        if sorted(units) != tids:
            problems.append(f"{name}: motivating tasks in the results {sorted(units)} differ from the expected {tids}")
        for u in ulist:
            if not isinstance(u.get("seeds"), dict) or set(u["seeds"]) != set(SEEDS) or \
                    any(not isinstance(v, dict) or set(v) != set(ARMS) for v in u["seeds"].values()):
                problems.append(f"INVALID {name}: task {u.get('task')} does not hold exactly seeds {SEEDS} x arms {ARMS}")
        for tid in tids:
            u = units.get(tid)
            if u is None:
                continue
            if u.get("family") != meta[tid]["family"] or u.get("source") != meta[tid]["source"]:
                problems.append(f"{name}: task {tid} metadata differs from the task file")
            for s in SEEDS:
                for arm in ARMS:
                    a = (u.get("seeds") or {}).get(s, {}).get(arm)
                    if _typed(a):
                        continue
                    if arm == "S-shuffled" and isinstance(a, dict) and a.get("not_applicable") and a.get("recovered") is None:
                        continue
                    problems.append(f"{name}: {arm} seed {s} on {tid} has no typed recovered endpoint")
            if not (_typed(u.get("C7m")) and isinstance(u["C7m"].get("failed"), bool)):
                problems.append(f"{name}: matched search on {tid} has no typed endpoint")
        e_tasks = w.get("e_tasks")
        if not isinstance(e_tasks, dict):
            problems.append(f"INVALID {name}: the results' excluded tasks are not a record")
            e_tasks = {}
        if sorted(e_tasks) != e_ids or len(e_tasks) != len(e_ids):
            problems.append(f"{name}: excluded tasks in the results differ from the expected set")
        for t in e_ids:
            e = e_tasks.get(t)
            if e is None:
                continue
            for k in ("C7m", "reuse", "transfer"):
                if not _typed(e.get(k)):
                    problems.append(f"{name}: excluded task {t} has no typed {k} endpoint")
            if _typed(e.get("C7m")) and not isinstance(e["C7m"].get("failed"), bool):
                problems.append(f"INVALID {name}: excluded task {t}'s matched search has no failure flag")
            if e.get("family") != meta[t]["family"] or e.get("source") != meta[t]["source"]:
                problems.append(f"{name}: excluded task {t} metadata differs from the task file")
        if not strict:
            continue
        # --- world identity and task files
        man = E.load(os.path.join(wd, "partitions", "PARTITIONS_MANIFEST.json"))
        if man.get("world") != name or w.get("world") != name or name not in cfg["worlds"]:
            problems.append(f"{name}: world name differs between directory, manifest and results")
        for rel, key in (("partitions/TASKS_SYSTEM.json", "tasks_system_sha256"),
                         ("evaluator_only/TASKS_EVAL.json", "tasks_eval_sha256"),
                         ("evaluator_only/REMOVED.json", "removed_sha256")):
            if E.sha256(os.path.join(wd, rel)) != man.get(key):
                problems.append(f"{name}: {rel} differs from its manifest")
        rem = E.load(os.path.join(wd, "evaluator_only", "REMOVED.json"))
        if name in cfg["worlds"] and (list(rem["removed"]) != list(cfg["worlds"][name]["removed"]) or
                                      list(rem["families"]) != list(cfg["worlds"][name]["families"]) or
                                      man.get("salt") != cfg["worlds"][name]["salt"] or
                                      list(w.get("removed", [])) != list(rem["removed"])):
            problems.append(f"{name}: removed set, families or salt differ from the configuration")
        gen = os.path.join(E.STUDY, "runs", "generated", name, "partitions", "PARTITIONS_MANIFEST.json")
        if not os.path.exists(gen) or E.load(gen) != man:
            problems.append(f"{name}: manifest differs from the generated (committed) manifest")
        # --- kernel record and custody chain
        st_path = os.path.join(wd, "runs", "STAGES.json")
        st = E.load(st_path) if os.path.exists(st_path) else {}
        if st.get("status") != "complete" or st.get("world") != name:
            problems.append(f"{name}: kernel status {st.get('status')!r} for world {st.get('world')!r}")
        for s in STAGES:
            if st.get("stages", {}).get(s, {}).get("status") != "done":
                problems.append(f"{name}: stage {s} not done")
        if st.get("task_manifest_sha256") != (E.sha256(gen) if os.path.exists(gen) else None):
            problems.append(f"{name}: the kernel verified another task manifest than the committed one")
        pm_path = os.path.join(E.STUDY, "runs", "kaggle", "PACKAGE_MANIFEST.json")
        if not os.path.exists(pm_path) or st.get("archive_sha256") != E.load(pm_path).get("archive_sha256"):
            problems.append(f"{name}: the kernel ran from another package than runs/kaggle/PACKAGE_MANIFEST.json")
        # --- output manifest: coverage, required entries, digests
        om_path = os.path.join(wd, "runs", "OUTPUT_MANIFEST.json")
        om = E.load(om_path) if os.path.exists(om_path) else None
        if not isinstance(om, dict) or not om:
            problems.append(f"{name}: OUTPUT_MANIFEST.json missing or empty")
        else:
            present = set()
            for d, _, files in os.walk(os.path.join(wd, "runs")):
                for f in files:
                    rel = os.path.relpath(os.path.join(d, f), wd)
                    if not rel.endswith(".tmp") and rel != "runs/OUTPUT_MANIFEST.json":
                        present.add(rel)
            if set(om) != present:
                problems.append(f"{name}: OUTPUT_MANIFEST.json does not cover runs/ exactly "
                                f"(missing {sorted(present - set(om))[:5]}, extra {sorted(set(om) - present)[:5]})")
            for rel in REQUIRED_OUTPUTS:
                if rel not in om:
                    problems.append(f"{name}: required output not in the manifest: {rel}")
            for rel, h in om.items():
                p = os.path.join(wd, rel)
                if not os.path.exists(p) or E.sha256(p) != h:
                    problems.append(f"{name}: output {rel} missing or differs from the manifest")
        # --- module pins against the bound freeze
        _check_pins(wd, name, freeze, problems)
        # --- committed predictions: digest chain and exact key sets
        cpath = os.path.join(wd, "runs", "cas_commit", "COMMITTED_PREDICTIONS.json")
        spath = os.path.join(wd, "runs", "cas_commit", "COMMITTED_SHA256")
        if os.path.exists(os.path.join(wd, "runs", "cas_commit", "INCOMPLETE.json")):
            problems.append(f"{name}: commit recorded INCOMPLETE")
        if not (os.path.exists(cpath) and os.path.exists(spath)):
            problems.append(f"{name}: no committed predictions")
        else:
            with open(spath, encoding="utf-8") as f:
                want_sha = f.read().strip()
            if E.sha256(cpath) != want_sha or w.get("committed_sha256") != want_sha:
                problems.append(f"{name}: committed predictions digest chain broken")
            com = E.load(cpath)
            _check_commitments(name, com, tids, e_ids, meta, problems)
            _rescore(name, wd, w, com, tids, e_ids, problems)
        # --- the controller summary against the hashed system task list and the results' decisions
        try:
            sys_ids = sorted(E.load(os.path.join(wd, "partitions", "TASKS_SYSTEM.json")))
            summ = E.load(os.path.join(wd, "runs", "prep_v4", "controller_summary.json"))
            if sorted(summ) != sys_ids:
                problems.append(f"INVALID {name}: the controller summary's tasks differ from the hashed system tasks")
            bad = sorted(t for t, v in summ.items() if (v or {}).get("decision") not in DECISIONS)
            if bad:
                problems.append(f"INVALID {name}: controller decisions outside the controller's set on {bad[:3]}")
            ctrl = w.get("controller") or {}
            if sorted(ctrl) != sys_ids or any((ctrl[t] or {}).get("decision") != summ[t].get("decision")
                                              for t in sys_ids if t in summ and t in ctrl):
                problems.append(f"INVALID {name}: the results' controller decisions differ from the controller summary")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            problems.append(f"INVALID {name}: controller summary or system task list unreadable")
    for src, ws in m_sources.items():
        if len(ws) > 1:
            problems.append(f"source {src} serves motivating tasks of {sorted(ws)}: the primary's no-link condition is broken")
    if strict:
        # rule 6 in full: a motivating source of one world is the source of no task (any partition) of another
        all_src = {}
        for wd in world_dirs:
            name = os.path.basename(os.path.realpath(wd))
            try:
                for t, v in E.load(os.path.join(wd, "evaluator_only", "TASKS_EVAL.json")).items():
                    all_src.setdefault(v["source"], set()).add((name, v["partition"]))
            except (OSError, ValueError, KeyError):
                problems.append(f"INVALID {name}: task metadata unreadable for the source rule")
        for src, uses in all_src.items():
            m_worlds = {wn for wn, part in uses if part == "M"}
            if m_worlds and len({wn for wn, _ in uses}) > 1:
                problems.append(f"INVALID source {src}: a motivating source of {sorted(m_worlds)} also serves "
                                f"{sorted(uses)} (rule 6)")
    return worlds, problems


# ------------------------------------------------------------------ statistics (S1's code)
def per_task(u, arm, field="recovered"):
    v = [u["seeds"].get(s, {}).get(arm, {}).get(field) for s in SEEDS]
    if any(x is None for x in v):
        return None                                                  # not applicable (no donor): excluded, counted
    v = [bool(x) for x in v]
    return {"any": any(v), "majority": sum(v) >= 2, "all3": all(v), "seeds": sum(v)}


def promoted_majority(u, arm):
    cnt = {}
    for s in SEEDS:
        sid = u["seeds"].get(s, {}).get(arm, {}).get("promoted")
        if sid:
            cnt[sid] = cnt.get(sid, 0) + 1
    return sorted(k for k, n in cnt.items() if n >= 2)


def cluster_id(row):
    """Dependence-aware cluster: the family, with W2's four linked families as one cluster."""
    return "W2 (linked group)" if row["world"] == "W2" else f"{row['world']}:{row['family']}"


def joint_components(rows):
    """Connected components of the cluster links and the source links (tasks sharing a source input)."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for r in rows:
        union(("c", r["cluster"]), ("t", r["task"]))
        union(("s", r["source"]), ("t", r["task"]))
    return {r["task"]: "component:" + str(find(("t", r["task"]))) for r in rows}


def compare(rows, a, b, cluster_field):
    """S1's paired comparison, clustering the bootstrap by `cluster_field` (its 'family' argument)."""
    rows = [dict(r, family=r[cluster_field]) for r in rows if r.get(a) and r.get(b)]
    return TR._compare(rows, a, b) if rows else None


def contrast(rows, a, b, joint=False):
    """The statistics: McNemar (conditional), the dependence-aware interval (decision), and the 11-family,
    source-clustered and unit intervals (reported); with joint, the joint source-and-family components interval
    (descriptive, when at least 4 components)."""
    dep = compare(rows, a, b, "cluster")
    if dep is None:
        return None
    fam = compare(rows, a, b, "family_id")
    src = compare(rows, a, b, "source_cluster")
    out = {"units": dep["units"], "both": dep["both"], "only_" + a: dep["only_" + a], "only_" + b: dep["only_" + b],
           "neither": dep["neither"], "mean_diff": dep["mean_diff"],
           "mcnemar_p_conditional": dep["mcnemar_p"], "unit_ci95": dep["unit_ci95"],
           "dependence_aware_ci95": dep["family_ci95"],
           "clusters": len({r["cluster"] for r in rows if r.get(a) and r.get(b)}),
           "family_ci95_11_families": fam["family_ci95"] if fam else None,
           "source_clustered_ci95": src["family_ci95"] if src else None}
    if joint:
        comp = joint_components([r for r in rows if r.get(a) and r.get(b)])
        rows_j = [dict(r, joint=comp[r["task"]]) for r in rows if r.get(a) and r.get(b)]
        n = len(set(comp.values()))
        out["joint_components"] = n
        out["joint_source_family_ci95"] = compare(rows_j, a, b, "joint")["family_ci95"] if n >= 4 else None
    return out


def decide(c):
    if c is None:
        return "no units"
    p, ci = c["mcnemar_p_conditional"], c["dependence_aware_ci95"]
    if p < 0.05 and ci and ci[0] > 0:
        return "S-hole beats matched search"
    if p < 0.05 and ci and ci[1] < 0:
        return "matched search beats S-hole"
    if ci and ci[1] < S1_DIFF:
        return "S1-sized advantage refuted"
    return "inconclusive"


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [None] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = round(run, 4)
    return adj


# ------------------------------------------------------------------ main
def main(out_dir, world_dirs, strict=True):
    worlds, problems = verify_complete(world_dirs, strict=strict)
    if problems:
        status = "INVALID" if any(p.startswith("INVALID") for p in problems) else "INCOMPLETE"
        E.dump(os.path.join(out_dir, "INCOMPLETE.json"), {"status": status, "problems": problems})
        print(status + ": " + "; ".join(problems[:30]))
        raise SystemExit(2)
    source_count = {}
    for w in worlds:
        for u in w["units"]:
            source_count[u["source"]] = source_count.get(u["source"], 0) + 1
        for e in w["e_tasks"].values():
            source_count[e["source"]] = source_count.get(e["source"], 0) + 1
    tasks, e_rows_reuse, e_rows_transfer, not_applicable = [], [], [], []
    for w in worlds:
        for u in w["units"]:
            row = {"world": w["world"], "task": u["task"], "family": u["family"], "template": u["template"],
                   "source": u["source"], "family_id": f"{w['world']}:{u['family']}",
                   "source_cluster": "src:" + u["source"],
                   "C7m": {"recovered": bool(u["C7m"]["recovered"])}, "C7m_failed": bool(u["C7m"].get("failed"))}
            row["cluster"] = cluster_id(row)
            for arm in ARMS:
                row[arm] = per_task(u, arm)                                  # committed outputs
                row[arm + "_reach"] = per_task(u, arm, "reach")              # oracle reach, descriptive
                if row[arm] is None:
                    not_applicable.append((w["world"], u["task"], arm))
            row["S-hole_promoted_majority"] = promoted_majority(u, "S-hole")
            tasks.append(row)
        for t, e in sorted(w["e_tasks"].items()):
            base = {"world": w["world"], "task": t, "family": e["family"], "source": e["source"],
                    "family_id": f"{w['world']}:{e['family']}", "source_cluster": "src:" + e["source"],
                    "C7m": {"recovered": bool(e["C7m"]["recovered"])}}
            base["cluster"] = cluster_id(base)
            e_rows_reuse.append(base | {"S-hole": {"recovered": bool(e["reuse"]["recovered"])},
                                        "structures": e["reuse"]["structures"], "reach": e.get("reach_reuse")})
            e_rows_transfer.append(base | {"S-hole": {"recovered": bool(e["transfer"]["recovered"])},
                                           "structures": e["transfer"]["structures"], "reach": e.get("reach_transfer")})

    def flat(crit, arms, field_suffix=""):
        out = []
        for r in tasks:
            d = {k: r[k] for k in ("task", "family", "world", "cluster", "family_id", "source_cluster", "source")}
            ok = True
            for a in arms:
                if a == "C7m":
                    d[a] = {"recovered": r["C7m"]["recovered"]}
                elif r[a + field_suffix] is None:
                    ok = False
                else:
                    d[a] = {"recovered": r[a + field_suffix][crit]}
            if ok:
                out.append(d)
        return out

    primary = contrast(flat("majority", ("S-hole", "C7m")), "S-hole", "C7m", joint=True) or {}
    primary["decision"] = decide(primary or None)
    primary["cross_world_motivating_source_links"] = 0           # verified above: none, by construction
    cfg = E.load(os.path.join(E.STUDY, "config", "STUDY_CONFIG.json"))
    den = {"planned_motivating_slots": 0, "unfilled_motivating_slots": 0, "built_motivating_slot_tasks": 0,
           "controller_exclusions": 0, "motivating_tasks": len(tasks)}
    for wd in world_dirs:
        name = os.path.basename(os.path.realpath(wd))
        man = E.load(os.path.join(wd, "partitions", "PARTITIONS_MANIFEST.json"))
        ev = E.load(os.path.join(wd, "evaluator_only", "TASKS_EVAL.json"))
        summ = E.load(os.path.join(wd, "runs", "prep_v4", "controller_summary.json"))
        fams = cfg["worlds"].get(name, {}).get("families", [])
        den["planned_motivating_slots"] += len(fams) * len(cfg["quota"]["M"])
        den["unfilled_motivating_slots"] += sum(u.get("partition") == "M" for u in
                                                (man.get("construction") or {}).get("unfilled", []))
        m = [t for t, v in ev.items() if v["partition"] == "M"]
        den["built_motivating_slot_tasks"] += len(m)
        den["controller_exclusions"] += sum(summ.get(t, {}).get("decision") != "INVENT_NEW_OPERATION" for t in m)
    primary["denominator"] = den
    # descriptive beside the decision: without tasks whose matched search failed; per world; leaving out each world
    fails = {(r["world"], r["task"]) for r in tasks if r.get("C7m_failed")}
    rows_p = flat("majority", ("S-hole", "C7m"))
    primary["without_failed_matched_search"] = dict(
        contrast([r for r in rows_p if (r["world"], r["task"]) not in fails], "S-hole", "C7m") or {},
        tasks_excluded=len(fails))
    primary["per_world"] = {wn: contrast([r for r in rows_p if r["world"] == wn], "S-hole", "C7m")
                            for wn in sorted({r["world"] for r in rows_p})}
    primary["leave_one_world_out"] = {wn: contrast([r for r in rows_p if r["world"] != wn], "S-hole", "C7m")
                                      for wn in sorted({r["world"] for r in rows_p})}
    primary["scope"] = ("conditional on the finite-cluster bootstrap (8 clusters, percentile interval), on task "
                        "exchangeability for the McNemar p-value, and on the families within W1 and within W3 being "
                        "independent beyond their shared regression set, validation pool and donors; the denominator "
                        "is the constructed, controller-eligible motivating tasks, reported with the planned and "
                        "unfilled slots and the controller exclusions, not a rate over the planned slots")
    sec = {"S-hole vs S-shuffled (majority)": contrast(flat("majority", ("S-hole", "S-shuffled")), "S-hole", "S-shuffled"),
           "S-hole vs S-enum (all 3 seeds)": contrast(flat("all3", ("S-hole", "S-enum")), "S-hole", "S-enum"),
           "reuse on excluded tasks: grown grammar vs C7m": contrast(e_rows_reuse, "S-hole", "C7m", joint=True),
           "transfer to other families: grown grammar vs C7m": contrast(e_rows_transfer, "S-hole", "C7m", joint=True)}
    names = list(sec)
    adj = holm([sec[k]["mcnemar_p_conditional"] if sec[k] else 1.0 for k in names])
    for k, a in zip(names, adj):
        if sec[k]:
            sec[k]["holm_p"] = a
            ci = sec[k]["dependence_aware_ci95"]
            sec[k]["holds"] = a < 0.05 and bool(ci) and (ci[0] > 0 or ci[1] < 0)
            if "joint_components" in sec[k]:
                sec[k]["scope"] = ("conditional on no cross-world source link among excluded tasks; the joint "
                                   "source-and-family interval beside it is descriptive")
    desc = {"counts": {}, "by_world": {}, "by_family": {}}
    for crit in ("any", "majority", "all3"):
        desc["counts"][crit] = {a: sum(r[a][crit] for r in tasks if r[a]) for a in ARMS} | \
            {"C7m": sum(r["C7m"]["recovered"] for r in tasks), "tasks": len(tasks)}
    for key, field in (("by_world", "world"), ("by_family", "family_id")):
        for r in tasks:
            d = desc[key].setdefault(r[field], {"tasks": 0, "C7m": 0} | {a: 0 for a in ARMS})
            d["tasks"] += 1
            d["C7m"] += r["C7m"]["recovered"]
            for a in ARMS:
                d[a] += bool(r[a] and r[a]["majority"])
    desc["descriptive_contrasts"] = {
        "S-hole vs S-demo (majority)": contrast(flat("majority", ("S-hole", "S-demo")), "S-hole", "S-demo"),
        "S-enum (majority) vs C7m": contrast(flat("majority", ("S-enum", "C7m")), "S-enum", "C7m"),
        "S-hole vs C7m, any-seed criterion": contrast(flat("any", ("S-hole", "C7m")), "S-hole", "C7m")}
    desc["oracle_reach_counts"] = {crit: {a: sum(r[a + "_reach"][crit] for r in tasks if r[a + "_reach"]) for a in ARMS}
                                   for crit in ("any", "majority", "all3")}
    desc["oracle_reach_excluded"] = {"reuse": sum(bool(r.get("reach")) for r in e_rows_reuse),
                                     "transfer": sum(bool(r.get("reach")) for r in e_rows_transfer),
                                     "excluded_tasks": len(e_rows_reuse)}
    desc["not_applicable_units"] = not_applicable
    desc["sources_shared_between_tasks"] = sum(n > 1 for n in source_count.values())
    e_src = {}
    for r in e_rows_reuse:
        e_src.setdefault(r["source"], set()).add(r["world"])
    desc["excluded_sources_shared_between_worlds"] = sum(len(v) > 1 for v in e_src.values())
    desc["c7m_failures"] = {w["world"]: {"M": sum(bool(u["C7m"].get("failed")) for u in w["units"]),
                                         "E": sum(bool(e["C7m"].get("failed")) for e in w["e_tasks"].values())} for w in worlds}
    desc["cpu_accounting"] = {w["world"]: w.get("cpu_accounting") for w in worlds}
    res = {"primary": primary, "secondary": sec, "descriptive": desc, "tasks": tasks,
           "reuse_rows": e_rows_reuse, "transfer_rows": e_rows_transfer,
           "structures": {w["world"]: w["structures"] for w in worlds}, "strict": strict}
    E.dump(os.path.join(out_dir, "ANALYSIS.json"), res)
    print(json.dumps({"primary": primary, "secondary_holm": {k: v and v.get("holm_p") for k, v in sec.items()}}))


if __name__ == "__main__":
    from cas import gate                              # phase 2: only under the claimed GO
    if not gate.check("analyse"):
        raise SystemExit(1)
    main(sys.argv[1], sys.argv[2:])
