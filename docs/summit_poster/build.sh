#!/bin/sh
# Rebuild the poster figures, poster.pdf and abstract.pdf from their sources.
# Reproducible: the figures are drawn from hash-pinned outputs; the PDFs use a
# fixed SOURCE_DATE_EPOCH and no trailer id, so a rebuild is byte-identical.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
"$ROOT/.venv_arc2026/bin/python" "$ROOT/scripts/summit_figures.py" > /dev/null
TMP=$(mktemp -d)
cd "$HERE"
for f in poster abstract; do
  SOURCE_DATE_EPOCH=1791763200 FORCE_SOURCE_DATE=1 pdflatex -interaction=nonstopmode -halt-on-error \
    -output-directory="$TMP" "$f.tex" > "$TMP/$f.out" 2>&1 || { tail -20 "$TMP/$f.out"; exit 1; }
  cp "$TMP/$f.pdf" "$HERE/$f.pdf"
done
rm -rf "$TMP"
sha256sum "$HERE/poster.pdf" "$HERE/abstract.pdf" "$HERE"/figures/*.png | sed "s#$HERE/##"
