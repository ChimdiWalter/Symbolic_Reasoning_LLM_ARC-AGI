"""Phase 1 dry run of the phase 2 code paths on SOURCE tasks only (no held task, no ARC-AGI-2 file is opened).

    python -I run.py dry_run OUT_DIR N_PER_BENCH

In this process only: the gate is replaced by a stub that returns the digest "dry-run" and the primary
"arm2_vs_arm1"; the "held" half is replaced by the first N source tasks of each benchmark; the ARC-AGI-2 set by two
source tasks (the single entry point ngb.arc2.challenges is replaced, so no evaluation file is opened; the stand-in
is asserted); the static allowances are computed by the real functions and then capped at 3 CPU-s. It runs every
held arm (arms 5 to 8 and the three static arms when the object-growth contract is set), the ARC-AGI-2 arms,
writes STAGES.json and OUTPUT_MANIFEST.json as the driver would, and runs the report with its manifest, identity,
completeness and provenance checks. It checks that the code runs end to end; its numbers mean nothing.
"""
import os

from ngb import env as E, gate as GT, held as HB, arc2 as A2, report as RP, score as SC, phase2 as P2
from ngrow import data as DT


def main(out_dir, n):
    n = int(n)
    out_dir = os.path.abspath(out_dir)
    if os.path.exists(out_dir) and os.listdir(out_dir):
        raise SystemExit("the dry-run folder must be empty (fresh run)")
    GT.require_go = lambda: "dry-run"
    GT.primary = lambda: "arm2_vs_arm1"
    real_half = DT.half
    def standin(b):                             # the first source task of each of the first n families (arm 8
        rows, fams = [], []                     # needs a donor of another family; Mini-ARC is one pool)
        for r in real_half("source", (b,)):
            if b == "mini_arc" or r[1] not in fams:
                fams.append(r[1])
                rows.append(r)
            if len(rows) == n:
                break
        return rows
    fake = {b: standin(b) for b in DT.BENCHMARKS}

    def half(name, benches=DT.BENCHMARKS):
        if name == "held":
            return [r for b in benches for r in fake[b]]
        return real_half(name, benches)
    DT.half = half
    picks = [(b, t) for b in ("mini_arc", "1d_arc") for _, _, t in fake[b][:1]]
    A2.challenges = lambda: {t: DT.tasks(b)[t] for b, t in picks}
    assert set(A2.challenges()) == {t for _, t in picks}, "the stand-in must replace the evaluation set"
    SC.arc2_solutions = lambda: {t: SC.solutions(b, [t])[t] for b, t in picks}
    real_allow, real_pool = HB.allowance, A2.pooled_allowance
    HB.allowance = lambda *a: dict(real_allow(*a), t_static_cpu_s=3.0, dry_run_cap=3.0)
    A2.pooled_allowance = lambda *a: dict(real_pool(*a), t_pooled_cpu_s=3.0, dry_run_cap=3.0)
    lib = os.path.join(E.STUDY, "feasibility", "library")
    held = os.path.join(out_dir, "held")
    from ngb import object_arm as OA
    obj = OA.available()
    for b in DT.BENCHMARKS:
        for arm in ("G0", "lib", "shuf", "obj", "obj_shuf") + (("construct", "construct_shuf") if obj else ()):
            HB.run(lib, held, b, arm)
        for arm in ("static_lib",) + (("static_obj", "static_construct") if obj else ()):
            for sh in ("0/2", "1/2"):
                HB.run(lib, held, b, arm, shard=sh)
            HB.retry_killed(lib, held, b, arm)
    for arm in ("G0", "lib") + (("obj", "construct") if obj else ()) + ("static_lib",) + \
            (("static_obj", "static_construct") if obj else ()):
        A2.run(lib, held, out_dir, arm)
    E.dump(os.path.join(out_dir, "STAGES.json"), {"go_sha256": "dry-run", "primary": "arm2_vs_arm1",
                                                  "status": "complete", "stages": {}, "dry_run": True})
    E.dump(os.path.join(out_dir, "OUTPUT_MANIFEST.json"), P2.manifest(out_dir))
    RP.MARKER_DIR = out_dir                       # the claim and completion markers stay inside the dry-run folder
    RP.main(out_dir, out_dir, out_dir)            # one folder stands for kernels A, B and C


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])
