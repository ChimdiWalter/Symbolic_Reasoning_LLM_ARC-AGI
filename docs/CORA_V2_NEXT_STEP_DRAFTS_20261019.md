# CORA v2: next-step drafts, conditional on Phase 2a (DRAFT 2026-10-19; nothing here is frozen or authorized)

Exactly one of the two is to be finalized after the Phase 2a evaluation.

## A. If Phase 2a is GO: the Phase 2b plan (diagnosis-driven revision selection)

**Question.** Does choosing a revision from the authentic diagnosis beat strong blind and shuffled choices, with the
same revision menu and the same unchanged verifier?

**Revision menu** (already built and unit-tested):
- the selection family (`selection.py`);
- the two-stage whole-object transformation (`tst.py`, integration staged in `_pending_tst_integration.py`);
- WIDEN_SEARCH (cap × 2).

**Arms (as frozen in the Phase 2 protocol):**
- **D:** v2, then only the revision its own diagnosis selects;
- **C:** v2 with every revision on every task;
- **Cm:** C, stopped at D's CPU;
- **E:** the revision selected by another task's diagnosis (a fixed derangement).

**Mechanism under test (in-sample signal):** the union effect. On 22eb0ac0, adding the selection family everywhere
turned a unique answer into a disagreement. A diagnosis that applies a revision only where the current class fails
should avoid that. Whether it does on fresh tasks is the question.

**Cohort.** A new eligible cohort is needed:
- the 4 remaining eligible tasks plus a new candidate batch, e.g. same-shape non-additive tasks in the published
  order;
- it requires a new user-authorized isolated eligibility check.

**Gate.** As frozen: D > E and D > Cm by one-sided exact sign tests (Holm), with 0 wrong certified and 0 lost.

## B. If Phase 2a is NO-GO: ONE small versioned intervention, v2.1 part-aware in-place stage

**Evidence.** These are exposed tasks, training pairs only:
- on 22 dev tasks, objects change in part (`records/CORA_REASONING_V2_TYPED_TRANSFORM_SLICES_20261019.md` section 5);
- the changed part is a part native's G-grow sources already define in 2 tasks fully and in 8 partly;
- parts touching another object are next most frequent.

The expected reach is small, and this is stated in advance.

**Intervention.** Add one stage-1 action: recolour or delete a **native part** (a G-grow source intersected with the
object). The acting objects are chosen by the existing decision list with a default. The colour comes from the
existing policies. It composes with the existing growth stage. No other family changes.

**Version.** v2.1. A new protocol, frozen before any fresh evaluation.

**Development.**
- exposed engineering tasks;
- one independently seeded synthetic family, labelled synthetic development.

**Evaluation.** A fresh eligible real cohort, after a new user-authorized isolated check.
- GO: at least 2 new correct attempts, 0 wrong certified.
- A diagnosis-targeted arm applies the part stage only where the diagnosis finds a native-part change, against
  everywhere and shuffled. This measures the union effect directly.

**Not done:** enlarging every family at once.
