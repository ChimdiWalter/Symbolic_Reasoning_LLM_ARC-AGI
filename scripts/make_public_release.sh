#!/bin/sh
# Rebuild the public branch `publish-arc2026-sprint` from local master, without the unpublished maize crop and the two
# PDFs that embed it (docs/summit_20261023_reframe/PUBLIC_RELEASE_NOTE.md). master itself is never rewritten.
#
#   sh scripts/make_public_release.sh            # rebuild locally; prints the checks
#   git push origin publish-arc2026-sprint:arc2026-sprint    # then, only as a fast-forward (never --force)
#
# The rewrite is deterministic: author and committer metadata are kept, so commits already published keep their hashes
# and each later sync is a fast-forward.
set -eu
cd "$(dirname "$0")/.."
BASE=a1a59f7          # the last commit public on origin/arc2026-sprint before 2026-10-20
EXCL="docs/summit_20261023_reframe/figures/fig_maize_annotated_DSC_0042_crop_x2.png docs/summit_20261023_reframe/poster_cancer_lesion_review.pdf docs/summit_20261023_reframe/explainer_cancer_lesion_review.pdf"
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "working tree not clean"; exit 1; }
git branch -f publish-arc2026-sprint master
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --index-filter "git rm --cached --ignore-unmatch -q $EXCL" \
    -- "$BASE..publish-arc2026-sprint" >/dev/null
git update-ref -d refs/original/refs/heads/publish-arc2026-sprint 2>/dev/null || true
git merge-base --is-ancestor "$BASE" publish-arc2026-sprint || { echo "not a fast-forward of $BASE"; exit 1; }
n=$(git rev-list --objects "$BASE..publish-arc2026-sprint" | grep -c -E "fig_maize_annotated|cancer_lesion_review\.pdf" || true)
[ "$n" = 0 ] || { echo "excluded paths still reachable ($n)"; exit 1; }
echo "publish-arc2026-sprint = $(git rev-parse --short publish-arc2026-sprint); tree differs from master only in:"
git diff --name-only publish-arc2026-sprint master
