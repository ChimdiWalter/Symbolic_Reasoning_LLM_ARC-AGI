# Public GitHub release, 20 October 2026

**Authorization:** the user's message "you can push without the maize annotation crop".

| item | value |
|---|---|
| remote | the project's public GitHub repository, branch `arc2026-sprint` (the branch earlier pushes used; `main` untouched) |
| push | `a1a59f7..ea48725`, a fast-forward with no force; 51 commits, all authored by the user, with no AI co-author lines |
| how it was built | `sh scripts/make_public_release.sh` copies local `master` and filters three paths out of every outgoing commit, keeping author and date metadata, so later syncs stay fast-forwards. Local `master` is never rewritten |
| excluded | `docs/summit_20261023_reframe/figures/fig_maize_annotated_DSC_0042_crop_x2.png`, `poster_cancer_lesion_review.pdf`, `explainer_cancer_lesion_review.pdf` (the PDFs embed the crop). The reason is in `docs/summit_20261023_reframe/PUBLIC_RELEASE_NOTE.md` |

**The audit before the push:**

| check | result |
|---|---|
| binary blobs scanned | every version of all 65 image, PDF and PPTX blobs in the range; the maize crop was found only in the PNG and in 4 versions of the 2 cancer-lesion PDFs, all excluded |
| maize-bearing blobs reachable from the pushed range | 0 |
| `voice_note/` or the research ZIP | none (they are untracked and also excluded locally in `.git/info/exclude`) |
| secrets in outgoing text | 0 pattern hits |
| answer keys, sealed data or model weights | none |
| ISIC image and mask | CC-0 (verified from the ISIC records) |
| protected-split membership | no file lists it. The Phase 2a record publishes the 40 *eligible* (non-protected) cohort IDs from a deterministic candidate order, so the complement is inferable in principle (low risk) |

**Open: the NVARC notebook copy.** `kaggle/neural_v1/kernel/notebook.ipynb` was already public from earlier pushes
(before `a1a59f7`), and this push did not change it. Its licence is unverified: the NVARC repository has no licence,
and the Kaggle notebook's terms were not checked. Before any further redistribution, the options are:
1. verify the Kaggle notebook's licence;
2. remove the file from the public tip (it stays in history unless history is rewritten, which would need explicit
   approval).

**To re-sync later:**
```
sh scripts/make_public_release.sh
git push origin publish-arc2026-sprint:arc2026-sprint
```
Never use `--force`.

## Sync log

Each entry is a fast-forward of `arc2026-sprint`, built by `scripts/make_public_release.sh`, with no force.

| push | range | what |
|---|---|---|
| 1 | `a1a59f7..ea48725` | the 18–20 October work, 51 commits, maize crop excluded |
| 2 | `ea48725..36bf5bb` | ncv2-g2 capability recovery; the frozen synthetic protocol; RESUME and ledger (3 commits; 0 new binaries; every check above repeated) |
