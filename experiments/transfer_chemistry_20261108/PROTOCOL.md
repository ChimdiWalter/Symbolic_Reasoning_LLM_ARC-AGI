# T3 chemistry protocol: enzyme reaction rules from a few examples (pre-registered)

Written on 8 November 2026 after development on development families only. No scoring-pool item has been run,
opened or printed. The sha256 of this file, the code, the configuration, the data manifest, the item pool and the
raw data are in `FREEZE.json`. Scoring runs only after the coordinator commits `runs/GO` (section 7 and
Amendment 1). A change after the freeze is a dated amendment with a new freeze, made before any held outcome.

**Label of every result:** real data; reconstruction of known enzyme transformations on held substrates, not
discovery.

## 1. Question and claim limit

**Question.** Does CORA's loop (propose from the building blocks, check, describe the failure, build the missing
piece, check again, keep it only if it helps on held checks) transfer to enzyme chemistry through an adapter?
Concretely: from k = 3 reactions of one enzyme rule family, does a rule built from the observed change give the
exact product on new substrates of that family more often than the best rule of a fixed published library?

**Claim scope.** The grown arm beats a fixed library of published rules and a shuffled change, and matches the
nearest-neighbour template baseline (development, section 8). Nearest neighbour stays a reference, not a gate: the
claim does not include beating it.

**Claim limit.**
- Held substrates come from the same families as the examples. A gain is reconstruction within a family, not
  discovery of new chemistry and not transfer across families.
- The static library is the published generalized rule set of Ni et al. 2021 applied to one substrate at a time
  (`ADAPTER_CARD.md`). Its rules carry no hydrogens and, for rules joining two substrates, only the template part
  of the second substrate. A gain over it is a gain over these fixed general rules used this way, not over every
  use of them.
- The nearest-neighbour comparator is a reference, not a gate. On development it matched the grown arm (section 8).

## 2. Data, families and items

Data and licences: `DATA_MANIFEST.md` (EnzymeMap v2, CC BY 4.0; Ni et al. 2021 rules via Pickaxe, MIT).

