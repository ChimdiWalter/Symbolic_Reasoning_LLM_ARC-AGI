"""Generate the Step-A trace copy of the frozen blind search, mechanically.

Step A must report which typed terms AROSE in the goal-directed derivation of
a failed leave-one-out fold. The frozen search returns candidates, not its
enumeration, so an observer is needed. Two ways to get one were available and
only one is acceptable:

    monkeypatching the frozen module at runtime -- rejected. The patch would
    live in the runner, would not be hashable as part of the searched code,
    and the reader could never check that the timed search was the frozen one.

    a generated copy whose ONLY difference is trace emission -- taken here.

The generation is anchored, insertion-only and audited. Every inserted line
ends in ``# TRACE`` and the observer plumbing lives inside one delimited
prologue, so the audit is exact: delete the prologue, delete every line
tagged ``# TRACE``, and the result must be byte-identical to the frozen
``search.py``. Enumeration order, per-type caps, the deadline, slot fitting,
ranking and acceptance are therefore provably untouched.

What this CANNOT remove is instrumentation cost. Appending a tuple per
generated term is work done inside the frozen 8-second budget, so the traced
search can truncate marginally earlier than the frozen one on a task that was
already at the budget wall. That is why Step A takes its LOO verdict and its
trace from the SAME traced run: the verdict always describes the run that
produced the evidence. The residual overhead is measured by the gate script
and recorded, never assumed to be zero.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "level4_blind_runtime"
FROZEN = RUNTIME_DIR / "search.py"
GENERATED = RUNTIME_DIR / "stepA_trace_search.py"
OUT = ROOT / "outputs" / "cora_breakthrough"

PROLOGUE = '''
# --- TRACE PROLOGUE BEGIN ---
# Inserted by scripts/cora_level4_build_trace_search.py. Everything below
# this comment and above the END marker is additive: it defines an observer
# and a way to install one. No name defined here is read by any line of the
# frozen body except through the ``_OBS`` calls, each of which is tagged
# ``# TRACE`` and returns None.


class _NullObserver:
    """The default: every hook is a no-op, so behaviour is the frozen one."""

    def term(self, wanted, depth, ast):
        pass

    def truncate(self, kind):
        pass

    def maybe_deadline(self, deadline):
        pass

    def candidate(self, ast, outcome):
        pass


class TraceObserver:
    """Records what arose. Appends only; no serialization while timed."""

    def __init__(self):
        self.terms = []
        self.truncations = set()
        self.candidates = []

    def term(self, wanted, depth, ast):
        self.terms.append((str(wanted), depth, ast))

    def truncate(self, kind):
        self.truncations.add(kind)

    def maybe_deadline(self, deadline):
        if time.monotonic() > deadline:
            self.truncations.add("deadline_depth_loop")

    def candidate(self, ast, outcome):
        self.candidates.append((ast, outcome))


_OBS = _NullObserver()


def set_observer(observer):
    """Install an observer for the next search; None restores the no-op."""
    global _OBS
    _OBS = observer if observer is not None else _NullObserver()
# --- TRACE PROLOGUE END ---
'''

#: (anchor, replacement). Every anchor must occur EXACTLY once in the frozen
#: text, and every added line must end in "# TRACE".
PATCHES = [
    (
        "from . import env as E\n",
        "from . import env as E\n" + PROLOGUE.lstrip("\n"),
    ),
    (
        "        if not V.type_equal(env.result_type(name), wanted):\n"
        "            continue\n"
        "        if time.monotonic() > deadline:\n"
        "            break\n",

        "        if not V.type_equal(env.result_type(name), wanted):\n"
        "            continue\n"
        "        if time.monotonic() > deadline:\n"
        "            _OBS.truncate"
        "(\"deadline_enumeration\")  # TRACE\n"
        "            break\n",
    ),
    (
        "        for combination in _product(options):\n"
        "            out.append((name, combination))\n"
        "            stats.generated += 1\n"
        "            if len(out) >= PER_TYPE_CAP:\n"
        "                break\n"
        "        if len(out) >= PER_TYPE_CAP:\n"
        "            break\n",

        "        for combination in _product(options):\n"
        "            out.append((name, combination))\n"
        "            _OBS.term(wanted, depth, (name, combination))  # TRACE\n"
        "            stats.generated += 1\n"
        "            if len(out) >= PER_TYPE_CAP:\n"
        "                _OBS.truncate(\"per_type_cap\")  # TRACE\n"
        "                break\n"
        "        if len(out) >= PER_TYPE_CAP:\n"
        "            _OBS.truncate(\"per_type_cap\")  # TRACE\n"
        "            break\n",
    ),
    (
        "    for depth in range(1, MAX_DEPTH + 1):\n"
        "        if time.monotonic() > deadline or by_signature:\n"
        "            break\n",

        "    for depth in range(1, MAX_DEPTH + 1):\n"
        "        _OBS.maybe_deadline(deadline)  # TRACE\n"
        "        if time.monotonic() > deadline or by_signature:\n"
        "            break\n",
    ),
    (
        "        for ast in frontier:\n"
        "            if time.monotonic() > deadline:\n"
        "                break\n"
        "            if E.type_of(ast, env) is None:\n"
        "                continue\n"
        "            stats.typed += 1\n",

        "        for ast in frontier:\n"
        "            if time.monotonic() > deadline:\n"
        "                _OBS.truncate(\"deadline_candidates\")  # TRACE\n"
        "                break\n"
        "            if E.type_of(ast, env) is None:\n"
        "                _OBS.candidate(ast, \"typecheck_failed\")  # TRACE\n"
        "                continue\n"
        "            stats.typed += 1\n"
        "            _OBS.candidate(ast, \"typed\")  # TRACE\n",
    ),
    (
        "            complete, evidence = fit_slots(ast, pairs, memo, env)\n"
        "            if complete is None:\n"
        "                stats.rejected += 1\n"
        "                continue\n"
        "            signature = observational_signature(complete, pairs, env)\n"
        "            if signature is None:\n"
        "                stats.rejected += 1\n"
        "                continue\n",

        "            complete, evidence = fit_slots(ast, pairs, memo, env)\n"
        "            if complete is None:\n"
        "                _OBS.candidate(ast, \"slot_fit_failed\")  # TRACE\n"
        "                stats.rejected += 1\n"
        "                continue\n"
        "            _OBS.candidate(ast, \"slot_fit_ok\")  # TRACE\n"
        "            _OBS.term(goal, depth, complete)  # TRACE\n"
        "            signature = observational_signature(complete, pairs, env)\n"
        "            if signature is None:\n"
        "                _OBS.candidate(ast, \"executed_not_exact\")  # TRACE\n"
        "                stats.rejected += 1\n"
        "                continue\n"
        "            _OBS.candidate(ast, \"exact\")  # TRACE\n",
    ),
]


def strip_generated(text: str) -> str:
    """Undo the generation: drop the prologue and every ``# TRACE`` line."""
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        if line.strip() == "# --- TRACE PROLOGUE BEGIN ---":
            inside = True
            continue
        if line.strip() == "# --- TRACE PROLOGUE END ---":
            inside = False
            continue
        if inside:
            continue
        if line.rstrip().endswith("# TRACE"):
            continue
        out.append(line)
    return "".join(out)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    frozen_text = FROZEN.read_text()
    generated = frozen_text
    applied = []
    for anchor, replacement in PATCHES:
        occurrences = generated.count(anchor)
        if occurrences != 1:
            print(f"ABORT: anchor occurs {occurrences} times, expected 1:\n"
                  f"{anchor[:120]!r}")
            return 1
        generated = generated.replace(anchor, replacement)
        applied.append({"anchor_first_line": anchor.splitlines()[0].strip(),
                        "added_lines": len(replacement.splitlines())
                        - len(anchor.splitlines())})

    # -- the audit that makes "differs only by trace emission" checkable ----
    restored = strip_generated(generated)
    if restored != frozen_text:
        print("ABORT: stripping the generated file does not restore search.py")
        first = next((i for i, (a, b) in enumerate(
            zip(restored.splitlines(), frozen_text.splitlines())) if a != b),
            None)
        print(f"first differing line index: {first}")
        return 1

    added = [line for line in generated.splitlines()
             if line.rstrip().endswith("# TRACE")]
    for line in added:
        if "_OBS." not in line:
            print(f"ABORT: tagged line is not an observer call: {line!r}")
            return 1

    GENERATED.write_text(generated)

    report = {
        "gate": "Step-A trace search generation",
        "method": ("anchored insertion-only patching of the frozen blind "
                   "search, audited by round-trip: removing the delimited "
                   "prologue and every line tagged # TRACE restores "
                   "search.py byte for byte"),
        "source": "level4_blind_runtime/search.py",
        "source_sha256": sha256(FROZEN),
        "generated": "level4_blind_runtime/stepA_trace_search.py",
        "generated_sha256": sha256(GENERATED),
        "generator_sha256": sha256(Path(__file__)),
        "patches_applied": applied,
        "trace_tagged_lines": len(added),
        "prologue_lines": len(PROLOGUE.strip().splitlines()),
        "round_trip_identical_to_frozen_search": True,
        "known_limitation": ("instrumentation costs time inside the frozen "
                             "budget; Step A therefore takes its LOO verdict "
                             "and its trace from the same traced run, and the "
                             "gate script measures the overhead"),
    }
    (OUT / "level4_stepA_trace_build.json").write_text(
        json.dumps(report, indent=1))

    print("TRACE SEARCH GENERATED")
    print(f"  patches applied     {len(applied)}")
    print(f"  trace-tagged lines  {len(added)}")
    print(f"  round-trip identity PASS")
    print(f"  generated sha256    {report['generated_sha256'][:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
