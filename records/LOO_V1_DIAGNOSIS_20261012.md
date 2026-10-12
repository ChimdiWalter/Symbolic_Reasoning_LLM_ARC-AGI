# Adaptive LOO stability v1: diagnosis (2026-10-12)

DEVELOPMENT, observation only, on the 4 failure-conditioned (FC) tasks of
reach v1 (`docs/CORA_REAL_TASK_LOO_STABILITY_v1.md`). No engine code was
changed; no target was read (leave-one-out holds out demonstrations). This
record is written and committed before any repair code.

## Run identity and verification

- Instrument 0e3d091; frozen 462e8ef (`outputs/loo_v1/diagnose_manifest.json`
  sha256 `58de06d5...7a7ede`); run once 2026-10-12T00:42:50Z to 03:03:29Z
  (2 h 21 min, 4 workers, coordinator 711041, boot unchanged, no resume);
  18 of 18 units, exit codes 0, 0 RUN_ERROR, every row restored, 4 isolation
  logs with 0 refused accesses; rows committed 4c14f9d. Reach v1 and pilot v2
  freezes re-checked after every commit: 0 problems.
- 102 engine and extraction runs: 29,828 CPU s, 30,535 wall s; CPU share
  0.94 to 0.997 (median 0.98) at host load 55 to 61.
- Frozen classifier (`scripts/loo_v1_classify.py`, pinned before the run;
  `outputs/loo_v1/diagnosis.json`): 0 problems; folds H3 3, H1 2, H4 1, H2 1,
  UNRESOLVED 7 (all at the engine's own leave-one-out with a deadline hit
  somewhere in the run, so neither H2 nor H5 applied); full-data A_E:
  kf892487f1049 ACCEPTED, the other three UNRESOLVED at the engine's LOO.
- Two forensic probes resolve the UNRESOLVED class (observation only,
  committed before they ran, 89bdb49 and the variant probe; outputs
  `outputs/loo_v1/probe_kf892487f1049.json`, `probe_variants.json`; isolation
  clean). The frozen labels are reported unchanged; the probes add the
  mechanism the frozen rules had no name for.

## The mechanism (dominant blocker): segmentation-variant admission mismatch

The engine searches at most MAX_SEG_VARIANTS_TRIED = 4 segmentation variants:
the coherent ones (`segmentation.evaluate_variant`) in the fixed trial order
S1, S2, S3, S5, S4, S6, S7, or one fallback when none is coherent. Coherence
is a property of the demonstration subset: fewer demonstrations make finer
variants coherent more easily. Every growth extension is constructed from
instances memorized in one variant V. When a demonstration subset admits
four variants ahead of V, or makes V incoherent, the engine never searches
V, and the installed relation cannot be used.

- kf892487f1049 (bbox_fill, V = S6). All four outer folds find, at the top
  level, exactly the full-data program G (one rule, selector `true`, grow by
  the installed relation, colour of self; the same sha f22944438323). The
  engine's own LOO then re-induces from 2 demonstrations: on the pairs
  (0,1), (0,3), (1,2), (2,3) it searches S6 first and returns G, which
  reproduces the other two demonstrations; on (0,2) and (1,3) the coherent
  variants S1, S2, S3, S5 fill the cap, S6 is never searched, and the winner
  (4 rules, relation selectors, constant class) is wrong on its held-out
  demonstration (21 to 33 cells). Every failed inner fold of every outer
  fold is one of these two pairs. Exploring every candidate variant
  (`_induce_candidate(explore_all=True)`) changes nothing: S6 is not among
  the candidates. G itself is train-exact on both pairs. A first hypothesis,
  that the cross-variant parsimony skip pruned S6, is REFUTED by the probe.
- k5a49896251a2 (connect, V = S6): S6 is the only coherent variant on the
  full data, so the top-level search uses the relation, but every
  2-demonstration subset of the engine's own LOO admits other variants first
  and cuts S6 (2 of 3), so the full-data run is rejected; the outer folds
  0 and 2 (NO_PROPOSAL) are the same cut in K's extraction, and outer fold 1
  is cut in both single-demonstration inner folds.
- k017955a77fc5 (window_fill, V = S2): S2 is incoherent on the full data
  (coherent: S4, S6, S7), so the installed relation is never searched and
  the engine's best program does not use it.
- k5991e227189e (connect, V = S6): no variant is coherent on the full data;
  S6 is searched only as the fallback, and most reduced subsets make other
  variants coherent or move the fallback (S2), so S6 is dropped.

## All 14 failed outer folds

