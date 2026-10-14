# CORA-FHR: 90-second summit demonstration (ARC Prize Research Summit, 23 October 2026)

**What this is.** An **offline replay** of a recorded development run: task
dev_D3_04 of the SYNTHETIC development corpus C4 v2. It is not a live
execution, and the native reasoner is not re-run here.

**Run it:**
```
sh run_demo.sh               # or: python3 replay.py [--png]
```
It needs Python 3.9+ and numpy (`pip install numpy`); the images also need
matplotlib.

**What it checks.** Every bundled file is hash-checked against
`MANIFEST.json` before anything is shown. The source records (corpus, run
rows, witness audit), with their sha256, are listed in `MANIFEST.json`.
The bundle was built with `build_bundle.py`, inside the repository on Athe.

**Evidence tier: DEVELOPMENT, SYNTHETIC.** This is not an ARC-AGI-2 result
and not a Kaggle result.

## The 90-second script (one line per screen of `replay.py`)

| time | screen | say |
|---|---|---|
| 0:00 | 1. the task | "CORA writes executable programs for ARC-style tasks. Here are three examples of one rule." |
| 0:10 | 2. the failure | "Frozen CORA fits them by memorizing the exact cells that changed. Its own leave-one-out check rejects that, so it answers nothing." |
| 0:20 | 3. the diagnosis | "CORA reads its own failure trace: the objects whose growth it could only memorize." |
| 0:28 | 4. the construction | "From that evidence it builds a new executable operator in a declared typed grammar: a ring around the object's minority-colour cell. Neither native CORA nor our earlier constructor can express it. We checked on 300 perturbed shapes." |
| 0:40 | 5. the operator | "Here it is, running on the test input's objects." |
| 0:48 | 6. the check | "It is installed into the same reasoner, which accepts and uses it. Then the strict test, three times: hide one example, rebuild everything from the other two (evidence, operator, program), and predict the hidden one. All three are exact." |
| 1:05 | 7. the result | "Only then does CORA commit its answer. An independent evaluator scores it: correct." |
| 1:12 | 8. the ablation | "Remove the operator and CORA fails again. The honest part: a constructor that never sees the failure trace finds the same operator. So this shows that CORA can construct and verify a missing capability; it does not yet show that the failure record made the difference. That comparison is the experiment we have designed next." |

## Facts behind each screen

All of these are in `data/witness.json`:
- frozen CORA failure stage: `loo`;
- the evidence: 15 memorized instances across 4 views;
- the operator: `ring(8)[part_minority]`, canonical `d1|1|39`, name
  `fx_bd15c802b6bb4940`, class NEW_COMPOSITION;
- perturbation check: native 7 of 300, best `cora_reach` setting 8 of 300;
- folds: 3 of 3 SUCCESS (rebuilt, accepted, used, exact);
- replay: every demonstration exact, engine state restored;
- evaluator: correct;
- ablation: without the extension, nothing is certified;
- controls:
  - C (failure-blind) and C' (correspondence-matched): also certified;
  - D (shuffled): no proposal.
