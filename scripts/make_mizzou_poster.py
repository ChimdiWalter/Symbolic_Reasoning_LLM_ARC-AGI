"""Derive the Mizzou-styled copy of the summit poster from its master Org file (header changes only).

  python3 scripts/make_mizzou_poster.py MASTER.org          -> MASTER_mizzou.org next to it

The copy keeps the content, layout and sizes. It adds:
- a black title band, edge to edge, with the Mizzou signature at upper left (figures/mizzou_logo.pdf, made with
  scripts/svg_paths_to_tikz.py from https://missouri.edu/themes/miz_missouri_edu_subtheme/images/
  MU_MizzouSig_rgb_White_Horiz.svg, the white version for dark backgrounds);
- the title in Mizzou Gold (#FDB719) and the subtitle and authors in white;
- a 4 mm gold rule under the band;
- black headings and diagram outlines, and Gold Tint 3 (#FFEDCF) for the bottleneck bands.
Brand colours: brand.missouri.edu/visual-identity/colors/ (gold text only on black).
"""
import sys

HEAD = ("# MIZZOU-STYLED COPY of {name} (same content, layout and sizes), made by scripts/make_mizzou_poster.py.\n"
        "# Edit the master, then rerun the script. Logo: figures/mizzou_logo.pdf (from missouri.edu's\n"
        "# MU_MizzouSig_rgb_White_Horiz.svg). Title in Mizzou Gold #FDB719 on black, gold rule, black headings.\n")
REPS = [(r"\definecolor{accent}{HTML}{2A78D6}", r"\definecolor{accent}{HTML}{000000}"),
        (r"\definecolor{band1}{HTML}{FDEBD3}\definecolor{band2}{HTML}{FADBD8}",
         r"\definecolor{band1}{HTML}{FFEDCF}\definecolor{band2}{HTML}{FFEDCF}\definecolor{mugold}{HTML}{FDB719}"
         r"\definecolor{mublack}{HTML}{000000}"),
        (r"\usetheme{Simple}\tikzposterlatexaffectionproofoff",
         r"\usetheme{Simple}\tikzposterlatexaffectionproofoff" "\n"
         r"#+LATEX_HEADER: \newcommand{\mizzoulogo}{\IfFileExists{figures/mizzou_logo.pdf}"
         r"{\includegraphics[width=120mm]{figures/mizzou_logo.pdf}}{}}" "\n"
         r"#+LATEX_HEADER: \definetitlestyle{MizzouBand}{width=\paperwidth, roundedcorners=0, linewidth=0pt, innersep=1cm, "
         r"titletotopverticalspace=10mm, titletoblockverticalspace=12mm, titlegraphictotitledistance=10pt, titletextscale=1}"
         r"{\fill[mublack] (-0.5\textwidth,\titleposbottom) rectangle (0.5\textwidth,0.5\textheight); "
         r"\fill[mugold] (-0.5\textwidth,\titleposbottom-4mm) rectangle (0.5\textwidth,\titleposbottom); "
         r"\node[anchor=west, inner sep=0pt] at (-0.5\textwidth+25mm, {(\titlepostop+\titleposbottom)/2}) {\mizzoulogo};}" "\n"
         r"#+LATEX_HEADER: \usetitlestyle{MizzouBand}"),
        (r"\colorlet{titlefgcolor}{ink}", r"\colorlet{titlefgcolor}{mugold}"),
        (r"\colorlet{titlebgcolor}{paper}", r"\colorlet{titlebgcolor}{mublack}"),
        (r"{\fontsize{50}{60}\selectfont \postersubtitle\par}", r"{\fontsize{50}{60}\selectfont\color{white} \postersubtitle\par}"),
        (r"{\fontsize{36}{44}\selectfont\color{ink2} \@author", r"{\fontsize{36}{44}\selectfont\color{white} \@author"),
        ("titletotopverticalspace=10mm, titletoblockverticalspace=6mm]",
         "titletotopverticalspace=10mm, titletoblockverticalspace=12mm]")]


def main(master):
    s = open(master).read()
    for old, new in REPS:
        if s.count(old) != 1:
            raise SystemExit(f"{master}: expected exactly one {old!r}")
        s = s.replace(old, new)
    out = master[:-len(".org")] + "_mizzou.org"
    open(out, "w").write(HEAD.format(name=master.rsplit("/", 1)[-1]) + s)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
