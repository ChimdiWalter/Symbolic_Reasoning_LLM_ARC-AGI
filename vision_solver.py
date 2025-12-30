
from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional, Callable

import numpy as np
from components import Grid
from dsl import Program
import text_describer as TD
import llm_bridge_ext as LBE  # your bridge (module file: llm_bridge_ext.py)

# A callable type for an LLM function: prompt -> text rule
LLMFn = Callable[[str], str]

def _default_prompt(train_pairs: List[Tuple[Grid, Grid]]) -> str:
    # Use make_llm_prompt_for_rule_induction if present; else fall back to simple describe_pairs.
    if hasattr(TD, "make_llm_prompt_for_rule_induction"):
        return TD.make_llm_prompt_for_rule_induction(train_pairs)
    desc = TD.describe_pairs(train_pairs) if hasattr(TD, "describe_pairs") else "No pairs."
    return (
        "You are solving an ARC-AGI task.\n"
        "Given demonstration pairs (input -> output), infer a concise transformation rule.\n"
        "Return ONE imperative sentence only (no explanations), e.g.,\n"
        "'reflect blue vertical', 'translate green by (1,-2)',\n"
        "'paint largest red to yellow', 'complete mirror horizontal'.\n\n"
        f"{desc}\n\nRule:"
    )

def solve_with_llm_fallback(
    train_pairs: List[Tuple[Grid, Grid]],
    test_inputs: List[Grid],
    llm_fn: LLMFn,
    max_trials: int = 2,
) -> List[Dict[str, Any]]:
    """
    Produce predictions for each test input using a simple text-rule LLM fallback:
      returns: [{ "attempt_1": grid, "attempt_2": grid }, ...]
    """
    prompt = _default_prompt(train_pairs)
    text_rule = (llm_fn(prompt) or "").strip()

    prog: Optional[Program] = LBE.parse_rule_to_program(text_rule)
    if prog is None:
        # A couple of tiny canned tweaks; harmless if the rule failed to parse
        for tweak in ("mirror vertical", "mirror horizontal"):
            prog = LBE.parse_rule_to_program(tweak)
            if prog is not None:
                break

    results: List[Dict[str, Any]] = []
    for x in test_inputs:
        if prog is None:
            # Still emit a valid shape so submissions remain well-formed
            arr = x.data.astype(int).tolist()
            results.append({"attempt_1": arr, "attempt_2": arr})
            continue
        # Try up to max_trials variants; for now, emit the same program twice (placeholder)
        y1 = prog.run(x).data.astype(int).tolist()
        y2 = y1
        results.append({"attempt_1": y1, "attempt_2": y2})
    return results
