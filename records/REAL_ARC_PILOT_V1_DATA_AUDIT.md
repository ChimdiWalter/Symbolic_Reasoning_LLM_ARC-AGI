# Real ARC causal pilot v1: data audit (2026-10-07)

Result: an authorized ARC-AGI-2 training set is available and verified.
DATASET_UNAVAILABLE does not apply.

## Identity

| file | sha256 | bytes | task ids |
|---|---|---|---|
| `arc-agi_training_challenges.json` | `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5` | 4,010,050 | 1,000 |
| `arc-agi_training_solutions.json` | `9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9` | 658,743 | 1,000 (same ids) |

- 1,000 tasks is the ARC-AGI-2 public training split. The two files share
  their 1,000 ids; every test entry in the challenges file has an input and
  no output.
- Byte-identical copies (sha256 and size) at:
  `Reasoning_Project_tti/data/` and `data/arc/`,
  `Reasoning_Project_tti_pin_e5ef8b5/data/` and `data/arc/`,
  `/home/cnptp/Downloads/`, `/home/cnptp/ARC-AGI/data/`,
  `/home/cnptp/ARC-AGI (copy)/data/`.
- The main project's `Reasoning_Project/data/arc/` holds the same two files
  (same sha256 and sizes). On the user's question (2026-10-07) only that
  folder was listed and only these two files were checksummed; nothing else
  in that tree was opened. Its evaluation solutions were NOT opened.
- `geocat_arc/continue.txt` (in this repository) records the byte sizes of
  the training files behind the sealed 185 of 1000 baseline (4,010,050 and
  658,743): the same files.
- Canonical source for the pilot:
  `/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti/data/arc/`
  (CORA-TTI project tree, readable without touching Step B), pinned by the
  two sha256 values above.

## Boundary

- Disjoint from the 60 DEV evaluation challenges in this repository
  (`data/arc/dev60_challenges.json`, sha256 `6f369650...`; only its ids were
  read to check: overlap 0). The 60 DEV, the 60 HOLDOUT, any evaluation
  solution, Step B outputs, VDCG, E_transfer and the Lockbox are not used.
- Exposure: the base engine (v23 lineage, copied here as geocat_arc) was
  developed on the public training split and solves 185 of the 1000 by its
  sealed record. The pilot therefore measures task-time rescue of baseline
  failures on training tasks the base was developed on; it is not a
  generalization result. The 185-task solved list lives in the main
  project's records, which this block does not read, so no
  baseline-failure-enriched stratum is used; the pilot runs the native
  baseline itself.
- Isolation for the pilot: the reasoner receives a bundle with the selected
  tasks' training pairs and test inputs only, under opaque keys; the test
  outputs and the key-to-task-id map go to a separate evaluator file that
  only the blind evaluator reads, after the reasoner's predictions are
  committed.
