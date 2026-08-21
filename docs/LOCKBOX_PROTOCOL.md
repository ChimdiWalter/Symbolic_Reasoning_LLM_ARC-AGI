# Lockbox Protocol (CORA Stage B: frozen split of the 1000 training tasks)

Date frozen: 2026-08-18. Manifest: `outputs/lockbox/manifest.json` (v1.0.0,
seed 20260818, sha256 recorded in `logs/lockbox_manifest.log` with marker
`LOCKBOX_MANIFEST_DONE`). Builder: `scripts/build_lockbox_manifest.py` -
rerunning it reproduces the manifest byte-identically.

## The split

The 1000 ARC-AGI-2 training tasks (`data/arc-agi_training_challenges.json`,
sha256 `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5`) are
partitioned once, by structural family (never randomly across the pool):

| Split | Size | Certified (of 181) | Purpose |
|---|---|---|---|
| Experience | 600 | 109 | The only tasks concepts may be INVENTED from. |
| Promotion | 200 | 36 | Independent-transfer tests for proposed concepts. |
| Lockbox | 200 | 36 | Untouched until system + library are frozen; evaluated ONCE. |

Family labels are derived deterministically from TRAIN-pair structure only
(shape relation, grid-size class, number of train pairs, palette class) plus
already-recorded solver metadata (near-solve `required_class` from
`outputs/nearsolve_compiler/ns_dataset.jsonl`; `origin_class` for the 181
certified tasks from `outputs/unified_harness_v22/results.json` +
`outputs/v22_arbitration/results.json`). Hidden test outputs were never read
for stratification. Each split carries proportional representation of every
family (per-family deviation from exact 60/20/20 is at most ~1 task), and the
181 currently-certified tasks are themselves spread 109/36/36.

## Rules

1. **Invention only from Experience.** New concepts, primitives, view
   programs, generator modes, expression-grammar extensions, and any
   parameter/threshold choices may be proposed, parameterized, and selected
   using Experience tasks only.
2. **Promotion = independent transfer.** A concept proposed from Experience
   tasks earns independent-transfer status only by solving a Promotion task
   that played NO role in proposing, parameterizing, or selecting it.
   Promotion tasks may be evaluated repeatedly, but never mined for new
   concepts: a failure on a Promotion task must not be turned into a repair
   hypothesis, primitive, or parameter change. Anything learned by looking at
   a Promotion task disqualifies that task as transfer evidence.
3. **Lockbox is sealed.** Lockbox tasks are not run, inspected, traced, or
   analyzed in any way until the system and the concept library are declared
   frozen. They are then evaluated exactly ONCE, and that number is reported
   as-is. No second attempt, no post-hoc repair round, no re-freeze-and-rerun
   against the same Lockbox.
4. **Public eval stays untouched.** The 120 public evaluation tasks are not
   run until AFTER the single lockbox evaluation.
5. **LOO gate unchanged.** The leave-one-out-by-reinduction gate remains the
   SOLE acceptance path for certified solves throughout all of the above.
   Experience/Promotion/Lockbox never weaken, replace, or bypass it; they add
   transfer evidence on top of it.

## Freeze / append-only

The manifest is frozen and append-only. No task may ever move between splits
in place. Any change: different family labeling, different sizes, corrected
metadata: requires a NEW manifest version (new file version + new sha256
logged to `logs/lockbox_manifest.log`) and a FULL regression replay of every
result that cited the old version. Results are only comparable within a single
manifest version.

## Verification

- Counts: 600 + 200 + 200 = 1000, each task in exactly one split.
- Rerun `python scripts/build_lockbox_manifest.py --out <tmp>` and `diff`
  against `outputs/lockbox/manifest.json`: must be byte-identical.
- The manifest's own sha256 must match the latest `LOCKBOX_MANIFEST_DONE`
  line in `logs/lockbox_manifest.log`.
- Fallback-labeled tasks (`meta:none`): 0 in v1.0.0.
