"""Tests of the two local copies of frozen modules (search_bl.py of the enumerator, gen_bl.py of the generator):
what was changed, that nothing else was, that they give what the originals give when no memory failure happens,
and that a memory failure can no longer be swallowed. The originals are imported here, for comparison only.
Author: Chimdi Walter Ndubuisi
Run: env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B -m pytest -q -p no:cacheprovider experiments/below_library_20261114/tests
"""
import ast
import difflib
import os
import re
import signal

import pytest

import bl_frozen
import dslx
import gen as frozen_gen             # the frozen generator: for comparison only
import search as frozen_search       # the frozen enumerator: for comparison only
import blocks_c as B
import build_bl as BB
import gen_bl
import guards_bl as G
import presets_bl as P
import search_bl

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = dslx.load()
PAIR = re.compile(r'^[ ]+except MemoryError:\n[ ]+raise ResourceStop\("[^"\n]*"\) from None\n', re.M)
# The listed additions of the budget counted in candidate combinations (search_bl.py only): (text of the copy, text of the original).
TICKS = (
    (", max_ticks=None):\n", "):\n"),
    ("    This copy: max_ticks, the stop 'budget_ticks' and the key ticks of the result are described in the module's text.\n", ""),
    ("    tick = 0                                # this copy: bound here too, so that the count exists on every path\n", ""),
    ('                        if max_ticks is not None and tick >= max_ticks:\n'
     '                            st["stop"] = "budget_ticks"         # this copy: exactly max_ticks combinations were evaluated\n'
     '                            break\n', ""),
    (", ticks=tick)\n", ")\n"),
)
COPIES = {
    "search_bl.py": ("experiments/core_operations_20261113/search.py", search_bl, 2, 1),
    "gen_bl.py": ("experiments/core_operations_20261113/gen.py", gen_bl, 4, 3),
}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def after_docstring(text):
    assert text.startswith('"""')
    return text[text.index('"""', 3) + 3:]


# ---------------------------------------------------------------- what was changed, and nothing else
@pytest.mark.parametrize("name", sorted(COPIES))
def test_the_saved_delta_is_the_difference_between_the_original_and_the_copy(name):
    rel, module, _, _ = COPIES[name]
    original, copy = read(os.path.join(bl_frozen.ROOT, rel)), read(os.path.join(HERE, name))
    delta = "".join(difflib.unified_diff(original.splitlines(True), copy.splitlines(True), fromfile=rel,
                                         tofile="experiments/below_library_20261114/" + name, n=2))
    assert delta == read(os.path.join(HERE, name.replace(".py", ".delta")))
    assert module.ORIGINAL == rel and module.ORIGINAL_SHA256 == bl_frozen.sha256_file(os.path.join(bl_frozen.ROOT, rel))
    assert module.ORIGINAL_SHA256 == bl_frozen.HASHES[rel] == bl_frozen.stage_a_files()[rel]


@pytest.mark.parametrize("name", sorted(COPIES))
def test_the_copy_is_the_original_with_the_listed_changes_only(name):
    """Taking the listed additions out of the copy gives the original's code back, character for character (for
    the enumerator: without eval_tree, which is not copied)."""
    rel, module, n_pairs, n_broad = COPIES[name]
    original, copy = read(os.path.join(bl_frozen.ROOT, rel)), read(os.path.join(HERE, name))
    code = after_docstring(copy)
    assert len(PAIR.findall(code)) == n_pairs
    code = PAIR.sub("", code)
    pin = ('\nORIGINAL = "%s"\nORIGINAL_SHA256 = "%s"\nif bl_frozen.HASHES[ORIGINAL] != ORIGINAL_SHA256:\n'
           '    raise SystemExit("%s is a copy of another version of %%s: refusing to run" %% ORIGINAL)\n' % (rel, module.ORIGINAL_SHA256, name))
    for addition in ("import bl_frozen\n", "from guards_bl import ResourceStop\n", pin):
        assert code.count(addition) == 1, addition
        code = code.replace(addition, "")
    want = after_docstring(original)
    if name == "search_bl.py":
        for added, was in TICKS:                                     # the budget counted in combinations: five listed places
            assert code.count(added) == 1, added
            code = code.replace(added, was)
        assert "max_ticks" not in code and "budget_ticks" not in code and "ticks=" not in code      # nothing of the budget is left
        cut = want.index("\n\ndef eval_tree(tree, ns, consts, params):")
        assert want[cut:].count("\ndef ") == 1                      # eval_tree is the last definition of the original
        want = want[:cut] + "\n"
        assert not hasattr(search_bl, "eval_tree")
    assert code == want
    # the original's own description is kept whole inside the copy's text
    head = original[3:original.index('"""', 3)]
    assert head.strip() in copy[:copy.index('"""', 3)] and "Author: Chimdi Walter Ndubuisi" in copy[:400]
    assert len(re.findall(r"except Exception", original)) == n_broad == len(re.findall(r"except Exception", copy))


