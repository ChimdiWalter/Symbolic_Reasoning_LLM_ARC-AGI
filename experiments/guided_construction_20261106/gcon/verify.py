"""Checks of the held run before any solution opens (PROTOCOL.md section 8; PROTOCOL_AMENDMENT_1.md section 1;
PROTOCOL_AMENDMENT_2.md sections 1 to 4). Behind the GO; reads the returned rows, the trusted task identities and the
kernel receipts only (no test output).

    python -s -B run.py verify RUN_DIR            -> RUN_DIR/INVARIANTS.json (PASS or INVALID, with every failure)

The rows are read as bytes once (`read_rows`) and checked as parsed from those bytes (`check`). The receipt binds the
verdict to the digest of every row file, to the trusted identities (`identities`), to the kernel receipts' exact
bytes (`kernel_receipts`, held run only), to the GO's, the freeze's, the protocol's and the configuration's digests
and to the mode. The scorer runs the same checks again on the exact bytes it scores and refuses unless the receipt
binds to them (score.py).

Trusted identities: for every expected task, its benchmark, family, number of demonstrations and number of test
inputs, from the task data behind the GO (the split and the benchmark files whose digests the freeze pins; the
ARC-AGI-2 challenges with their pinned digest); never from a row.

Every row must be exactly one permitted branch, with its evidence:
  reference error   ref_error = {type: a non-empty string, message, traceback_tail}; no ref, no shared, no arms
  base_fit          shared "base_fit"; the reference fitted at the base stage (fit true, stage "base", attempts
                    present) without construction (no retry, no candidate, no constructed operation); no arms
  under two demos   shared "under_two_demonstrations"; the trusted count is below 2; the reference did not fit
                    (fit false, stage "base", no retry, no candidate); no arms
  construction      no shared, no ref_error; at least 2 trusted demonstrations; the reference either failed (fit
                    false, stage "base") or fitted by construction (fit true, stage "construction", an operation);
                    every arm of the configuration present, none an error, each with stage "construction" exactly
                    when it fits (then with an operation and attempts) and "construction_none" otherwise, at most 3
                    retries, one hole record per hole
Then, on the construction rows:
1. the hand-set order through the test's code at 20,000 equals the reference `objgrow.arm.construction_answers(task,
   ops=())`: fit, stage, attempts, program, constructed operation, retried candidates (identifier, fit, hole rank, in
   order) and the candidate counts;
2. the guided and hand-set orders are identical at 20,000 on every task with no capped hole: the same answer and,
   per hole, the same candidate list.
And for every row: the task, benchmark, family, demonstration count and test-input count of the trusted identity,
the frozen digest and the GO's digest. A row must carry its own demonstration count (n_demos, an integer equal to the
trusted count); the trusted count alone decides a branch's eligibility (PROTOCOL_AMENDMENT_3.md section 1). In a held
run, the kernel receipts (`kernel_receipts`) must be complete.
"""
import hashlib
import json
import os

from gcon import env as E, gate as GT

SETS = ("1d_arc", "concept_arc", "mini_arc", "arc2")
FULL = 20000
CONFIG = os.path.join(E.STUDY, "config", "CONFIG.json")
RECEIPT = "INVARIANTS.json"
SHARED = ("base_fit", "under_two_demonstrations")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def joint(d):
    """Digest over a {name: sha256} map, in sorted order."""
    return sha_bytes("".join(f"{p} {h}\n" for p, h in sorted(d.items())).encode())


