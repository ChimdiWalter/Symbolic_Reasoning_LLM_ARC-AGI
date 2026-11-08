"""Source-free admission tests of the amended functions on synthetic inputs (phase 1; no natural task, no
benchmark output, no GO). Writes checks/ADMISSION_TESTS.json.

    python -I run.py admission_tests

1. gate: a GO naming arm 5 is refused while the object-growth slot is empty, with the freeze and protocol digests
   correct (tested on a temporary copy of the study's gate paths; no runs/GO is written);
2. score: decoding only the requested ids from a combined source-plus-held solution text; a duplicated key is
   refused; the held entry's bytes are never passed to the decoder (the decoder is wrapped to record the offsets it
   decodes);
3. report: Holm-adjusted decisions (the review's case: six discordant tasks one way, raw p = 0.03125, which with six
   secondaries gives Holm p = 0.1875 and the decision "inconclusive" instead of "beats"); a missing row is INCOMPLETE and a duplicate row INVALID, both before any
   solution is opened (the solution loader is wrapped to refuse any call);
4. held: a static child that exceeds its wall limit or fails yields a durable failure row (a stub child command);
5. object contract (amendment 2): the registry is bound by digest and a changed copy refused; the donor rule gives
   another family; a construction call on a synthetic task sees demonstrations and test inputs only;
6. report row validation: three attempts, a wrong number of grids, attempts without a fit, an invalid grid, a
   registry or G0 digest other than the frozen one are INVALID; a run missing the ARC-AGI-2 rows or a static arm is
   INCOMPLETE and nothing is scored; a second scoring under the same GO is refused; a held-id request asks the gate
   before the solution file is read;
7. amendment 3: a claim or a completion marker refuses scoring; arm_error and no_donor rows are INVALID; a killed
   static child is replaced by its retry row, is INCOMPLETE without one, and a retry without a killed original is
   INVALID; in rehearsal mode the gate refuses data that hold a held task; the object costs come from the frozen
   record.
"""
import json
import os
import subprocess
import sys
import tempfile

from ngb import env as E, gate as GT, score as SC, report as RP, held as HB
from ngrow import analysis as AN

OUT = os.path.join(E.STUDY, "checks", "ADMISSION_TESTS.json")


def test_gate(tmp):
    res = {}
    proto, freeze, go = (os.path.join(tmp, n) for n in ("PROTOCOL.md", "FREEZE.json", "GO"))
    with open(proto, "w") as f:
        f.write("synthetic protocol\n")
    fr = {"files_sha256": {}, "data_sha256": {}, "object_growth": {"code_sha256": None, "files_sha256": {}}}
    json.dump(fr, open(freeze, "w"))
    old = (GT.GO, GT.PROTOCOL, GT.FREEZE, GT.CONFIG)
    GT.GO, GT.PROTOCOL, GT.FREEZE, GT.CONFIG = go, proto, freeze, os.path.join(tmp, "no_config.json")
    try:
        for prim, expect in (("arm5_vs_arm4", "refused"), ("arm2_vs_arm1", "passed")):
            with open(go, "w") as f:
                f.write(f"protocol_sha256 {E.sha_file(proto)}\nfreeze_sha256 {E.sha_file(freeze)}\nprimary {prim}\n")
            try:
                GT.require_go()
                got = "passed"
            except GT.GateRefused as e:
                got = "refused"
                res[f"{prim}_message"] = str(e)[:90]
            res[prim] = {"expected": expect, "got": got, "ok": got == expect}
        with open(go, "w") as f:
            f.write(f"protocol_sha256 {E.sha_file(proto)}\nfreeze_sha256 0000\nprimary arm2_vs_arm1\n")
        try:
            GT.require_go()
            res["wrong_freeze_digest"] = {"ok": False}
        except GT.GateRefused:
            res["wrong_freeze_digest"] = {"ok": True}
    finally:
        GT.GO, GT.PROTOCOL, GT.FREEZE, GT.CONFIG = old
    return res


