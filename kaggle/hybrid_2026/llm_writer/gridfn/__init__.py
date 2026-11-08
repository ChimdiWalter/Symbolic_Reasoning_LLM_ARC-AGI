"""Grid-function language (gridfn-1): a bounded Python-like program language for the LLM-writer hybrid's versioned
comparison (CORA's typed language against a grid-function AST). The model's text is parsed with Python's `ast`
module, checked against an explicit allowlist and run by this package's own tree interpreter in a resource-limited
worker process; nothing it writes is compiled or executed as Python. Entry point: `llm_writer.gridfn.adapter`.
This package imports nothing heavy at import time (the worker process imports only the standard library and it).
"""
