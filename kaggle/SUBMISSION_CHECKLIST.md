# ARC Prize 2026 — Paper Track Submission Checklist

Deadline: November 9, 2026.
Competition: https://kaggle.com/competitions/arc-prize-2026-paper-track

## Steps

1. **Create Writeup on Kaggle**
   - Go to the Paper Track competition page.
   - Click "Submit" or "New Submission" (Writeup tab).
   - Copy the contents of `kaggle/writeup.md` into the writeup editor.
   - Verify formatting renders correctly (headings, table, bold).
   - Confirm word count is under 1500 (currently 1244).

2. **Attach Cover Image**
   - In the media gallery section of the submission, upload `kaggle/cover_image.png`.
   - Verify both panels are legible at the displayed size.

3. **Attach Public Notebook**
   - Your existing notebook: `arc-certified-solver` (or `arc_certified_solver1`).
   - Update the notebook's dataset to use the v22 tarball (`kaggle/arc_certified_solver_v22.tar.gz`): upload the tarball as a Kaggle dataset, point the notebook at it.
   - Ensure the notebook is set to **Public**.
   - Run or verify last successful run (offline, CPU, 12h limit).
   - Attach the notebook to the Paper Track submission.

4. **Optional: Attach Public PDF Link**
   - The compiled paper is at `paper/latex/main.pdf` (10 pages).
   - Options for a public link (pick one):
     - Upload to arXiv (preferred; may take 1-2 days for processing).
     - Host on GitHub: push `paper/latex/main.pdf` to the public repo and use the raw URL.
     - Upload to a preprint server or personal site.
   - Paste the public URL into the submission's PDF link field.

5. **Select Track**
   - Confirm you are submitting to the **Paper Track**, not the ARC-AGI-2 prediction track.

6. **Review Against Rubric Before Submitting**
   - Accuracy: training 185/1000 (18.5% CSR), eval 0/120 — honestly stated.
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

---

## Paper Track and release checklist, added 2026-09-23

### Deadlines

| item | date, UTC |
|---|---|
| ARC-AGI-2 entry deadline | 2026-10-26, 23:59 |
| final prediction and code submission | 2026-11-02, 23:59 |
| Paper Track final deadline | 2026-11-09, 23:59 |

A draft or unsubmitted writeup at the deadline does not count.

### Paper Track artifacts

- [ ] Kaggle Writeup, at most 1,500 words. Source: `kaggle/writeup.md`.
- [ ] Cover image. Spec: `kaggle/COVER_IMAGE_SPEC.md`. Build:
      `kaggle/cover_image.py`.
- [ ] Attached public notebook.
- [ ] Optional public project link, which may host the technical PDF. The URL
      must be reachable without login or paywall.

### Pending fields, never invented

| field | value |
|---|---|
| ARC-AGI-2 submission id | PENDING |
| public notebook URL | PENDING |
| public leaderboard score | PENDING |
| private leaderboard score | PENDING |
| final measured runtime | PENDING |

### Consistency gate, binding

The method described in the notebook, the writeup and the manuscript must be
the same method. Anything absent from the notebook is labelled ongoing
research and contributes nothing to the leaderboard claim. As of 2026-09-23
that includes the constructive AST proposer and the ConstructiveExtensionCompiler.

### Open-source gate before any public release

- [ ] remove protected research artifacts
- [ ] remove private data
- [ ] remove all Step-B sealed material
- [ ] verify licenses
- [ ] verify no secret tokens or private paths remain
- [ ] verify notebook dependencies resolve with the internet disabled

Nothing is published automatically.

### Author notes: evidence mapped to the Universality criterion

Not for the submitted paper. Strong evidence: a domain-independent formalism
over a domain tuple; a typed failure representation carrying no task id,
family name or answer; separation of verifier from proposer; both task-local
and persistent adaptation mechanisms; no task-family lookup; no direct answer
generation as the invention mechanism. Current limitation: empirical
cross-domain transfer is not demonstrated. No rubric-score prediction goes in
the paper.
