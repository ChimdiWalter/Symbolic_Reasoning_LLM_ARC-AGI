"""CORA × Qwen3-4B (NVARC) neural–symbolic fusion (DEVELOPMENT; separately versioned, 2026-10-19).

The neural solver (NVARC, reproduced unchanged) proposes candidate grids; CORA-v2 builds the executable hypotheses that
reproduce the demonstrations, checks which candidates they explain, and offers its own predictions. A fixed,
preregistered policy decides the two attempts. Nothing in NVARC or CORA-v2 is modified; the no-op policy returns
NVARC's attempts unchanged.
"""
