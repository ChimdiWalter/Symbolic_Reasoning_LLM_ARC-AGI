# CORA executable-abstraction audit

This standalone package exports the exact R16 development-synthetic study sources. It automatically discovers an executable macro from verified training programs, freezes its guide and finite candidate universe, compares eleven bounded search arms, freezes predictions, then generates synthetic query targets.

The recorded result was **0/8 for every arm**, with no selected held programs. The experiment established macro compression and a candidate-ordering failure. It did not establish real-ARC gain, new semantic expressivity, causal failure benefit or independent confirmation.

## Verify the export

Python 3.10 or newer; no third-party packages are required.

```sh
python3 -B research/cora_synthetic_audit_20261030/reproduce.py --verify-only
```

This validates source hashes and syntax without executing the study or generating held task values.

## Reproduce in a fresh output directory

```sh
python3 -B research/cora_synthetic_audit_20261030/reproduce.py --run --output /tmp/cora-r16-reproduction
```

The output directory must not exist. A started reproduction cannot reuse an output directory. On POSIX systems the runner guards study execution at 30 CPU seconds and 60 wall seconds, with an approximately 32-CPU-second process soft-limit backstop. Export verification, directory/intent setup and terminal receipt writing fall outside those study timers. It records study costs and status, separately from the reference run's whole-job preparation/queue accounting.

The study also has small per-arm CPU cutoffs. Different hardware and interpreter versions can change observed prefixes, so a bit-for-bit result is not promised. Preserve incomplete results and the resource receipt if a guard stops the run.

`EXPECTED_SUMMARY.json` contains the aggregate reference outcome. `EXPORT_MANIFEST.json` binds the exported source bytes. The trusted `exec` in `engine.py` loads only hash-pinned interpreter source; no model-generated Python is executed.

Source provenance: independent CORA R11 executable semantics, reused unchanged in R16, plus the R16 audit engine and synthetic generator. The package contains a synthetic task generator and requires no ARC data, pretrained weights or account access.

Publication checks verified export hashes, Python syntax and pinned interpreter imports. The closed study was not rerun to publish this package; the new portable runner's full execution is untested in this checkpoint.
