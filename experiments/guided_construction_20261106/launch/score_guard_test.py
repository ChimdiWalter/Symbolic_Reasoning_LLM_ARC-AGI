"""Regression tests of the scorer's guard (PROTOCOL_AMENDMENT_1.md section 1). Run by launch/smoke_test.py in rehearsal
mode, against a copy of the smoke test's rows (source stand-ins) inside the unpacked package, whose roots hold no
solution file; the two solution functions are also replaced by raising sentinels, and the marker call is watched.

    python -s -B launch/score_guard_test.py RUN_DIR        (package roots in the environment, GC_REHEARSAL=1)

Cases, each on a fresh copy of RUN_DIR:
  sentinel_mutated_rows   the companion review's case: an invented receipt {verdict PASS, go OLD_GO, freeze OLD_FREEZE}
                          with the current GO and a mutated row file (an authored extra row)
  sentinel_current_rows   the same invented receipt with the current, valid rows
  stale_receipt           a valid receipt, then one row file changed in a field no check covers
  copied_receipt          a valid receipt of another run folder (rows differing in one such field) copied in
  forged_receipt          a receipt claiming PASS with every current digest, over rows that break invariant 1
  missing_receipt         no receipt at all
  positive_control        a valid receipt over the unchanged rows: the guard passes and the marker call is reached
                          (in rehearsal mode the marker itself refuses: nothing is ever scored)
Expected: every case stops with GateRefused, no solution function is called and no marker file exists; the negative
cases stop before the marker call.
Verification sentinels (amendment 2): each mutates one construction row of a fresh copy (the companion's cases:
changed hand@20000 stage, family, benchmark, base_fit without base stage or without fit, empty or False reference
error, a reference error beside an answer and arms, under_two_demonstrations with two or more trusted
demonstrations, an unknown shared stage; this study's: changed reference stage, an arm whose stage contradicts its
fit, changed test or demonstration count, the old string form of a reference error) and requires verify INVALID and,
with a forged receipt claiming PASS with every current digest, a refusal before the marker; two positive controls (a
consistent base_fit row and a consistent reference-error row) must verify PASS and reach the marker.
Kernel receipts (amendment 2 section 3): an invented consistent tree passes; a missing tree, kernel, push or fetch
receipt, a substituted role, internet on, not private, a GPU, metadata changed after the manifest, a failed push or
worker, a rehearsal record, a changed archive, a package naming another GO, and a row file not returned by its
kernel each fail.
Amendment 3: a row without its demonstration count (n_demos) gives INVALID; a driver record (kernel_run.json) edited
after return, or missing from the fetch receipt's file digests, fails; the scorer, fed fake outputs, reports the donor
comparison total with its cache-delta scope label. Prints one JSON object.
"""
import json
import os
import shutil
import sys

STUDY_ATHE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDY_ATHE)

from gcon import env as E, gate as GT, score as SC, verify as VF            # noqa: E402


class HeldAccess(Exception):
    pass


CALLS, MARKS = [], []


def sentinel(*a, **k):
    CALLS.append(repr(a)[:80])
    raise HeldAccess("solution function reached")


_take = GT.take_marker


def take_spy():
    MARKS.append(1)
    return _take()


SC.held_solutions = sentinel
SC.arc2_solutions = sentinel
GT.take_marker = take_spy


def rows_file(d):
    for s in ("1d_arc", "concept_arc", "mini_arc"):
        p = os.path.join(d, s)
        for fn in sorted(os.listdir(p)) if os.path.isdir(p) else []:
            if fn.startswith("rows."):
                return os.path.join(p, fn)
    raise SystemExit("no rows")


