#!/usr/bin/env bash
# Build the science-first summit review documents FROM THEIR ORG SOURCES: Org -> LaTeX (Emacs batch) -> PDF (pdflatex).
# Offline. Each document is built in a fresh, empty temporary directory that holds only its .org and the figures/ folder.
#
#   sh scripts/build_summit_org.sh poster       # docs/summit_20261023_reframe/poster_science_first_review.{tex,pdf}
#   sh scripts/build_summit_org.sh explainer    # docs/summit_20261023_reframe/explainer_science_first_review.{tex,pdf}
#   sh scripts/build_summit_org.sh all
#   sh scripts/build_summit_org.sh poster_cancer | explainer_cancer | cancer   # the V2 cancer-lesion review versions
#   sh scripts/build_summit_org.sh selftest     # edits a COPY of each .org and checks the edit appears in its PDF
#
# The PDF is compiled from the .tex that Org just exported, never from a hand-maintained .tex.
# ORG_BUILD_MANIFEST.json records the sha256 of the .org, the exported .tex, the PDF and every included figure, plus the
# tool versions, page count and page size. The dates are fixed (SOURCE_DATE_EPOCH) so a rebuild gives the same PDF.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
DOC="$REPO/docs/summit_20261023_reframe"
EL="$REPO/scripts/export_summit_org.el"
export SOURCE_DATE_EPOCH=1791763200 FORCE_SOURCE_DATE=1

compile_in() {   # $1 = build dir, $2 = document name; exports and compiles inside $1
  local B=$1 name=$2
  (cd "$B" && emacs --batch -Q -l "$EL" --eval "(summit-export \"$B/$name.org\")" > "$name.export.log" 2>&1) \
    || { echo "Org export FAILED for $name"; tail -20 "$B/$name.export.log"; return 1; }
  for pass in 1 2; do
    (cd "$B" && pdflatex -interaction=nonstopmode -halt-on-error "$name.tex" > "$name.pdflatex$pass.log" 2>&1) \
      || { echo "pdflatex pass $pass FAILED for $name"; grep -E "^!" -A3 "$B/$name.pdflatex$pass.log" | head -20; return 1; }
  done
}

build() {   # $1 = document name, $2 = allowed page counts (space-separated), $3 = expected page size substring
  local name=$1 pages_ok=$2 size_ok=$3
  local B
  B=$(mktemp -d "${TMPDIR:-/tmp}/summit_org_build.XXXXXX")
  cp "$DOC/$name.org" "$B/"
  cp -r "$DOC/figures" "$B/figures"
  compile_in "$B" "$name"
  local pages size
  pages=$(pdfinfo "$B/$name.pdf" | awk '/^Pages:/{print $2}')
  size=$(pdfinfo "$B/$name.pdf" | awk -F': *' '/^Page size:/{print $2}')
  echo "$name: pages=$pages size=$size"
  case " $pages_ok " in *" $pages "*) ;; *) echo "page-count check FAILED ($pages not in: $pages_ok)"; return 1;; esac
  case "$size" in *"$size_ok"*) ;; *) echo "page-size check FAILED ($size)"; return 1;; esac
  if grep -q -E "Overfull \\\\hbox \(([3-9][0-9]|[0-9]{3,})" "$B/$name.pdflatex2.log"; then
    echo "WARNING: an overfull box wider than 30pt in $name"; grep -E "Overfull \\\\hbox" "$B/$name.pdflatex2.log" | head -5
  fi
  cp "$B/$name.tex" "$B/$name.pdf" "$DOC/"
  python3 - "$B" "$name" "$DOC" "$pages" "$size" <<'PY'
