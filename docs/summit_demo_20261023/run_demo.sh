#!/bin/sh
# Offline replay of the recorded CORA-FHR development witness (see README.md). No network, no Athe.
cd "$(dirname "$0")"
python3 -c "import numpy" 2>/dev/null || { echo "needs numpy: pip install numpy"; exit 1; }
python3 replay.py "$@"