def edit_first_construction_row(d, fn):
    p = rows_file(d)
    lines = open(p, encoding="utf-8").read().splitlines()
    for k, x in enumerate(lines):
        r = json.loads(x)
        if r.get("arms"):
            fn(r)
            lines[k] = json.dumps(r, sort_keys=True, default=list)
            break
    else:
        raise SystemExit("no construction row")
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def run_case(base, name, prepare):
    d = os.path.join(os.path.dirname(base), "guard_" + name)
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(base, d)
    rp = os.path.join(d, VF.RECEIPT)
    if os.path.exists(rp):
        os.remove(rp)
    prepare(d)
    CALLS.clear()
    MARKS.clear()
    try:
        SC.score(d)
        status = "returned"
    except HeldAccess:
        status = "solution function reached"
    except GT.GateRefused as e:
        status = "refused: " + str(e)
    except Exception as e:                                                     # noqa: BLE001
        status = "error: " + repr(e)[:300]
    return {"status": status, "refused": status.startswith("refused"), "marker_call_reached": bool(MARKS),
            "solution_calls": len(CALLS), "marker_exists": os.path.exists(GT.MARKER)}


INVENTED = {"verdict": "PASS", "go_sha256": "OLD_GO", "freeze_sha256": "OLD_FREEZE",
            "summary": {"AUTHORED": "previous rows"}}


def write_receipt(d, rec):
    with open(os.path.join(d, VF.RECEIPT), "w", encoding="utf-8") as f:
        json.dump(rec, f)


def p_sentinel_mutated(d):
    write_receipt(d, INVENTED)
    p = rows_file(d)
    r = json.loads(open(p, encoding="utf-8").read().splitlines()[0])
    r["task"] = "AUTHORED_CURRENT_MUTATED_ROW"
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(r, sort_keys=True, default=list) + "\n")


def p_sentinel_current(d):
    write_receipt(d, INVENTED)


def bump_cpu(r):
    k = sorted(r["arms"])[0]
    r["arms"][k]["cpu_s"] = r["arms"][k].get("cpu_s", 0) + 1.0


def p_stale(d):
    VF.verify(d)
    edit_first_construction_row(d, bump_cpu)


def p_copied(d):
    other = d + "_other"
    if os.path.exists(other):
        shutil.rmtree(other)
    shutil.copytree(d, other)
    edit_first_construction_row(other, bump_cpu)
    VF.verify(other)
    shutil.copy(os.path.join(other, VF.RECEIPT), os.path.join(d, VF.RECEIPT))


def break_inv1(r):
    h = r["arms"]["hand@20000"]
    h["fit"] = not h["fit"]


def p_forged(d):
    edit_first_construction_row(d, break_inv1)
    rec, _ = VF.run_checks(d)
    rec["verdict"] = "PASS"
    write_receipt(d, rec)


def p_missing(d):
    pass


def p_positive(d):
    VF.verify(d)


# ------------------------------------------------------------------ verification sentinels (amendment 2)
def first_construction(d):
    """(path, lines, index) of the first construction row in the held sets of copy d."""
    for st in ("1d_arc", "concept_arc", "mini_arc"):
        q = os.path.join(d, st)
        for fn in sorted(os.listdir(q)) if os.path.isdir(q) else []:
            if fn.startswith("rows."):
                path = os.path.join(q, fn)
                lines = open(path, encoding="utf-8").read().splitlines()
                for k, x in enumerate(lines):
                    if json.loads(x).get("arms"):
                        return path, lines, k
    raise SystemExit("no construction row")


def mutate(d, fn):
    path, lines, k = first_construction(d)
    r = json.loads(lines[k])
    fn(r)
    lines[k] = json.dumps(r, sort_keys=True, default=list)
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def to_base_fit(r):
    r["shared"] = "base_fit"
    r["arms"] = {}
    r["ref"].update(fit=True, stage="base", preds=r["ref"]["preds"] or [[[[1]]]], program=r["ref"]["program"] or "P",
                    retries=[], candidates=0, candidates_loo=0, op=None)


def to_under_two(r):
    r["shared"] = "under_two_demonstrations"
    r["arms"] = {}
    r["ref"].update(fit=False, stage="base", preds=None, program=None, retries=[], candidates=0, candidates_loo=0,
                    op=None)


def to_ref_error(r, value=None):
    r.pop("ref", None)
    r.pop("shared", None)
    r["arms"] = {}
    r["ref_error"] = value if value is not None else {"type": "RuntimeError", "message": "authored",
                                                        "traceback_tail": "authored"}


