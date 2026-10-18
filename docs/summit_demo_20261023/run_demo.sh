#!/bin/sh
# Offline replay of the recorded CORA-FHR development witness (see README.md). No network, no Athe.
cd "$(dirname "$0")"
python3 -c "import numpy" 2>/dev/null || { echo "needs numpy: pip install numpy"; exit 1; }
if [ "$1" = "--real" ]; then python3 replay_real.py; else python3 replay.py "$@"; fi
