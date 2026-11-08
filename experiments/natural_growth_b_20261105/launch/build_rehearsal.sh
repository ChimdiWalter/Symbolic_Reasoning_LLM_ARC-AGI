#!/bin/sh
# Build the rehearsal kernels RA and RB (one CPU slot): REHEARSAL_GO names the candidate freeze; the build checks the
# package (smoke test) and the rehearsal data before writing the notebooks.
cd /path/to/repository/experiments/natural_growth_b_20261105
PS=$(sha256sum PROTOCOL.md | cut -c1-64); FS=$(sha256sum FREEZE.json | cut -c1-64)
printf 'protocol_sha256 %s\nfreeze_sha256 %s\nprimary arm5_vs_arm4\nrehearsal only: source-half inputs; no held task, no test output\n' "$PS" "$FS" > rehearsal/REHEARSAL_GO
python3 -I ngb/kaggle_build.py rehearsal > logs/build_rehearsal.log 2>&1; echo "BUILD EXIT $?"
echo EXIT
