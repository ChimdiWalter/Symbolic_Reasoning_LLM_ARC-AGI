;;; export_summit_org.el --- repo-local Org -> LaTeX exporter for the summit review documents -*- lexical-binding: t -*-

;; Usage (batch, offline; the run is pinned with -Q so no user init file changes the result):
;;   emacs --batch -Q -l scripts/export_summit_org.el --eval '(summit-export "docs/summit_20261023_reframe/X.org")'
;;
;; It registers two LaTeX classes that the .org files select with #+LATEX_CLASS:
;;   summit-tikzposter  one A0 portrait page (tikzposter). The .org lays it out with special blocks
;;                      (#+BEGIN_posterblock ... #+END_posterblock) and a few one-line #+LATEX: commands for columns.
;;   summit-article     the A4 explainer: Org headings become numbered sections.
;; Both start from [NO-DEFAULT-PACKAGES], so every package used is declared in the .org's #+LATEX_HEADER lines.
;; The exporter writes X.tex next to X.org. scripts/build_summit_org.sh compiles that exported .tex, never a
;; hand-maintained one.

(require 'org)
(require 'ox-latex)

(setq org-export-with-smart-quotes nil
      org-export-time-stamp-file nil       ; no "% Created <time>" line: the exported .tex is deterministic
      org-latex-with-hyperref nil            ; the explainer loads and configures hyperref in its own header
      org-latex-prefer-user-labels t
      org-export-allow-bind-keywords nil
      org-latex-image-default-width ""
      org-latex-default-figure-position "H")

(add-to-list 'org-latex-classes
             '("summit-tikzposter"
               "\\documentclass[25pt, a0paper, portrait, blockverticalspace=7mm]{tikzposter}
[NO-DEFAULT-PACKAGES]
[PACKAGES]
[EXTRA]"))

(add-to-list 'org-latex-classes
             '("summit-article"
               "\\documentclass[11pt, a4paper]{article}
[NO-DEFAULT-PACKAGES]
[PACKAGES]
[EXTRA]"
               ("\\section{%s}" . "\\section*{%s}")
               ("\\subsection{%s}" . "\\subsection*{%s}")
               ("\\subsubsection{%s}" . "\\subsubsection*{%s}")))

(defun summit-export (file)
  "Export FILE (an .org) to LaTeX next to it; print the output path; signal an error on failure."
  (let ((buf (find-file-noselect (expand-file-name file))))
    (with-current-buffer buf
      (let ((out (org-latex-export-to-latex)))
        (princ (format "EXPORTED %s\nORG_VERSION %s\nEMACS_VERSION %s\n" out (org-version) emacs-version))
        out))))

;;; export_summit_org.el ends here
