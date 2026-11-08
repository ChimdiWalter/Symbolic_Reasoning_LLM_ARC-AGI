"""The scorer of study B (evaluator side): the only module that opens test outputs.

The benchmark's solution file holds the source and held halves together (study A's prepared data, read only). Without
the GO, a request for source outputs never materialises a held value: the file is read as text, its digest is
checked against the freeze, and only the requested source ids' values are decoded in place (`raw_decode` at each
id's key); the held entries stay undecoded text. A request that includes any held id requires the GO (ngb.gate),
after which the file is parsed whole. The ARC-AGI-2 solutions are opened only behind the GO. Scoring rules are study
A's (ngrow.score): exact match per test output, pass@2 over the two attempts; a search without a fit abstains.
"""
import hashlib
import json
import os

from ngb import env as E, gate as GT
from ngrow import data as DT, score as SA

ARC2_CHALLENGES, ARC2_SOLUTIONS, ARC2_SHA256 = SA.ARC2_CHALLENGES, SA.ARC2_SOLUTIONS, SA.ARC2_SHA256
score_row, per_output = SA.score_row, SA.per_output
_WS = " \t\r\n"


class SolutionFileError(RuntimeError):
    pass


#: where the scorer reads solution files; on Athe in rehearsal mode the data root holds source inputs only, so the
#: real prepared root is given here (its source values are decoded in place; no held value is decoded)
SOL_ROOT = os.environ.get("NGB_SOLUTIONS_ROOT", E.DATA)


def _read_checked(bench):
    path = os.path.join(SOL_ROOT, bench, "solutions_scorer_only", "solutions.json")
    with open(path, "rb") as f:
        raw = f.read()
    digest = hashlib.sha256(raw).hexdigest()
    if os.path.exists(GT.FREEZE):
        want = E.load(GT.FREEZE).get("scorer_only_sha256", {}).get(f"{bench}/solutions_scorer_only/solutions.json")
        if want and want != digest:
            raise SolutionFileError(f"{bench}: the solution file's digest differs from the frozen one")
    return raw.decode("utf-8"), digest


def _decode_ids(text, ids):
    """Decode only the requested ids' values; every other value stays undecoded text."""
    dec = json.JSONDecoder()
    out = {}
    for t in ids:
        key = json.dumps(t) + ":"
        i = text.find(key)
        if i < 0 or text.find(key, i + 1) >= 0:
            raise SolutionFileError(f"task {t}: key not found exactly once")
        j = i + len(key)
        while text[j] in _WS:
            j += 1
        val, _ = dec.raw_decode(text, j)
        out[t] = [DT.grid(g) for g in val]
    return out


def solutions(bench, ids):
    """Source ids: the file is read as text and only their values are decoded. Any held id of the REAL split (also
    in rehearsal mode, where the held half is replaced by the source half): the GO is required BEFORE the file is
    read, and the file is then parsed whole."""
    ids = list(ids)
    held = {t for _, _, t in E.REAL_HALF("held", (bench,))}
    if set(ids) & held:
        if E.REHEARSAL:
            raise GT.GateRefused("rehearsal mode never opens a held test output")
        GT.require_go()
        text, _ = _read_checked(bench)
        sol = json.loads(text)
        return {t: [DT.grid(g) for g in sol[t]] for t in ids}
    text, _ = _read_checked(bench)
    return _decode_ids(text, ids)


BENCH_OF_PREFIX = {"co": "concept_arc", "mi": "mini_arc", "1d": "1d_arc"}


def arc2_solutions():
    """Behind the GO. In rehearsal mode the stand-in evaluation set is made of source tasks, whose outputs are
    decoded in place from the source-plus-held solution files (no held value is decoded)."""
    GT.require_go()
    if E.REHEARSAL:
        ids = sorted(E.load(os.path.join(E.STUDY, "rehearsal", "arc2_standin_challenges.json")))
        out = {}
        for t in ids:
            out.update(solutions(BENCH_OF_PREFIX[t[:2]], [t]))
        return out
    if E.sha_file(ARC2_SOLUTIONS) != ARC2_SHA256["arc-agi_evaluation_solutions.json"]:
        raise SolutionFileError("ARC-AGI-2 evaluation solutions changed")
    with open(ARC2_SOLUTIONS, encoding="utf-8") as f:
        sol = json.load(f)
    return {t: [DT.grid(g) for g in v] for t, v in sol.items()}