def test_score():
    text = json.dumps({"src1": [[[1, 2], [3, 4]]], "held1": [[[9, 9]]], "src2": [[[5]]]})
    decoded = []
    real = json.JSONDecoder.raw_decode

    def spy(self, s, idx=0):
        decoded.append(idx)
        return real(self, s, idx)
    json.JSONDecoder.raw_decode = spy
    try:
        out = SC._decode_ids(text, ["src1", "src2"])
    finally:
        json.JSONDecoder.raw_decode = real
    held_pos = text.find('"held1":') + len('"held1":')
    ok_values = out == {"src1": [((1, 2), (3, 4))], "src2": [((5,),)]}
    ok_no_held = all(i != held_pos for i in decoded) and len(decoded) == 2
    try:
        SC._decode_ids(text + json.dumps({"src1": []}), ["src1"])
        dup = False
    except SC.SolutionFileError:
        dup = True
    return {"values_ok": ok_values, "held_not_decoded": ok_no_held, "decoded_offsets": decoded,
            "duplicate_key_refused": dup, "ok": ok_values and ok_no_held and dup}


def test_report_holm():
    rows = [{"bench": "x", "cluster": f"c{i}", "A": 1, "B": 0} for i in range(6)] + \
           [{"bench": "x", "cluster": f"c{i}", "A": 0, "B": 0} for i in range(6, 40)]
    c = RP.compare(rows, "A", "B")
    raw_dec = RP.decide(c, c["exact_mcnemar_p"])
    adj = AN.holm({"S1": c["exact_mcnemar_p"], **{f"S{k}": 1.0 for k in range(2, 7)}})["S1"]
    adj_dec = RP.decide(c, adj)
    return {"raw_p": c["exact_mcnemar_p"], "raw_decision": raw_dec, "holm_p": adj, "holm_decision": adj_dec,
            "ok": abs(adj - 0.1875) < 1e-9 and adj_dec == "inconclusive"}


def test_report_completeness(tmp):
    d = os.path.join(tmp, "held", "mini_arc")
    os.makedirs(d)
    row = {"bench": "mini_arc", "family": "mini_arc", "arm": "lib", "go_sha256": "G", "library_sha256": "L",
           "registry_sha256": "R", "g0_sha256": None, "fit": False, "preds": None, "program": None, "cpu_s": 1,
           "calls": 1, "stop": "budget", "level_complete": 3}
    with open(os.path.join(d, "lib.jsonl"), "w") as f:
        for t in ("t1", "t1", "t3"):
            f.write(json.dumps(dict(row, task=t)) + "\n")
    rows, problems = RP.collect(tmp, os.path.join("held", "mini_arc"), "lib", "mini_arc", {"t1": 1, "t2": 1, "t3": 1},
                                "G", {"g0": None, "library": "L", "registry": "R"})
    kinds = sorted(p.split(" ")[0] for p in problems)
    return {"problems": problems, "ok": kinds == ["INCOMPLETE", "INVALID"] and set(rows) == {"t1", "t3"}}


def test_report_refuses_before_solutions(tmp):
    """A run with a missing row is reported INCOMPLETE and the solution loader is never called."""
    calls = []
    real_sol, real_go, real_prim = SC.solutions, GT.require_go, GT.primary
    SC.solutions = lambda *a: calls.append(a) or (_ for _ in ()).throw(RuntimeError("solutions opened"))
    GT.require_go, GT.primary = (lambda: "G"), (lambda: "arm2_vs_arm1")
    run_dir = os.path.join(tmp, "run")
    os.makedirs(os.path.join(run_dir, "held", "mini_arc"))
    json.dump({"go_sha256": "G", "primary": "arm2_vs_arm1", "status": "complete"},
              open(os.path.join(run_dir, "STAGES.json"), "w"))
    from ngb import phase2 as P2
    json.dump(P2.manifest(run_dir), open(os.path.join(run_dir, "OUTPUT_MANIFEST.json"), "w"))
    old_study = E.STUDY
    try:
        try:
            RP.main(run_dir, run_dir, run_dir)
            status = "returned"
        except SystemExit as e:
            status = f"exit {e.code}"
        res = json.load(open(os.path.join(run_dir, "RESULTS.json")))
        return {"status": status, "result_status": res.get("status"), "solutions_calls": len(calls),
                "ok": status == "exit 2" and res.get("status") == "INCOMPLETE" and not calls}
    finally:
        SC.solutions, GT.require_go, GT.primary = real_sol, real_go, real_prim
        E.STUDY = old_study