def read_rows(run_dir):
    """({set: [rows]}, {relative path: sha256}, joint digest). Each row file is read once, as bytes, and parsed from
    those bytes."""
    rows, files = {}, {}
    for s in SETS:
        d = os.path.join(run_dir, s)
        rows[s] = []
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.startswith("rows.") and fn.endswith(".jsonl"):
                with open(os.path.join(d, fn), "rb") as f:
                    raw = f.read()
                files[f"{s}/{fn}"] = sha_bytes(raw)
                rows[s] += [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
    return rows, files, joint(files)


def load_rows(run_dir, s):
    return read_rows(run_dir)[0][s]


def identities():
    """{set: {task id: {task, bench, family, n_demos, n_test}}} from the trusted task data (behind the GO; in
    rehearsal mode the source stand-ins)."""
    from gcon import held as HL
    out = {}
    for s in SETS:
        rows, tasks = HL.task_list(s)
        out[s] = {t: {"task": t, "bench": b, "family": f, "n_demos": len(tasks[t]["train"]),
                      "n_test": len(tasks[t]["test_inputs"])} for b, f, t in rows}
    return out


def identity_digest(ids):
    return sha_bytes(json.dumps(ids, sort_keys=True, separators=(",", ":")).encode())


def ref_view(ref):
    op = ref.get("op")
    st = ref.get("stage")
    return {"fit": ref["fit"], "stage": {"construction": "construction", "base": "no_fit"}.get(st, f"unknown:{st}"),
            "preds": ref["preds"], "program": ref["program"],
            "op": op["sid"] if isinstance(op, dict) else op,
            "retries": [[r["sid"], bool(r["fit"]), r["hole_rank"]] for r in ref.get("retries") or []],
            "candidates": ref.get("candidates", 0), "candidates_loo": ref.get("candidates_loo", 0)}


def arm_view(a):
    st = a.get("stage")
    return {"fit": a["fit"], "stage": {"construction": "construction", "construction_none": "no_fit"}.get(
                st, f"unknown:{st}"),
            "preds": a["preds"], "program": a["program"], "op": a.get("op"),
            "retries": [[r["sid"], bool(r["fit"]), r["hole_rank"]] for r in a.get("retries") or []],
            "candidates": a.get("candidates", 0), "candidates_loo": a.get("candidates_loo", 0)}


def norm(x):
    return json.loads(json.dumps(x, sort_keys=True, default=list))


def _no_construction(ref):
    return (not ref.get("retries")) and ref.get("candidates", 0) == 0 and ref.get("candidates_loo", 0) == 0 and \
        ref.get("op") is None


def branch_problems(r, ident, arm_keys):
    """[] when the row is exactly one permitted branch with its evidence; otherwise the problems."""
    p = []
    has_err, shared, ref, arms = "ref_error" in r, r.get("shared"), r.get("ref"), r.get("arms") or {}
    if has_err:
        e = r["ref_error"]
        if not (isinstance(e, dict) and isinstance(e.get("type"), str) and e["type"].strip() and
                isinstance(e.get("message"), str) and isinstance(e.get("traceback_tail"), str)):
            p.append("reference error without its evidence")
        if ref is not None or shared is not None or arms:
            p.append("reference error together with an answer, a shared stage or arms")
        return p
    if not isinstance(ref, dict):
        return ["no reference answer"]
    if shared is not None:
        if shared not in SHARED:
            return [f"unknown shared stage {shared!r}"]
        if arms:
            p.append("shared stage with arms")
        if shared == "base_fit":
            if not (ref.get("fit") is True and ref.get("stage") == "base" and ref.get("preds")):
                p.append("base_fit without a base-stage fit")
            if not _no_construction(ref):
                p.append("base_fit with construction evidence")
        else:
            if ident["n_demos"] >= 2:
                p.append("under_two_demonstrations with two or more trusted demonstrations")
            if not (ref.get("fit") is False and ref.get("stage") == "base" and _no_construction(ref)):
                p.append("under_two_demonstrations with a fit or construction evidence")
        return p
    # construction
    if ident["n_demos"] < 2:
        p.append("construction with fewer than two trusted demonstrations")
    ok_ref = ((ref.get("fit") is False and ref.get("stage") == "base") or
              (ref.get("fit") is True and ref.get("stage") == "construction" and isinstance(ref.get("op"), dict)))
    if not ok_ref:
        p.append("reference neither a failed construction nor a construction fit")
    if sorted(arms) != sorted(arm_keys):
        p.append("arms present differ from the configuration")
        return p
    nh = r.get("n_holes")
    for k, a in sorted(arms.items()):
        if "error" in a:
            p.append(f"arm error {k}")
            continue
        fit, st = a.get("fit"), a.get("stage")
        if fit is True:
            if st != "construction" or not a.get("op") or not a.get("preds"):
                p.append(f"{k}: a fit without stage construction, operation and attempts")
        elif fit is False:
            if st != "construction_none" or a.get("op") is not None or a.get("preds") is not None:
                p.append(f"{k}: no fit, but stage or answer present")
        else:
            p.append(f"{k}: fit is not a boolean")
        if len(a.get("retries") or []) > 3:
            p.append(f"{k}: more than 3 retries")
        if not isinstance(a.get("holes"), list) or (nh is not None and len(a["holes"]) != nh):
            p.append(f"{k}: hole records differ from the task's holes")
    return p


def kernel_receipts(study, run_dir, row_files, go_sha, freeze_sha, protocol_sha):
    """Held run only. ([failures], {bound path: sha256}): the final manifest names exactly the three expected kernels
    with their identities and sets and carries the current GO, freeze and protocol; per kernel, its metadata (private,
    CPU only, no TPU, internet off), notebook, push receipt (return code 0), fetch receipt (its sets, the archive's
    digest, every fetched file's digest), the archive's bytes and the kernel driver's record (every worker returned
    0, none stopped at the limit, and its bytes equal the returned kernel_run.json's digest in the fetch receipt:
    PROTOCOL_AMENDMENT_3.md section 2); every row file of a set is one the set's kernel returned, byte for byte, and
    every row file it returned is present."""
    from gcon import kaggle_build as KB
    fails, bound = [], {}
    kdir = os.path.join(study, "runs", "kaggle")

    def take(path):
        if not os.path.exists(path):
            fails.append({"check": "kernel receipts", "missing": os.path.relpath(path, study)})
            return None
        with open(path, "rb") as f:
            raw = f.read()
        bound[os.path.relpath(path, study)] = sha_bytes(raw)
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return raw
    man = take(os.path.join(kdir, "PACKAGE_MANIFEST_final.json"))
    if not isinstance(man, dict):
        return fails or [{"check": "kernel receipts", "problem": "no final manifest"}], bound
    if man.get("mode") != "final":
        fails.append({"check": "kernel receipts", "problem": "manifest is not the final one"})
    mf = man.get("files_sha256") or {}
    for name, want in (("runs/GO", go_sha), ("FREEZE.json", freeze_sha), ("PROTOCOL.md", protocol_sha)):
        if mf.get(f"{KB.STUDY_REL}/{name}") != want:
            fails.append({"check": "kernel receipts", "problem": f"the package's {name} is not the current one"})
    want = {k: (f"{KB.OWNER}/cora-guided-construction-{slug}", list(sets)) for k, (slug, sets) in KB.KERNELS.items()}
    if sorted((man.get("kernels") or {})) != sorted(want):
        fails.append({"check": "kernel receipts", "problem": "the manifest's kernels are not the expected three"})
    owner = {}
    for k, (kid, sets) in sorted(want.items()):
        m = (man.get("kernels") or {}).get(k)
        if not m or m.get("id") != kid or m.get("sets") != sets:
            fails.append({"check": "kernel receipts", "kernel": k, "problem": "identity or sets differ"})
            continue
        for s in sets:
            owner[s] = k
        meta = take(os.path.join(kdir, k, "kernel-metadata.json"))
        if bound.get(f"runs/kaggle/{k}/kernel-metadata.json") != m.get("metadata_sha256"):
            fails.append({"check": "kernel receipts", "kernel": k, "problem": "metadata digest"})
        if not (isinstance(meta, dict) and meta.get("id") == kid and meta.get("is_private") is True and
                meta.get("enable_internet") is False and meta.get("enable_gpu") is False and
                meta.get("enable_tpu") is False):
            fails.append({"check": "kernel receipts", "kernel": k, "problem": "metadata: private, CPU only, "
                                                                              "internet off"})
        take(os.path.join(kdir, k, "notebook.ipynb"))
        if bound.get(f"runs/kaggle/{k}/notebook.ipynb") != m.get("notebook_sha256"):
            fails.append({"check": "kernel receipts", "kernel": k, "problem": "notebook digest"})
        push = take(os.path.join(kdir, k, "PUSHED.json"))
        if not (isinstance(push, dict) and push.get("kernel") == kid and push.get("return_code") == 0 and
                push.get("notebook_sha256") == m.get("notebook_sha256")):
            fails.append({"check": "kernel receipts", "kernel": k, "problem": "push receipt"})
        fetch = take(os.path.join(run_dir, k + "_meta", "KAGGLE_FETCH.json"))
        if not (isinstance(fetch, dict) and fetch.get("kernel") == kid and fetch.get("sets") == sets and
                isinstance(fetch.get("files_sha256"), dict) and fetch.get("archive")):
            fails.append({"check": "kernel receipts", "kernel": k, "problem": "fetch receipt"})
            continue
        take(os.path.join(study, fetch["archive"]))
        if bound.get(os.path.relpath(os.path.join(study, fetch["archive"]), study)) != fetch.get("archive_sha256"):
            fails.append({"check": "kernel receipts", "kernel": k, "problem": "archive digest"})
        kr_path = os.path.join(run_dir, k + "_meta", "kernel_run.json")
        kr = take(kr_path)
        kr_sha = bound.get(os.path.relpath(kr_path, study))
        if kr_sha is None or fetch["files_sha256"].get("kernel_run.json") != kr_sha:
            fails.append({"check": "kernel receipts", "kernel": k,
                          "problem": "kernel driver record differs from the returned file (fetch digest)"})
        if not (isinstance(kr, dict) and sorted((kr.get("sets") or {})) == sorted(sets) and
                all(v.get("return_codes") and all(c == 0 for c in v["return_codes"]) and not v.get("stopped_at_limit")
                    for v in kr["sets"].values()) and not kr.get("rehearsal")):
            fails.append({"check": "kernel receipts", "kernel": k, "problem": "kernel driver record"})
        got = {p: h for p, h in fetch["files_sha256"].items() if p.split("/")[0] in sets and
               p.split("/")[-1].startswith("rows.") and p.endswith(".jsonl")}
        have = {p: h for p, h in row_files.items() if p.split("/")[0] in sets}
        if got != have:
            fails.append({"check": "kernel receipts", "kernel": k, "problem": "row files differ from the returned ones"})
    if sorted(owner) != sorted(SETS):
        fails.append({"check": "kernel receipts", "problem": "a set has no kernel"})
    return fails, bound


def check(rows_by_set, arms_by_set, go_sha, freeze_sha, ids):
    """The row checks; returns (failures, summary)."""
    fails, summary = [], {}
    for s in SETS:
        rows = rows_by_set.get(s, [])
        exp = ids[s]
        idl = [r.get("task") for r in rows]
        if sorted(map(str, idl)) != sorted(exp):
            missing = sorted(set(exp) - set(map(str, idl)))
            dup = sorted({t for t in idl if idl.count(t) > 1}, key=str)
            extra = sorted(set(map(str, idl)) - set(exp))
            fails.append({"set": s, "check": "rows", "missing": missing[:20], "n_missing": len(missing),
                          "duplicates": dup[:20], "extra": extra[:20]})
        want = [f"{a}@{b}" for a, b in arms_by_set[s]]
        counts = {"construction": 0, "base_fit": 0, "under_two_demonstrations": 0, "reference_error": 0}
        inv1 = inv2 = inv2_skipped = 0
        for r in rows:
            t = r.get("task")
            ident = exp.get(t)
            if ident is None:
                continue
            if "n_demos" not in r or type(r["n_demos"]) is not int:
                fails.append({"set": s, "task": t, "check": "row without its demonstration count (n_demos)"})
            elif (r.get("bench"), r.get("family")) != (ident["bench"], ident["family"]) or \
                    r.get("n_test") != ident["n_test"] or r["n_demos"] != ident["n_demos"]:
                fails.append({"set": s, "task": t, "check": "identity (benchmark, family, demonstrations, tests)"})
            if r.get("go_sha256") != go_sha or r.get("freeze_sha256") != freeze_sha:
                fails.append({"set": s, "task": t, "check": "digests"})
            probs = branch_problems(r, ident, want)
            if probs:
                fails.append({"set": s, "task": t, "check": "branch", "problems": probs})
                continue
            if "ref_error" in r:
                counts["reference_error"] += 1
                continue
            if r.get("shared"):
                counts[r["shared"]] += 1
                continue
            counts["construction"] += 1
            arms = r["arms"]
            h = arms[f"hand@{FULL}"]
            if norm(arm_view(h)) != norm(ref_view(r["ref"])):
                fails.append({"set": s, "task": t, "check": "invariant 1"})
            else:
                inv1 += 1
            g = arms[f"guide@{FULL}"]
            if any(x["capped"] for x in h["holes"]) or any(x["capped"] for x in g["holes"]):
                inv2_skipped += 1
                continue
            same = (norm(arm_view(g)) == norm(arm_view(h)) and
                    [x["top"] for x in g["holes"]] == [x["top"] for x in h["holes"]])
            if not same:
                fails.append({"set": s, "task": t, "check": "invariant 2"})
            else:
                inv2 += 1
        summary[s] = dict(counts, rows=len(rows), expected=len(exp), invariant_1_equal=inv1, invariant_2_equal=inv2,
                          invariant_2_capped_tasks=inv2_skipped)
    return fails, summary


def context():
    """The digests a receipt binds to, computed now (behind the GO)."""
    go_sha = GT.require_go()
    return {"go_sha256": go_sha, "freeze_sha256": E.sha_file(GT.FREEZE), "protocol_sha256": E.sha_file(GT.PROTOCOL),
            "config_sha256": E.sha_file(CONFIG), "mode": "rehearsal" if GT.REHEARSAL else "held_run"}


def arms_by_set():
    c = E.load(CONFIG)
    return {s: [tuple(a) for a in (c["arms_arc2"] if s == "arc2" else c["arms_held"])] for s in SETS}


def run_checks(run_dir):
    """(receipt fields, parsed rows): every check on the exact bytes now in RUN_DIR."""
    ctx = context()
    rows, files, digest = read_rows(run_dir)
    ids = identities()
    fails, summary = check(rows, arms_by_set(), ctx["go_sha256"], ctx["freeze_sha256"], ids)
    if GT.REHEARSAL:
        kfails, kbound, kstate = [], {}, "not checked in rehearsal mode (rehearsal never scores)"
    else:
        kfails, kbound = kernel_receipts(E.STUDY, run_dir, files, ctx["go_sha256"], ctx["freeze_sha256"],
                                         ctx["protocol_sha256"])
        kstate = "checked"
    fails += kfails
    rec = dict(ctx, verdict="PASS" if not fails else "INVALID", failures=fails[:200], n_failures=len(fails),
               summary=summary, rows_sha256=digest, row_files=files, identity_sha256=identity_digest(ids),
               kernel_receipts=kbound, kernel_receipts_sha256=joint(kbound), kernel_receipts_state=kstate)
    return rec, rows


def verify(run_dir):
    rec, _ = run_checks(run_dir)
    E.dump(os.path.join(run_dir, RECEIPT), rec, indent=1)
    print(json.dumps({"verdict": rec["verdict"], "n_failures": rec["n_failures"], "summary": rec["summary"],
                      "rows_sha256": rec["rows_sha256"], "kernel_receipts": rec["kernel_receipts_state"]}))
    return rec


def main(run_dir):
    return verify(os.path.abspath(run_dir))
