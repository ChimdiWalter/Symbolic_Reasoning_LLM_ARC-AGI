"""Prompts. Every invention arm (C2, C3, C5) gets the same system message, language card, puzzle and instructions;
they differ only in the failure report: none (C2), another family's task's report (C3), the task's own report (C5).
C1 (whole-program writing with repair) gets the same puzzle and substrate rules. All program text in prompts uses
neutral codes (naming.py). `scan` refuses any prompt that names a removed capability.
"""
import re

from cgrow import naming as NM

BANNED = ("compress", "downscale", "upscale", "hupscale", "vupscale", "trim", "scale", "arc-dsl", "arc_dsl", "hodel")
SUBSTRATE = ("plain Python on lists of lists (no imports); built-ins len, range, min, max, sum, abs, set, sorted, "
             "list, tuple, zip, enumerate, any, all, dict; helpers shape(g) -> (rows, cols), "
             "new_grid(rows, cols, color) and copy(g); no other library functions")
SYSTEM = ("You are the invention module of a program-synthesis system for grid puzzles. A grid is a list of rows; "
          "each cell is an integer from 0 to 9. Answer in the requested format only.")


class Leak(ValueError):
    pass


def scan(text):
    low = text.lower()
    hits = [w for w in BANNED if re.search(r"(?<![a-z])" + re.escape(w), low)]
    if hits:
        raise Leak("prompt names a removed capability: " + ", ".join(hits))
    return True


def puzzle_block(task):
    out = []
    for k, (a, b) in enumerate(task["train"], 1):
        out.append(f"Example {k} input:\n{NM.grid_block(a)}\nExample {k} output:\n{NM.grid_block(b)}")
    for q in task["test_inputs"]:
        out.append(f"Query input:\n{NM.grid_block(q)}")
    return "\n\n".join(out)


def card_block(names, g):
    lines = names.card(g)
    return ("Operations of the current language that take and return whole grids (each code is an arbitrary name):\n"
            + "\n".join("  " + x for x in lines)
            + f"\nThe language also has {names.n_other(g)} operations on objects, cell sets, numbers and functions "
            "(not listed). A program is a composition of operations applied to the input grid I.")


def failure_block(rec, names, max_sketches=2, max_pairs=2, sketches=True):
    b, d = rec["base"], rec["probe_deeper_search"]
    lines = ["FAILURE REPORT (from the system's own search on this puzzle)"]
    comp = "complete" if not b["closure_capped"] else "complete except capped function-valued subprograms"
    lines.append(f"- Search: every program of cost up to {b['level_complete']} was enumerated ({comp}; "
                 f"{b['bank']} distinct intermediate values); none reproduces all examples. A deeper search with 4 "
                 f"times the budget (cost up to {d['level_complete']}) found none either.")
    c = rec.get("closest")
    if c:
        pct = round(100 * c["cells_correct"] / max(1, c["cells_total"]))
        lines.append(f"- Closest program: {names.show(c['program_tree'])} gives outputs of the right size on every "
                     f"example, with {pct}% of all output cells correct.")
        if c["residual"] is not None:
            lines.append(f"  On example {c['residual_demo'] + 1}, the expected value where it is wrong (. = right):\n"
                         + "\n".join("    " + "".join(r) for r in c["residual"]))
    else:
        lines.append("- No program produced outputs of the right size on every example.")
    lines.append(f"- Output size: {rec['shape_relation']}.")
    if sketches:
        lines.append("- Unreachable sketches. Each decomposes the outputs into a known part and a missing part ?; no "
                     "program up to the searched cost produces ? on all examples:")
    for k, s in enumerate(rec["sketches"][:max_sketches] if sketches else [], 1):
        if s["form"] == "?(I)":
            lines.append(f"  ({k}) ?(I): ? must map each example input to its output, as shown in the puzzle "
                         f"(input already explains {round(100 * s['score'])}% of the target)")
            continue
        if s["form"] == "B(?(I))":
            form = f"{names.code[s['outer']]}(?(I))"
            what = f"? must map each example input to the grid that {names.code[s['outer']]} turns into the output"
        else:
            form = f"?({names.code[s['inner']]}(I))"
            what = f"? must map {names.code[s['inner']]}(input) to the output"
        lines.append(f"  ({k}) {form}: {what} (input already explains {round(100 * s['score'])}% of the target):")
        for j, (x, y) in enumerate(s["pairs"][:max_pairs], 1):
            lines.append(f"    example {j}: ? maps\n{NM.grid_block(x, '      ')}\n    to\n{NM.grid_block(y, '      ')}")
    verdicts = "; ".join(f"{h['level']}: {h['verdict']}" for h in rec["hypotheses"])
    lines.append(f"- Competing diagnoses: {verdicts}.")
    return "\n".join(lines)


