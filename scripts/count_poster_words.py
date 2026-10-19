"""Count a poster .org's words by category: prose (body sentences), diagram labels (TikZ export blocks),
block titles, and the footer/references line. Figure PNG text is not counted (it is pixels)."""
import re, sys
src = open(sys.argv[1]).read()
def clean(t):
    t = re.sub(r"@@latex:(.*?)@@", r"\1", t)
    t = re.sub(r"\[\[file:[^\]]*\]\]", " ", t)
    t = re.sub(r"\\(fontsize\{[^}]*\}\{[^}]*\}|selectfont|color\{[^}]*\}|textbf|textit|emph|bfseries|itshape|mdseries|"
               r"par|centering|raggedright|secfont|diagsub|vspace\{[^}]*\}|hspace\{[^}]*\}|\\(\[[^\]]*\])?|,|"
               r"[a-zA-Z]+\*?)", " ", t)
    t = re.sub(r"\$[^$]*\$", " ", t)
    t = re.sub(r"[{}*=~]", " ", t)
    return [w for w in t.split() if re.search(r"[A-Za-z0-9]", w)]
prose, labels, titles, footer, latex_lines = [], [], [], [], []
in_export = False
for line in src.splitlines():
    s = line.strip()
    if s.startswith("#+BEGIN_EXPORT"):
        in_export = True; continue
    if s.startswith("#+END_EXPORT"):
        in_export = False; continue
    if in_export:
        # TikZ: only text inside node braces {...} counts as diagram labels
        for m in re.finditer(r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\};", s):
            labels += clean(m.group(1))
        for m in re.finditer(r"node\[[^\]]*\] \{([^}]*)\}", s):
            labels += clean(m.group(1))
        continue
    if s.startswith("#+ATTR_LATEX: :options {") and s != "#+ATTR_LATEX: :options {}":
        titles += clean(s.split(":options", 1)[1]); continue
    if "\\maketitle" in s:
        continue
    if s.startswith("#"):
        if s.startswith("#+LATEX:") and not s.startswith("#+LATEX_HEADER"):
            t = re.sub(r"\\(begin|end|column)\{[^}]*\}(\[[^\]]*\])?(\{[^}]*\})?", " ", s[len("#+LATEX:"):])
            t = re.sub(r"\\(bignum)\{([^}]*)\}", " ", t)          # the big number is a figure label
            got = clean(t)
            (prose if "One reasoning loop" not in t else titles).extend(got if "One reasoning loop" not in t else [])
            if "One reasoning loop" in t:
                titles.extend(clean("One reasoning loop."))
            elif got:
                latex_lines.append(" ".join(got))
        continue
    (footer if s.startswith("Prior work:") or "CLAIM_LEDGER" in s or footer and not s else prose).extend(clean(s))
print(f"prose {len(prose)}  diagram-labels {len(labels)}  block-titles {len(titles)}  footer/references {len(footer)}")
if len(sys.argv) > 2:
    print(" ".join(prose))
    print("FROM #+LATEX LINES:", latex_lines)
