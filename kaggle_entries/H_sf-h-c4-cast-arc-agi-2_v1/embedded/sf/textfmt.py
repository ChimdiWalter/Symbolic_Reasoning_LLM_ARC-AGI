"""The checkpoint's grid text format, as found empirically (probes/format_probe.py; PROGRESS.md, 26 Oct).

The vocabulary has 16 tokens: digits 0-9 are ids 0-9, newline 10, "user" 11, "assistant" 12, <|endoftext|> 13,
<|im_start|> 14, <|im_end|> 15. A task is a multi-turn chat: each demonstration input is a user turn and its output
the following assistant turn; the test input is the last user turn and the answer is generated as the assistant turn.
Inside a turn a grid is its rows of digits joined by newlines, with no trailing newline.
"""
import numpy as np

NL, USER, ASSIST, EOT, IMS, IME = 10, 11, 12, 13, 14, 15
DIGITS = tuple(range(10))
MAX_SIDE = 30
MAX_OUT_TOKENS = MAX_SIDE * (MAX_SIDE + 1)        # 30 rows of 30 digits, 29 newlines, the end token


def grid_ids(g):
    out = []
    for r, row in enumerate(np.asarray(g).tolist()):
        if r:
            out.append(NL)
        out.extend(int(v) for v in row)
    return out


def user_turn(g):
    return [IMS, USER, NL] + grid_ids(g) + [IME, NL]


def assistant_turn(g):
    return [IMS, ASSIST, NL] + grid_ids(g) + [IME, NL]


ANSWER_PREFIX = [IMS, ASSIST, NL]


def prompt_ids(pairs, test_input):
    ids = []
    for i, o in pairs:
        ids += user_turn(i) + assistant_turn(o)
    return ids + user_turn(test_input) + ANSWER_PREFIX


def target_ids(g):
    """The tokens the model should emit for grid g: its rows, then the end-of-turn token."""
    return grid_ids(g) + [IME]


def parse_ids(ids):
    """Tokens of a generated answer (end token optional) to a grid, or None if they are not a valid grid."""
    rows, cur = [], []
    for t in ids:
        if t == IME:
            break
        if t == NL:
            rows.append(cur)
            cur = []
        elif 0 <= t <= 9:
            cur.append(int(t))
        else:
            return None
    rows.append(cur)
    if not rows or not rows[0] or len(rows) > MAX_SIDE:
        return None
    w = len(rows[0])
    if w > MAX_SIDE or any(len(r) != w for r in rows):
        return None
    return rows


class GridConstraint:
    """Per-sequence state for constrained decoding: every emitted sequence is a rectangular grid of at most 30 x 30
    followed by the end token. allowed() returns the set of permitted next tokens."""

    __slots__ = ("width", "row_len", "n_rows", "done")

    def __init__(self):
        self.width, self.row_len, self.n_rows, self.done = None, 0, 0, False

    def allowed(self):
        if self.done:
            return ()
        if self.width is None:
            if self.row_len == 0:
                return DIGITS
            if self.row_len >= MAX_SIDE:
                return (NL, IME)
            return DIGITS + (NL, IME)
        if self.row_len < self.width:
            return DIGITS
        if self.n_rows + 1 >= MAX_SIDE:
            return (IME,)
        return (NL, IME)

    def step(self, t):
        if t == IME:
            self.done = True
        elif t == NL:
            if self.width is None:
                self.width = self.row_len
            self.n_rows += 1
            self.row_len = 0
        else:
            self.row_len += 1
