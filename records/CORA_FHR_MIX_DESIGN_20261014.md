# CORA-FHR mixed-coverage causal pilot: design and stop rule (2026-10-14; DEVELOPMENT ONLY)

**Status.** Frozen before any run. It is development-only: no final split, no prospective claim. A
prospective version would need its own frozen protocol and the user's authorization.

**Why.** On C4, E's evidence equals C′'s by construction: every growth correspondence in a G-family task
is a memorized `pattern` fallback. So H3 (that failure evidence causes the gain) cannot be tested there.

**Corpus.**
- Source: `cora_fhr/corpus_mixed.py`, which writes `outputs/cora_fhr/mix_dev.json` (8 tasks, seeds
  13000+).
- Every scene mixes two kinds of object with the same added colour:
  - kind N grows by `ring(8)[self]`, which native explains;
  - kind G grows by `ring(8)[part_minority]`, which needs construction.
- Generator checks: kind N is native-explainable, kind G is neither native nor reach.
- **M1** (4 tasks): the kinds differ by colour.
- **M3** (4 tasks): same colours; the kinds differ by size only.

**Static feasibility** (`mix_dev_feasibility.json`; generator-side proxies, not native records):

| proxy | finds `ring(8)[part_minority]` and predicts the test? |
|---|---|
| E (kind-G correspondences only) | yes, 8 of 8 tasks |
| C′ (all correspondences pooled) | no; no single expression fits (8 of 8) |
| C″ (C′ grouped by colour signature) | yes in M1, no in M3 |

**Arms.**

| arm | evidence |
|---|---|
| A | frozen |
| B | matched search, f_B = 1.33 (provisional) |
| E | native's authentic `pattern` fallbacks |
| C′ (C2) | every native growth correspondence from the same extraction, with no failure filter |
| C″ (C3) | C′ regrouped by colour signature; a stronger blind control, added here |
| D | shuffled: a donor's authentic evidence from c4_dev_v2 D1/D2, which uses other rules (cross-family; Amendment 2 C, development use) |

All arms share the same:
- grammar;
- extraction budget;
- native gate;
- adaptive LOO;
- tie rule;
- commit rule.

Answers are read only by `cora_fhr.evaluate` / `dev_table`.

**Prerequisite gate (stop rule; decided now).** The pilot PASSES only if **both** hold:
1. On at least 2 of the 4 M3 tasks:
   - E is certified with the extension and correct;
   - C′, C″, D and B are not certified-correct;
   - E's selected proposal differs from C′'s, or C′ makes no proposal.
2. E has 0 wrong certificates over all 8 tasks.

**If it fails:** stop. Report the stage that failed (native coverage differs from the design, native
gate, routing, LOO, tie). Do not enlarge or retune.

**Expected confound, stated now.** In M1, colour clustering (C″) should match E. Only M3 can show
failure evidence carrying information that blind clustering lacks.

**Every attempted case is recorded:** `rows_mix_dev.jsonl` and `dev_table_mix_dev.md`.

**Run.** `outputs/cora_fhr/followup_mix.sh`, detached. It waits for the C′ run to finish, so the
footprint stays at 4 workers.

**Added caveat (2026-10-14, before any pilot result).** In M3 the kinds differ by size. Even if E beats the
colour-only blind controls there, that alone does not show causal use of failure evidence. A follow-up
would need an equally equipped size-aware blind control, for example C′ regrouped by object size.

**Run log.**
- **Run 1** (22:03 to 22:25Z) crashed before writing any row. The C″ arm's group label `<view>|<colours>`
  reached `SegmentationVariant(...)` in the tie check. No result was produced or seen.
- **Fix:** the tie check now parses `prop["view"].split("|")[0]`. This is a no-op for every existing arm,
  and `tests/test_fhr.py` passes.
- **Run 2** reruns all 8 tasks unchanged. The crash log is kept as `outputs/cora_fhr/followup_mix_run1_crash.log`.

## Result of run 2 (2026-10-15, 01:13Z; `rows_mix_dev.jsonl`, `dev_table_mix_dev.md`)

| family | arm | proposed | engine accepted and used | all folds passed | certified correct | wrong |
|---|---|---|---|---|---|---|
| M1 (colour) | E | 4 | 3 | 2 | **2** | 0 |
| M1 | C″ (colour clusters) | 4 | 2 | 2 | **2** | 0 |
| M1 | C′ (pooled) | 0 | 0 | 0 | 0 | 0 |
| M1 | D (other-rule donor) | 3 | 0 | 0 | 0 | 0 |
| M1 | A, B | — | — | — | 0 | 0 |
| M3 (size only) | E | **3** | **0** | 0 | 0 | 0 |
| M3 | C′, C″ | 0 | 0 | 0 | 0 | 0 |
| M3 | D | 1 | 0 | 0 | 0 | 0 |
| M3 | A, B | — | — | — | 0 | 0 |

No arm lost an answer.

**Stop rule: FAILED.** E was certified-correct on 0 of the 4 M3 tasks; the rule required at least 2.

**Where it failed.** In M3, E's failure evidence did change proposal selection: E proposed the novel
operator (NEW_COMPOSITION) on 3 tasks, while both blind controls proposed nothing. But native's own gate
rejected the program with the extension installed on all 3 (ENGINE_REJECTION). The fourth task had no
fitting operator. The frozen engine apparently cannot dispatch the constructed operator and its own halo
rule to objects that differ only by size.

**In M1:** E beat pooled C′ (2 vs 0), but colour clustering C″ matched E (2 vs 2). That gain is
therefore not attributable to the failure record.

**Conclusion (development only):**
- Authentic failure evidence can change which operator is proposed (M3: 3 vs 0).
- It has not yet produced a held-out correctness gain over an equally equipped blind control.
- As the rule requires, the study is not enlarged or retuned.