def broad_handlers(tree):
    """[(try node, index of the handler of Exception)] for every try statement of a module."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for i, h in enumerate(node.handlers):
                if h.type is None or (isinstance(h.type, ast.Name) and h.type.id in ("Exception", "BaseException")):
                    out.append((node, i))
    return out


def translated_before(node, i):
    """True when a handler of MemoryError comes before handler i of this try statement and never falls into it: it
    raises, or it records an infrastructure stop by name (the two places that end a search or a target)."""
    for h in node.handlers[:i]:
        if isinstance(h.type, ast.Name) and h.type.id == "MemoryError":
            if len(h.body) == 1 and isinstance(h.body[0], ast.Raise):
                return True
            return "memory_failure" in ast.unparse(h)
    return False


def test_no_broad_handler_can_see_a_memory_failure_first():
    """In every module of this experiment, each handler of ordinary errors (`except Exception`) is preceded, in the
    same try statement, by a handler of MemoryError that raises or records a memory failure. There is no bare
    handler and no handler of BaseException."""
    names = [n for n in sorted(os.listdir(HERE)) if n.endswith("_bl.py") or n in ("blocks_c.py", "bl_frozen.py")]
    assert {"search_bl.py", "gen_bl.py", "build_bl.py", "guards_bl.py", "blocks_c.py"} <= set(names)
    seen = 0
    for name in names:
        tree = ast.parse(read(os.path.join(HERE, name)))
        for node, i in broad_handlers(tree):
            h = node.handlers[i]
            assert h.type is not None and h.type.id == "Exception", "%s line %d: a bare or BaseException handler" % (name, h.lineno)
            assert translated_before(node, i), "%s line %d: except Exception without except MemoryError before it" % (name, h.lineno)
            seen += 1
    assert seen >= 5
    # the originals, as the control: their broad handlers have no such translation
    for rel, n in (("experiments/core_operations_20261113/search.py", 1), ("experiments/core_operations_20261113/gen.py", 3)):
        tree = ast.parse(read(os.path.join(bl_frozen.ROOT, rel)))
        found = broad_handlers(tree)
        assert len(found) == n and not any(translated_before(node, i) for node, i in found)


def test_the_experiments_modules_do_not_import_the_originals():
    for name in sorted(os.listdir(HERE)):
        if name.endswith("_bl.py") or name == "blocks_c.py":
            tree = ast.parse(read(os.path.join(HERE, name)))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported |= {a.name for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    imported.add(node.module)
            assert not imported & {"search", "gen", "core", "consumers", "vsearch", "gate", "episode", "library", "frozen"}, (name, imported)


# ---------------------------------------------------------------- the same searches, when no memory failure happens
def invented_cases():
    """(label, block set, hidden, examples, size limit, operations kept or None, function-valued leaves kept)."""
    tt = [(((1, 2), (3,)),), (((), (4, 5, 6), (7,)),), (((8, 9, 1, 2),),), (((3, 4), (), (5,), (6, 7, 8)),), (((1,), (2, 3)),), (((9,), (), ()),)]
    flat = [((3, 1, 2), 4), ((5, 5), 1), ((9, 0, 4, 4), 7), ((7,), 2), ((2, 8), 3), ((6, 1, 1), 5)]
    bools = [(True, (True,)), (True, (False, True)), (False, (True, False)), (False, (False,)), (True, (True, False)), (True, (False,))]
    targets = [
        ("lengths", lambda x0: tuple(len(e) for e in x0), tt), ("count", lambda x0: len(x0), tt),
        ("reverse", lambda x0, x1: x0[::-1], flat), ("shifted", lambda x0, x1: tuple(x1 - e for e in x0), flat),
        ("and first", lambda x0, x1: x0 and x1[0], bools), ("nothing fits", lambda x0, x1: (x1, x1, len(x0), 99), flat),
    ]
    out = []
    for label, f, argsets in targets:
        ex = [(tuple(a), f(*a)) for a in argsets]
        for block_set, size in (("C", 2), ("C", 3), ("L", 2), ("L", 3), ("LC", 2)):
            out.append(("%s %s%d" % (label, block_set, size), block_set, (), ex, size, None, None))
    ex = [(tuple(a), tuple(a[1] - e for e in a[0])) for a in flat]
    out.append(("lbind restricted C5", "C", (), ex, 5, {"c_map_tuple", "c_sub", "c_add", "lbind", "rbind", "compose"}, {"c_sub", "c_add", "c_len"}))
    out.append(("fork restricted C6", "C", (), ex, 6, {"c_map_tuple", "c_sub", "c_len", "fork", "chain"}, {"c_sub", "c_len", "c_neg"}))
    out.append(("and first C4", "C", (), [(tuple(a), a[0] and a[1][0]) for a in bools], 4, None, None))
    return out


def development_cases():
    out = []
    for name in ("backdrop", "mapply", "rot180", "color"):
        g = gen_bl.gen_examples(name, n_total=P.N_GEN)
        assert g["status"] == "ok" and name in P.DEV_ROSTER
        hidden = sorted(LIB["fam_of"][name])
        for block_set, size in (("L", 3), ("C", 3), ("LC", 3), ("L", 4)):
            out.append(("%s %s%d" % (name, block_set, size), block_set, hidden, g["examples"][:9], size, None, None))
    return out


def one_search(module, block_set, hidden, ex, size, keep_ops, keep_fn):
    ops, leaves, Y = BB.build(block_set, hidden, ex)[:3]
    if keep_ops is not None:
        ops = [o for o in ops if o[0] in keep_ops]
        leaves = [leaf for leaf in leaves if leaf[0][0] != "FN" or leaf[0][1] in keep_fn]
    r = module.search(ops, leaves, Y, 300.0, size, P.MAX_FN, P.MAX_BANK)
    return (r["found"], r["stop"], r["level"], r["bank"], r["function_cap_reached"]), set(r)


def test_the_copy_of_the_enumerator_gives_the_same_searches():
    cases = invented_cases() + development_cases()
    assert len(cases) >= 30 and {c[1] for c in cases} == {"L", "C", "LC"} and len({c[4] for c in cases}) >= 4
    found = 0
    for label, block_set, hidden, ex, size, keep_ops, keep_fn in cases:
        mine, mine_keys = one_search(search_bl, block_set, hidden, ex, size, keep_ops, keep_fn)
        theirs, their_keys = one_search(frozen_search, block_set, hidden, ex, size, keep_ops, keep_fn)
        assert mine == theirs, label                               # found text, size and tree; stop; level; bank; function cap
        assert mine_keys == their_keys | {"ticks"} and "ticks" not in their_keys, label       # the one key the copy adds
        assert mine[1] in ("found", "size_exhausted", "size_exhausted_function_cap"), label     # whole searches, not cut by time
        found += mine[0] is not None
    assert 5 <= found < len(cases)
    assert search_bl.render(("L", "f", ("P", "x0"), ("C", "ONE"))) == frozen_search.render(("L", "f", ("P", "x0"), ("C", "ONE")))
    assert search_bl.CAP == frozen_search.CAP == P.MAX_ELEMENTS and issubclass(search_bl.Hard, BaseException)


@pytest.mark.parametrize("name", P.DEV_ROSTER)
def test_the_copy_of_the_generator_gives_the_same_examples(name):
    mine, theirs = gen_bl.gen_examples(name, n_total=P.N_GEN), frozen_gen.gen_examples(name, n_total=P.N_GEN)
    assert set(mine) == set(theirs) == {"examples", "draws", "raised", "rejected", "status", "reason", "function_pool_excluded"}
    for key in ("draws", "raised", "rejected", "status", "reason", "function_pool_excluded"):
        assert mine[key] == theirs[key], key
    assert len(mine["examples"]) == len(theirs["examples"])
    for (a1, o1), (a2, o2) in zip(mine["examples"], theirs["examples"]):
        assert dslx.canon(tuple(a1)) == dslx.canon(tuple(a2)) and dslx.canon(o1) == dslx.canon(o2)
    assert gen_bl.seed_for(name) == frozen_gen.seed_for(name) and gen_bl.UNARY == frozen_gen.UNARY and gen_bl.BINARY == frozen_gen.BINARY


# ---------------------------------------------------------------- an injected memory failure is never swallowed
def failing_after(real, k, calls):
    """`real`, raising MemoryError at its k-th call (and only then)."""
    def f(*a, **kw):
        calls.append(1)
        if len(calls) == k:
            raise MemoryError()
        return real(*a, **kw)
    return f


EX = [((3, 1, 2), 4), ((5, 5), 1), ((9, 0, 4, 4), 7), ((7,), 2)]


def doubled(x0, x1):
    return x1 + x1                                               # first met at three nodes, after several hundred candidates


def length(x0, x1):
    return len(x0)                                               # met at two nodes: the first candidate of all


def small_search(module, target=doubled):
    ops, leaves, Y = BB.build("C", (), [(a, target(*a)) for a in EX])[:3]
    return module.search(ops, leaves, Y, 30.0, 3, P.MAX_FN, P.MAX_BANK)


def test_a_memory_failure_while_a_candidate_is_evaluated(monkeypatch):
    """The enumerator tags every value a candidate gives, inside its broad handler. A memory failure there: the
    original drops the candidate and goes on to the end; the copy stops with ResourceStop."""
    before = signal.getsignal(signal.SIGVTALRM)
    clean = small_search(frozen_search)
    assert clean["found"] is not None and small_search(search_bl)["found"] == clean["found"]
    calls = []
    monkeypatch.setattr(frozen_search, "tag", failing_after(dslx.tag, 400, calls))
    swallowed = small_search(frozen_search)                         # the control: no exception at all
    assert len(calls) > 400 and swallowed["stop"] in ("found", "size_exhausted")
    calls = []
    monkeypatch.setattr(search_bl, "tag", failing_after(dslx.tag, 400, calls))
    with pytest.raises(G.ResourceStop):
        small_search(search_bl)
    assert len(calls) == 400
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and signal.getsignal(signal.SIGVTALRM) == before


@pytest.mark.parametrize("where", ["canon", "norm", "tagset"])
def test_a_memory_failure_elsewhere_in_the_enumeration(monkeypatch, where):
    """Canonical text at acceptance (inside the bank's add), the tags of a new entry, the tags of the leaves: all
    outside the broad handler. The original lets a raw MemoryError out; the copy translates it."""
    before = signal.getsignal(signal.SIGVTALRM)
    for module, error in ((frozen_search, MemoryError), (search_bl, G.ResourceStop)):
        calls = []
        with monkeypatch.context() as m:
            m.setattr(dslx, where, failing_after(getattr(dslx, where), 1 if where == "canon" else 5, calls))
            with pytest.raises(error):
                small_search(module, length)
        assert calls
        assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and signal.getsignal(signal.SIGVTALRM) == before
    assert small_search(search_bl, length)["found"][0] == "c_len(x0)"       # nothing is left patched


def test_a_memory_failure_in_an_operation_reaches_the_caller_as_a_resource_stop():
    def hungry(x):
        raise MemoryError()
    ops, leaves, Y = BB.build("C", (), [(a, (a[1], a[1], len(a[0]))) for a in EX])[:3]
    for module in (frozen_search, search_bl):                       # the wrapper path: either enumerator
        with pytest.raises(G.ResourceStop):
            module.search(ops + [("hungry", BB.operation_wrapper(hungry), (dslx.ACC["Integer"],), False)], leaves, Y, 30.0, 2, P.MAX_FN, P.MAX_BANK)
    bare = ops + [("hungry", hungry, (dslx.ACC["Integer"],), False)]
    assert frozen_search.search(bare, leaves, Y, 30.0, 2, P.MAX_FN, P.MAX_BANK)["stop"] == "size_exhausted"      # swallowed by the original
    with pytest.raises(G.ResourceStop):
        search_bl.search(bare, leaves, Y, 30.0, 2, P.MAX_FN, P.MAX_BANK)


def patched_library(monkeypatch, name, k):
    """The full library with operation `name` raising MemoryError at its k-th call."""
    calls = []
    ns = dict(dslx.full_ns())
    ns[name] = failing_after(ns[name], k, calls)
    monkeypatch.setattr(dslx, "full_ns", lambda: ns)
    return calls


@pytest.mark.parametrize("target,failing,k,handler", [
    ("color", "color", 5, "the operation run on a draw"),
    ("mapply", "mapply", 5, "the operation tried with a drawn function"),
    ("rapply", "identity", 1, "a function tried on a value"),
])
def test_a_memory_failure_inside_each_handler_of_the_generator(monkeypatch, target, failing, k, handler):
    """X (or a function tried by the generator) raises MemoryError inside each of the generator's three broad
    handlers. The original discards the draw and returns as if nothing had happened; the copy stops."""
    before = signal.getsignal(signal.SIGVTALRM)
    with monkeypatch.context() as m:
        calls = patched_library(m, failing, k)
        swallowed = frozen_gen.gen_examples(target, n_total=P.N_GEN)                    # the control
        assert len(calls) > k and swallowed["status"] in ("ok", "excluded")
    with monkeypatch.context() as m:
        calls = patched_library(m, failing, k)
        with pytest.raises(G.ResourceStop):
            gen_bl.gen_examples(target, n_total=P.N_GEN)
        assert len(calls) == k
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and signal.getsignal(signal.SIGVTALRM) == before
    assert gen_bl.gen_examples(target, n_total=P.N_GEN)["draws"] == frozen_gen.gen_examples(target, n_total=P.N_GEN)["draws"]


def test_a_memory_failure_elsewhere_in_the_generator(monkeypatch):
    """Outside the three handlers (here: while an input is drawn). The original lets a raw MemoryError out; the
    copy translates it."""
    for module, error in ((frozen_gen, MemoryError), (gen_bl, G.ResourceStop)):
        with monkeypatch.context() as m:
            calls = patched_library(m, "asindices", 3)
            with pytest.raises(error):
                module.gen_examples("color", n_total=P.N_GEN)
            assert len(calls) == 3
    assert gen_bl.gen_examples("color", n_total=P.N_GEN)["status"] == "ok"


# ---------------------------------------------------------------- the budget counted in candidate combinations
INTEGER = dslx.ACC["Integer"]
UNREACHABLE = (-5, -5, -5)


def arithmetic(calls):
    """Two total operations on integers and one integer parameter on three examples. Every value differs from one
    example to the next and nothing raises, so the enumerator evaluates each combination once for every example:
    the number of calls of the two operations is three times the number of combinations evaluated."""
    def counted(f):
        def g(*a):
            calls.append(1)
            return f(*a)
        return g
    ops = [("inc", counted(lambda a: a + 1), (INTEGER,), False), ("add", counted(lambda a, b: a + b), (INTEGER, INTEGER), False)]
    return ops, [(("P", "x0"), (1, 2, 3))]


def budgeted(module, y, size, cpu=60.0, **kw):
    """(result, number of calls of the operations) of one search over the two arithmetic operations."""
    calls = []
    ops, leaves = arithmetic(calls)
    return module.search(ops, leaves, y, cpu, size, P.MAX_FN, P.MAX_BANK, **kw), len(calls)


def test_a_search_stopped_at_N_combinations_evaluated_exactly_N():
    full, calls = budgeted(search_bl, UNREACHABLE, 10)
    total = full["ticks"]
    assert full["stop"] == "size_exhausted" and full["found"] is None and total == 145 and calls == 3 * total
    for n in (1, 2, 7, total // 2, total - 1):
        r, calls = budgeted(search_bl, UNREACHABLE, 10, max_ticks=n)
        assert r["stop"] == "budget_ticks" and r["ticks"] == n and calls == 3 * n, n       # exactly n combinations, each on all three examples
        assert r["found"] is None and r["level"] < full["level"] and r["bank"] <= full["bank"]
    r, calls = budgeted(search_bl, UNREACHABLE, 10, max_ticks=0)
    assert r["stop"] == "budget_ticks" and r["ticks"] == 0 and calls == 0 and r["level"] == 0
    # a budget that is not exceeded changes nothing: the last combination of the whole enumeration is still evaluated
    for n in (total, total + 1, 10 * total):
        r, calls = budgeted(search_bl, UNREACHABLE, 10, max_ticks=n)
        assert (r["stop"], r["ticks"], r["level"], r["bank"], calls) == ("size_exhausted", total, full["level"], full["bank"], 3 * total)
    # one enumeration: a larger budget goes on from where a smaller one stopped
    banks = [budgeted(search_bl, UNREACHABLE, 10, max_ticks=n)[0]["bank"] for n in range(0, total + 1, 5)]
    assert banks == sorted(banks) and banks[0] == 1 and banks[-1] == full["bank"]


def test_a_fit_is_found_when_the_budget_reaches_its_combination_and_not_one_earlier():
    y = (3, 5, 7)                                                    # first met as inc(add(x0, x0)), the fifth combination of all
    full, calls = budgeted(search_bl, y, 6)
    k = full["ticks"]
    assert full["stop"] == "found" and full["found"][:2] == ("inc(add(x0, x0))", 4) and k == 5 and calls == 3 * k
    r, calls = budgeted(search_bl, y, 6, max_ticks=k)
    assert r["stop"] == "found" and r["found"] == full["found"] and r["ticks"] == k and calls == 3 * k
    r, calls = budgeted(search_bl, y, 6, max_ticks=k - 1)
    assert r["stop"] == "budget_ticks" and r["found"] is None and r["ticks"] == k - 1 and calls == 3 * (k - 1)


def test_without_a_budget_the_copy_gives_what_the_original_gives_and_the_count_besides():
    def same(r):
        return {k: v for k, v in r.items() if k not in ("cpu_s", "ticks")}
    for y, size in ((UNREACHABLE, 8), ((3, 5, 7), 6), ((2, 3, 4), 3)):
        mine, mine_calls = budgeted(search_bl, y, size)
        again, again_calls = budgeted(search_bl, y, size, max_ticks=None)
        theirs, their_calls = budgeted(frozen_search, y, size)
        assert same(mine) == same(again) == same(theirs) and mine_calls == again_calls == their_calls
        assert set(mine) == set(theirs) | {"ticks"} and mine["ticks"] == again["ticks"] and mine_calls == 3 * mine["ticks"]
    with pytest.raises(TypeError):
        budgeted(frozen_search, UNREACHABLE, 3, max_ticks=5)         # the control: the original has no such parameter


class SteppingClock:
    """Stands in for the time module inside the enumerator: every reading of the processor clock is one second later."""

    def __init__(self):
        self.now = 0.0

    def process_time(self):
        self.now += 1.0
        return self.now


def test_the_other_limits_stay_as_they_are_beside_the_budget(monkeypatch):
    """The original checks the processor-time budget every 128 combinations, after counting. With a clock that is
    past the allowance at the first check, the search ends there, whatever the budget in combinations, and the
    combination counted last was not evaluated; a budget in combinations below 128 ends the search first. (The
    clock is made up: the real one moves in steps of about a millisecond on this machine, too coarse for a search
    of 281 combinations.)"""
    assert budgeted(search_bl, UNREACHABLE, 12)[0]["ticks"] == 281
    for kw in (dict(max_ticks=10 ** 9), dict()):
        monkeypatch.setattr(search_bl, "time", SteppingClock())
        r, calls = budgeted(search_bl, UNREACHABLE, 12, cpu=0.5, **kw)
        assert r["stop"] == "budget_cpu" and r["ticks"] == 128 and calls == 3 * 127, kw
    monkeypatch.setattr(search_bl, "time", SteppingClock())
    r, calls = budgeted(search_bl, UNREACHABLE, 12, cpu=0.5, max_ticks=100)
    assert r["stop"] == "budget_ticks" and r["ticks"] == 100 and calls == 300
    monkeypatch.undo()
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and search_bl.time.process_time() >= 0.0


def test_the_blocks_and_guards_are_what_the_copies_import():
    assert search_bl.ResourceStop is G.ResourceStop is gen_bl.ResourceStop and search_bl.tag is dslx.tag
    assert B.ResourceStop is G.ResourceStop and BB.search_bl is search_bl
