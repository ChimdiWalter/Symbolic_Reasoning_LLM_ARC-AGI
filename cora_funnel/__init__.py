"""CORA failure funnel (records/CORA_FAILURE_FUNNEL_20261014.md).

Measures where the frozen native object layer loses each task:
perception -> candidate generation -> demonstration fit -> leave-one-out
certification -> held-out correctness. Then, on the failing subsets, it
tests the competing explanations by controlled interventions.

- instrument.py: a read-only probe around the unchanged native code. It
  records what the inducer generated, fitted and certified, and restores
  every patched name on exit.
- run.py: the blind solver-side runner. It sees training pairs and test
  inputs only.
- evaluate.py: the independent evaluator, the only code that reads
  held-out answers.

Nothing here changes the verifier, native v23 or any frozen asset.
"""
