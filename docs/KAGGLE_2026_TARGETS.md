# ARC Prize 2026 targets (recorded 2026-08-12 from user's Kaggle pages)
DEADLINE: Nov 9, 2026 (both tracks). User already entered; has draft
notebooks (arc-certified-solver, arc_certified_solver1).

## Track A: ARC-AGI-2 prediction (kaggle.com/competitions/arc-prize-2026-arc-agi-2)
- SCORING: hidden ARC-AGI-2 eval; 2 attempts per test output; ANY
  match = 1. submission.json must contain ALL task_ids, both
  attempt_1 + attempt_2 keys always present.
- CONSTRAINTS: notebook, <=12h CPU or GPU, NO internet; external
  public data/models allowed; L4x4 (96GB GPU) available at 2x quota.
- OUR HONEST EXPECTATION: low single digits at best (our eval-split
  analogue = 0/120 certified); attempt_1 certified + attempt_2 best
  material available. Submit anyway — the leaderboard number feeds
  the paper track's Accuracy criterion and makes us eligible.

## Track B: PAPER TRACK (kaggle.com/competitions/arc-prize-2026-paper-track) — OUR BEST SHOT
- Prizes: $50K/$20K/$5K + $375K bonus pool for rubric >4.5/5.
- REQUIREMENTS: Kaggle Writeup <=1500 WORDS + cover image (media
  gallery) + attached PUBLIC NOTEBOOK (the Track A submission
  notebook) + optional public PDF link (our LaTeX paper -> host as
  public link; can also arXiv).
- RUBRIC (equal weight): Accuracy (weak for us), Universality
  (STRONG: certification protocol is domain-general), Progress
  (moderate-strong: honest map of what does/doesn't work + E10),
  Theory (STRONGEST: the falsifiability thesis explains WHY),
  Completeness (STRONG: every claim regenerable from artifacts),
  Novelty (STRONGEST: E10 primitive invention, gate across learner
  classes). Judges: Chollet + Knoop. 2025 precedent: TRM +
  CompressARC won as method papers WITHOUT top leaderboard scores.
- DELIVERABLES TO BUILD: (1) 1500-word writeup distilling the paper
  (thesis, gate, E10, calibration, honest negatives); (2) public
  notebook = the v20 submission notebook; (3) PDF of paper/latex
  build; (4) cover image (calibration lattice or E10 diagram).
- MUST open-source solution if prize-eligible (repo already public).
