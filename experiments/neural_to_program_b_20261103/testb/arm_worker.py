"""One Test B arm (PROTOCOL.md section 4), run as the per-arm guard's child under RLIMIT_CPU.

    python -I arm_worker.py INPUT.json RESULT.json PROGRESS.json

No process or thread can be created by this worker. Before anything else runs (and before the construction code is
imported), RLIMIT_NPROC is set to 0 for both its soft and hard limits, so the kernel refuses every fork, vfork,
clone, posix_spawn and thread creation (subprocess, os.fork, os.system, multiprocessing, ctypes calls into libc);
the limit cannot be raised again. The per-arm guard sets the same limit in the child before exec, and an audit hook
refuses the process-creation events with a clear error. The worker is therefore the arm's only process, and the
guard's RLIMIT_CPU of 100 CPU-s bounds all of the arm's compute (protocol section 5, child-inclusive).

The answer guard is installed before anything is read. Every function of the construction code is called unchanged:
lang0.build_g0([]), search.run, controller.sketches, s1.spec_candidates(schema.seeded_order(0), holes), and for up
to s1.M_RETRIES hole-matching operations a fresh build_g0([]) plus the operation, added exactly as the construction
test's retry step adds it (lang0.add_production with s1.Gates.fn), then search.run at the base budget. Every search
runs with track_partial=True, so the arm's closest right-shaped program is the best one over all of its searches
(most correct cells; the earliest search on a tie). After each search the progress is written atomically, so an arm
stopped by its guard keeps the searches it finished.
"""
import os
import resource

for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "1"                      # one BLAS thread, set before any library is loaded
resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))

import signal                                 # noqa: E402
import sys                                    # noqa: E402
import time                                   # noqa: E402

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import common as C              # noqa: E402
from testb import labels as LB             # noqa: E402

C.deny_process_creation()
C.install_answer_guard([p for p in os.environ.get("TESTB_BLOCKED", "").split(os.pathsep) if p])
signal.signal(signal.SIGXCPU, signal.SIG_DFL)
CGROW = os.path.join(C.REPO, "experiments", "capability_growth_20261027")


def _grid(g):
    return [list(r) for r in g]


def _search_record(name, r):
    part = r.get("partial")
    return {"search": name, "fit": bool(r["fit"]), "program": r["program"], "stop": r["stop"],
            "stop_reason": LB.STOP_REASON.get(r["stop"], r["stop"]), "level_complete": r["level_complete"],
            "calls": r["calls"], "closures": r["closures"], "closure_capped": bool(r["closure_capped"]),
            "cpu_s": r["cpu_s"],
            "closest": {"program": part["program"], "cells_correct": part["cells_correct"]} if part else None}


def run_arm(spec, progress_path):
    sys.path.insert(0, CGROW)
    from cgrow import paths as P
    P.ensure_import_paths()
    from cgrow import controller as CT, lang0 as L0, schema as SG, search as S, s1
    from a2 import arcdsl as D

    t0 = time.process_time()
    x = D.to_grid(spec["x"])
    pairs = [(D.to_grid(a), D.to_grid(b)) for a, b in spec["demos"]]
    if spec["target"] is not None:
        pairs.append((x, D.to_grid(spec["target"])))
    cells = sum(len(b) * len(b[0]) for _, b in pairs)
    rec = {"arm": spec["arm"], "target_arm": spec["target"] is not None, "searches": [], "holes": None,
           "n_hole_matching_operations": None, "tried_operations": [], "shape_relation": CT.shape_relation(pairs),
           "cells_total": cells, "process_creation": {"rlimit_nproc": list(resource.getrlimit(resource.RLIMIT_NPROC))}}

    def progress():
        C.write_json_atomic(progress_path, {"arm": spec["arm"], "searches": rec["searches"], "cells_total": cells})

    g = L0.build_g0([])
    base = S.run(g, pairs, [x], track_partial=True)
    rec["searches"].append(_search_record("base", base))
    progress()
    fit, level = (base, "base grammar") if base["fit"] else (None, None)
    if fit is None:
        ranked, _inv = CT.sketches(pairs, g)
        rec["holes"] = [{"form": c["form"], "outer": c["outer"], "inner": c["inner"], "score": c["score"]}
                        for c in ranked]
        cands = s1.spec_candidates(SG.seeded_order(0), ranked)
        rec["n_hole_matching_operations"] = len(cands)
        by_sid = SG.by_sid()
        for c in cands[:s1.M_RETRIES]:
            st = by_sid[c["sid"]]
            head = "f:sig_" + c["sid"].replace(":", "_")
            g1 = L0.build_g0([])
            L0.add_production(g1, head, s1.Gates.fn(None, st), 1 if st.param else 0)
            r = S.run(g1, pairs, [x], track_partial=True)
            rec["tried_operations"].append({"sid": c["sid"], "head": head, "sketch_rank": c["sketch_rank"],
                                            "sketch_form": c["sketch_form"]})
            rec["searches"].append(_search_record("retry " + c["sid"], r))
            progress()
            if r["fit"]:
                fit, level = r, "base grammar + " + head
                break
    rec["closest"] = LB.closest_of(rec["searches"], cells)
    if fit is not None:
        pred = _grid(fit["preds"][0][0])
        rec.update(fit=True, program=fit["program"], level=level, prediction=pred,
                   outcome="VERIFIED" if spec["target"] is not None else "REACHABLE")
        if spec["target"] is not None:
            rec["prediction_equals_target"] = pred == spec["target"]
    else:
        rec.update(fit=False, program=None, level=None, prediction=None, outcome=LB.NO_FIT,
                   no_fit_flags=LB.no_fit_flags(rec["searches"]))
    rec["procedure_cpu_s"] = round(time.process_time() - t0, 3)   # after imports; the receipt covers all
    return rec


def main():
    inp, out, prog = sys.argv[1:4]
    spec = C.load_json(inp)
    rec = run_arm(spec, prog)
    rec["input_sha256"] = C.sha_file(inp)
    C.write_json_atomic(out, rec)


if __name__ == "__main__":
    main()