| fold | reach v1 | frozen class | mechanism (probes) |
|---|---|---|---|
| kf892487f1049 f0 | LOO_FAILURE | UNRESOLVED loo | same e; inner pair (1,3) cuts S6 |
| kf892487f1049 f1 | LOO_FAILURE | H4 ORDERING | window_fill selected first (bbox_fill also proposed; the held-out demonstration distinguishes them); inner pair (0,2) cuts S6 |
| kf892487f1049 f2 | LOO_FAILURE | UNRESOLVED loo | same e; inner pair (1,3) cuts S6 |
| kf892487f1049 f3 | LOO_FAILURE | H2 RE_INDUCTION | same e; inner pair (0,2) cuts S6 (no deadline hit at all) |
| k5a49896251a2 f0 | NO_PROPOSAL | H3 EVIDENCE | K's extraction on (1,2): four variants are admitted ahead of S6, S6 cut |
| k5a49896251a2 f1 | LOO_FAILURE | UNRESOLVED loo | same e; both single-demonstration inner folds cut S6 |
| k5a49896251a2 f2 | NO_PROPOSAL | H3 EVIDENCE | K's extraction on (0,1) cuts S6 |
| k5991e227189e f0 | LOO_FAILURE | UNRESOLVED loo | same e; S6 dropped in inner subsets (incoherent; fallback moves) |
| k5991e227189e f1 | NO_PROPOSAL | H3 EVIDENCE | outer subset (0,2,3) admits S3, S4, S7; S6 dropped |
| k5991e227189e f2 | LOO_FAILURE | UNRESOLVED loo | same e; S6 dropped in inner subsets |
| k5991e227189e f3 | LOO_FAILURE | UNRESOLVED loo | same e; S6 dropped in inner subsets |
| k017955a77fc5 f0 | NO_PROPOSAL | H1 IDENTIFIABILITY | the S2 evidence comes from demonstrations 0 and 1 only: support lost |
| k017955a77fc5 f1 | NO_PROPOSAL | H1 IDENTIFIABILITY | same |
| k017955a77fc5 f2 | LOO_FAILURE | UNRESOLVED loo | same e; S2 searched, a single-demonstration inner fold re-induces a program wrong on the other demonstration (identifiability from one demonstration) |

Frequencies: variant admission 11 of 14 folds (8 with the extension
rebuilt, 3 in K's extraction), support 2, identifiability from one
demonstration 1; ordering (H4) co-occurs in 1. The three full-data
rejections are variant admission (k5a49896251a2 inner subsets,
k017955a77fc5 and k5991e227189e V never admitted as coherent).

## Outer against inner leave-one-out

On kf892487f1049 the full-data engine LOO re-induces from 3 demonstrations,
every 3-subset admits S6, and it passes 4 of 4; each outer fold's engine LOO
re-induces from 2 and passes 2 of 3, failing exactly on the pairs whose
variant admission cuts S6. The nested reduction is the causal path, through
variant admission, not through the number of demonstrations as such: the
same 2-demonstration re-induction returns G on four of six pairs.

## Resources

WALL and CPU1 (deadlines on process CPU time) gave identical acceptance and
stage in all 23 paired arms; the 17 WALL hard-cap hits all completed under
CPU1 without acceptance. Deadline hits occur inside the engine's own
leave-one-out under both clocks: they are intrinsic to the search, not host
contention. Matched compute (E, up to 270 s) never accepted. No budget is a
blocker here.

## Novelty labels (protocol section 8)

For the four extensions: GROW_SUBLANGUAGE_ABSENT (the engine's detect_grow
falls back to the constant pattern on every instance) and NOT_A_CACHE hold;
SEARCH_INACCESSIBLE_WITHIN_BUDGET holds for K alone at full data under WALL,
CPU1 and matched compute (A_K never accepts; D and E never accept on any
fold). BOUNDED_SEMANTIC_EXTENSION_CERTIFIED is not established: no complete
bounded semantic-absence procedure over the whole native engine exists here.
The reach v1 record's word "separated" means these three weaker labels.

## The one licensed repair (proposed; not implemented here)

Class: fixing a demonstrable segmentation-variant mismatch (directive
section 8). VARIANT-CARRYING INSTALLATION: a growth extension records the
segmentation variant V of the instances it was constructed from; while it is
installed, the engine searches V first and admits it even when its
coherence filter would not; every other variant, the cap on the engine's own
variants, the acceptance gate (train-exact and the engine's own
leave-one-out), K alone and the failure-evidence extraction are unchanged.
Generic and task-independent: V comes from the construction, never from a
task id or an answer. Disclosed: it changes how K + e searches, so the
recheck reports K + e against K alone, REMOVED and MATCHED as before.

Expectation, written before any repair exists: it addresses the variant cut
inside the engine's own leave-one-out (kf892487f1049 folds 0, 2, 3;
k5a49896251a2 fold 1 and its full-data run; k017955a77fc5 and
k5991e227189e full-data searches). It does not address the evidence side (K's
extraction, folds k5a49896251a2 f0 and f2, k5991e227189e f1), support
(k017955a77fc5 f0 and f1) or ordering (kf892487f1049 f1, where window_fill is
selected and is wrong on the held-out demonstration). So complete adaptive
leave-one-out on any of the four tasks, and with it the screen, is not
expected; the recheck measures it.
