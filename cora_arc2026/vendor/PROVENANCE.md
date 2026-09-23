# Vendored TFG extractor

Source: `Reasoning_Project_tti/cora_tti/tfg_extractor.py`
Source sha256: `edab8f0910298d327be5cb7d1aa20645373bf992a792fa092bd18eaeb301d1b9`
Vendored: 2026-09-23, at TTI worktree head 98d71a7.

The research worktree is frozen, so the one compatibility change is made on
this copy instead of upstream. The change is backward compatible: with no
evaluator supplied the vendored copy behaves exactly as the original.

Same representation throughout: `cora_parent.tfg.ConcreteTFG`, `TFGNode`,
`TFGEdge`, the same node kinds, the same `FRONTIER_OUTCOMES`, the same
frontier cap. No second graph format and no second observer schema.

## The only diff

`build_tfg(..., candidate_evaluator=None)` and
`extract(..., candidate_evaluator=None)`, threaded to
`_mismatch_signature`, which calls `candidate_evaluator(ast, grid, env)`
when one is given and `E.evaluate(ast, grid, env)` otherwise.

This changes only how an ALREADY OBSERVED candidate is executed to produce
diagnostic evidence. It does not change search, candidate generation,
candidate ordering, fitting, grammar, verifier, acceptance, budgets, the
frontier definition, Step B, or the TTI research tree.