def test_child_failures():
    task = {"train": [(((1,),), ((1,),))], "test_inputs": [((1,),)]}
    real_run, real_timeout = subprocess.run, HB.subprocess.run
    out = {}

    def slow(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)
    HB.subprocess.run = slow
    try:
        out["timeout"] = HB.child_search(task, 0.01)
    finally:
        HB.subprocess.run = real_run

    class P:
        returncode, stdout, stderr = 1, "", "boom"
    HB.subprocess.run = lambda *a, **k: P()
    try:
        out["failed"] = HB.child_search(task, 0.01)
    finally:
        HB.subprocess.run = real_run
    ok = out["timeout"]["stop"] == "child_timeout" and out["failed"]["stop"] == "child_failed" and \
        all(v["fit"] is False and v["preds"] is None for v in out.values()) and \
        all("child_cpu_measured_s" in v and v.get("cpu_s") is not None for v in out.values())
    return {"rows": out, "ok": ok}


def _row(**kw):
    base = {"bench": "mini_arc", "family": "mini_arc", "arm": "lib", "go_sha256": "G", "library_sha256": "L",
            "registry_sha256": "R", "g0_sha256": "Z", "fit": True, "preds": [[[[1, 2], [3, 4]]]], "program": "p",
            "cpu_s": 1, "calls": 1, "stop": "fits", "level_complete": 3}
    base.update(kw)
    return base


