"""CORA-TTI: competition-track components (phase P2 of CORA_PARENT_ARCHITECTURE.md).

Governed by docs/CORA_DATA_ACCESS_DAG.md and by tests/test_cora_parent_isolation.py:
this package may read public ARC training data, synthetic corpora, and the frozen
eval-split protocol file — nothing sealed. The DEV/HOLDOUT discipline of
outputs/tti/eval_split_v1.json is enforced in code (holdout runs demand an explicit
gate name and are ledgered).
"""
