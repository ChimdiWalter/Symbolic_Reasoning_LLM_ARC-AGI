# Construction below the library (started 14 November 2026)

Author: Chimdi Walter Ndubuisi. Chosen by the author on 14 November 2026 after the run of evidence across several
failures did not meet its criterion (`records/CORA_NEXT_DECISION_20261114.md`). The question: can removed library
operations be rebuilt from building blocks smaller than library operations? CPU only, no model. Terms set by the
author: the design goes to the independent review before any code of the new experiment, and any full run waits
for its check of the freeze.

Nothing in this folder is a result yet.

- `pilot_five_nodes.py`: stage 0, a configuration pilot on development names only (never a result). The frozen
  episode of the earlier experiment, read-only, with three settings changed together: size limit of the search 5
  nodes instead of 4, bank cap 1,500,000 instead of 250,000, allowance 60 processor seconds instead of 10. Because
  they change together, a difference is not an effect of depth alone. Outputs in `pilot_five_nodes_out/`; read by
  `pilot_compare.py` into `pilot_compare.json`. Outcome on the 15 eligible development names: no right first fit
  gained in any arm; seven new first fits, all wrong; no five-node search was exhaustive (26 of the 51 fruitless
  ones ended at the allowance, 25 reached the cap on function-valued entries); search time 15 to 17 times that at
  four nodes.
- `census_source.py` and `census_source.json`: how large each library operation's own definition is, counted from
  the library's source by parsing it (nothing executed). Sizes are upper bounds on description length.
- `census_against_outcomes.py` and `census_against_outcomes.json`: those sizes beside what the run of 14 November
  could and could not rebuild (that run's numbers are not yet audited).

- `census_syntax.py` and `census_syntax.json`: which Python constructs the library's source uses (the basis for a
  block set that is not a matter of taste).
- `census_closure.py` and `census_closure.json`: how many operations could be regrown step by step, with and without
  cycles, by the source's own decomposition (bounds; nothing run).
- `pilot_compare.py`: reads the pilot beside the four-node development rehearsal.
- `PROTOCOL_DRAFT.md`: the design of the experiment (draft 1 went to the independent review before any code; the
  current draft is draft 2 with its amendments).

Run from the repository root. The census: `python3 -I experiments/below_library_20261114/census_source.py <out.json>`.

## The experiment's code (BL1), added 14 November 2026

Specification: `PROTOCOL_DRAFT.md` (the frozen text will be `PROTOCOL.md`). A development comparison on a known
constructed benchmark; every number from the 20 development names is "development only". Method credit: bottom-up
enumerative synthesis with observational equivalence and typed component-based synthesis are standard; the library
is arc-dsl by Michael Hodel (MIT). Nothing new is claimed about the method.

### Question in one paragraph
An operation X of the library is hidden with its whole family and is known only through examples of its inputs and
outputs. Two fixed two-stage systems, each selected on fit alone and each allocated 3,800,000 candidate
combinations for a target (1,900,000 to each of its two 36-example searches), try to rebuild it: *library-only* (the remaining library at four nodes, then at five) and *smaller-blocks*
(the library with the blocks of a restricted language C at four nodes, then C alone at a size limit s). Six
searches for a target: L4-9, LC4-9 (nine examples), L4-36, L5-36, LC4-36, C-36 (36 examples). The primary reading
compares "rebuilt by a system" (its selected expression agrees with X on the whole final panel) on the committed
eligible targets outside the development names whose source body has at least seven census nodes.

### Modules
- `bl_frozen.py`: before anything is imported from stage A or the operations study, checks the sha256 of every
  imported module and of the three data files of the frozen loader against stage A's `FREEZE.json`; refuses to
  run on a difference.
- `presets_bl.py`: every preset (roles 0-8 / 0-35 / 36-65 of the 66 generator examples, limits, guards, the memory
  ceiling, the search table, the two systems, the seven retained operations, the strata and the 28 control names
  as literals computed once from `census_source.json`). `SIZE_C` is 4, set on 14 November from `pilot_s.json` by
  the 80% rule of protocol section 6, and given again by the same rule under the combination budget
  (`pilot_s_2.json`). `MAX_COMBINATIONS` is 1,900,000, from `derive_n.py` (record `N_RECORD.json`, made from
  `ticks_measure.json`); processor time is then a safety limit of 600 seconds, an infrastructure stop.
  `CALIBRATION_MIN_K` is 19: an amendment by the author on 15 November, after the setup pass gave K = 19 and
  before any outcome (protocol section 9); it was 20 in the drafts.
