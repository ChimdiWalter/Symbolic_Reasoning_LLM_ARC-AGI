"""Convert a flat SVG of filled <path>s (no transforms) into a standalone TikZ document (vector, via svg.path)."""
import re, sys
svg = open(sys.argv[1], encoding="iso-8859-1").read()
assert not re.search(r"transform=|<(?:polygon|rect|circle|ellipse|polyline|line|use|image|text)\b", svg), "unsupported SVG"
w, h = (float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()[2:])
paths = re.findall(r'<path\s+(?:style="fill:(#[0-9A-Fa-f]{6});"\s+)?d="([^"]+)"', svg)
assert len(paths) == svg.count("<path"), "a path was not matched"
out = [r"\documentclass{standalone}", r"\usepackage{tikz}\usetikzlibrary{svg.path}", r"\pdftrailerid{}", r"\begin{document}",
       r"\begin{tikzpicture}[yscale=-1]", rf"\useasboundingbox (0pt,0pt) rectangle ({w}pt,{h}pt);"]
for fill, d in paths:
    col = (fill or "#000000").lstrip("#").upper()          # an SVG path without a fill is black
    out.append(rf"\definecolor{{c{col}}}{{HTML}}{{{col}}}\fill[c{col}] svg {{{' '.join(d.split())}}};")
out += [r"\end{tikzpicture}", r"\end{document}"]
open(sys.argv[2], "w").write("\n".join(out) + "\n")
print(f"{len(paths)} paths, viewBox {w} x {h}")
