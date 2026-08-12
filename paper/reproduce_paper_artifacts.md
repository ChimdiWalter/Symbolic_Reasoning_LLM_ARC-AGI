# Reproduce Paper Artifacts

Use the existing local artifacts and bounded post-hoc analysis steps only. This paper package does not require new downloads.

```bash
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
python3.11 scripts/analyze_h4_sweep.py --sweep-dir outputs/paper_breadth_validation_5seed_sweep
python3.11 scripts/build_submission_package.py --repo-root /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project --breadth-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep --h2-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/h2_family_validation_10seed_sweep --h4-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment
python3.11 -m pytest
```

Primary outputs:

- `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment`
- `outputs/submission_package`
- `paper/manuscript_draft.md`