import hashlib, json, os, re, subprocess, sys
B, name, DOC, pages, size = sys.argv[1:]
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
tex = open(os.path.join(B, f"{name}.tex")).read()
figs = sorted(set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)))
ver = lambda cmd: subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()[0]
log = open(os.path.join(B, f"{name}.export.log")).read()
rec = {"org": f"{name}.org", "org_sha256": sha(os.path.join(B, f"{name}.org")),
       "tex_exported_by_org_sha256": sha(os.path.join(B, f"{name}.tex")), "pdf_sha256": sha(os.path.join(B, f"{name}.pdf")),
       "pages": int(pages), "page_size": size, "figures": {f: sha(os.path.join(B, f)) for f in figs},
       "emacs": ver(["emacs", "--version"]), "org_version": re.search(r"ORG_VERSION (\S+)", log).group(1),
       "pdflatex": ver(["pdflatex", "--version"]), "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH")}
p = os.path.join(DOC, "ORG_BUILD_MANIFEST.json")
m = json.load(open(p)) if os.path.exists(p) else {}
m[name] = rec
json.dump(m, open(p, "w"), indent=1, sort_keys=True)
print(f"{name}: {len(figs)} figures; org {rec['org_sha256'][:12]} tex {rec['tex_exported_by_org_sha256'][:12]} pdf {rec['pdf_sha256'][:12]}")
PY
  rm -rf "${B:?}"
}

selftest() {   # proves each .org is the real source: an edit to a COPY must appear in that copy's PDF
  local name sentinel B
  for name in ${SELFTEST_DOCS:-poster_science_first_review explainer_science_first_review poster_cancer_lesion_review explainer_cancer_lesion_review}; do
    sentinel="ORGSOURCECHECK$(date +%s)$RANDOM"
    B=$(mktemp -d "${TMPDIR:-/tmp}/summit_org_selftest.XXXXXX")
    cp -r "$DOC/figures" "$B/figures"
    python3 - "$DOC/$name.org" "$B/$name.org" "$sentinel" <<'PY'
import sys
src, dst, sentinel = sys.argv[1:]
s = open(src).read()
key = "\n#+END_posterblock" if "poster" in src else "\n* "        # a real block end / the second section, at a line start
i = s.index(key) if "poster" in src else s.index(key, s.index(key) + 1)
open(dst, "w").write(s[:i] + f"\n{sentinel}\n" + s[i:])
PY
    compile_in "$B" "$name"
    pdftotext "$B/$name.pdf" "$B/$name.txt"                          # no pipe: grep -q + pipefail would SIGPIPE pdftotext
    if grep -q "$sentinel" "$B/$name.txt"; then echo "selftest $name: PASS (the edited copy's PDF contains $sentinel)"
    else echo "selftest $name: FAIL"; rm -rf "${B:?}"; return 1; fi
    rm -rf "${B:?}"
  done
}

case "${1:-all}" in
  poster) build poster_science_first_review "1" "2383.94 x 3370.39" ;;
  explainer) build explainer_science_first_review "10 11 12" "595.276 x 841.89" ;;
  all) build poster_science_first_review "1" "2383.94 x 3370.39"
       build explainer_science_first_review "10 11 12" "595.276 x 841.89" ;;
  # the cancer-lesion poster is also written at the summit's print sizes (A1, 24 x 36 in) by exact vector scaling
  poster_cancer) build poster_cancer_lesion_review "1" "2383.94 x 3370.39"
                 sh "$(dirname "$0")/scale_summit_poster.sh" ;;
  # the V2 explainer adds the medical-image section (about 1.5 pages), so its expected range is 11-13
  explainer_cancer) build explainer_cancer_lesion_review "11 12 13" "595.276 x 841.89" ;;
  cancer) build poster_cancer_lesion_review "1" "2383.94 x 3370.39"
          sh "$(dirname "$0")/scale_summit_poster.sh"
          build explainer_cancer_lesion_review "11 12 13" "595.276 x 841.89" ;;
  selftest) selftest ;;
  *) echo "usage: $0 poster|explainer|all|poster_cancer|explainer_cancer|cancer|selftest"; exit 2 ;;
esac
