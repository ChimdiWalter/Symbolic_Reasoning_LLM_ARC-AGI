"""Real ARC causal pilot v1 (protocol docs/CORA_REAL_ARC_CAUSAL_PILOT_v1.md).

Two sides that never share a process: the REASONER (bundle.py, native.py,
reasoner.py, isolation.py) sees only demonstrations and unlabelled test
inputs under opaque keys; the BLIND EVALUATOR (evaluator.py) holds the key
map and reads the pinned solutions file only after the reasoner's
predictions are committed.
"""
