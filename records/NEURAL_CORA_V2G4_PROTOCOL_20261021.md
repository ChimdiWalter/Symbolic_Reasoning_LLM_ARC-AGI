# ncv2-g4 study (syn-v4, and a real cohort pending authorization): protocol (21 October 2026)

**Status: FROZEN, NOT RUN.** It is frozen by `python scripts/neural_cora_v2g4_eval.py freeze` in the commit that adds
`records/NEURAL_CORA_V2G4_FREEZE_MANIFEST.json`. `solve` refuses unless `--authorized` is given and the lock holds:
the code (native `geocat_arc`, every ncv2 package, `cora_neural_v2g4`, the generator and this runner), this protocol
and the regenerated tasks must match the manifest, and the protocol and manifest must be committed unchanged. Running
it needs the user's explicit authorization of this exact study and budget. The real-cohort part (section 9) is
specified here but cannot be run until two further authorizations (the eligibility check and the run).

## 1. Question

Does ncv2-g4's evidence-driven construction (inversion of whole-object changes; part, region and ray rules built from
the demonstrations; covers of the changed cells, alone or after a partial inversion program) reach and choose correct
programs that ncv2-g3 does not, **at equal candidate budget and at matched CPU**, without regressions and without
more false fits? Which component accounts for any difference, and is it more than "more head candidates"?

**It is not evidence about real ARC tasks.** syn-v4 is written by the author of g4. Nine of the eleven target-group
families are written in g4's own language, so a coverage gain there is expected by construction. The informative
parts of this study are the size of the effect at equal budget, the attribution controls (sections 4 and 6: matched
compute, random head candidates, ablations), false fits outside g4's construction languages, regressions on ncv2-g3's
own ground, and selection under traps.

## 2. System under test

