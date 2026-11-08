"""LLM-writer hybrid entry: a publicly available pretrained language model writes CORA programs; CORA parses,
type-checks, executes, diagnoses and selects them. Prompting and sampling only (no training of any kind). Every
answer grid comes from CORA's execution of a program; the model never writes a grid, and nothing it writes is run
as Python. See PROGRESS.md and DESIGN.md.
"""
