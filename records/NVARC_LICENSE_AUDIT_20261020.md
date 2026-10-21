# NVARC licence audit (read-only, 20 October 2026)

**The request:** a read-only licence audit of NVARC's Kaggle notebook and GitHub code. Rights are to be kept apart
by kind, and any copied notebook without verified redistribution permission is to be prepared for removal from the
public branch, with attribution. There is no history rewrite and no force-push.

## 1. Rights, by kind

| asset | licence | how checked (20 Oct) | status |
|---|---|---|---|
| NVARC **repository code** (github.com/1ytic/NVARC) | **none declared** | GitHub API `license: null`, re-checked today; no LICENSE file [prior-art L11–L12] | not cleared for copying |
| NVARC **Kaggle notebook** `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue` | **unknown** | page: only the title renders (JavaScript); Kaggle API `kernels pull -m` metadata has no licence field; Kaggle Terms page: only the title renders | **not verified** |
| NVARC **model checkpoint** `sorokin/qwen3_4b_grids15_sft139` | Apache 2.0 | Kaggle model API [prior-art L15] | cleared, with attribution |
| NVARC **datasets** (synthetic puzzles) | unknown | [prior-art L16] | not used |
| Kaggle dependency `sorokin/pip-install-unsloth-flash-patch` | unknown | referenced by kernel metadata, not copied | not redistributed |

A public checkpoint licence does not license the notebook's code.

## 2. NVARC-derived files in this repository

All are tracked, and all have been in the public branch since 2026-10-13 (commit `d09a2ae` and later).

| file | what it is | public action |
|---|---|---|
| `kaggle/neural_v1_smoke/upstream/arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb` | the verbatim upstream notebook | **remove from the public tip** |
| `kaggle/neural_v1_smoke/upstream/kernel-metadata.json` | upstream's kernel metadata | **remove from the public tip** |
| `kaggle/neural_v1/kernel/notebook.ipynb` | upstream + CORA's compatibility patches (the 27.64 deployment) | **remove from the public tip** |
| `kaggle/neural_v1_smoke/kernel/notebook.ipynb` | upstream + smoke patches | **remove from the public tip** |
| `kaggle/neural_v1_smoke/kernel_probe/notebook.ipynb` | upstream-derived probe | **remove from the public tip** |
| `kaggle/neural_v1/build_full.py`, `kaggle/neural_v1_smoke/build_smoke.py` | CORA's own patch builders, with short upstream excerpts as exact-string anchors | kept; flagged for the author's review |
| `kaggle/neural_v1/audit_run.py`, `probe_ids.json`, CORA's own kernel metadata | CORA's own | kept |

## 3. The prepared removal (local only; NOT pushed)

- `kaggle/NVARC_NOTICE.md` adds attribution, links to the originals and the reason.
- `scripts/make_public_release.sh` now deletes the five public-action files above from every outgoing commit that
  contains the notice. That is, from the notice's commit onward.
  - Commits published before the notice keep their hashes, so the next push is still a **fast-forward**: no history
    rewrite, no `--force`.
  - Earlier public commits still contain the files. Removing them from history would need an explicitly approved
    rewrite and force-push.
- Local `master` keeps every file. The frozen deployment (`kaggle/neural_v1/**`, hashed in the v1 freeze manifest) and
  its reproduction depend on them.
- **The push needs the author's authorization.**