`cora_neural_v2g4` exactly as committed at `6baf61b` (the manifest hashes every file). It contains:
- the inversion engine (`invert.py`): native feature tables, selector induction (`(true)`, single tests, and-pairs,
  `exists` over the 12 relations; native-confirmed; don't-care objects), group inversion, compositions, parameter
  leave-one-out;
- sub-object parts and the part and ray layer (`parts.py`, `program.py`), parity-tested against native;
- construction (`construct.py`): part, region and ray rules from evidence, rival groups, greedy covers, partial
  inversion programs as bases;
- g4-readable selection (`select.py`) and the search (`search.py`): a head of at most 30% of the budget (inversion,
  construction, then a geometry tier), then the unchanged ncv2-g3 search.

**Not in it** (so not tested here): grouping units (proposal C2), alternative parses beyond native's views (C1),
feedback-driven representation edits (C7), GROW through `detect_grow`, and any neural or Qwen component.

## 3. Tasks

**HELDOUT syn-v4** (`cora_neural_v2g4_eval/families_v4.py`): 21 families, seeds 1–10, 3 demonstrations and 1 test
input each, 210 tasks (0 missing at prepare):

| group | families (executor) | what it measures |
|---|---|---|
| part | interior of large objects, corners of rectangles, hollow the largest (g4) | sub-object recolouring |
| region | holes of large rings, bounding-box background of concave objects (g4); `fill_interior` (native) | regions and negative space |
| ray | down from dots to an obstacle, diagonal rays through (g4); `ray_until_obstacle` (native) | additive line extension |
| mixed | native move then hole fill; native delete then corners (g4 with a native base) | whole-object and part-level change together |
| control | delete rectangles; recolour size-3 objects (native) | regressions on ncv2-g3's own ground |
| beyond | `halo`, rays of length 2 (native); gravity, a checkerboard of interior cells (custom Python) | false fits outside g4's construction languages |
| trap | interior of rectangles; corners of large objects (g4) | selection when a memorizer also fits and mispredicts |
| ambiguity | endpoints of lines vs size-2 objects whole; holes vs bounding-box background (g4) | whether the two attempts cover both readings |

The **target groups** are part, region, ray and mixed: 11 families, 110 tasks.

- **Three executors** make the expected outputs: the g4 executor, native CORA (ncv2-g2 grammar, including native's
  generative operations) and custom Python. The two native families that g4 can express were reproduced by a g4
  program on 10 of 10 tasks each at prepare (`PARITY`). The beyond group's custom families are outside both
  languages by design; that is not proven.
- **Separation before augmentation:** DEV and HELDOUT families differ by semantics (part kind, region, direction
  set, stop rule, operation or executor). Augmentation (colours, shapes, counts, placement) lives in the scenes. No
  native program here is an ncv2-g2 or syn-v3 family program (a unit test checks this).
- **Certification at generation:** every demonstration and the test change a cell. A multi-component program is kept
  only if dropping its base or any rule breaks the fit. Trap tasks are kept only if a memorizer from ncv2-g2's own
  generators (syn-v3's `certify_trap`: an induced feature map, the colour map, native's pixel rule) fits the
  demonstrations and mispredicts the test. Ambiguity tasks are kept only if the alternative g4 program fits and
  disagrees on the test. Trap and ambiguity scenes differ between demonstrations and the test by design (as in
  syn-v3), which deliberately targets a known weakness.
- **Never used:** the v1 395, the ncv2-g2 200, syn-v3 (being scored now), the finished real-ARC cohort (40 + 4), dev60
  and any protected or sealed split. The freeze refuses if any task's grids match an ncv2-g2 family task or a syn-v3
  task (DEV and HELDOUT, seeds 1–20) by hash.
- **Development exposure:** g4 was built on hand-made tasks and DEV-style tests before syn-v4 existed. DEV syn-v4
  families (9, seeds 1–3) were generated and inspected for the generator and the runner. HELDOUT inputs were
  generated only to count yields and parity; no solver has run on them.
- A seed that cannot produce a certified task is recorded as missing at freeze and is never replaced.

## 4. Arms (paired, the same tasks)

| arm | what runs | budget |
|---|---|---|
| `g3` | `cora_neural_v2g3.search.search`, as frozen for syn-v3 (the control) | 3,000 candidates; 120 CPU-s |
| `g4` | `cora_neural_v2g4.search.search` (the system under test) | the same |
| `g4_no_construct` | g4 with `construct.programs` returning nothing: inversion and geometry head | the same |
| `g4_no_invert` | g4 with `invert.invert` returning nothing: construction's rules alone (no partial-program bases), geometry | the same |
| `g4_parts_only` | g4 with `construct.shapes` keeping part and region shapes only | the same |
| `g4_rays_only` | g4 with `construct.shapes` keeping ray shapes only | the same |
| `g3_cpu` (phase 2) | ncv2-g3 with the CPU that g4 used on the same task (at most 120 s) and up to 9,000 candidates | matched compute |
| `g4_random` (phase 2) | g4 with construction and inversion off and, in their place, as many random g4-language programs as g4 evaluated from them (1–2 part or ray rules over the task's own selector vocabulary, random kinds, direction sets, stops and colours; seeded by task id); the geometry tier stays | 3,000 candidates; 120 CPU-s |

- **Ablations** replace one function of the frozen g4 code for the duration of one arm (`unittest.mock.patch`). The
  frozen files are never edited.
- **Isolation:** each (task, arm) runs in a fresh worker process (`maxtasksperchild=1`), and the g4 caches are
  cleared at the start of each arm, so no arm inherits another's work.
- CPU only, 2 workers at nice 10.

**What each comparison isolates:**
- `g4` − `g3`: everything g4 adds, at equal candidates;
- `g4` − `g3_cpu`: whether the gain is more compute;
- `g4` − `g4_random`: whether it is more head candidates without the evidence;
- `g4` − `g4_no_construct` and `g4` − `g4_no_invert`: the two construction engines;
- `g4_parts_only` vs `g4_rays_only`: sub-object units (the proposal's arm B, approximately) against new additive
  operations (its A+ops, approximately).

The proposal's arms C and D (joint representation search with feedback-driven edits, and its failure-blind twin) are
not built, so **this study cannot answer whether feedback-driven representation revision helps**.

## 5. Measures

All measures use the first test output, as in syn-v3.
- **Correct-candidate coverage @B**, B = 300, 1,000 and 3,000: some retained prediction whose find position (the
  candidate evaluation at which it was first found) is at most B equals the expected output. Each arm retains its
  first 50 distinct predictions in find order. For `g3_cpu`, coverage is also taken over its whole run
  (`coverage_full`).
- **pass@2:** either of the arm's two selected attempts equals the expected output.
- **top-1;** **wrong attempts** (attempts made, none correct); **find-order pass@2** (the first two distinct fits),
  so that selection is separated from construction.
- **Both readings** (ambiguity): pass@2, and the alternative program's prediction is also an attempt.
- **Paired** pass@2 gains and losses, `g4` vs `g3`; selection gains and losses, `g4` vs its find order.
- **Compute:** CPU (median, 95th percentile) and peak resident memory per arm; construction's native runs
  (`head.construct_native_runs` + `loo_native_runs`), which are not candidate evaluations.
- **Post-run checks:** tasks with 50 retained predictions per arm (coverage there may be underestimated); errors
  per arm.
- Per group and per family, every measure for every arm.

Coverage comes before pass@2 in reading the results: a selector cannot choose a correct program that no candidate
produced.

## 6. Decision rule (frozen, HELDOUT, decision budget 3,000)

| # | criterion | threshold |
|---|---|---|
| G1 | target groups, coverage@3000: `g4` − `g3` | ≥ 30 points |
| G2 | target groups, pass@2: `g4` − `g3` | ≥ 25 points |
| G3 | compute attribution, target coverage: `g4` @3000 − `g3_cpu` over its whole run | ≥ 25 points |
| G4 | candidate attribution, target coverage@3000: `g4` − `g4_random` | ≥ 25 points |
| G5 | paired pass@2 losses (`g3` right, `g4` wrong), all groups | ≤ 2% of tasks |
| G6 | control group, pass@2: `g4` ≥ `g3` | no regression |
| G7 | beyond group, wrong-attempt rate: `g4` − `g3` | ≤ 10 points |
| G8 | trap group, top-1: `g4` − `g3` | ≥ 20 points |
| G9 | median `g4` CPU and peak memory | ≤ 60 s; ≤ 4 GB |

**Label**, taken in this order (every criterion is reported whatever the label):
1. **NO_GAIN** if G1 or G2 fails;
2. **NO_GO_REGRESSION** if G5, G6, G7 or G9 fails;
3. **GAIN_NOT_ATTRIBUTED** if G3 or G4 fails;
4. **SELECTION_GAP** if G8 fails;
5. **GO_ENGINEERING** if all hold.

The thresholds are set before any HELDOUT task is solved. They are high on purpose: the target families are mostly in
g4's language, so only a large gain that survives the compute and random-candidate controls, with no regression,
counts.

**What a GO licenses:** only proposing the real-cohort check of section 9, which needs its own authorizations. It is
never a claim about real ARC, the leaderboard, representation learning or learning from failure.

## 7. Relation to the real-ARC failure analysis

The finished real-ARC cohort (`records/NEURAL_CORA_G4_REALARC_FAILURE_ANALYSIS_20261021.md`, descriptive) suggested
part-level change (13 tasks), additive line extension (7) and whole-object changes with no rule found (12) as the
main gaps. syn-v4's part, region, ray and mixed groups are designed after those observations; they do not sample them.
Grouping (6 of the 13 part-level tasks also showed it) is not built and not tested.

## 8. Stop rules

- One run.
- If more than 5 tasks raise errors in `solve`, the runner stops and the failure is reported (`MAX_ERROR_TASKS`).
- No change to families, seeds, code, budgets, arms or thresholds after the freeze. A change makes a new, labelled
  version.
- `score` is the only stage that regenerates expected outputs and reads alternative programs. `solve` passes each
  arm only the task id, the demonstrations and the test inputs.

## 9. Real cohort (PENDING AUTHORIZATION; specified, not built, not run)

- **Candidates:** the next 100 in-scope public ARC-AGI-2 training tasks in the pilot's published order, by the rule of
  `scripts/neural_cora_v2g2_realarc_cohort.py`. It excludes dev60, Phase 2a's 40, the frozen 120, the 240 stand-ins,
  the 100 tasks checked on 19 October (which include the 4 leftover tasks), the 100 candidates of 20 October (which
  include the finished cohort's 40), and every ID in any CORA-FHR, v2 or Neural-CORA output or record.
- **Eligibility:** the frozen, metadata-only Step B eligibility checker, in one authorized run. It belongs to Step B,
  which this work does not touch without the user's authorization; nothing of it has been run for g4.
- **Cohort freeze:** an addendum and a manifest (candidate and eligible hashes), committed before any solve.
- **Arms:** `g3`, `g4`, `g4_no_construct`, `g4_no_invert`, then `g3_cpu`; 3,000 candidates and 120 CPU-s.
- **Decision (PRIMARY stratum):** **GO_REAL_COVERAGE** if all hold, else **NO_REAL_GAIN**:
  1. `g4` coverage − `g3` coverage ≥ 3 tasks;
  2. `g4` pass@2 − `g3` pass@2 ≥ 3 tasks;
  3. paired pass@2 losses ≤ 1;
  4. `g4` coverage − `g3_cpu` coverage ≥ 2 tasks.
- **Licensed by** syn-v4 GO_ENGINEERING, or by the user's explicit decision. These are public training tasks: the
  result is development evidence, not unseen performance.

## 10. Resources

210 tasks × 8 arms at 3,000 candidates (`g3_cpu` up to 9,000 within g4's CPU).

DEV measurements at 3,000 on this machine, under load:
- g4: 8–27 s per task; g3: 5–8 s;
- construction's native runs: 72 to about 17,000 per task, plus up to about 23,000 in leave-one-out.

So about 100–120 CPU-s per task in all, about 6–7 CPU-hours, or 3–5 hours of wall time at 2 workers and nice 10 under
the usual load. Peak memory per worker is expected far below 4 GB (the syn-v3 DEV selftest measured 77 MB). Step B is
not touched.