FORMAT = """Reply in exactly this format:
OBSERVATION: one sentence: how each example output relates to its input
LEVEL: the part of the system that is inadequate (one of: representation, interpretation, relation, operation, composition, search, insufficient_evidence)
GAP: one sentence: which capability is missing
NAME: a short identifier for the new operation
PARAMS: none (an integer parameter only if the operation needs one, written as  n: int LOW..HIGH)
SEMANTICS: one or two sentences: the output as a function of the input
PRECONDITIONS: conditions on the input grid, or none
USE: how a program uses it, for example NEW(I), or Qxxx(NEW(I)) with an existing code Qxxx
```python
def new_op(grid):
    ...
    return result

TESTS = [
    (input_grid, expected_output_grid),
]
```
The function must be named new_op; with a parameter its signature is new_op(grid, n). Write the code in {substrate};
no comments. Give 2 or 3 TESTS on tiny grids (at most 4 x 4; with a parameter: (input_grid, n, expected_output_grid)).
Keep the whole reply short."""


def spec_block(pairs, param):
    """Evaluator-only diagnostic D0: the exact behaviour of the missing operation on this puzzle's grids."""
    lines = ["SPECIFICATION OF THE MISSING OPERATION (diagnostic): the operation the system lacks maps these grids"
             + (f" (with its integer parameter equal to {param})" if param is not None else "") + ":"]
    for j, (x, y) in enumerate(pairs, 1):
        lines.append(f"  example {j}:\n{NM.grid_block(x, '    ')}\n  to\n{NM.grid_block(y, '    ')}")
    return "\n".join(lines)


def invent_messages(task, names, g, failure=None, extra=None, sketches=True):
    parts = [card_block(names, g), "PUZZLE (grids: one row per line, one digit per cell)\n" + puzzle_block(task)]
    if failure is not None:
        parts.append(failure_block(failure, names, sketches=sketches))
    if extra is not None:
        parts.append(extra)
    parts.append("YOUR TASK\nPropose ONE new grid operation that is not already in the language and that would let "
                 "the system solve this puzzle. Prefer an operation general enough to be reused on other puzzles: "
                 "the system will add it to its language and search again for a program that combines it with the "
                 "existing operations.\n\n" + FORMAT.replace("{substrate}", SUBSTRATE))
    text = "\n\n".join(parts)
    scan(text)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]


C1_FORMAT = """Reply with one code block:
```python
def transform(grid):
    ...
    return result
```
Write the code in {substrate}; no comments. Keep the reply short."""


def c1_messages(task):
    text = ("PUZZLE (grids: one row per line, one digit per cell)\n" + puzzle_block(task) + "\n\nYOUR TASK\nWrite a program transform(grid) that maps every example "
            "input to its output; it will be run on the query input.\n\n" + C1_FORMAT.replace("{substrate}", SUBSTRATE))
    scan(text)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]


def c1_repair_messages(task, code, feedback):
    text = ("PUZZLE (grids: one row per line, one digit per cell)\n" + puzzle_block(task) + "\n\nA previous program:\n```python\n" + code + "\n```\n"
            "Its results on the examples:\n" + feedback + "\n\nYOUR TASK\nWrite a corrected program transform(grid) "
            "that maps every example input to its output.\n\n" + C1_FORMAT.replace("{substrate}", SUBSTRATE))
    scan(text)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]
