# Hybrid ceiling test on C2-dev: result (2026-10-13)

**Label: SYNTHETIC, ORACLE-ASSISTED DIAGNOSTIC. Not prediction accuracy.**

- **Script:** `cora_hybrid/ceiling_dev.py`, giving
  `outputs/hybrid_c2_dev/ceiling_summary.json`.
- **Corpus:** C2's 12 families × seeds 9100–9104 (60 tasks). This is
  disjoint from C2's evaluation seeds and never used to score C2.
- **Arms:** the frozen native_v1 notebook ran unchanged twice:
  - **A, native:** 3 demonstrations, then the test input;
  - **B, answer-given:** the same 3 demonstrations plus the true test pair as
    a 4th demonstration, then the same test input.

  Both returned rc 0, in 4,139 s and 4,028 s on 4 workers.

**What B measures.** In B the answer is a demonstration. Any program that
fits all 4 pairs therefore outputs the answer. B success means only that
native's bounded language and search reach and accept a rule consistent with
the answer. It is never an accuracy claim, and the answers are never used in
any blind procedure.

| | tasks |
|---|---|
| A native exact | **31 / 60** |
| B answer-given exact | **50 / 60** |
| exact only with the answer (ceiling) | **19** |
| exact only without it | 0 |
| not reached even with the answer | 10 (d_diag_drop 5, f_layer_frame 5) |

| family | A | B | B only |
|---|---|---|---|
| multicolor_majority | 0 | 5 | 5 |
| d_layer_size | 0 | 5 | 5 |
| f_diag_mirror | 1 | 5 | 4 |
| bbox_fill_L | 3 | 5 | 2 |
| recolor_by_size, halo, same_color_sizes | 4 each | 5 each | 1 each |
| translate_down, g_row_extend, g_mirror_complete | 5 each | 5 each | 0 |
| d_diag_drop, f_layer_frame | 0 each | 0 each | 0 |

## Reading

**Joined with the C2 CORA_ONLY score** (`records/C2_CORA_ONLY_SCORE_20261013.md`;
the same families, other seeds):
- multicolor_majority, d_layer_size and f_diag_mirror were claimed in 10 of
  10 C2 tasks and right in only 0–1 of them.
- Here, with one more demonstration, native expresses and accepts the
  correct rule in 14 of 15.

So for these families the failure is **not expressibility**. With 3
demonstrations native picks, and accepts, a different rule that fits them
but does not generalize: under-determined hypothesis selection plus false
acceptance.

**Bounded expressibility.** d_diag_drop and f_layer_frame are not reached
even with the answer as a demonstration. This is a bounded-search
observation, not proof of inexpressibility.

**What it bounds for "neural proposes, CORA certifies".** If a neural
candidate were correct, up to 19 of 60 more tasks could become expressible
on this synthetic set. Even then, certification would have to come from the
training demonstrations alone, under leave-one-out. This is an upper bound,
not an expected gain.

**The real-ARC counterpart** is the failure funnel's dev60 oracle probe
(`cora_funnel/oracle.py`) and whole-harness step (`cora_funnel/harness_run.py`).
