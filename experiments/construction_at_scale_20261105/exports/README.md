# Worked example export: generated task t52073858 (world W1)

`WORKED_EXAMPLE_t52073858.json` holds the process record of one generated task of the construction test at scale, for
the worked example of the ARC paper (Section 2, Figure 3). Every section names its source files with their sha256.
All sources are committed run records in `runs/generated/W1/runs/`, plus `PROTOCOL.md` for the size of the
schema space.

**Content rule.** The file holds process fields only: no predicted grid, no held query answer and no test output.
Demonstration grids appear by size only. Where a record mixes predictions with process fields, the predictions
(`preds`) and the structure parameters (`thetas`) were dropped in code. A field missing from the records is written
"not recorded" and is never filled in from the implementation's policy. The two pickles (`prep_v4/records.pkl`,
`cas_arms/gates_spec.pkl`) are this run's own files. They were read with `python3 -I` and an unpickler that accepts
built-in types only.

**The chain, as recorded (W1 removes compress, downscale, trim and upscale; this task is built on compress):**
1. **Observe.** 4 demonstrations. Recorded shape relation: "output is never larger than the input; the amount
   removed varies".
2. **Represent and search.** The base search over the starting language stopped on its budget: 150,000 calls,
   complete to cost level 9, 4,668 programs in its bank, no fit.
3. **Fail.** The deeper probe at four times the budget also stopped without a fit: 600,000 calls, level 11. The
   diagnosis recorded "an operation the program needs is missing" as supported, so the decision was
   INVENT_NEW_OPERATION. A matched longer static search also found no fit, stopping on its CPU cap (378.515 against
   378.15 CPU-s, level 14).
4. **Typed hole.** Three ranked sketches were recorded. The admitted candidate came from the top one, `?(I)` (score
   0.6615): one unknown operation applied to the input. It must map each demonstration input to its output (10x10 to
   2x2, 7x8 to 3x4, 6x11 to 2x2, 10x10 to 4x4). The slot's type is not recorded.
5. **Candidates tried.** The schema space has 211 pre-registered operator structures, and the hole's specification
   passed 4 candidates (`n_candidates`). One was sent to the gates on each seed: SEL:fore:fore on seed 0, and
   SEL:fore:multi on seeds 1 and 2. SEL structures keep the rows and columns that satisfy a predicate. The
   identities of the other three candidates, and the admitted candidate's rank among the four, are not recorded.
6. **Checks.** The admitted candidate passed all three gates:
   - no starting-language program reproduces it (`duplicate` false, no witnesses; the length bound is not recorded);
   - no solved task breaks (14 checked, none lost, no prediction changed);
   - another unsolved task, taa19c2e9, fits (with `vmirror` around it).

   It was promoted and recovered the task on every seed. The charged costs were 48.445, 52.683 and 52.684 CPU-s.
7. **Retained.** SEL:fore:multi is in the committed grown bank (with SEL:multi:all and SEL:multi:multi). SEL:fore:fore
   is not, and the reason is not recorded.
8. **Reused.** Five later tasks, scored after the bank was committed, ran SEL:fore:multi in their committed reuse
   program. All five were solved: t1039746e, t27d7e317, t8fbb99ee, tbb7eb1e5 and te56f3b91.
