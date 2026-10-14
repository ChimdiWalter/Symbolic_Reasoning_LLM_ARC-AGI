# CORA-FHR v1: development results and integrity gate (2026-10-14)

**Label: DEVELOPMENT, SYNTHETIC (corpus C4).** The final split has never been
generated, and no arm has run on a final-family task.
- **Code:** `cora_fhr/`, commits d0cdcfb to 31b3a23.
- **Protocol:** `records/CORA_FHR_PROTOCOL_20261014.md`, with Amendment 1.

## 1. Development run v1 (dev split v1, sha 4af56bb2; arms A, C, D, E)

**Result.** A certified 0 of 27 and no construction arm certified anything.
- **Native's own LOO failed in every family, N0 included.** The cause was a
  corpus artifact. A distractor present in only some demonstrations makes
  selectors unrebuildable from demonstration subsets.
- **The fix** is generator v2 (Amendment 1 item 10): distractors are a
  per-task property.

## 2. Development run v2 (dev split v2, sha d5bab8e4; 27 tasks)

| arm | correct | gains over A | NEW_COMPOSITION gains (counted) | new certified-wrong | lost A-correct | CPU-h |
|---|---|---|---|---|---|---|
| A frozen | 4 (N0 3/3, X 1) | — | — | — | — | 1.23 |
| C failure-blind | 7 | 3 | **1** | 0 | 0 | 0.51 |
| D shuffled | 7 | 3 | **1** | 0 | 0 | 0.52 |
| E authentic | 7 | 3 | **1** | 0 | 0 | 0.76 |

**By family:**

| family | outcome |
|---|---|
| D1 | no arm certifies |
| D2 | no arm certifies |
| D3 | C, D and E each 1 counted gain |
| N0 | A 3/3; construction arms never displace A (commit rule) |
| S | C, D and E 2/3 each, through AVAILABLE_REACH, which is selection and not counted |
| U | no construction arm commits; E abstained on a tie once |
| X | the trigger never fires |

**Fold-local reconstruction, end to end.** 54 adaptive-LOO folds installed a
rebuilt extension and re-ran native. 45 succeeded: the extension was rebuilt
from the fold's own demonstrations, native accepted and used it, and the
held-out demonstration was predicted exactly. 9 abstained on a fold-level
tie. With v2, none failed on native's nested acceptance; v1's nesting
failures were the corpus artifact. Every overlay was restored.

**The witness, dev_D3_04** (frozen verification). The truth is a ring around
the object's minority-colour cell.
The planted `union(ring(8), hull)[part_minority]` collapses to exactly that, because D3 objects have
one minority cell (`records/CORA_FHR_DEGENERACY_AUDIT_20261014.md`). The witness is a single-step
composition, not a union.
1. A fails: native memorizes, and its LOO rejects.
2. E's evidence is native's own `pattern` fallbacks: 15 instances in 4 views.
3. E constructs `ring(8)[part_minority]`, classified NEW_COMPOSITION (neither
   a native mode nor a `cora_reach` setting).
4. It is installed into the unchanged engine. Native accepts and uses it, and
   the overlay restores.
5. All 3 folds rebuild the same operator from their own 2 demonstrations,
   with acceptance, use and an exact held-out prediction, and no tie.
6. The committed test prediction is **correct**.

**But C, failure-blind, does exactly the same.** D, whose donor was dev_N0_00
from another family, finds nothing, as a shuffled control should.

**Matched search.** f_B recalibrated on v2 is 1.33. Arm B results: pending
(section 6).

## 3. The E-versus-C' confound (the user's integrity point 1)

**Control C'** observes the same identity-frame native induction as E and
keeps every growth correspondence native built. It therefore has the same
correspondence source and the same extraction compute; only the failure
filter is withheld.

**Audit over dev v2** (`outputs/cora_fhr/c2_audit_c4_dev_v2.json`): E's
evidence equals C''s on **5 of 5 D1 and 5 of 5 D3 tasks**. On D2, native
builds no growth correspondence at all (the matching bottleneck). Native
explains some growth and memorizes the rest only in U (3 of 3), N0 (1 of 3)
and S (1 of 3).

