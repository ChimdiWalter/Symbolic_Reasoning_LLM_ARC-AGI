"""Phase 1 dry run of the phase 2 code paths on SOURCE tasks only (no held task, no ARC-AGI-2 file is opened).

    python -I run.py dry_run OUT_DIR N_PER_BENCH

The gate is replaced in this process only; the "held" half is replaced by the first N source tasks of each
benchmark, and the ARC-AGI-2 set by two source tasks. Runs every held arm (G0, the four grown arms, matched static
search in child processes), the ARC-AGI-2 arms and the report, from the phase 1 registries in feasibility/grow.
The static allowances are computed by the real functions and then capped at 3 CPU-s (with N tasks standing in
for a held half they would be far too large). It checks that the code runs end to end; its numbers mean nothing.
"""
import os

from ngrow import env as E, data as DT, gate as GT, held as HL, arc2 as A2, report as RP, score as SC


def main(out_dir, n):
    n = int(n)
    out_dir = os.path.abspath(out_dir)
    GT.require_phase2 = lambda: "dry-run"
    real_half = DT.half
    fake = {b: real_half("source", (b,))[:n] for b in DT.BENCHMARKS}

    def half(name, benches=DT.BENCHMARKS):
        if name == "held":
            return [r for b in benches for r in fake[b]]
        return real_half(name, benches)
    DT.half = half
    picks = [(b, t) for b in ("mini_arc", "1d_arc") for _, _, t in fake[b][:1]]
    A2.challenges = lambda: {t: DT.tasks(b)[t] for b, t in picks}
    SC.arc2_solutions = lambda: {t: SC.solutions(b, [t])[t] for b, t in picks}
    real_allow, real_pool = HL.growth_total_cpu, A2.pooled_allowance

    def allow(*a):
        r = real_allow(*a)
        return dict(r, t_static_cpu_s=min(r["t_static_cpu_s"], 3.0), dry_run_cap=3.0)

    def pool_allow(*a):
        r = real_pool(*a)
        return dict(r, t_pooled_cpu_s=min(r["t_pooled_cpu_s"], 3.0), dry_run_cap=3.0)
    HL.growth_total_cpu, A2.pooled_allowance = allow, pool_allow
    ctrl = ",".join(os.path.join(E.STUDY, "feasibility", f"controller_source_shard{i}.jsonl") for i in (0, 1))
    grow = os.path.join(E.STUDY, "feasibility", "grow")
    held = os.path.join(out_dir, "held")
    for b in DT.BENCHMARKS:
        for arm in ("G0", "S-hole", "S-shuffled", "S-demo", "S-enum"):
            HL.run(grow, held, b, arm)
        HL.run(grow, held, b, "static", shard="0/2", ctrl_paths=ctrl)
        HL.run(grow, held, b, "static", shard="1/2", ctrl_paths=ctrl)
    for arm in ("G0", "growth", "static"):
        A2.run(grow, held, out_dir, arm)
    RP.main(out_dir, out_dir)


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])
