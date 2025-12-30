
from typing import List, Tuple
import numpy as np
from components import Grid

def _palette(arr: np.ndarray):
    return sorted(int(x) for x in np.unique(arr))

def _summ_one(g: Grid) -> str:
    H, W = g.data.shape
    pal = _palette(g.data)
    return f"{H}x{W}, palette={pal}"

def _summ_pair(inp: Grid, out: Grid) -> str:
    return f"in[{_summ_one(inp)}] -> out[{_summ_one(out)}]"

def describe_pairs(train_pairs: List[Tuple[Grid, Grid]]) -> str:
    """Make a compact, model-friendly description of the demonstration pairs."""
    lines = []
    for i, (x, y) in enumerate(train_pairs):
        lines.append(f"Pair {i+1}: " + _summ_pair(x, y))
    return "\n".join(lines)



def make_llm_prompt_for_rule_induction(train_pairs) -> str:
    """Return a complete prompt asking an LLM to propose a one-sentence rule."""
    desc = describe_pairs(train_pairs) if train_pairs else "No pairs."
    return (
        "You are solving an ARC-AGI task.\n"
        "Given demonstration pairs (input -> output), infer a concise transformation rule.\n"
        "Constraints:\n"
        "- Return ONE imperative sentence (no explanations), e.g.,\n"
        "  'reflect blue vertical', 'translate green by (1,-2)',\n"
        "  'paint largest red to yellow', 'complete mirror horizontal'.\n"
        "- Use only color words (black, blue, red, green, yellow, gray, pink, orange, teal, brown)\n"
        "  or digits 0..9 for colors. If translation, write (dr,dc) as integers.\n"
        "- Do not include any extra text.\n\n"
        f"{desc}\n\n"
        "Rule:"
    )