**Why.** The G-rejection rule guarantees that native explains none of the
true growth. So every growth correspondence on a G task is a memorization,
and the failure filter removes nothing.

**Consequence.** On C4 as designed, H3 ("authentic failure evidence matters")
cannot be tested. An E-over-C difference would measure native's
correspondence against nearest-object attribution, not reasoning from
failure.

## 4. Verification variants (development what-if, from recorded folds; no rerun)

| arm | certified, frozen rules | certified without the fold-level tie check (top-level kept) | of which NEW_COMPOSITION and correct | wrong |
|---|---|---|---|---|
| E | 3 | 6 | 4 (D1_02, D1_04, D3_00, D3_04) | 0 |
| C | 3 | 5 | 3 | 0 |
| D | 3 | 3 | 1 | 0 |

**Why the fold-level tie check costs these certifications.** It demands that
the operator be uniquely determined by every pair of demonstrations. That is
stricter than native's own LOO, which requires a correct re-derived
prediction, not uniqueness.

**Effect of removing it.** In development it added 0 wrong certificates. The
top-level tie check, which protects U, is kept.

**E's extra over C (D1_04)** is an attribution difference: nearest-object
attribution found no instances.

## 5. Shuffled-control defects found

1. **Same-mechanism donors.** "The next key in sorted order" pairs a task with
   a same-family sibling in C4. dev_D3_00's donor, dev_D3_01, shares its
   mechanism. That is why D certified there.
2. **D's evidence never shrinks.** E and C lose a demonstration per fold;
   D's folds reuse the donor's full evidence, which makes its LOO easier.

## 6. Final development results (2026-10-15, 00:05Z; replaces "Pending")

Per-family table: `outputs/cora_fhr/dev_table_c4_dev_v2.md` / `.json`, from `python -m cora_fhr.dev_table`.

**C′ run** (`rows_c4_dev_v2_C2.jsonl`; 21:21 to 22:04Z):

| | E | C′ | C | D |
|---|---|---|---|---|
| certified with an extension and correct | 3 (D3 1, S 2) | 3 | 3 | 3 (D3 via a same-family donor) |
| wrong extension certificates | 0 | 0 | 0 | 0 |
| A-correct answers lost | 0 | 0 | 0 | 0 |

- E and C′ agree on outcome **and** selected operator in 22 of 27 tasks. That covers every G-family
  task (D1, D2, D3) and S.
- The 5 differences are N0 (3) and U (2). There C′ proposes native-available rules (`ring(8)[self]`,
  `ray(.)[self]`), which end in ROUTING_FAILURE or ENGINE_REJECTION, while E has nothing to learn from.
  Neither gains an answer: A certifies the N0 tasks itself.
- **Causal verdict on C4: failure evidence adds no measurable correctness over C′**, as the
  structural audit predicted. The failure filter only suppresses useless proposals on
  native-covered tasks.

**Native A on the controls:**
- 3 of 3 N0 tasks certified correct.
- 2 wrong native certificates on the designed-ambiguous U (1) and wrong-action X (1) controls.
- The precise-verifier claim (0 false certificates) refers to the 60 real dev tasks and to the
  construction arms, not to native on these adversarial controls.

**Refold, ungated** (Amendment 2 A what-if): identical outcome counts in every arm.

**Dropping fold-level ties** (Amendment 2 B, recorded-fold what-if):
- the no-fold-tie certifications would be correct in D1 (E 2, C2 2) and S;
- B is still not recommended, because it is a relaxation with in-sample support only.

**Also done:**
- the asset audit (funnel record);
- the D3 degeneracy audit (`records/CORA_FHR_DEGENERACY_AUDIT_20261014.md`): the witness is a
  single-step composition;
- the Amendment 2 recommendation (protocol);
- the mixed-coverage pilot (`records/CORA_FHR_MIX_DESIGN_20261014.md`), run 2 in progress.
