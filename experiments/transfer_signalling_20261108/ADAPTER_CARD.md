# T5 adapter card: signalling logic models (CellNOpt-style)

**Status:** frozen for the held test with PROTOCOL.md, amendment 1; see FREEZE.json. No held item has been scored.
Every number on this card is development.

## The loop in this domain

1. **Propose a program.** A program is a logic model over the prior network. Each node's value is the OR of its
   active terms, and each term is the AND of signed inputs.
2. **Check it on the observations.** The checker simulates the steady state of every training condition: stimuli
   are on, and inhibited nodes are forced to 0. It compares each readout with the data, binarised at 0.5.
3. **On failure, describe what is missing.** For each readout, the description lists the training conditions where
   it is measured ON but predicted OFF. For those conditions, it also lists the conditions that must stay OFF. The
   reverse case is described in the same way: measured OFF but predicted ON, with the conditions that must stay ON.
4. **Build the missing piece.** All pieces go into the failing readout:
   - a new edge: one signed input;
   - a new gate of two inputs;
   - a gate that extends an active term with one more input.

   Each piece is scored only against the failure description. Each source must not be downstream of its readout, but
   pieces added in the same round can still close a loop between readouts. A cyclic program is then simulated by
   synchronous iteration, and bits that do not settle are NA, which count as wrong.
5. **Check again.** This is a minimal repair: the current program is kept, and each piece is added only if it lowers
   the training errors. Steps 3 to 5 repeat for up to 3 rounds.
6. **Keep the pieces only if they help on held checks.** The growth is rebuilt inside 4 internal folds of the
   training conditions. The grown program is kept only if the rebuilt growth's fold errors are no worse than the
   static program's. This bar of 0 was set in development.

## Arms

- **Static:** the prior network's model space, with the CellNOpt preprocessing:
  - remove non-observable and non-controllable nodes;
  - compress single-input and single-output nodes;
  - expand AND gates of up to 2 inputs.

  The program is chosen with the fewest training errors, then the fewest inputs, then the smallest bit string, by
  iterated local search with fixed seeds.
- **Grown:** the loop above.
- **Shuffled control:** the same loop, except that, in each round, one Sattolo cycle over the training columns moves
  each failure description's condition sets.
  - The cycle covers the t1 and t0 columns together, so a moved column can change time point.
  - The readout and the direction (ON or OFF) of each failure are kept.
  - This is weaker than a shuffle within each time point (PROTOCOL.md, section 4).
- **Classical comparator:** CellNOpt's objective, run over the static space under CellNOpt's binary genetic algorithm
  with the gaBinaryT1 defaults. The objective is the squared deviation over t1 and t0 divided by 2, plus 1 per NA
  prediction, plus nDataPts × 0.0001 × nInputs / nInTot, all divided by the measured t1 points. R is not installed,
  so this is a Python re-implementation from the package's documented objective. Its scores have not been checked
  against R.

## Reused and rebuilt

| Part | Reused or rebuilt | Where |
|---|---|---|
| Bit-column representation (one bit per condition, Python ints) | idea reused | Boolean-network core, `experiments/universality_boolean_bbm_20261103/u6/bn.py` |
| Expression evaluator used by the checker (`simulate_core` recomputes every final program's steady state with the same step count and oscillation rule, and must agree with the fast simulator) | reused as is: `u6.bn.evaluate` | same file (sha256 66bd2d08...) |
| Paired bootstrap over tasks (10,000 resamples) | reused as is: `u6.stats.Bootstrap`, `diff_of_ratios` | `u6/stats.py` (sha256 aa3ff994...) |
| SIF and MIDAS parsing, CellNOpt preprocessing | rebuilt | `t5/data.py` (209 lines) |
| Steady-state simulator with CellNOpt semantics, binarised checker | rebuilt | `t5/model.py` (211 lines) |
| Local search, least-error vote (written, not used by the arms), CellNOpt objective and genetic algorithm | rebuilt | `t5/search.py` (241 lines) |
| Failure description, piece builder, minimal repair, rebuilt-fold acceptance, shuffled control | rebuilt | `t5/grow.py` (278 lines) |
| Tasks, hash splits, synthetic-from-real-network generator | rebuilt | `t5/tasks.py` (204 lines) |

**Lines of code:**
- The adapter is 1,143 lines in `t5/`, plus 466 lines of scripts and 131 lines of tests.
- It reuses 356 lines of core: 268 in `bn.py` and 88 in `stats.py`. Only the evaluator and the bootstrap are called.

The reuse is therefore light. The loop's structure transfers, but most of the domain machinery had to be written for
this domain.