def first_failed_ref(r):
    return r["ref"]["stage"] == "base" and r["ref"]["fit"] is False


VERIFY_CASES = {
    # the companion's sentinels (formal review and early-branch sentinel)
    "stage_mutant_hand_20000": (lambda r: r["arms"]["hand@20000"].update(stage="AUTHORED_WRONG_STAGE"), False),
    "family_mutant": (lambda r: r.update(family="AUTHORED_WRONG_FAMILY"), False),
    "benchmark_mutant": (lambda r: r.update(bench="mini_arc" if r["bench"] != "mini_arc" else "concept_arc"), False),
    "base_fit_without_base_stage": (lambda r: (to_base_fit(r), r["ref"].update(stage="construction")), False),
    "base_fit_without_fit": (lambda r: (to_base_fit(r), r["ref"].update(fit=False)), False),
    "empty_ref_error": (lambda r: to_ref_error(r, ""), False),
    "false_ref_error": (lambda r: to_ref_error(r, False), False),
    "ref_error_plus_answer_and_arms": (lambda r: r.update(ref_error={"type": "RuntimeError", "message": "a",
                                                                       "traceback_tail": "a"}), False),
    "under_two_with_trusted_demonstrations": (to_under_two, False),
    "unknown_shared_branch": (lambda r: r.update(shared="AUTHORED_BYPASS"), False),
    # this study's own
    "reference_stage_mutant": (lambda r: r["ref"].update(stage="AUTHORED_WRONG_STAGE"), False),
    "arm_fit_without_construction_stage": (lambda r: r["arms"][sorted(r["arms"])[0]].update(stage="construction_none")
                                           if r["arms"][sorted(r["arms"])[0]]["fit"] else
                                           r["arms"][sorted(r["arms"])[0]].update(stage="construction"), False),
    "test_count_mutant": (lambda r: r.update(n_test=r["n_test"] + 1), False),
    "demonstration_count_mutant": (lambda r: r.update(n_demos=r.get("n_demos", 2) + 1), False),
    "string_ref_error_old_format": (lambda r: to_ref_error(r, "Traceback (most recent call last): authored"), False),
    "row_without_n_demos": (lambda r: r.pop("n_demos"), False),
    # positive controls: a consistent base_fit row and a consistent reference-error row are accepted
    "positive_base_fit_branch": (to_base_fit, True),
    "positive_reference_error_branch": (to_ref_error, True),
}


def verify_case(base, name, fn, valid):
    d = os.path.join(os.path.dirname(base), "vcase_" + name)
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(base, d)
    rp = os.path.join(d, VF.RECEIPT)
    if os.path.exists(rp):
        os.remove(rp)
    mutate(d, fn)
    rec, _ = VF.run_checks(d)
    out = {"verify_verdict": rec["verdict"], "failures": [f.get("check") for f in rec["failures"]][:5]}
    # the scorer boundary with a forged receipt that claims PASS with every current digest
    forged = dict(rec, verdict="PASS")
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(forged, f)
    CALLS.clear()
    MARKS.clear()
    try:
        SC.score(d)
        status = "returned"
    except HeldAccess:
        status = "solution function reached"
    except GT.GateRefused as e:
        status = "refused: " + str(e)
    except Exception as e:                                                     # noqa: BLE001
        status = "error: " + repr(e)[:300]
    out.update(score_status=status, marker_call_reached=bool(MARKS), solution_calls=len(CALLS),
               marker_exists=os.path.exists(GT.MARKER))
    if valid:
        out["ok"] = (rec["verdict"] == "PASS" and out["marker_call_reached"] and
                     "rehearsal mode never scores" in status and not CALLS and not out["marker_exists"])
    else:
        out["ok"] = (rec["verdict"] == "INVALID" and status.startswith("refused") and not MARKS and not CALLS and
                     not out["marker_exists"])
    return out


