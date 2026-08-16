# ARC Prize 2026 — Paper Track Submission Checklist

Deadline: November 9, 2026.
Competition: https://kaggle.com/competitions/arc-prize-2026-paper-track

## Steps

1. **Create Writeup on Kaggle**
   - Go to the Paper Track competition page.
   - Click "Submit" or "New Submission" (Writeup tab).
   - Copy the contents of `kaggle/writeup.md` into the writeup editor.
   - Verify formatting renders correctly (headings, table, bold).
   - Confirm word count is under 1500 (currently 1081).

2. **Attach Cover Image**
   - In the media gallery section of the submission, upload `kaggle/cover_image.png`.
   - Verify both panels are legible at the displayed size.

3. **Attach Public Notebook**
   - Your existing notebook: `arc-certified-solver` (or `arc_certified_solver1`).
   - Update the notebook's dataset to use the v20 tarball (`kaggle/arc_certified_solver_v21.tar.gz`): upload the tarball as a Kaggle dataset, point the notebook at it.
   - Ensure the notebook is set to **Public**.
   - Run or verify last successful run (offline, CPU, 12h limit).
   - Attach the notebook to the Paper Track submission.

4. **Optional: Attach Public PDF Link**
   - The compiled paper is at `paper/latex/main.pdf` (9 pages).
   - Options for a public link (pick one):
     - Upload to arXiv (preferred; may take 1-2 days for processing).
     - Host on GitHub: push `paper/latex/main.pdf` to the public repo and use the raw URL.
     - Upload to a preprint server or personal site.
   - Paste the public URL into the submission's PDF link field.

5. **Select Track**
   - Confirm you are submitting to the **Paper Track**, not the ARC-AGI-2 prediction track.

6. **Review Against Rubric Before Submitting**
   - Accuracy: training 177/1000 (17.7% CSR), eval 0/120 — honestly stated.
   - Universality: protocol is domain-general; E9 demonstrates on neural learner.
   - Progress: honest map of what works/doesn't; E10 primitive invention.
   - Theory: the falsifiability thesis; three-way triangulation.
   - Novelty: machine-invented primitives under falsifiable gate; gate across learner classes.
   - Completeness: every claim regenerable from artifacts; notebook attached.

7. **Submit**
   - Submit before November 9, 2026.
   - Note: you can update the submission after initial entry (verify on the competition page).

## Also Submit to Track A (ARC-AGI-2 Prediction)

The Paper Track requires an attached public notebook that is also your Track A submission. Submit the same `arc-certified-solver` notebook to Track A as well. Expected score is low (0/120 eval certified) but the leaderboard number feeds the Accuracy criterion and makes you eligible.
