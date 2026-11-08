# Adapter card: what this study reuses and what is new

The calibrated acceptance study of 8 Nov 2026 reuses the bioimage grammar study of 2 Nov 2026, called U5 below
(`experiments/universality_bio_grammar_20261103`). It changes one thing: the rule that decides which edits are
accepted. Everything else is reused byte for byte, and the sha256 of every reused file is in `FREEZE.json`.

## Reused, read-only and unchanged

U1 below is the earlier study of the submitted packages on S-BSST265 (`experiments/universality_submitted_pkg_20261101`).
Its adapter supplies U5's strong native deletion rule.

| what | where | role here |
|---|---|---|
| The 11 literature operators, unit features, matching, unit effects, exact edit application with the conflict rule | U5 `scripts/u5core.py` | the edit grammar and its executor |
| Program enumeration (theta, guards of decile predicates), selection, U5's strict rule and tolerant rule | U5 `scripts/u5policy.py` | the program space of every CORA arm; STRICT and TOLERANT |
| Image sets, unit tables, `run_policy`, exact certification, `apply_accepted` (accepted == applied == logged) | U5 `scripts/u5run.py` | STRICT and TOLERANT runs; certification and application for CALIBRATED |
| Static beam search and program application | U5 `scripts/u5static.py` | MATCHED_SEARCH, fitted with CALIBRATED's CPU |
| Failure-evidence specification and the derangement of class labels | U5 `scripts/u5induce.py`, `u5probe.py` | the failure-evidence order; CAL_SHUFFLED |
| Bootstrap, Holm adjustment, ratio bootstrap | U5 `scripts/u5eval.py` (`boot`, `holm`, `cboot_ratio`) | every interval and adjusted p value |
| Normalization and polygon rasterization | U5 `scripts/u5data.py` (`norm01`, `_poly_labels`) | intensity images; PUMA references |
| The strong native deletion rule and its features | U1's `adapter.py` (`rule_deletes`, `FEATS`), `cora_cross_domain_transfer/adapters/bbbc039.py` (`Features`, `h_maxima`) | STRONG_NATIVE on PUMA |
| StarDist 0.9.2 `2D_versatile_he` weights | byte copy of U5's `models/stardist/2D_versatile_he` | the baseline segmenter |
| NuInsSeg-tuned thresholds (probability 0.4562, NMS 0.3), low threshold 0.2281, deletion rule contact >= 3 | U5 `work/nuinsseg/seg/THRESHOLDS.json`, `STRONG_NATIVE_RULE.json` | NATIVE, TUNED, LOW, STRONG_NATIVE on PUMA, without re-tuning |
| NuInsSeg calibration organs (12 organs, 236 images): segmentation S, intensity, low labels, references | U5 `work/nuinsseg/` | demonstrations and development |
| Failure records of the frozen CORA component on NuInsSeg induction organs, and per-class oracle gains | U5 `work/nuinsseg/probes/induction/`, `GATE.json` | the failure evidence |

- **U5's code freeze still holds.** Every file in U5's `CODE_FREEZE.json` was checked before this study ran: 24 of 24
  match.
- **No bytecode in U5's folders.** U5's modules are imported with Python's `-B` flag, so nothing is written into U5's
  `__pycache__` folder.

## New (this study's folder only)

| file | what it adds |
|---|---|
| `scripts/calrule.py` | **the calibrated acceptance rule.** It covers: per-image scoring of U5's programs (each image its own parent); judged-alone harmful and beneficial counts per program; leave-one-organ-out fold programs under an in-fold harmful-rate limit of 0.40; organ-clustered t bounds certifying the out-of-organ gain (lower bound above 0) and the out-of-organ harmful-edit rate (upper bound at most 0.60), each one-sided at 0.05; and fixed-sequence testing over an arm's operators |
| `scripts/cadata.py` | PUMA access: the archive listing, the format ROI, the salted held selection after GO, guarded image and reference readers, the GeoJSON-to-label conversion through U5's rasterizer |
| `scripts/seg_puma.py` | StarDist on PUMA ROIs at U5's thresholds; it follows U5's `seg_stardist.py` without tuning |
| `scripts/caharness.py` | the arms, each in its own process; MATCHED_SEARCH with CALIBRATED's CPU; development scoring; STRONG_NATIVE on PUMA; the frozen-record check; decision hashing; the evaluator (replay of every edit, contrasts, Holm, labels) |
| `scripts/cal_chain.sh` | the calibration-side chain before GO (final policy, matched search, development) |
| `scripts/run_after_go.py` | the held chain after GO, with CPU accounting and the stop rules |
| `scripts/make_freeze.py`, `scripts/verify_freeze.py` | write and check `FREEZE.json` |
| `tests/test_calacc.py` | 13 regression tests: the rule against brute force, the bounds, the false-acceptance rate on pure noise, the separate in-fold limit and bound, the held selection, the reader guards, rasterization, per-image parents, U5's code freeze |
| `tests/dryrun_held.py` | an end-to-end dry run of the held path (decisions, the frozen-record check, decision hashing, the evaluator) on 4 NuInsSeg calibration images posing as held ROIs; no PUMA image is touched |
| `calibration/final/` | the frozen calibration records (a byte copy of `data/work/cal/final/`, hashed in `FREEZE.json`) |
| `development/` | development records: the first version, both scans, the development split |

## Differences from U5's procedure, on purpose

- **Calibration and held data.** Calibration is NuInsSeg in-domain (its 12 calibration organs). The held data are a
  fresh source (PUMA), not U5's held-out organs.
- **No admission step.** U5's section 9 admission step is not used. Every CORA arm receives its 3 operators directly,
  so the arms differ only in the acceptance rule or in the operator choice.
- **Fresh processes.** Each arm runs in its own process, so its CPU includes its own unit tables (U5's controls reused
  CORA's cache).
- **Control seeds.** The held run's control seeds come from the GO salt instead of U5's fixed seeds.