# ------------------------------------------------------------------ kernel receipts (amendment 2 section 3)
def fake_kernel_tree(root, row_files, go, freeze, protocol):
    """A consistent invented tree of kernel receipts under root (a scratch study folder)."""
    import hashlib
    from gcon import kaggle_build as KB

    def put(rel, obj):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        data = obj if isinstance(obj, bytes) else json.dumps(obj, indent=1, sort_keys=True).encode()
        with open(p, "wb") as f:
            f.write(data)
        return hashlib.sha256(data).hexdigest()
    man = {"mode": "final", "archive_sha256": "x", "files_sha256": {
        f"{KB.STUDY_REL}/runs/GO": go, f"{KB.STUDY_REL}/FREEZE.json": freeze, f"{KB.STUDY_REL}/PROTOCOL.md": protocol},
        "kernels": {}}
    for k, (slug, sets) in KB.KERNELS.items():
        kid = f"{KB.OWNER}/cora-guided-construction-{slug}"
        meta = {"id": kid, "is_private": True, "enable_internet": False, "enable_gpu": False, "enable_tpu": False}
        msha = put(f"runs/kaggle/{k}/kernel-metadata.json", meta)
        nsha = put(f"runs/kaggle/{k}/notebook.ipynb", b"authored notebook " + k.encode())
        put(f"runs/kaggle/{k}/PUSHED.json", {"kernel": kid, "notebook_sha256": nsha, "return_code": 0})
        asha = put(f"runs/kaggle_out/{k}/T/{k}_outputs.tar.gz", b"authored archive " + k.encode())
        krsha = put(f"runs/held_run/{k}_meta/kernel_run.json", {"sets": {s: {"return_codes": [0, 0, 0, 0],
                                                                             "stopped_at_limit": False} for s in sets},
                                                                "rehearsal": False})
        files = {p: h for p, h in row_files.items() if p.split("/")[0] in sets}
        files["kernel_run.json"] = krsha
        put(f"runs/held_run/{k}_meta/KAGGLE_FETCH.json", {"kernel": kid, "sets": list(sets), "archive_sha256": asha,
                                                          "archive": f"runs/kaggle_out/{k}/T/{k}_outputs.tar.gz",
                                                          "files_sha256": files})
        man["kernels"][k] = {"id": kid, "sets": list(sets), "notebook_sha256": nsha, "metadata_sha256": msha}
    put("runs/kaggle/PACKAGE_MANIFEST_final.json", man)


