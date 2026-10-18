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

## Second witness: a REAL ARC task (ka95aa62f67d9), with `sh run_demo.sh --real` or `python3 replay_real.py`

**What it shows.** On an ARC-AGI-2 **training** task that frozen CORA and matched extra search both fail,
CORA built a rule with an **applicability guard**:

> if the object's colours are {1}: shoot a ray north-west from its centre; otherwise shoot it south-east.

The unchanged engine accepted and used the rule. Every leave-one-out fold rebuilt it and predicted the
held-out example. Here the rule is re-executed and reproduces exactly the cells CORA's answer changes, and
the evaluator marks the answer correct.

**Narration, about 30 seconds:**

"This one is a real ARC puzzle. CORA's solver could only memorize it. From that evidence it built a rule
that says *where* an operation applies as well as *what* it does: different coloured objects shoot rays in
opposite directions. It held up when each example was hidden in turn, and it answers correctly. Three
honest caveats: I found this case through my own failure analysis; it is a training puzzle; and a
version that ignores the failure record found the same rule."

**Scope:**
- The guard was developed on 18 October, **after** the CORA_FHR_V1 Kaggle entry was submitted, and is
  **not** part of that entry.
- Step kinds: offline replay of the recorded run, plus standalone re-execution of the rule; not a live
  engine run.
- Clean-environment test (2026-10-18): fresh numpy-only venv, network blocked, exit code 0.

## The 20-second version

"CORA failed this practice puzzle. From the objects it could only memorize, it built one new rule, a ring
around the odd-coloured cell. It checked the rule three times on examples it had not seen while rebuilding
it, then answered correctly; without the rule the answer is lost. A version that ignored the failure found
the same rule, so this shows that CORA can build and check a missing tool, not yet that learning from the
failure is what helped."

## What kind of run each step is

| step | kind |
|---|---|
| task, failure evidence, folds, ablation, controls | **offline replay** of the recorded run (hash-checked records in `data/`) |
| the operator's output on the test objects | **standalone re-execution** of the recorded expression (`ggrow_standalone.py`), here and now |
| native CORA, construction search, leave-one-out | **not rerun** here; a full engine rerun needs the repository (`python -m cora_fhr.witness --key dev_D3_04`) |

**What is designed by hand and what is automatic.** The trigger ("objects native could only memorize"),
the grammar (10 sources × 50 transforms) and the checks are human-designed. The choice of expression and
its rebuilding in every fold are automatic. Leave-one-out is a consistency check on 3 examples, not a proof
that the rule holds in general.

**Clean-environment test (2026-10-18).**
- **Setup:** a copy of this folder outside the repository, run from a fresh venv containing only numpy,
  with every network call blocked by a socket guard.
- **Command:** `python -s replay.py`.
- **Result:** exit code 0, which means every `MANIFEST.json` sha256 matched (the script exits on any
  mismatch). Evaluator correct, and the ablation and controls were printed.

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

**Scope of the witness.** The constructed operator is single-step. D3's planted rule
`union(ring(8), hull)[part_minority]` reduces to it, because each D3 object has one minority cell, so the
hull step adds nothing (`records/CORA_FHR_DEGENERACY_AUDIT_20261014.md`). Do not present it as learning
a two-part rule. `data/task.json` keeps the planted string as generated (hash-pinned).

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
