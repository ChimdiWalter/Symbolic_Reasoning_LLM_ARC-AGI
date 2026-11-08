#!/bin/sh
# Poll one private development kernel until it finishes, then download its outputs into a new folder and extract
# its dev/ files into the study's dev/kaggle/<tag>/ (regular files only, no path parts). Run detached.
#   sh launch/poll_fetch.sh <kernel slug, e.g. cora-spec-guide-devgen-b> <tag>
ST=$(cd "$(dirname "$0")/.." && pwd)
K_CLI=$HOME/.venvs/kaggle-cli/bin/kaggle
slug=$1; tag=$2
i=0
while :; do
  i=$((i+1))
  st=$($K_CLI kernels status chimdiwalter/$slug 2>/dev/null | grep -o 'KernelWorkerStatus\.[A-Z_]*' | tail -1)
  case "$st" in *COMPLETE*|*ERROR*|*CANCEL*) echo "$slug $st $(date -u +%H:%M:%SZ)"; break ;; esac
  [ $i -gt 600 ] && { echo "$slug: timeout"; exit 1; }
  sleep 60
done
d=$ST/runs/kaggle_dev/out_$tag
mkdir -p $d
$K_CLI kernels output chimdiwalter/$slug -p $d >/dev/null 2>&1
arc=$(ls $d/*_outputs.tar.gz 2>/dev/null | head -1)
[ -z "$arc" ] && { echo "$slug: no archive"; exit 1; }
sha256sum $arc
python3 -I - "$arc" "$ST/dev/kaggle/$tag" <<'PY'
import sys, tarfile, os
arc, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
with tarfile.open(arc, "r:gz") as tf:
    ms = [m for m in tf.getmembers() if m.isfile() and m.name.startswith("dev/") and ".." not in m.name.split("/")
          and not m.name.startswith("/")]
    for m in ms:
        m.name = os.path.basename(m.name)
        tf.extract(m, dst)
print("extracted", len(ms), "files to", dst)
PY
echo "FETCHED $(date -u +%H:%M:%SZ)"