def kernel_cases(scratch_study):
    import hashlib
    row_files = {f"{s}/rows.0.jsonl": hashlib.sha256(s.encode()).hexdigest() for s in VF.SETS}
    go, freeze, protocol = "a" * 64, "b" * 64, "c" * 64

    def run(mut=None):
        root = os.path.join(scratch_study, "runs", "kcase")
        if os.path.exists(root):
            shutil.rmtree(root)
        fake_kernel_tree(root, row_files, go, freeze, protocol)
        rf = dict(row_files)
        if mut:
            res = mut(root, rf)
            if isinstance(res, dict):
                rf = res
        fails, bound = VF.kernel_receipts(root, os.path.join(root, "runs", "held_run"), rf, go, freeze, protocol)
        return {"failures": len(fails), "first": [f.get("problem") or f.get("missing") for f in fails][:3],
                "bound_files": len(bound)}

    def jedit(root, rel, fn, resign_meta=None):
        p = os.path.join(root, rel)
        d = json.load(open(p))
        fn(d)
        data = json.dumps(d, indent=1, sort_keys=True).encode()
        open(p, "wb").write(data)
        if resign_meta:
            mp = os.path.join(root, "runs/kaggle/PACKAGE_MANIFEST_final.json")
            m = json.load(open(mp))
            m["kernels"][resign_meta]["metadata_sha256"] = hashlib.sha256(data).hexdigest()
            open(mp, "wb").write(json.dumps(m, indent=1, sort_keys=True).encode())

    def rm(root, rel):
        os.remove(os.path.join(root, rel))
    cases = {
        "valid_receipts": (None, True),
        "no_receipts_at_all": (lambda root, rf: shutil.rmtree(os.path.join(root, "runs")), False),
        "missing_one_kernel": (lambda root, rf: jedit(root, "runs/kaggle/PACKAGE_MANIFEST_final.json",
                                                      lambda m: m["kernels"].pop("GC1D")), False),
        "kernel_role_substitution": (lambda root, rf: jedit(root, "runs/kaggle/PACKAGE_MANIFEST_final.json",
                                                            lambda m: m["kernels"]["GC1D"].update(sets=["arc2"])), False),
        "kernel_internet_on": (lambda root, rf: jedit(root, "runs/kaggle/GC1D/kernel-metadata.json",
                                                      lambda m: m.update(enable_internet=True), "GC1D"), False),
        "kernel_not_private": (lambda root, rf: jedit(root, "runs/kaggle/GC1D/kernel-metadata.json",
                                                      lambda m: m.update(is_private=False), "GC1D"), False),
        "kernel_gpu_on": (lambda root, rf: jedit(root, "runs/kaggle/GC1D/kernel-metadata.json",
                                                 lambda m: m.update(enable_gpu=True), "GC1D"), False),
        "metadata_changed_after_manifest": (lambda root, rf: jedit(root, "runs/kaggle/GCCM/kernel-metadata.json",
                                                                   lambda m: m.update(title="x")), False),
        "push_failed": (lambda root, rf: jedit(root, "runs/kaggle/GCARC2/PUSHED.json",
                                               lambda m: m.update(return_code=1)), False),
        "push_receipt_missing": (lambda root, rf: rm(root, "runs/kaggle/GC1D/PUSHED.json"), False),
        "fetch_receipt_missing": (lambda root, rf: rm(root, "runs/held_run/GCCM_meta/KAGGLE_FETCH.json"), False),
        "row_file_not_returned_by_kernel": (lambda root, rf: dict(rf, **{"1d_arc/rows.0.jsonl": "0" * 64}), False),
        "extra_row_file": (lambda root, rf: dict(rf, **{"mini_arc/rows.9.jsonl": "1" * 64}), False),
        "archive_changed": (lambda root, rf: open(os.path.join(root, "runs/kaggle_out/GC1D/T/GC1D_outputs.tar.gz"),
                                                  "ab").write(b"x"), False),
        "package_go_differs": (lambda root, rf: jedit(root, "runs/kaggle/PACKAGE_MANIFEST_final.json",
                                                      lambda m: m["files_sha256"].update(
                                                          {[k for k in m["files_sha256"] if k.endswith("runs/GO")][0]:
                                                           "0" * 64})), False),
        "worker_failed": (lambda root, rf: jedit(root, "runs/held_run/GCARC2_meta/kernel_run.json",
                                                 lambda m: m["sets"]["arc2"].update(return_codes=[0, 1, 0, 0])), False),
        "rehearsal_kernel_record": (lambda root, rf: jedit(root, "runs/held_run/GC1D_meta/kernel_run.json",
                                                           lambda m: m.update(rehearsal=True)), False),
        # amendment 3: the driver record's bytes are bound to its returned-file digest
        "kernel_run_edited_stale_digest": (lambda root, rf: jedit(root, "runs/held_run/GCCM_meta/kernel_run.json",
                                                                  lambda m: m.update(note="edited after return")),
                                           False),
        "kernel_run_entry_missing": (lambda root, rf: jedit(root, "runs/held_run/GC1D_meta/KAGGLE_FETCH.json",
                                                            lambda m: m["files_sha256"].pop("kernel_run.json")), False),
    }
    out = {}
    for name, (mut, valid) in cases.items():
        res = run(mut)
        res["ok"] = (res["failures"] == 0) if valid else (res["failures"] > 0)
        out[name] = res
    return out