def test_report_row_validation(tmp):
    """Three attempts, an attempt with the wrong number of grids, attempts without a fit, a registry digest that is
    not the frozen one, and a G0 digest that is not the frozen one are each INVALID; a correct row passes."""
    d = os.path.join(tmp, "v", "held", "mini_arc")
    os.makedirs(d)
    rows = [_row(task="ok"), _row(task="three", preds=[[[[1]]], [[[2]]], [[[3]]]]),
            _row(task="shape", preds=[[[[1]], [[2]]]]), _row(task="nofit", fit=False, preds=[[[[1]]]]),
            _row(task="reg", registry_sha256="other"), _row(task="g0", g0_sha256="other"),
            _row(task="badgrid", preds=[[[[1, 2], [3]]]])]
    with open(os.path.join(d, "lib.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    expected = {r["task"]: 1 for r in rows}
    frozen = {"g0": "Z", "library": "L", "registry": "R"}
    got, problems = RP.collect(os.path.join(tmp, "v"), os.path.join("held", "mini_arc"), "lib", "mini_arc", expected,
                               "G", frozen)
    invalid = {p.split("/")[-1].split(":")[0] for p in problems if p.startswith("INVALID")}
    return {"problems": problems, "passed_rows": sorted(got),
            "ok": sorted(got) == ["ok"] and invalid == {"three", "shape", "nofit", "reg", "g0", "badgrid"}}


def test_report_requires_every_arm(tmp):
    """A run folder missing the arc2 rows (and a static_obj arm) is INCOMPLETE; nothing is scored."""
    calls = []
    real_sol, real_go, real_prim = SC.solutions, GT.require_go, GT.primary
    SC.solutions = lambda *a: calls.append(a) or (_ for _ in ()).throw(RuntimeError("solutions opened"))
    GT.require_go, GT.primary = (lambda: "G2"), (lambda: "arm5_vs_arm4")
    run_dir = os.path.join(tmp, "run2")
    os.makedirs(os.path.join(run_dir, "held", "mini_arc"))
    json.dump({"go_sha256": "G2", "primary": "arm5_vs_arm4", "status": "complete"},
              open(os.path.join(run_dir, "STAGES.json"), "w"))
    from ngb import phase2 as P2
    json.dump(P2.manifest(run_dir), open(os.path.join(run_dir, "OUTPUT_MANIFEST.json"), "w"))
    try:
        try:
            RP.main(run_dir, run_dir, run_dir)
            status = "returned"
        except SystemExit as e:
            status = f"exit {e.code}"
        except RP.RunRefused as e:
            status = f"refused: {e}"
        res = json.load(open(os.path.join(run_dir, "RESULTS.json"))) if os.path.exists(
            os.path.join(run_dir, "RESULTS.json")) else {}
        probs = res.get("problems", [])
        return {"status": status, "result_status": res.get("status"), "solutions_calls": len(calls),
                "missing_static_obj_listed": any("static_obj" in p for p in probs),
                "missing_arc2_listed": any("arc_agi_2_eval" in p for p in probs),
                "ok": status == "exit 2" and res.get("status") == "INCOMPLETE" and not calls and
                any("static_obj" in p for p in probs) and any("arc_agi_2_eval" in p for p in probs)}
    finally:
        SC.solutions, GT.require_go, GT.primary = real_sol, real_go, real_prim


def test_exclusive_scoring(tmp):
    """A completion marker or a claim for the GO makes a second scoring refuse before anything is read."""
    real_go, real_prim, real_dir = GT.require_go, GT.primary, RP.MARKER_DIR
    GT.require_go, GT.primary = (lambda: "G3"), (lambda: "arm2_vs_arm1")
    RP.MARKER_DIR = os.path.join(tmp, "markers")
    os.makedirs(RP.MARKER_DIR, exist_ok=True)
    out = {}
    try:
        for name in ("SCORED_G3", "SCORING_G3"):
            m = os.path.join(RP.MARKER_DIR, name)
            open(m, "w").write("synthetic\n")
            try:
                RP.main(tmp, tmp, tmp)
                out[name] = "ran"
            except RP.RunRefused as e:
                out[name] = "refused" if "exclusive" in str(e) else f"other: {e}"
            os.remove(m)
        return {"got": out, "ok": all(v == "refused" for v in out.values())}
    finally:
        GT.require_go, GT.primary, RP.MARKER_DIR = real_go, real_prim, real_dir


def test_defects_and_retries(tmp):
    """arm_error and no_donor rows are INVALID; a killed static child with its retry row is replaced by it; a killed
    child without a retry is INCOMPLETE; a retry row without a killed original is INVALID."""
    d = os.path.join(tmp, "dr", "held", "mini_arc")
    os.makedirs(d)
    with open(os.path.join(d, "lib.jsonl"), "w") as f:
        for t, stop in (("a", "arm_error"), ("b", "no_donor"), ("c", "budget")):
            f.write(json.dumps(_row(task=t, fit=False, preds=None, stop=stop)) + "\n")
    _, prob_lib = RP.collect(os.path.join(tmp, "dr"), os.path.join("held", "mini_arc"), "lib", "mini_arc",
                             {"a": 1, "b": 1, "c": 1}, "G", {"g0": "Z", "library": "L", "registry": "R"})
    st = dict(_row(arm="static_obj", registry_sha256=None, fit=False, preds=None))
    with open(os.path.join(d, "static_obj.shard0of2.jsonl"), "w") as f:
        for t, stop in (("k1", "child_killed"), ("k2", "child_killed"), ("ok", "cpu_cap")):
            f.write(json.dumps(dict(st, task=t, stop=stop)) + "\n")
    with open(os.path.join(d, "static_obj.retry.jsonl"), "w") as f:
        f.write(json.dumps(dict(st, task="k1", stop="cpu_cap", retry_of={"stop": "child_killed"})) + "\n")
        f.write(json.dumps(dict(st, task="ok", stop="cpu_cap", retry_of={"stop": "child_killed"})) + "\n")
    rows, prob_st = RP.collect(os.path.join(tmp, "dr"), os.path.join("held", "mini_arc"), "static_obj", "mini_arc",
                               {"k1": 1, "k2": 1, "ok": 1}, "G", {"g0": "Z", "library": "L", "registry": None})
    ok_lib = sorted(p.split("/")[-1].split(":")[0] for p in prob_lib if p.startswith("INVALID")) == ["a", "b"]
    ok_st = rows.get("k1", {}).get("killed_then_retried") is True and \
        any(p.startswith("INCOMPLETE killed child") and p.endswith("/k2") for p in prob_st) and \
        any(p.startswith("INVALID retry row") and "/ok" in p for p in prob_st)
    return {"lib_problems": prob_lib, "static_problems": prob_st, "ok": ok_lib and ok_st}


def test_rehearsal_data_guard(tmp):
    """In rehearsal mode the gate refuses data that hold a held task of the real split."""
    from ngrow import data as DT
    real = (E.DATA, E.STUDY, GT.REHEARSAL_DATA)
    data = os.path.join(tmp, "rdata")
    held_id = [t for _, _, t in E.REAL_HALF("held", ("mini_arc",))][0]
    src_ids = {b: [t for _, _, t in E.REAL_HALF("source", (b,))][0] for b in DT.BENCHMARKS}
    digests = {}
    for b in DT.BENCHMARKS:
        os.makedirs(os.path.join(data, b))
        ids = [src_ids[b]] + ([held_id] if b == "mini_arc" else [])
        for name in ("real.json", "meta.json"):
            p = os.path.join(data, b, name)
            json.dump({t: {} for t in ids}, open(p, "w"))
            digests[f"{b}/{name}"] = E.sha_file(p)
    study = os.path.join(tmp, "rstudy")
    os.makedirs(os.path.join(study, "rehearsal"))
    st = os.path.join(study, "rehearsal", "arc2_standin_challenges.json")
    json.dump({}, open(st, "w"))
    json.dump({"data_sha256": digests, "arc2_standin_sha256": E.sha_file(st)},
              open(os.path.join(study, "rehearsal", "REHEARSAL_DATA.json"), "w"))
    E.DATA, E.STUDY, GT.REHEARSAL_DATA = data, study, os.path.join(study, "rehearsal", "REHEARSAL_DATA.json")
    try:
        probs = GT.rehearsal_data_problems()
    finally:
        E.DATA, E.STUDY, GT.REHEARSAL_DATA = real
    return {"problems": probs, "ok": any("held tasks" in p and p.startswith("mini_arc") for p in probs)
            and not any(p.startswith("concept_arc") or p.startswith("1d_arc") for p in probs)}


def test_object_costs():
    """The object arms' source cost comes from the frozen cost record and equals its parts' sum."""
    from ngb import object_arm as OA, held as HB2
    out, ok = {}, True
    for b in ("concept_arc", "mini_arc", "1d_arc"):
        c = OA.costs(b)
        parts = c["controller_cpu_s"] + c["construction_cpu_s"] + c["gate_cpu_s_distinct"] + \
            c["combined_regression_cpu_s"]
        out[b] = {"source_cost": OA.source_cost(b), "held_source_cost_obj": HB2.source_cost(None, b, "obj"),
                  "parts_sum": round(parts, 3)}
        ok = ok and abs(out[b]["source_cost"] - parts) < 0.01 and out[b]["held_source_cost_obj"] == out[b]["source_cost"]
    return {"costs": out, "ok": ok}


def test_held_loader_gate_first():
    """A request with a held id asks the gate before the solution file is read."""
    reads = []
    real_read, real_go = SC._read_checked, GT.require_go
    SC._read_checked = lambda b: reads.append(b) or ("{}", "d")
    GT.require_go = lambda: (_ for _ in ()).throw(GT.GateRefused("no GO"))
    from ngrow import data as DT
    held = [t for _, _, t in DT.half("held", ("mini_arc",))][:1]
    try:
        try:
            SC.solutions("mini_arc", held)
            got = "returned"
        except GT.GateRefused:
            got = "refused"
        return {"got": got, "reads_before_gate": len(reads), "ok": got == "refused" and not reads}
    finally:
        SC._read_checked, GT.require_go = real_read, real_go


def test_object_contract(tmp):
    """The registry is bound by digest; a changed copy is refused; the donor comes from another family; the
    construction call sees no test output (a synthetic task with demonstrations and test inputs only)."""
    from ngb import object_arm as OA
    res = {"available": OA.available()}
    if not res["available"]:
        res["ok"] = False
        return res
    good = OA.registry_doc("concept_arc")
    res["registry_bound"] = len(good["registry"]) == 2
    spec = OA.spec()
    bad = os.path.join(tmp, "registry.json")
    json.dump(dict(good, registry=good["registry"][:1]), open(bad, "w"))
    old = spec["registries"]["concept_arc"]
    real_path = OA.registry_path
    OA.registry_path = lambda b: bad if b == "concept_arc" else real_path(b)
    try:
        OA.registry_doc("concept_arc")
        res["changed_registry_refused"] = False
    except RuntimeError:
        res["changed_registry_refused"] = True
    finally:
        OA.registry_path = real_path
    from ngrow import data as DT
    fam = {t: f for _, f, t in DT.half("source", ("1d_arc",))}
    t0 = next(iter(fam))
    d = OA.donor_of("1d_arc", t0, half="source")
    res["donor_other_family"] = d is not None and fam[d] != fam[t0]
    task = {"train": [(((1, 1, 0, 0),), ((0, 1, 1, 0),)), (((1, 1, 1, 0, 0),), ((0, 1, 1, 1, 0),))],
            "test_inputs": [((1, 0, 0),)]}
    r = OA.construct(task, OA.ops("1d_arc"))
    res["construction_returns"] = sorted(k for k in r if k in ("fit", "preds", "cpu_s", "stage"))
    res["construction_saw_no_output"] = "test_outputs" not in task and set(task) == {"train", "test_inputs"}
    res["ok"] = all(res.get(k) for k in ("registry_bound", "changed_registry_refused", "donor_other_family",
                                          "construction_saw_no_output")) and res["construction_returns"] == \
        ["cpu_s", "fit", "preds", "stage"]
    return res


def main():
    os.makedirs(os.path.join(E.STUDY, "checks"), exist_ok=True)
    with tempfile.TemporaryDirectory(dir=os.path.join(E.STUDY, "checks"), prefix="tmp_admission_") as tmp:
        res = {"gate": test_gate(tmp), "score": test_score(), "report_holm": test_report_holm(),
               "report_completeness": test_report_completeness(tmp),
               "report_refuses_before_solutions": test_report_refuses_before_solutions(tmp),
               "child_failures": test_child_failures(), "object_contract": test_object_contract(tmp),
               "report_row_validation": test_report_row_validation(tmp),
               "report_requires_every_arm": test_report_requires_every_arm(tmp),
               "exclusive_scoring": test_exclusive_scoring(tmp), "held_loader_gate_first": test_held_loader_gate_first(),
               "defects_and_retries": test_defects_and_retries(tmp),
               "rehearsal_data_guard": test_rehearsal_data_guard(tmp), "object_costs": test_object_costs()}
    res["all_ok"] = all(v["ok"] if "ok" in v else all(x["ok"] for x in v.values() if isinstance(x, dict) and "ok" in x)
                        for v in res.values())
    E.dump(OUT, res)
    print(json.dumps({k: (v.get("ok") if isinstance(v, dict) and "ok" in v else v) for k, v in res.items()
                      if k != "gate"} | {"gate": {k: v for k, v in res["gate"].items() if not k.endswith("_message")}},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
