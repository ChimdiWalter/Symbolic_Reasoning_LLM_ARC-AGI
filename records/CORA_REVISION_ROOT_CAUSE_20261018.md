# CORA-FHR proposal bottleneck: root-cause autopsy (2026-10-18; DEVELOPMENT; read-only over retained rows)

**Script:** `python -m cora_fhr.root_cause`, which writes `outputs/cora_fhr/root_cause_20261018.json`.

**Sources:**
- the Kaggle committed rehearsal (`outputs/kaggle_deploy/cora_fhr_v1/run_v1/fhr_rows.jsonl`, 240 stand-in
  ARC-AGI-2 training tasks);
- the 60 real development tasks (`outputs/cora_fhr/rows_dev60.jsonl`).

Both are training tasks, so nothing here is a generalization claim.

## 1. Every case, from the logs (observable at inference unless marked)

**Rehearsal.**
- 169 tasks were skipped as not growth-shaped and 9 as native object-certified; 62 ran FHR.
- The 62 break down exactly as follows:

| class (what the solver's own trace shows) | rehearsal (62) | dev60 (60) |
|---|---|---|
| NO_MEMORIZED_GROWTH_EVIDENCE: native's identity-frame induction recorded no single-colour memorized-growth correspondence in any view, so E has nothing to construct from | **20** | **32** |
| EVIDENCE_BUT_NO_OPERATOR: there are views with evidence, but no proposal. The logs do not say whether cross-demonstration support was missing or no G-grow expression fits | **39** | **25** |
| RESOURCE_CAP_EXTRACTION: evidence extraction hit its 450 s CPU cap | **2** (13713586, 34cfa167) | **2** |
| PROPOSAL_RECONSTRUCTION_FAILURE: a proposal was made but failed leave-one-out | **1**: 3aa6fb7a, `reflect(H)[self]`, AVAILABLE_REACH; both folds had NO_PROPOSAL, so the evidence did not survive removing a demonstration | **1**: kf892487f1049, `hull[self]`, AVAILABLE_REACH; 4 of 4 folds failed |
| certified | 0 | 0 |

**Evaluator-only** (dev60 only, from the funnel's answer-based categories):
- EVIDENCE_BUT_NO_OPERATOR is mostly FIT_BUT_ALL_WRONG: 18 of 25. Native memorized there, and the evidence
  that exists is not expressible as one G-grow operator, or not supported (section 2).
- NO_MEMORIZED_GROWTH_EVIDENCE spans NO_FIT_EXHAUSTED 11, NO_FIT_DEADLINE 7, FIT_BUT_ALL_WRONG 7,
  CERTIFIED_CORRECT 5 and NATIVE_ERROR 2.

**Native failure stages** (observable): see the cross-tables in the JSON. No single native stage dominates
any class.

**Engineering defects in frozen native v23** (recorded as ENGINE_ERROR, not reasoning results):
- `ValueError("invalid literal for int() with base 10: 'h'")` in `_induce_composed`, on kd506f38dd7d6. It is
  triggered by the frozen assets.
- `KeyError('window')`, a native crash on dev60, recorded in the funnel.

Any fix must be a separate experimental arm; native v23 stays frozen.

## 2. Declared diagnostic (decided before running, 2026-10-18, 13:05Z)

**The undetermined class.** The logs cannot separate "insufficient support" from "inexpressible", and
that split decides whether any revision is justified.

**The rule.**
- **Cases:** every dev60 task in EVIDENCE_BUT_NO_OPERATOR (25), real tasks on this machine, so
  re-extraction reproduces the logged evidence.
- **What runs:** only E's evidence extraction (same code) and G-grow searches over that evidence.
- **Outputs, per view:** demonstrations covered, joint fit, and the number of singly expressible instances.
- **Classes:**
  - INSUFFICIENT_SUPPORT;
  - GROUPING_CONFLICT: instances expressible singly but not jointly; a typed applicability or grouping
    revision could address it;
  - INEXPRESSIBLE: even single instances have no G-grow expression; the language lacks the operation for
    this evidence;
  - NOT_REPRODUCED.
- No answer is read; nothing is installed or certified.
- Gate 0 is decided from this table.