- `blocks_c.py`: the executable catalogue of C (68 blocks in the order of the protocol's table). Every block
  checks its own arguments and validates what it returns, and what any function it calls returns, on every call.
  `check_tree` checks an expression tree statically.
- `guards_bl.py`: the guard of a batch of evaluations (processor time), the resource stop, the checked call, the
  reading of the largest address space of the process.
- `search_bl.py`, `gen_bl.py`: local copies of the frozen enumerator and generator with one kind of change (a
  memory failure is never an ordinary error); `search_bl.delta` and `gen_bl.delta` are the differences, and a
  test rebuilds them. The copy of the enumerator has a second listed change: it returns its count of candidate
  combinations (`ticks`) and can be given a budget in that count (`max_ticks`; presets `MAX_COMBINATIONS`). A
  search stopped by it ends as `combination_budget_used_up`, a bounded ending.
- `build_bl.py`: what one search is given for the block sets L, C and LC, with neutral parameter names; the
  wrapper around every library operation (memory failure; a container never holds a function; the arity rule;
  the record of function-making); the evaluator `eval_tree_bl`; the check that no hidden name is reachable.
- `episode_bl.py`: one target. `Records` opens the roles one at a time. Steps: setup (eligibility), the two
  nine-example searches, the four 36-example searches, the two selections, the final panel, the final checks,
  the witness of a control. Each step is sealed (sha256 in the journal) before the next may read its data.
- `summarize_bl.py`: `SUMMARY.json` (the primary with its states met, not_met, provisional, not_interpretable; the
  calibration; the secondary tables; the development names apart; costs; reconciliation with the committed setup
  record). The paired table is on the committed eligible targets of the longer stratum outside the development
  names; the cohort that must be complete is every target the setup record commits as eligible, whatever its
  stratum, the development names included.
- `run_bl.py`: the runner (below). `tests/`: the tests, including refusals in fresh processes.
- Diagnostics on development names, never results: `diag_function_cap_by_block_set.py`,
  `diag_speed_c_search.py`, `sensitivity_l5_rule.py`, with their outputs. `check_generator_copy.py` compares the
  copy of the generator with the frozen generator, operation by operation, over a roster (nothing is searched).
  `check_process_dependence.py` compares, across two fresh processes with different memory layouts (address
  randomization on and off), the values of the setup step of every development name and of whole episodes of a
  few of them. `ticks_measure.py` measures, on the development names, how many candidate combinations each kind
  of search counts and how many it counts in a processor second. `load_check.sh` makes the development run again
  beside a processor burner on the other thread of the same core, and `compare_runs.py` compares two output
  folders field by field (`load_check_compare.json`: no difference outside times and memory).
- `witness_manifest.json`: the evaluator's witnesses of the controls and of the development control (the draft
  `WITNESS_DRAFT_BY_THE_LEAD.json`, unchanged, after its static check `check_witness_draft.json`). Read only in
  the witness step of an episode, after the selections are sealed and the final panel is open, and by the summary.
- After the run (covered by the freeze, taking no part in the run): `after_run_bl.py`, the checks made before any
  number is read out; `earlier_result_check.py`, the earlier result as a check (protocol section 9).
  `rehearse_run_once_path_bl.py` rehearses the whole one-launch path, these two included, on a copy of this folder
  with a few development names.

### Run (from the repository root)
    P="env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B"
    $P -m pytest -q -p no:cacheprovider experiments/below_library_20261114/tests
    $P experiments/below_library_20261114/run_bl.py --setup-only <setup.json> --roster dev|all
    $P experiments/below_library_20261114/run_bl.py --pilot-s <pilot_s.json>
    $P experiments/below_library_20261114/run_bl.py <outdir> --roster dev [--targets a,b] [--dev-size-c N] [--setup-record setup.json]
    $P experiments/below_library_20261114/run_bl.py --make-freeze <FREEZE.json> --setup-record <setup.json>
    $P experiments/below_library_20261114/run_bl.py <outdir> --roster all --freeze <FREEZE.json> --setup-record <setup.json>
    $P experiments/below_library_20261114/run_bl.py --summarize <outdir> [--setup-record setup.json]
    $P experiments/below_library_20261114/after_run_bl.py --out <outdir> --freeze <FREEZE.json> --setup-record <setup.json> --status <run.status> [--write-manifest] [--report <r.json>]
    $P experiments/below_library_20261114/earlier_result_check.py <outdir> <record.json>
Every mode sets the ceiling on the memory of the process first. `--roster all` refuses without the freeze and the
committed setup record, when presets `SIZE_C` is not set, when any hash differs, when the output folder is not new
or empty, or when a receipt of an all-roster run exists (whatever its output folder: the run is launched once and
never resumed); it writes an exclusive read-only receipt first. No variable or flag moves the receipt folder.
`--make-freeze` refuses a setup record made by other code than the files being frozen. `--setup-only` never
searches and opens no fit role and no final role. When the address space of the process comes near the ceiling,
the unit of work is recorded as an infrastructure stop and the process ends with exit status 86.

### Seeds of this experiment
The pooled inputs of a target are drawn under this experiment's own tag (`presets_bl.SEQ_TAG`). The 66 generator
examples of a target are made by the same generator as in the earlier studies; on the 20 development names their
first 36 are the earlier studies' 36 (`earlier_result_check_dev.json`).
