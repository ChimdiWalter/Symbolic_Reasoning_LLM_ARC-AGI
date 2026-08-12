# Agent Instructions

These instructions apply to future work in `code/Reasoning_Project`.

## Environment

Use:

```bash
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
python3.11
```

Network is restricted. Do not assume dependency installation or Kaggle downloads are available.

## Experiment Discipline

- Current phase priority is diagnosis over expansion. Prefer artifact quality, variance analysis, failure taxonomy, and leakage checks over new model features.
- Treat all hypothesis claims as provisional until supported by repeated seeds.
- Report paired contrasts, per-seed deltas, mean, standard deviation, and 95% bootstrap confidence intervals when feasible.
- For H2 and H5, require compute-matched comparisons before treating gains as supported; explicitly report when comparisons are not compute-matched.
- Do not escalate a claim from promising to supported unless:
  - repeated-seed evidence exists,
  - tests pass,
  - artifacts are checked and non-empty,
  - `RUN_HISTORY.md` lists exact paths and commands.

## Testing

After code edits:

1. Run the smallest relevant test subset.
2. If it passes, run the full suite:

```bash
python3.11 -m pytest
```

## Reporting Format

For each major change, record:

- what changed,
- what ran,
- what passed or failed,
- what remains,
- exact file paths for created/modified artifacts.

Update `RUN_HISTORY.md`, `PROCESS_LOG.md`, or `RESUME.md` when runs are long or resumable.

Keep responses concise and point to exact files, commands, metrics, and next steps.

## Review Checklist

Before marking work complete, review for:

- silent metric drift,
- data leakage,
- seed leakage,
- benchmark contamination,
- overclaiming in docs/report text,
- missing artifact checks,
- missing resume instructions.

## ARC Boundary

Do not add ARC integration unless local ARC files are confirmed present and readable. If absent, log that explicitly and continue with synthetic/smoke evaluations.

## Formal Boundary

Never describe finite checks as full category theory, full HoTT, or exact algorithmic information dynamics. Use:

- category-inspired finite compositional checks,
- finite path witness / repairability check,
- AID proxy / MDL-style intervention proxy.
