# Adapter card: spreadsheet string transformations (test T2)

Study folder: `experiments/transfer_spreadsheet_20261108/`. Author: Chimdi Walter Ndubuisi.

## The loop and what the adapter supplies

| step of the loop | in this domain | code |
|---|---|---|
| 1. propose a program from the current building blocks | bottom-up search by program size, merging programs that give the same values on the training examples, under a budget of operation executions | `t2/dsl.py: search` |
| 2. check it on the observations | the program must reproduce every training output exactly | `t2/dsl.py: search` |
| 3. on failure, describe what is missing | the base search's string programs are ranked by how much of every wanted output they explain as a prefix, a suffix or an inner part. The gap left by each of the 3 best (and by the whole output) is a hole: one (source string, wanted string) pair per training example | `t2/grow.py: failure_description` |
| 4. build the missing piece | a piece of the structure space that maps every pair of a hole exactly, or a constant when the hole is the same string everywhere | `t2/pieces.py: consistent`, `t2/grow.py: candidates` |
| 5. check again | search again with the piece added, at the base budget (at most 3 candidates) | `t2/grow.py: try_candidates` |
| 6. keep the piece only if it helps on held checks | leave-one-out rebuilding: for each training example, rebuild the piece from the other examples' pairs, put it in the program in place of the piece, and require that program to reproduce the left-out example | `t2/grow.py: loo_accept` |

**Building blocks.** The base building blocks are the SyGuS-Comp string grammar of the SLIA track (strings with
linear integer arithmetic):
- concatenation, first-occurrence replacement, character at, integer to string, substring, addition, subtraction,
  length, string to integer and index of;
- the task's own grammar constants.

Conditionals and Boolean operations are left out of every arm, because with 2 or 3 examples a conditional can
memorise each example.

**Structure space.** A built piece is drawn from 13 spreadsheet text structures in the style of FlashFill and
BlinkFill. Each one becomes a unary string operation once its parameters are fixed:
- field of a split; k-th token of a character class; text before, after or between delimiters;
- keep or delete a character class; replace every occurrence;
- upper, lower, title or capitalised case, alone or around a field, token, before, after or between;
- initials; trimming; collapsing spaces.

The delimiters are a fixed list of 25 punctuation and space characters plus the task's own short constants.
Each task has 5,645 to 6,794 pieces (the median on the development tasks is 5,645).

**Checker.** Exact string equality on every example.

**Selection rule.** Within each arm, the first fitting program in enumeration order is the answer. For the grown
arm, it is the first candidate that fits and passes leave-one-out, in candidate order: sketches in order (the whole
output first, then partial programs by explained characters), then pieces in canonical structure order.

## Reused and rebuilt

- **Reused ideas, rebuilt code.** No module is imported from the earlier studies. The adapter re-implements their
  conventions:
  - the list study's typed bottom-up enumerator (`experiments/capability_growth_20261027/cgrow/u3/listdsl.py`:
    enumeration by size, observational equivalence, an execution budget, first fit);
  - the shared self-extension core (`cgrow/selfext_core.py`): holes as typed (input, target) pairs, ranked sketches
    (the whole-output hole and holes left around known operations), a piece taken from a pre-set structure space
    when it is consistent with every hole pair, a retry at the base budget, and a candidate cap;
  - the grid construction studies (`construction_at_scale_20261105`, `natural_growth_20261105`), which use that core.
- **Rebuilt for this domain:**
  - the string language and its semantics (SMT-LIB 2.6);
  - the failure description by prefix, suffix and inner gaps against the best partial programs (the grid and list
    studies used inverse operations instead);
  - the structure space;
  - leave-one-out rebuilding as the acceptance rule. The core's gates (novelty, regression on solved tasks,
    validation on a pool) are not used.
- **Why not import the core.** Its plug-in interface expects integer-parameter structures and invertible unary
  operations over a shared task pool. For a quick development check, a self-contained adapter was faster and easier
  to audit.

**Lines of code** (Python, including comments):

| part | lines |
|---|---|
| language and enumerator `t2/dsl.py` | 219 |
| structure space `t2/pieces.py` | 226 |
| loop: failure description, construction, leave-one-out, arms `t2/grow.py` | 208 |
| runner `t2/run.py` | 180 |
| benchmark reader and preparation `t2/sl_parse.py`, `t2/prepare.py` | 302 |
| statistics `t2/stats.py` | 41 |
| total adapter | 1,176 |
| reused core imported | 0 |

## Arms

| arm | what it does |
|---|---|
| static | the base language, (1 + 3) x the base budget of executions |
| grown | base search at the base budget; on failure, steps 3 to 6 with up to 3 candidates at the base budget each |
| shuffled-failure control | as grown, but the pieces are built from another task's failure description (the next failing task in run order, cyclically) |
| classical comparator | bottom-up enumeration with observational equivalence over the base language plus every piece of the structure space, (1 + 3) x the base budget (a reference, not a gate) |
| grown without leave-one-out (secondary) | the first fitting candidate, with no acceptance rule |