- **Rows:** EnzymeMap rows with source `direct` and steps `single` (as recorded in BRENDA, one step).
- **Main product:** the largest product (heavy atoms) that is not on the fixed cofactor list
  (`config/T3_CONFIG.json`, names resolved through EnzymeMap's own name table, plus the 44 Pickaxe coreactants)
  and has at least 3 heavy atoms. **Main substrate:** the non-cofactor reactant that gives the most mapped heavy
  atoms to the main product. Ties, unmapped substrate atoms and pairs that differ only in stereochemistry are
  dropped (`data/POOL.json` lists the counts).
- **Family:** EC number (four levels) plus EnzymeMap rule id. **Item:** one (main substrate, main product) pair of
  a family, deduplicated on the pair without stereochemistry.
- **Pool:** 33,565 items in 5,875 families.

## 3. Splits (development and held are disjoint)

- **Development families:** sha256("t3chem-dev-20261108|" + family) read as a fraction below 0.15: 903 families,
  151 with at least 8 items. Only these were used in development.
- **Scoring pool:** every other family with at least 8 items after removing every (substrate, product) pair that
  occurs in a development family: 681 families, 14,391 items.
- **Hash rule (salt fixed after the freeze, Amendment 1).** salt = the sha256 (64 hex characters) of the exact
  committed bytes of `runs/GO`, which the coordinator writes and commits alone after the pre-run review (section 7).
  Families of the scoring pool are ordered by sha256(salt + "|family|" + family) and the first 40 are scored. Within a family, items are ordered by sha256(salt + "|item|" + family + "|" + pair): the first 3
  are the examples, the next 5 are the held targets. **Held targets: 40 x 5 = 200.**
- **Shuffle partner:** the next scored family in the salted order whose rule id differs.

## 4. Task, check and arms

- **Task:** from the 3 examples (mapped substrate and product), predict the main product of each held substrate.
  The arms see the held substrate only.
- **Exact check:** canonical SMILES without stereochemistry (RDKit 2026.03.2, round trip). A held target is
  **recovered** when the arm's outcome set is exactly {true product}: the true product and nothing else.
- **Arms** (`ADAPTER_CARD.md`, `t3chem/arms.py`):
  1. **static:** the library rule with the most exact products on the 3 examples (then most covered, then fewest
     raw products, then name);
  2. **grown:** the full loop. If the static rule is exact on all 3 examples it is kept. Otherwise the reaction
     centre of each example is described and a rule is built at levels L0 to L6; a level counts when its piece
     reproduces all 3 examples; the chosen level has the most leave-one-out exact predictions (ties: the more
     general level, chosen on development); the piece is kept only if that count beats the static rule's exact
     count on the 3 examples, else the static rule is used;
  3. **shuffled control:** the grown arm with the build step fed the examples of the shuffle partner;
  4. **nearest neighbour (reference):** the L4 rule of the most similar example (Morgan radius 2, 2,048 bits,
     Tanimoto), backing off to the next most similar example when it does not match.

## 5. Pre-registered primary, secondaries and decision rule

**Primary.** Exact held recoveries, grown against static, paired on the 200 held targets: the difference in the
recovery rate with a 95% family-cluster paired bootstrap interval (10,000 resamples of families, seed
20261108), plus the two-sided exact McNemar test on the discordant targets.
- **Positive:** the lower bound of the interval is above 0.
- **Negative:** the upper bound is at or below 0.
- **Otherwise:** inconclusive.

**Control.** The same comparison for grown against shuffled. A positive primary is read as needing the family's
own change only if grown against shuffled is also positive.

**Reference (not a gate).** Grown against nearest neighbour, same statistics.

**Secondaries (reported, not gated):** the share of targets whose outcome set contains the true product, for
every arm; the grown arm with the other tie-break (the more specific level, reported as `grown_alt`); the loop
status counts (static sufficient, piece kept, piece not kept, no piece) and the chosen levels; the families with
at least one recovery.

## 6. Budgets and stop rules

- One detached scoring run (`launch/run_score.sh`, through `scripts/run_detached.sh` with `--slot`: setsid nohup,
  a shared CPU slot, nice 19, idle I/O; status in `runs/score/run.status` and
  `outputs/detached/transfer_chemistry_held/run.status`).
- **The slot queue is long** (13 jobs on 8 November), so the run may wait for a slot before it starts. That is
  fine: waiting costs no CPU, and the cap below counts CPU time, not wall time.
- **CPU cap:** 30 CPU-minutes. The runner checks before each family and stops at the cap with status
  `STOPPED_CPU_BUDGET`. Development cost per family: median 8.5 and mean 29.4 CPU-seconds (31 families, maximum
  170), so 40 families are expected to take about 20 CPU-minutes. If it stops, every statistic is computed on the
  families completed (a prefix of the salted order) and the result is labelled "stopped at the CPU cap".
- **Integrity:** the runner refuses to start unless (as amended by Amendment 2, which adds `runs/GO_AMENDMENT2`
  and keeps every other check):
  - no held result exists yet (`runs/score/families.jsonl`, `runs/score/summary.json`; under Amendment 2 the
    folder `runs/score/` must not exist at all);
  - `runs/GO` is plain ASCII, starts with the line `GO`, carries every field of section 7, is committed at HEAD and
    is unchanged since its first commit (the first committed GO is final);
  - GO's `freeze_commit` is the last commit on HEAD that changed `FREEZE.json` and holds these exact bytes;
  - GO's `freeze_json_sha256` is the sha256 of `FREEZE.json`, and every file hash in `FREEZE.json` matches;
  - the nonce is 64 lowercase hex characters, `pre_run_review` is a 40-character commit of the repository and
    `written_utc` is a UTC time;
  - the Python and RDKit versions match `FREEZE.json`.
  It derives the salt itself and records it, with the freeze commit, in `runs/score/run.status` and
  `runs/score/summary.json`.
- **No rerun** after a crash or a stop without a dated amendment written before any held outcome is opened.
- **Reporting:** `RESULT.md` with every number and its denominator, every negative as result, lesson, direction;
  then an independent post-score audit.

## 7. Custody

1. This protocol and `FREEZE.json` (sha256 of the code, the configuration, the manifest and the data).
2. Report to the coordinator.
3. An independent pre-run review.
4. The coordinator writes `runs/GO` and commits it alone (`git add <path>; git commit -m "..." -- <path>`). It is
   plain ASCII, one `key: value` field per line after the first:
   ```
   GO
   study: transfer_chemistry_20261108
   freeze_commit: <40-character hash of the last commit that changed FREEZE.json>
   freeze_json_sha256: <sha256 of FREEZE.json at that commit>
   pre_run_review: <40-character commit of the pre-run review>
   nonce: <64 lowercase hex characters, drawn once after the review, e.g. python3 -c "import secrets; print(secrets.token_hex(32))">
   written_utc: <YYYY-MM-DDTHH:MM:SSZ>
   ```
   The first committed GO is final; it is never redrawn or replaced.
5. One detached scoring run, with no argument:
   `sh /path/to/repository/experiments/transfer_chemistry_20261108/launch/run_score.sh`.
   A dry check of every refusal rule, which scores nothing: `python -I t3chem/run.py --mode score --check-only`.
6. `RESULT.md`.
7. An independent post-score audit.

Under Amendment 2, steps 3 to 5 are followed by: a delta review of the amendment; `runs/GO_AMENDMENT2`, written and
committed alone by the coordinator; and one detached rerun with the same salt (Amendment 2).

## 8. Development record (development families only; labelled development)

Development run `runs/dev_c40/` (31 development families completed of 40 planned before the development CPU cap,
155 development targets, k = 3, then the most specific tie-break):

| arm | exact | contains the true product |
|---|---|---|
| static library | 27 / 155 | 101 / 155 |
| grown (most specific tie-break) | 81 / 155 | 110 / 155 |
| grown (most general tie-break, frozen choice) | 85 / 155 | 115 / 155 |
| shuffled control | 27 / 155 | 101 / 155 |
| nearest neighbour | 76 / 155 | 107 / 155 |

- Grown (most specific) against static: 55 targets only grown, 1 only static; difference +0.348, family-cluster
  bootstrap 95% interval [0.219, 0.484]; exact McNemar p < 1e-14.
- Grown against nearest neighbour: 20 only grown, 15 only nearest neighbour; difference +0.032, interval
  [-0.097, 0.174]; p = 0.50.
- The shuffled control equals static on every target: a piece built from another family's change never passed the
  family's own checks, so the arm always fell back to the static rule.
- Loop status over the 31 families: static sufficient 3, piece kept 18, piece not kept 1, no piece 9.
- Extractor check: a rule cut from one example gives back its own product at every level on 40 of 40 development
  items (exactly and only it at L6 on 36 of 40); the fast checks agree with the full outcome sets on 1,329 of
  1,329 development checks.

## Amendment 1 (8 November 2026, made before any held item was chosen)

- **Reason.** Under the first freeze (commit `70d6a9a62a39e7224dc0b334519fe7df511c59b9`) the salt was the freeze
  commit hash. The designer makes that commit and could grind it, and a check on the salt string alone accepts any
  commit, including one with the same tree. Two other studies' pre-run reviews failed on this today.
- **Change.** The salt is now the sha256 of the exact committed bytes of `runs/GO`, which the coordinator writes and
  commits alone after the pre-run review, with a fresh 256-bit nonce (section 7). The runner derives the salt
  itself (the `--salt` option is removed) and refuses unless every rule of section 6 holds. The launcher now goes
  through `scripts/run_detached.sh` with `--slot`. `FREEZE.json` also records the Python and RDKit versions. The
  claim scope sentence (section 1) and the slot-queue note (section 6) were added at the coordinator's request.
- **Unchanged.** Data, pool, families, k, held count, arms, levels, tie-break, checks, primary, decision rule,
  CPU cap and development record.
- **Held items.** None chosen, run, opened or printed: there is no `runs/GO` and no `runs/score/`.
- **Refusal test.** On a scratch git repository holding a copy of the frozen files, `--check-only` accepted a
  well-formed committed GO and refused each case listed in `PROGRESS.md` (8 November, Amendment 1).

## Amendment 2 (8 November 2026, after a crash, made before any held outcome was opened)

- **What happened.** The single held run (GO commit `190756a6`, launched once at 07:11:22Z) stopped with exit code
  1 at 07:11:55Z after 3 of 40 families. In the 4th family the shuffled arm was cutting a rule from its partner's
  examples. RDKit's fragment writer (`MolFragmentToSmiles`) then raised "Pre-condition Violation: neither end atom
  traversed", and the error escaped `extract_rule`.
- **Cause.** RDKit keeps the direction marks of single bonds next to an E/Z double bond, which come from the input
  SMILES. A cut fragment that holds such a single bond but not its double bond can make the fragment writer fail,
  even with stereochemistry output switched off. Development ran 31 families and sampled the extractor (40 and 15
  items), so it never met such a case.
- **The fix** (`t3chem/chem.py`, `extract_rule`). Rules carry no stereochemistry. After parsing the two mapped
  molecules, the extractor clears chiral tags, bond directions and bond stereo, then cuts the rule; any remaining
  RDKit failure means "no rule at this level". Nothing else in the code that scores changed.
- **Development evidence** (`dev/amendment2_check.py`, output `dev/amendment2_check_development.json`;
  development items only):
  - 1,500 development items at 7 levels, 10,500 extractions;
  - identical rules on all 10,473 extractions where the frozen extractor works, with 0 differences;
  - rules produced for all 27 extractions where it fails;
  - every atom subset of five small E/Z molecules: the fragment writer fails on 100 of 635 subsets on the frozen
    path, and on 0 of 635 after clearing.
- **The same held set.** The salt stays the sha256 of the committed bytes of the original `runs/GO`
  (`8f91d8e54350686fc0ce3ce7da7cb7de5941c911597dc5a0b0955843de9089bf`). So the same 40 families and 200 held
  targets are used, with the same examples and shuffle partners. Nothing is redrawn, and `runs/GO` stays
  unchanged.
- **Attempt 1 is kept and disclosed.**
  - `runs/score/` is renamed `runs/score_attempt1/` and committed, with a copy of the launcher's records in
    `runs/score_attempt1/launcher/`.
  - Its 3 family records (15 held targets) stay unopened.
  - The rerun's records for the same targets are the ones scored; `RESULT.md` discloses the crash, the rerun and the
    unopened attempt.
  - A rerun after a crash, with no outcome opened, is disclosed in every report of this test.
- **The new authorization.** The coordinator writes `runs/GO_AMENDMENT2` after the delta review and commits it
  alone. It is plain ASCII, one `key: value` field per line after the first:
  ```
  GO_AMENDMENT2
  study: transfer_chemistry_20261108
  freeze_commit: <40-character hash of the last commit that changed FREEZE.json (the Amendment 2 freeze)>
  freeze_json_sha256: <sha256 of FREEZE.json at that commit>
  delta_review: <40-character commit of the delta review>
  original_go_commit: 190756a6fab499af19b762c4d0cb6046abe49152
  written_utc: <YYYY-MM-DDTHH:MM:SSZ>
  ```
- **The runner** (`t3chem/run.py`) keeps every Amendment 1 check on the original `runs/GO`, except the one that
  binds GO to the current FREEZE.json, which moves to GO_AMENDMENT2. Its freeze_commit must still hold the
  FREEZE.json that GO names. The runner refuses unless all of these hold:
  - `runs/score/` does not exist, and no development option is given;
  - both files are committed at HEAD, were committed once, and each was committed alone;
  - GO_AMENDMENT2 names the commit of `runs/GO`;
  - its freeze_commit is the last commit on HEAD that changed FREEZE.json and holds these exact bytes;
  - its freeze_json_sha256 matches, and every file hash in FREEZE.json matches;
  - the commits run in order: first freeze, pre-run review, GO, new freeze, delta review, GO_AMENDMENT2;
  - the Python and RDKit versions match.

  It derives the salt from the original `runs/GO`. A refusal in a real launch goes to `runs/refusals.log`, never
  into `runs/score/`, and `--check-only` writes nothing.
- **The launcher** uses the detached name `transfer_chemistry_held_a2`, so attempt 1's launcher records stay
  where they were.
- **Unchanged.** Data, pool, families, k, held count, arms, levels, tie-break (`most_general`), nearest-neighbour
  level (`L4`), checks, primary, decision rule and the 30 CPU-minute cap.
