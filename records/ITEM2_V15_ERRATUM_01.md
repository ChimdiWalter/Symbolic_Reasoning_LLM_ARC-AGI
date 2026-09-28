# Item-2 v1.5 erratum 1: corrections from the pre-run adversarial review

Date 2026-09-28. Scope: the v1.5 protocol, implementation and tests. No v1.5
test group existed at any point, and no selector had been fitted or scored
on any real data. First freeze: commit 89ac728 (protocol sha256
dc02e1ae..., manifest sha256 16dc3ef7...). This erratum supersedes that
freeze; the new identities are in the manifest and in `RESUME.md`.

## The review

One reviewer, distinct from the author. Its tool calls were scanned
afterwards:
- it wrote only to the scratchpad;
- on real records it called only label-free functions: building queries and
  views, the standardizer, the matched shuffle, the fold construction and the
  differing step;
- it fitted or scored nothing on real data.

It confirmed:
- `signflip_p` is exact, valid for fixed models scored on held-out groups,
  and conservative for D against D+F;
- PASS was impossible without gate B;
- design columns line up and inactive blocks stay at exactly zero weight;
- the Newton fit, ties, NLL, units, group ordering, the twin-fold mapping and
  the twin swap are correct;
- in balanced groups, token priors, the grammar state, candidate order and
  the anchor or contrast role cannot beat one half;
- the shuffle uses no label and never draws F from the same group;
- the seed ranges are disjoint;
- the integrity checks match real record formats;
- no imported project module lies outside the hashed trees;
- all 43 tests passed.

## Findings and corrections

1. **Blocking: the ladder issued negatives the data contradict.**
   - A significant increment below delta_min (for example 0.044 with
     p = 7.8e-8) was labelled DEMONSTRATIONS_SUFFICIENT.
   - The same label was issued when nothing selected (A, B and D failed,
     C passed).
   - TWIN_ONLY was issued on an underpowered test.

   Corrections:
   - A negative label now needs a decisive failure: the comparison is not
     significant and its one-sided 95 percent upper bound is below
     delta_min.
   - DEMONSTRATIONS_SUFFICIENT also requires D itself to select above
     chance.
   - TWIN_ONLY sits below the powered-size rule and requires a decisive test
     failure.
   - A significant increment below delta_min is MIXED_OR_INCONCLUSIVE.
   - Regression tests cover all three cases.
2. **Major: "beyond demonstrations" was overclaimed.** The failure evidence
   is computed by the reasoner from the same demonstrations. The reviewer's
   synthetic case, F = h(D) + noise with no information beyond D, passed
   both B and C, because the linear D_RICH model cannot express h and the
   shuffle matches D only approximately (real-pool donor correlation 0.73
   to 0.78 per field).
   - The claim is narrowed to "beyond the D_RICH demonstration summary".
   - Shuffle donors are matched within the pair's family first (which also
     fixes the grammar state), then across families.
   - The report gives the shuffle's fidelity to D.
3. **Major: verification was never gated.** Where the other candidate fails
   to reproduce the demonstrations, running the two candidates already
   decides the query. New **gate H** requires the paired increment over D on
   verification-ambiguous queries to be at least zero, over at least 30
   groups with such queries.
4. **Major: thin training.** 540 weights are fitted on 336 twin queries
   covering 19 of the 45 key-feature pairs.
   - Twin cross-validation folds now keep token pairs together, so held-out
     pairs are unseen, as test pairs can be.
   - The test report breaks results down by seen and unseen pairs and by
     family.
   - Every negative is stated as conditional on this selector and this
     training resource.
5. **Major: the generator kept running after a failed freeze check.** It now
   stops at the first failed check, and keeps the record that shows it.
6. **Minor:**
   - The admission pilot's admitted groups were not excluded. They now are
     (6 targets, 3 groups; the set is now 477 targets and 72 groups, sha256
     `6a5761d6...`). Skip provenance of never-run pairs is not collected.
   - The recorded target tokens were not checked against the re-derived
     programs; they now are.
   - Statistics ran before the floor, and the evaluator crashed below it.
     Now nothing is computed below 72 groups.
   - No convergence check existed; every Newton fit must now converge.
   - Single-threaded BLAS was set only by the shell script; it is now also
     enforced inside the evaluator before numpy loads.
   - The clock was read twice at the cap; it is now read once.
   - The delta_min justification's "an increment cannot exceed the
     standalone signal" was wrong; it is withdrawn.
   - The joint power of gates A to D at delta_min is about 0.45; this is now
     disclosed.
   - The pilot text on `other_candidate_fits` is corrected: it was recorded
     but not read.

Noted and accepted:
- the matched shuffle couples pairs of test groups, which makes gate C's
  sign-flip test mildly anti-conservative;
- gate F cannot fail by construction.

## Not changed

delta_min, alpha, the 288-group target, the floor, the caps, lambda, the
views, the conditions, the training resource, the test generation law, the
seeds and every statistical test. No second review round.