# ------------------------------------------------------------------ donor comparison total (amendment 3 section 3)
def donor_total_case(base):
    """The scorer, fed fake outputs, reports the donor comparison total: on a copy with two rows' donor comparison
    counts set to known values and a fresh receipt, the solution functions return blank outputs and the marker is a
    scratch file, so the scoring runs to the end; RESULTS.json must report the sum over the held rows with its
    cache-delta scope label."""
    d = os.path.join(os.path.dirname(base), "donor_total")
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(base, d)
    rp = os.path.join(d, VF.RECEIPT)
    if os.path.exists(rp):
        os.remove(rp)
    k = 0
    for st in ("1d_arc", "concept_arc", "mini_arc"):
        q = os.path.join(d, st)
        for fn in sorted(os.listdir(q)) if os.path.isdir(q) else []:
            if fn.startswith("rows."):
                path = os.path.join(q, fn)
                lines = open(path, encoding="utf-8").read().splitlines()
                for i, x in enumerate(lines):
                    r = json.loads(x)
                    if r.get("arms") and k < 2:
                        r["donor_feature_comparisons"] = (7, 11)[k]
                        k += 1
                        lines[i] = json.dumps(r, sort_keys=True, default=list)
                open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    held = [r for st in ("1d_arc", "concept_arc", "mini_arc") for r in VF.load_rows(d, st)]
    want = sum(r.get("donor_feature_comparisons", 0) for r in held)
    VF.verify(d)

    def blank(rows):
        return {r["task"]: [((0,),)] * r["n_test"] for r in rows}
    saved = (SC.held_solutions, SC.arc2_solutions, GT.take_marker)
    SC.held_solutions = lambda bench, ids: {t: v for t, v in blank(VF.load_rows(d, bench)).items() if t in ids}
    SC.arc2_solutions = lambda: blank(VF.load_rows(d, "arc2"))
    GT.take_marker = lambda: os.open(os.path.join(d, "SCRATCH_MARKER"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        res = SC.score(d)
        got = res["work"]["held"]["shared_and_feature_work"]
        out = {"status": "scored with fake outputs", "want": want, "got": got.get("donor_feature_comparisons"),
               "scope_label": (got.get("scope") or {}).get("donor_feature_comparisons"),
               "real_marker_exists": os.path.exists(GT.MARKER)}
    except Exception as e:                                                     # noqa: BLE001
        out = {"status": "error: " + repr(e)[:300], "want": want, "got": None, "scope_label": None,
               "real_marker_exists": os.path.exists(GT.MARKER)}
    finally:
        SC.held_solutions, SC.arc2_solutions, GT.take_marker = saved
    out["ok"] = (out["got"] == want and want >= 18 and bool(out["scope_label"]) and "cache delta" in out["scope_label"]
                 and not out["real_marker_exists"])
    return out


def main(run_dir):
    if not GT.REHEARSAL:
        raise SystemExit("rehearsal mode only")
    run_dir = os.path.abspath(run_dir)
    cases = {"sentinel_mutated_rows": p_sentinel_mutated, "sentinel_current_rows": p_sentinel_current,
             "stale_receipt": p_stale, "copied_receipt": p_copied, "forged_receipt": p_forged,
             "missing_receipt": p_missing, "positive_control": p_positive}
    res = {name: run_case(run_dir, name, prep) for name, prep in cases.items()}
    neg = [k for k in res if k != "positive_control"]
    ok = all(res[k]["refused"] and not res[k]["marker_call_reached"] and res[k]["solution_calls"] == 0 and
             not res[k]["marker_exists"] for k in neg)
    pc = res["positive_control"]
    ok = ok and pc["refused"] and pc["marker_call_reached"] and "rehearsal mode never scores" in pc["status"] and \
        pc["solution_calls"] == 0 and not pc["marker_exists"]
    vres = {name: verify_case(run_dir, name, fn, valid) for name, (fn, valid) in VERIFY_CASES.items()}
    kres = kernel_cases(os.path.dirname(os.path.dirname(run_dir)))
    dres = donor_total_case(run_dir)
    ok_v = all(v["ok"] for v in vres.values())
    ok_k = all(v["ok"] for v in kres.values())
    print(json.dumps({"passed": ok and ok_v and ok_k and dres["ok"], "scorer_boundary_passed": ok,
                      "verify_sentinels_passed": ok_v, "kernel_receipt_cases_passed": ok_k,
                      "donor_total_case_passed": dres["ok"], "cases": res, "verify_cases": vres,
                      "kernel_cases": kres, "donor_total_case": dres}, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1])
