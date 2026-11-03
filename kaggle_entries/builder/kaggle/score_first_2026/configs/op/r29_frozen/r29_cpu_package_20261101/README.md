# CORA R29 portable CPU candidates — review candidate

This self-contained private package adapts the frozen R29 forward, diagnosed-inverse and conditional-beam constructors to a stricter single-output interface. It contains ten byte-exact authored CORA source files, no pretrained model, ARC data, NVARC notebook/code, learned registry, C4 artifact or external service integration. This is CAGE work within CORA.

The wrapper is new. **The historical R29 3/32 result does not measure this package:** genuine leave-one-out and single-output priority change both acceptance and predictions. All-abstention is an admissible outcome; validation gates must not be weakened to obtain coverage. No prediction or scoring run has yet been performed by this package's author.

```python
from cage.r29_cpu_package_20261101 import candidates, candidates_with_report
values = candidates(task, cpu_s=12.0, wall_s=20.0)
values, report = candidates_with_report(task, cpu_s=12.0, wall_s=20.0)
```

`values` has one entry per test input, each an ARC grid or `None`. `task` contains `train` pairs with exactly `input,output`, and `test` records with exactly `input`. Optional top-level `id/task_id` metadata is ignored without reading its value; no identity reaches the constructors. Other fields, test outputs, invalid grids and invalid budgets fail closed. Grids are rectangular integer colors 0–9, dimensions 1–30, up to ten demonstrations and 100 queries. Booleans are not colors/budgets. Fewer than two demonstrations returns all `None` and `INSUFFICIENT_VALIDATION_EVIDENCE`. No inputs are modified.

Each constructor must fit all demonstrations, independently replay them, and pass **every** leave-one-out fold. Every fold calls synthesis anew on all remaining pairs; no full model, fold model, cache or capability registry is shared across folds. Each fold replays its retained examples before predicting the excluded input. Imports/code may be cached within the isolated process; fitted state may not. Conditional trees require at least two retained demonstrations and therefore cannot qualify with only two total demonstrations. The full-model fit never receives test inputs. Only after full/LOO acceptance does its frozen program run on tests.

Fixed priority is forward, then diagnosed inverse, then conditional beam. Each test query receives the first valid program output from an accepted method. There is no score selection or answer access. Once all query slots are filled later methods are not run. R29's two-attempt complementarity is not preserved by a one-grid API; this package makes no claim that this priority is optimal.

Every full/fold fit has the original at-most-one-CPU-second ceiling shared with its own independent replay and subsequent queries, plus the original logical caps. Other folds' CPU is excluded from that model's internal allowance but included in the whole call. Finite generation/semantic/predicate/cell exhaustion is ordinary method abstention (`UNKNOWN`, never impossibility). Actual CPU/wall timeout or an unexpected solver exception invalidates the entire task and returns all `None`. Ordinary query precondition/coverage failure abstains for that query. `KeyboardInterrupt/SystemExit` and external `TimeoutError` cancellation (distinct from the API's own deadline exception) are external lifecycle cancellation: the owned child is killed/waited and the original cancellation propagates unchanged.

The parent validates/copies the task, writes a private temporary request, and launches a fresh `python -I -S -B` worker. Thus off-main-thread calls still perform heavy work in a child **main thread**, where SIGPROF CPU and SIGALRM wall timers are installed before JSON/vendor imports. RLIMIT_CPU provides a coarser backup. Interpreter/minimal timer-bootstrap CPU is included in absolute process CPU, while the parent wall deadline includes process startup and all IPC. The parent uses per-PID `wait4` CPU accounting; its calling-thread CPU, serialization and response validation are added, with conservative finalization reserve. Any through-return overrun discards outputs. OS signal granularity and short cleanup tails are measured rather than presented as instruction-exact real-time bounds. No unrelated process or global signal handler is changed; every call uses its own child and temporary files.

Runtime assumptions: Linux/POSIX `wait4`, SIGPROF/SIGALRM, RLIMIT_CPU and a supported CPython interpreter. The code targets Python 3.13 and uses only the standard library. **Local Python is 3.12.3; 3.13 compatibility has not been executed or certified.** A Kaggle Python 3.13 smoke test remains required. It does not require NumPy/SciPy, GPU, network, installation or a repository-specific absolute path. Copy this whole directory intact; its vendored `cage/experiments` layout resolves only within `vendor/`. Package hashes are checked inside every worker before solver imports. A mismatch yields all `None`.

CLI from the CORA/CAGE checkout:

```bash
python3 -B -m cage.r29_cpu_package_20261101.cli permitted_input_only_task.json --cpu-s 12 --wall-s 20 --output new_result.json
```

Portable import outside the checkout: place the whole directory on a parent path and import `r29_cpu_package_20261101`; the child still resolves its private vendor tree. The CLI should then be invoked as `python -m r29_cpu_package_20261101.cli ...`. Outputs are created exclusively; existing files are not overwritten.

Tests are authored in `test_package.py`, including fresh-fold synthesis versus memorized full-fit rejection, no identity/answer access, invalid budgets/schema, real subprocess CPU/wall guards off the caller main thread, manifest mismatch, lifecycle cancellation cleanup, and repeated actual hflip synthesis. **They have not been run during preparation.** Root must review the frozen package and run them within the existing shared CPU admission protocol; do not bypass occupied CPU slots.

`VENDORED_PROVENANCE.json` maps original relative source paths and exact hashes. `MANIFEST.json` identifies the reviewable package; its own hash is recorded outside itself by the reviewer. New acceptance/inference code is distinguished from the immutable original constructors. `LICENSE_STATUS.md` records unresolved release requirements. No public license, competition launch, submission, final selection, manuscript modification or publication is authorized by this package.
