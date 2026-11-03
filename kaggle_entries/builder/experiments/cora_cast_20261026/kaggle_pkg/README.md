# cast_v1: CAST v1 core as a drop-in candidate generator (configuration B)

**API.** `from cast_v1 import cast_candidates`; `cast_candidates(task, cpu_s=15.0, wall_s=30.0, details=False)`
takes one ARC task dict (`{"train": [{"input", "output"}, ...], "test": [{"input"}, ...]}`; test outputs are never
read) and returns a list with one entry per test input: a grid (list of lists of ints) or `None`. With
`details=True` it returns `{"grids", "module", "program", "status", "version", "cpu_s"}`; status is `OK`, `TIMEOUT`
or `ERROR:<type>`. Intended use: neural attempt 1 stays; a non-None CAST grid may replace attempt 2.

**What it runs.** The frozen CAST v1 core, in this order: M4 general symmetry completion (complete predictions only),
M2 typed guarded rewriting and guarded frames, L0 contract-guided search (depth 2, 1,000 executions). The modules are
byte copies of the frozen research snapshots (`runs/chain_v1/code`, `runs/chain_v2/code`) with only two changes:
package-relative imports, and the four scipy image calls routed through `_nd.py` (pure numpy; scipy used as an
accelerator when importable; both backends are tested to agree).

**Acceptance rule (general; no task ids or task-specific rules).** A module's first attempt for a query is returned
only if the program reproduces every demonstration exactly, the answer is complete (valid grid, not the unchanged
query, no undetermined cell), and leave-one-demonstration-out passes (each demonstration, held out in turn, is among
the top two attempts of the same module rebuilt from the others; tasks with fewer than two demonstrations are never
accepted). This filter is stricter than the confirmation arms (which used the modules' attempts without it): it can
only remove candidates.

**Caps and safety.** Hard per-call caps: `cpu_s` of process CPU (ITIMER_VIRTUAL) and `wall_s` of wall time
(ITIMER_REAL), installed only when called from the main thread; the caller's handlers and timers are restored. Any
timeout, error or invalid input returns `None` for every test input. Deterministic: no randomness; identical output
across `PYTHONHASHSEED` values and backends (tested). No file, network or subprocess access.

**Requirements.** Python 3.12 (tested); written for Python >= 3.10 and uses nothing removed in 3.13, but Python 3.13
was not available on the build host, so 3.13 is UNTESTED. numpy >= 1.24 (tested with 2.4.3 and 2.5.2); scipy optional.
Cost: about 0.4-8 CPU-s per task on the tasks tried; worst case is the cap (240 tasks x 30 s wall = 2 h).

**Tests.** `cd kaggle_pkg && python -m pytest -q tests` (7 tests: symmetric completion returned; fail-safe on invalid
and one-demonstration tasks; timeout returns None and restores timers; numpy and scipy backends agree; determinism
across hash seeds and backends; no ARC task id in the source; where the package answers, the grid equals the frozen
core's recorded first attempt). Evidence status: development only. The only evaluation answer CAST adds over the
neural pool (62593bfd) is design-exposed; see `../FINAL_DECISION.md` and `../results/confirm/` for the confirmation.
