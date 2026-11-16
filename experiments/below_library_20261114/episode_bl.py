"""One target of the below-library experiment (BL1): setup, six searches, two selections, the final panel, the
final checks and the check of a control's witness. Author: Chimdi Walter Ndubuisi

A development comparison on a known constructed benchmark (protocol section 0). CPU only, invented inputs, no
model. Bottom-up enumerative synthesis with observational equivalence and typed component-based synthesis are
standard; the library is arc-dsl by Michael Hodel (MIT). Nothing new is claimed about the method.

A target operation X is hidden with its whole family and is known only through examples of its inputs and
outputs. The true operation reaches no search; the evaluator alone holds it. The steps, each sealed (its sha256
journalled) before the next one may read its data (class Records enforces the order):

  setup            generator (66 examples), the rule on unsupported values, the pooled sequence, the usability
                   slice, eligibility, the hidden names and that none is reachable            -> seal setup_record
  nine examples    L4-9 and LC4-9, each built on generator examples 0 to 8 alone              -> seal first_fits_9
  36 examples      L4-36, L5-36, LC4-36 and C-36 on examples 0 to 35, all four always run     -> seal first_fits_36
  selection        each system's candidate, chosen on fit alone (first stage, else second)    -> seal selections
  final panel      generator examples 36 to 65 and the usable tuples of the final slice,
                   formed from X alone, opened last                                           -> seal final_set
  final checks     every sealed expression on the complete panel, one guard per batch
  witness          for a control: the evaluator's witness on the 36 fit examples and the panel (calibration)

Every search is its own call of the enumerator (search_bl, this experiment's copy of the frozen one) with its own
operations, leaves and namespaces built from its own examples (build_bl); nothing is shared between two searches.
A tree is evaluated later with build_bl.eval_tree_bl, through the same wrapped operations as inside the search.

A value that is, or holds, a function is never compared: canonical text is computed only after has_callable said
no. Identity keys of INPUT tuples (to keep pooled tuples apart from generator tuples) write a function argument by
its name, as the frozen generator's keys do; no output is ever keyed or compared that way.

A timeout of a guard, a memory failure and an address space near the ceiling are infrastructure stops
(guards_bl): the search or the target is recorded as incomplete, never as "none".
"""
import gc
import hashlib
import json
import os
import random
import time
import traceback

import bl_frozen  # noqa: F401  (hash check, sys.path)
import dslx
import blocks_c as B
import build_bl as BB
import gen_bl
import guards_bl as G
import presets_bl as P
import search_bl as S

LIB = dslx.load()
LABEL = P.LABEL
HERE = os.path.dirname(os.path.abspath(__file__))
# what opening a role needs: the seal that must exist first (None: nothing)
ROLE_RANGES = dict(P.ROLE_RANGES, pool_source=P.FIT36)
ROLE_NEEDS = {"pool_source": None, "fit9": "setup_record", "fit36": "first_fits_9", "final": "selections"}
INFRASTRUCTURE = ("hard_stop", "memory_failure", "address_space_near_ceiling", "infrastructure_failure", "time_safety_limit")
BOUNDED = ("size_limit_completed_function_cap", "allowance_used_up", "bank_cap_reached", "combination_budget_used_up")
STOP_CLASSES = ("found", "size_limit_completed") + BOUNDED + INFRASTRUCTURE
_POOLS = {}


class OrderError(RuntimeError):
    """A step or a role was asked for before the record it must follow was sealed."""


class Journal:
    """One line of JSON per event (the same form as stage A's journal)."""

    def __init__(self, path):
        self.path = path
        open(path, "w").close()

    def log(self, event, **kw):
        with open(self.path, "a") as f:
            f.write(json.dumps(dict(event=event, **kw), sort_keys=True, default=str) + "\n")


def sha256_json(obj):
    """sha256 of the compact JSON text of an object with sorted keys (the same form as stage A's seals)."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ---------------------------------------------------------------- values
def has_callable(v):
    """True when v is a function or holds one anywhere inside it."""
    if callable(v):
        return True
    if isinstance(v, (tuple, frozenset, list, set)):
        for e in v:
            if has_callable(e):
                return True
    return False


def holds_function(v):
    """True when a value that is not itself a function holds a function anywhere inside it."""
    return (not callable(v)) and has_callable(v)


def same(a, b):
    """Agreement of two values that hold no function: equal typed canonical text."""
    return dslx.canon(a) == dslx.canon(b)


def output_kind(y):
    """usable / unsupported / too_large for an output of the true operation (protocol section 4)."""
    if has_callable(y) or dslx.tag(y) == "U":
        return "unsupported"
    if dslx.vsize(y) > P.MAX_ELEMENTS:
        return "too_large"
    return "usable"


def input_key(v):
    """Identity key of an INPUT value: its canonical text; a function, as an argument or inside an input container,
    is written by its name (the form of the frozen generator's keys). Never used for an output."""
    if callable(v):
        return "f:" + getattr(v, "__name__", "?")
    t = type(v)
    if t is tuple:
        return "t(" + ",".join(input_key(x) for x in v) + ")"
    if t is frozenset:
        return "s{" + ",".join(sorted(input_key(x) for x in v)) + "}"
    return dslx.canon(v)


def short(v, n=300):
    """Canonical text of a value that holds no function, cut to n characters with a hash of the whole."""
    if has_callable(v):
        return "<a value that is or holds a function>"
    c = dslx.canon(v)
    return c if len(c) <= n else c[:n] + "...#" + hashlib.sha256(c.encode()).hexdigest()[:8]


def show_args(args, n=160):
    return [("function " + getattr(a, "__name__", "?")) if callable(a) else short(a, n) for a in args]


# ---------------------------------------------------------------- pooled inputs (as on 14 November, from this
# experiment's copy of the generator)
def pools():
    """(examples {operation: [(args, out)]}, pools {annotation: [values]}) over every operation the generator
    serves, values pooled by annotation and kept once (by input key), in the library's order."""
    if "p" not in _POOLS:
        examples, pl, seen = {}, {}, {}
        for op in LIB["lib_order"]:
            G.assert_inactive("the generator")
            g = G.call_checked(gen_bl.gen_examples, op)
            if g["status"] != "ok":
                continue
            examples[op] = g["examples"]
            for args, _ in g["examples"]:
                for (_, ann), v in zip(LIB["sigs"][op], args):
                    if ann == "Callable" or callable(v):
                        continue
                    key = input_key(v)
                    if key not in seen.setdefault(ann, set()):
                        seen[ann].add(key)
                        pl.setdefault(ann, []).append(v)
        _POOLS["p"] = (examples, pl)
    return _POOLS["p"]


def roster_all():
    """The operations the generator serves (the 145 of the earlier studies), in the library's order."""
    return list(pools()[0])


def pooled_args(X, own, pl, rng):
    args = []
    for j, (_, ann) in enumerate(LIB["sigs"][X]):
        if ann == "Callable" or callable(own[0][0][j]) or ann not in pl:
            args.append(rng.choice(own)[0][j])
        else:
            args.append(rng.choice(pl[ann]))
    return tuple(args)


def pooled_sequence(X, own, avoid_keys, total, tag, max_iter=60000):
    """Seeded sequence of UNIQUE pooled argument tuples, none equal to a generator tuple of the target
    (avoid_keys). X is not run here. `own`: the target's own examples from which a function-typed argument is taken
    (never a final one)."""
    pl = pools()[1]
    rng = random.Random("%d:%s:%s" % (P.SEED, X, tag))
    seen, out = set(avoid_keys), []
    for _ in range(max_iter):
        args = pooled_args(X, own, pl, rng)
        k = input_key(args)
        if k in seen:
            continue
        seen.add(k)
        out.append(args)
        if len(out) >= total:
            break
    return out


# ---------------------------------------------------------------- the records of a target, by role
class Records:
    """The 66 generator examples of one target, readable by role only after the role was opened; a role opens only
    when the seal it needs exists (fit9: the setup record; fit36: the first fits at nine examples; final: the
    selections). pool_source is the 36 fit examples as the setup step may read them: to take function-typed
    arguments for the pooled sequence and to check the hiding, and for nothing else."""

    def __init__(self, examples, sealed):
        self._ex = list(examples)
        self._sealed = sealed
        self.opened = []

    def open(self, role):
        if role not in ROLE_RANGES:
            raise KeyError(role)
        need = ROLE_NEEDS[role]
        if need is not None and need not in self._sealed:
            raise OrderError("the role '%s' cannot open before '%s' is sealed" % (role, need))
        if role not in self.opened:
            self.opened.append(role)

    def get(self, role):
        if role not in self.opened:
            raise OrderError("record role '%s' is not open" % role)
        a, b = ROLE_RANGES[role]
        return self._ex[a:b]

    def keys(self):
        """Input keys of the argument tuples of ALL records: used only to keep pooled tuples apart from them."""
        return {input_key(tuple(a)) for a, _ in self._ex}

    def unusable(self):
        """For eligibility: how many of the 66 examples are unusable, by reason. No value is handed out."""
        out = dict(container_argument_holds_a_function=0, output_is_or_holds_a_function=0)
        for args, y in self._ex:
            if any(holds_function(a) for a in args):
                out["container_argument_holds_a_function"] += 1
            elif has_callable(y):
                out["output_is_or_holds_a_function"] += 1
        return out


# ---------------------------------------------------------------- evaluation under a guard
def stream_usable(xfn, argsets, seconds):
    """([(args, output)], counts): the tuples on which the true operation runs and gives a usable output, in order,
    under ONE guard. A tuple on which it raises, or whose output is unsupported or too large, is discarded and
    counted; a timeout ends the pass and the tuples not evaluated are neither usable nor discarded. A memory
    failure anywhere in the pass leaves as ResourceStop."""
    try:
        return _stream_usable(xfn, argsets, seconds)
    except MemoryError:
        raise G.ResourceStop("memory failure in a pass of the true operation over pooled tuples") from None


def _stream_usable(xfn, argsets, seconds):
    out = []
    info = dict(draws=len(argsets), evaluated=0, usable=0, raised=0, unsupported=0, too_large=0, guard_timeout=False)
    try:
        with G.guard(seconds):
            for args in argsets:
                try:
                    y = G.call_checked(xfn, *args)
                    kind = G.call_checked(output_kind, y)
                except MemoryError:
                    raise G.ResourceStop("memory failure while the true operation ran on a pooled tuple") from None
                except Exception:                                # noqa: BLE001  (the operation raises on this input)
                    y, kind = None, "raised"
                info["evaluated"] += 1
                info[kind] += 1
                if kind == "usable":
                    out.append((args, y))
    except G.GuardTimeout:
        info["guard_timeout"] = True
    return out, info


def check_batch(fn, argsets, xouts, seconds):
    """One batch of evaluations of a candidate against the true operation's outputs, under ONE guard.

    A candidate that raises on an input is wrong there; a value that is or holds a function is unsupported and
    wrong there, and no canonical text is computed for it. A timeout ends the batch: with no counterexample before
    it the counterexample is dict(index=-1, note="guard timeout") (wrong by convention, listed by the summary); a
    counterexample found before it stays and is marked guard_timeout_after_this. An input that was not evaluated
    is never a counterexample. A memory failure is not an error of the candidate: it leaves as ResourceStop."""
    try:
        return _check_batch(fn, argsets, xouts, seconds)
    except MemoryError:
        raise G.ResourceStop("memory failure in a batch of checks") from None


def _check_batch(fn, argsets, xouts, seconds):
    oks, first, errors, unsupported, timed_out = [], None, 0, 0, False
    order_same = order_of = 0
    try:
        with G.guard(seconds):
            for i, (a, xo) in enumerate(zip(argsets, xouts)):
                note, v = "different value", None
                try:
                    v = G.call_checked(fn, *a)
                    if G.call_checked(has_callable, v):
                        ok, note = False, "unsupported value: it is or holds a function"
                        unsupported += 1
                    else:
                        ok = G.call_checked(same, v, xo)
                        if ok and type(xo) is frozenset and len(xo) >= 2:
                            order_of += 1
                            order_same += [dslx.canon(e) for e in v] == [dslx.canon(e) for e in xo]
                except MemoryError:
                    raise G.ResourceStop("memory failure in a check on the final panel") from None
                except Exception as e:                           # noqa: BLE001  (the candidate raises on this input)
                    ok, note = False, "error: " + type(e).__name__
                    errors += 1
                describe = not ok and first is None
                if describe:
                    first = dict(index=i, note=note)             # the counterexample exists from here on, whatever comes next
                oks.append(ok)
                if describe:
                    first.update(args=show_args(a), want=short(xo, 160), got=short(v, 160) if note == "different value" else None)
    except G.GuardTimeout:
        timed_out = True
        if first is None:
            first = dict(index=-1, note="guard timeout")
        else:
            first["guard_timeout_after_this"] = True
            if first["index"] == len(oks):                       # the timeout came before this input was counted: it was evaluated
                oks.append(False)
    n = len(argsets)
    return dict(n=n, evaluated=len(oks), agree=sum(oks), errors=errors, unsupported=unsupported, guard_timeout=timed_out,
                right=bool(len(oks) == n and all(oks) and not timed_out), counterexample=first,
                order_of_sets=dict(same_order=order_same, of=order_of), oks=oks)


def stop_class(stop, found, function_cap_reached=False, combination_mode=False):
    """How a search ended, kept apart: found / size_limit_completed (the only exhaustive ending) /
    size_limit_completed_function_cap / allowance_used_up / bank_cap_reached / combination_budget_used_up (the
    budget counted in candidate combinations, when presets MAX_COMBINATIONS is on) / an infrastructure class.
    The enumerator's processor-time stop means two different things: with the combination budget OFF
    (combination_mode False) it is the binding allowance, a bounded ending; with it ON it is the safety limit, an
    infrastructure stop ("time_safety_limit"): the record is incomplete and never reads as "none"."""
    if stop in INFRASTRUCTURE:
        return stop
    if found:
        return "found"
    if stop == "size_exhausted" and not function_cap_reached:
        return "size_limit_completed"
    if stop in ("size_exhausted", "size_exhausted_function_cap"):
        return "size_limit_completed_function_cap"
    if stop == "budget_cpu":
        return "time_safety_limit" if combination_mode else "allowance_used_up"
    if stop == "budget_bank":
        return "bank_cap_reached"
    if stop == "budget_ticks":
        return "combination_budget_used_up"
    if stop == "hard_timeout":
        return "hard_stop"
    return "infrastructure_failure"


def coverage(cls):
    """exhaustive / bounded for a fruitless search that ended on its own; None for a fit or an infrastructure stop."""
    return "exhaustive" if cls == "size_limit_completed" else ("bounded" if cls in BOUNDED else None)


def address_space_ceiling():
    """The ceiling the address-space check compares with: the limit in force when one is set, else the preset."""
    import resource
    soft = resource.getrlimit(resource.RLIMIT_AS)[0]
    return P.MEMORY_CEILING_BYTES if soft == resource.RLIM_INFINITY else soft


def load_witness_manifest():
    """The evaluator's manifest of witnesses ({target: {"tree": [...], "nodes": int, "note": str}}) or None when
    the file does not exist. Opened only by the witness step of an episode (after the selections are sealed) and
    by the summary; no search path reads it."""
    path = os.path.join(HERE, P.WITNESS_MANIFEST)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------- one target
class Episode:
    def __init__(self, X, outdir=None, journal=None):
        self.X, self.outdir, self.j = X, outdir, journal
        self.hidden = sorted(LIB["fam_of"][X])
        self.n_params = len(LIB["sigs"][X])
        self.sealed, self.done, self.fit = {}, set(), {}
        self.incomplete = []                                     # reasons why the record is not complete
        self.F = None
        self.res = dict(target=X, label=LABEL, dev=X in P.DEV_ROSTER, development_only=X in P.DEV_ROSTER, stratum=P.stratum_of(X),
                        half=P.half_of(X), control=X in P.CONTROL_NAMES, development_control=X == P.DEV_CONTROL,
                        family=LIB["fam_label"][X], hidden=list(self.hidden), memory=[],
                        presets=dict(allowance=P.ALLOWANCE, time_safety_limit_s=P.TIME_SAFETY_LIMIT_S, cpu_budget_s=P.cpu_budget(), max_bank=P.MAX_BANK, max_fn=P.MAX_FN, arity_rule=P.ARITY_RULE, size_c=P.SIZE_C,
                                     max_combinations=P.MAX_COMBINATIONS))

    # ------------------------------------------------------------------ bookkeeping
    def log(self, event, **kw):
        if self.j:
            self.j.log(event, target=self.X, **kw)

    def seal(self, name, obj):
        if name in self.sealed:
            raise OrderError("'%s' is sealed already" % name)
        sha = sha256_json(obj)
        self.sealed[name] = sha
        self.log("seal", name=name, sha256=sha)
        return sha

    def need(self, step, *sealed, done=()):
        missing = [s for s in sealed if s not in self.sealed] + [d for d in done if d not in self.done]
        if missing:
            raise OrderError("%s cannot start before %s" % (step, missing))

    def memory_check(self, unit):
        """Read the largest address space this process ever had, store it, and stop when it is within the margin of
        the ceiling or cannot be read (guards_bl.NearCeiling: an infrastructure stop that ends the process)."""
        peak = G.address_space_peak_kb()
        self.res["memory"].append(dict(after=unit, address_space_peak_kb=peak, resident_peak_kb=G.resident_peak_kb()))
        if G.near_ceiling(peak, address_space_ceiling(), P.ADDRESS_SPACE_MARGIN_BYTES):
            raise G.NearCeiling(unit, peak)
        return peak

    def exclude(self, reason, kind):
        self.res.update(status="excluded", reason=reason, reason_kind=kind)
        self.log("excluded", reason=reason)
        return self.res

    # ------------------------------------------------------------------ setup (no search; the final role is not read)
    def setup(self):
        """Generator, unsupported values, pooled sequence, usability slice, eligibility, hiding. Returns the record
        when the target is excluded, None when it is eligible."""
        X = self.X
        S_ = self.res["setup"] = dict(retained_present=BB.retained_present(self.hidden))
        G.assert_inactive("the generator")
        g = G.call_checked(gen_bl.gen_examples, X, n_total=P.N_GEN)
        S_["generator"] = dict(status=g["status"], draws=g["draws"], examples=len(g["examples"]), rejected=g.get("rejected"))
        self.memory_check("setup: generator")
        if g["status"] != "ok":
            return self.exclude("generator: " + str(g["reason"]), "generator")
        if len(g["examples"]) != P.N_GEN:
            return self.exclude("generator gave %d examples" % len(g["examples"]), "generator")
        self.rec = Records(g["examples"], self.sealed)
        S_["opened_roles"] = self.rec.opened
        bad = G.call_checked(self.rec.unusable)
        S_["unusable_generator_examples"] = bad
        self.memory_check("setup: generator examples")
        if sum(bad.values()):
            return self.exclude("%d of %d generator examples are unusable (a container argument holds a function: %d; the output is or "
                                "holds a function: %d)" % (sum(bad.values()), P.N_GEN, bad["container_argument_holds_a_function"],
                                                           bad["output_is_or_holds_a_function"]), "unsupported_values")
        # ---- pooled sequence: unique, apart from every generator tuple of X (keys only); function-typed arguments
        # come from the 36 fit examples; a pooled tuple in which a container argument holds a function is dropped
        self.rec.open("pool_source")
        own = self.rec.get("pool_source")
        seq = G.call_checked(pooled_sequence, X, own, self.rec.keys(), P.SEQ_TOTAL, P.SEQ_TAG)
        kept = [t for t in seq if not any(holds_function(v) for v in t)]
        n = len(kept)
        nr, na, nb = int(n * P.SEQ_FRAC_R), int(n * P.SEQ_FRAC_A), int(n * P.SEQ_FRAC_B)
        cuts = [0, nr, nr + na, nr + 2 * na, nr + 2 * na + nb, nr + 2 * na + 2 * nb]       # R, A, UA, B, UB as on 14 November
        self.slice_final, self.slice_usability = kept[cuts[3]:cuts[4]], kept[cuts[4]:cuts[5]]
        S_["pooled_sequence"] = dict(tag=P.SEQ_TAG, drawn=len(seq), dropped_a_container_argument_holds_a_function=len(seq) - n,
                                     unique_tuples=n, final_slice=len(self.slice_final), usability_slice=len(self.slice_usability))
        self.memory_check("setup: pooled sequence")
        # ---- usability slice (eligibility only; apart from the final slice)
        self.x_true = dslx.full_ns()[X]
        usable, u = stream_usable(self.x_true, self.slice_usability, P.STREAM_GUARD_S)
        S_["usability"] = u
        self.log("setup_usability", **u)
        self.memory_check("setup: usability slice")
        if len(usable) < P.MIN_FINAL_POOL:
            return self.exclude("too few usable pooled inputs (usability slice: %d of %d draws usable, need %d%s)" % (
                len(usable), len(self.slice_usability), P.MIN_FINAL_POOL, "; the guard ran out" if u["guard_timeout"] else ""),
                "too_few_usable_pooled_inputs")
        # ---- hiding: no hidden name is reachable from any operation, leaf or function-valued argument of any block set
        S_["hidden_unreachable"] = {}
        for block_set in BB.BLOCK_SETS:
            ops, leaves, _, op_ns, leaf_ns, _ = G.call_checked(BB.build, block_set, self.hidden, own)
            S_["hidden_unreachable"][block_set] = BB.assert_hidden_unreachable(self.hidden, ops, leaves, (op_ns, leaf_ns)) > 0
        self.memory_check("setup: hiding")
        self.seal("setup_record", self.setup_view())
        self.done.add("setup")
        return None

    def setup_view(self):
        """What a setup-only pass commits: the decisions, and (apart) the counts."""
        s = self.res.get("setup", {})
        excluded = self.res.get("status") == "excluded"
        u = s.get("usability") or {}
        decision = dict(status="excluded" if excluded else "eligible", reason_kind=self.res.get("reason_kind"), dev=self.res["dev"],
                        stratum=self.res["stratum"], half=self.res["half"], control=self.res["control"],
                        development_control=self.res["development_control"], hidden=self.res["hidden"],
                        retained_present=s.get("retained_present"), hidden_unreachable=s.get("hidden_unreachable"),
                        usability_guard_timeout=u.get("guard_timeout"))
        counts = dict(generator=s.get("generator"), unusable_generator_examples=s.get("unusable_generator_examples"),
                      pooled_sequence=s.get("pooled_sequence"), usability=u or None, reason=self.res.get("reason"))
        return dict(decision=decision, counts=counts)

    # ------------------------------------------------------------------ one search
    def run_search(self, name, block_set, role, size_limit):
        """One search: its own build from its own examples (read through its role), its own call of the enumerator.
        Returns the record; the tree and the namespaces of a fit are kept apart for the later checks."""
        examples = self.rec.get(role)
        counts, eval_counts, book = BB.new_counts(), BB.new_counts(), BB.new_function_book(len(examples))
        budget = P.combination_budget()                          # None (off) or a number of candidate combinations
        a = dict(block_set=block_set, role=role, examples=len(examples), size_limit=size_limit, allowance=P.ALLOWANCE,
                 cpu_budget_s=P.cpu_budget(), cpu_budget_is="a safety limit" if budget is not None else "the binding allowance",
                 max_fn=P.MAX_FN, max_bank=P.MAX_BANK, arity_rule=P.ARITY_RULE, max_combinations=budget)
        t0 = time.process_time()
        found = built = None
        error = None
        try:
            G.assert_inactive("the enumerator")
            built = G.call_checked(BB.build, block_set, self.hidden, examples, counts=counts, eval_counts=eval_counts, book=book)
            ops, leaves, Y, op_ns, leaf_ns, consts = built
            BB.assert_hidden_unreachable(self.hidden, ops, leaves, (op_ns, leaf_ns))
            a["function_valued_leaves"] = sum(1 for _, v in leaves if dslx.tagset(v) == frozenset("F"))
            a["operations"], a["leaves"] = len(ops), len(leaves)
            more = {} if budget is None else dict(max_ticks=budget)       # passed only when the budget is on
            r = G.call_checked(S.search, ops, leaves, Y, P.cpu_budget(), size_limit, P.MAX_FN, P.MAX_BANK, **more)
            found = r["found"]
        except G.ResourceStop as e:
            r, error = dict(stop="memory_failure"), str(e)
        except MemoryError:
            r, error = dict(stop="memory_failure"), "MemoryError"
        except Exception as e:                                   # noqa: BLE001  (infrastructure: incomplete, never "none")
            r, error = dict(stop="infrastructure_failure"), "%s: %s" % (type(e).__name__, str(e)[:300])
        if error is not None:
            built = None
            gc.collect()                                         # give back what the stopped search held before anything else is built
        a["cpu_s"] = round(time.process_time() - t0, 3)
        a.update(stop=r["stop"], level_completed=r.get("level"), bank=r.get("bank"), function_cap_reached=r.get("function_cap_reached"),
                 ticks=r.get("ticks"), enumerator_cpu_s=round(r["cpu_s"], 3) if "cpu_s" in r else None, error=error,
                 expr=found[0] if found else None, size=found[1] if found else None)
        a["refused_by_the_wrappers"] = dict(counts)
        a["function_making"] = dict(
            by_operation={op: {str(sz): row for sz, row in sorted(rows.items())} for op, rows in book["by_operation"].items()},
            admitted=book["admitted"], cap_reached_at=book["cap_reached_at"], first_refused_by_cap=book["first_refused_by_cap"],
            calls_outside_the_enumerator=book["calls_outside_the_enumerator"])
        if "function_valued_leaves" in a:
            a["function_valued_entries"] = a["function_valued_leaves"] + book["admitted"]
        # ---- the later evaluation must give the search's own target again on the search's own examples
        if found and built is not None:
            ops, leaves, Y, op_ns, leaf_ns, consts = built
            fn = self.candidate(found[2], op_ns, leaf_ns, consts)
            try:
                chk = check_batch(fn, [e[0] for e in examples], list(Y), P.FINAL_GUARD_S)
                a["fit_recheck"] = dict(agree=chk["agree"], of=chk["n"], guard_timeout=chk["guard_timeout"])
                if chk["guard_timeout"]:
                    a["stop"], a["error"] = "infrastructure_failure", "the later evaluation of the search's own fit ran out of its guard"
                elif not chk["right"]:
                    a["stop"], a["error"] = "infrastructure_failure", "the later evaluation does not give the search's own fit again"
            except G.ResourceStop as e:
                a["stop"], a["error"] = "memory_failure", str(e)
            self.fit[name] = dict(tree=found[2], op_ns=op_ns, leaf_ns=leaf_ns, consts=consts, eval_counts=eval_counts)
        del built
        gc.collect()
        # ---- the address space, read after the search; near the ceiling the search is an infrastructure stop
        peak = G.address_space_peak_kb()
        a["address_space_peak_kb"], a["resident_peak_kb"] = peak, G.resident_peak_kb()
        near = G.near_ceiling(peak, address_space_ceiling(), P.ADDRESS_SPACE_MARGIN_BYTES)
        if near:
            a["stop_before_the_address_space_check"] = a["stop"]
            a["error"] = ("%s; " % a["error"] if a["error"] else "") + "address space peak %s kB" % peak
            a["stop"] = "address_space_near_ceiling"
        a["stop_class"] = stop_class(a["stop"], bool(found), bool(a.get("function_cap_reached")), combination_mode=budget is not None)
        a["incomplete"] = a["stop_class"] in INFRASTRUCTURE
        a["coverage"] = coverage(a["stop_class"])
        a["fit"] = a["stop_class"] == "found"
        if a["incomplete"]:
            self.fit.pop(name, None)
            self.incomplete.append("search %s: %s (%s)" % (name, a["stop_class"], a["error"]))
        self.log("search", search=name, **{k: v for k, v in a.items() if k != "function_making"})
        if near:
            self.res.setdefault("searches", {})[name] = a
            raise G.NearCeiling("search " + name, peak)
        return a

    def candidate(self, tree, op_ns, leaf_ns, consts):
        names = ["x%d" % i for i in range(self.n_params)]

        def f(*args):
            return BB.eval_tree_bl(tree, op_ns, leaf_ns, consts, dict(zip(names, args)))
        return f

    def step_searches(self, names, role, needs, seal_name):
        self.need("the searches %s" % (names,), *needs, done=("setup",))
        self.rec.open(role)
        searches = self.res.setdefault("searches", {})
        for name in names:
            spec = [s for s in P.SEARCHES if s[0] == name][0]
            assert spec[2] == role
            searches[name] = self.run_search(name, spec[1], role, P.size_limit(name))
        self.seal(seal_name, {n: dict(expr=searches[n]["expr"], stop=searches[n]["stop"], stop_class=searches[n]["stop_class"])
                              for n in names})
        self.done.add(seal_name)

    def step_nine(self):
        self.step_searches(P.NINE, "fit9", ("setup_record",), "first_fits_9")

    def step_thirty_six(self):
        self.step_searches(P.THIRTY_SIX, "fit36", ("first_fits_9",), "first_fits_36")

    # ------------------------------------------------------------------ selection, on fit alone
    def step_select(self):
        """Each system's candidate: the first stage's fit if it found one, else the second stage's, else nothing.
        Nothing of the final panel exists yet; the final panel never changes a selection. A stage that ended by an
        infrastructure stop leaves the selection undetermined (the record is incomplete)."""
        self.need("the selection", "first_fits_36")
        searches = self.res["searches"]
        sel = self.res["selection"] = {}
        for system in P.SYSTEM_NAMES:
            first, second = P.SYSTEMS[system]
            a, b = searches[first], searches[second]
            if a["incomplete"]:
                s = dict(determined=False, expr=None, stage=None, search=None, reason="the first stage (%s) ended by an infrastructure stop" % first)
            elif a["fit"]:
                s = dict(determined=True, expr=a["expr"], size=a["size"], stage=1, search=first, reason="the first stage (%s) found a fit" % first)
            elif b["incomplete"]:
                s = dict(determined=False, expr=None, stage=None, search=None,
                         reason="the first stage (%s) found no fit and the second (%s) ended by an infrastructure stop" % (first, second))
            elif b["fit"]:
                s = dict(determined=True, expr=b["expr"], size=b["size"], stage=2, search=second,
                         reason="the first stage (%s) found no fit; the second (%s) found one" % (first, second))
            else:
                s = dict(determined=True, expr=None, stage=None, search=None, reason="neither stage (%s, %s) found a fit" % (first, second))
            sel[system] = s
        self.seal("selections", {k: dict(expr=v["expr"], stage=v["stage"], search=v["search"], reason=v["reason"]) for k, v in sel.items()})
        self.done.add("selections")

    # ------------------------------------------------------------------ the final panel, opened last
    def fin(self):
        if self.F is None:
            raise OrderError("the final panel is opened only after the selections are sealed")
        return self.F

    def open_final(self):
        self.need("the final panel", "selections")
        self.rec.open("final")
        gfin = self.rec.get("final")
        pooled, info = stream_usable(self.x_true, self.slice_final, P.STREAM_GUARD_S)
        F = dict(gen_args=[a for a, _ in gfin], gen_x=[y for _, y in gfin], pool_args=[a for a, _ in pooled], pool_x=[y for _, y in pooled])
        F["args"], F["x"] = F["gen_args"] + F["pool_args"], F["gen_x"] + F["pool_x"]
        reasons = BB.reachable_hidden(self.hidden, [v for a in F["args"] for v in a if callable(v)])
        if reasons:
            raise RuntimeError("a hidden name is reachable from an argument of the final panel: " + "; ".join(reasons[:4]))
        self.res["final_panel"] = dict(generator=len(gfin), pooled=len(pooled), inputs=len(F["args"]), pooled_slice=info,
                                       pooled_discarded=info["raised"] + info["unsupported"] + info["too_large"],
                                       pooled_not_evaluated=info["draws"] - info["evaluated"], pooled_short=len(pooled) < P.MIN_FINAL_POOL,
                                       formed=not info["guard_timeout"])
        self.memory_check("the final panel")
        if info["guard_timeout"]:
            # where the pass was cut depends on timing: such a panel is not THE panel of this target
            self.incomplete.append("the final panel could not be formed: the guard of the pass over the final slice ran out")
            self.log("final_panel_not_formed", **self.res["final_panel"])
            return False
        self.F = F
        self.seal("final_set", [input_key(tuple(a)) for a in F["args"]])
        self.log("final_opened", **self.res["final_panel"])
        return True

    def final_check(self, what, fn):
        """One batch on the complete final panel; a memory failure makes the check, and the record, incomplete."""
        F = self.fin()
        t0 = time.process_time()
        try:
            c = check_batch(fn, F["args"], F["x"], P.FINAL_GUARD_S)
        except G.ResourceStop as e:
            self.incomplete.append("final check of %s: memory failure (%s)" % (what, e))
            self.memory_check("final check of " + what)
            return dict(incomplete=True, error=str(e), right=None, cpu_s=round(time.process_time() - t0, 4))
        n_gen = len(F["gen_args"])
        oks = c.pop("oks")
        c.update(generator=[sum(oks[:n_gen]), min(n_gen, len(oks))], pooled=[sum(oks[n_gen:]), max(0, len(oks) - n_gen)],
                 incomplete=False, cpu_s=round(time.process_time() - t0, 4))
        self.memory_check("final check of " + what)
        return c

    def step_final(self):
        self.need("the final checks", "selections")
        searches, sel = self.res["searches"], self.res["selection"]
        if not self.open_final():
            # no final panel: no final check is made; what was found and selected stays in the record, unchecked
            for a in searches.values():
                a.update(final=None, first_fit=None if (a["incomplete"] or a["fit"]) else "none")
            for s in sel.values():
                s.update(rebuilt=None if (not s["determined"] or s["search"] is not None) else False, oracle_union=None)
            self.done.add("final")
            return
        for name in P.SEARCH_NAMES:
            a = searches[name]
            fit = self.fit.get(name)
            if a["incomplete"]:
                a.update(final=None, first_fit=None)
            elif fit is None:
                a.update(final=None, first_fit="none")
            else:
                c = self.final_check("the first fit of " + name, self.candidate(fit["tree"], fit["op_ns"], fit["leaf_ns"], fit["consts"]))
                a["final"] = c
                a["first_fit"] = None if c["incomplete"] else ("right" if c["right"] else "wrong")
                a["refused_by_the_wrappers_in_later_evaluations"] = dict(fit["eval_counts"])
        for system in P.SYSTEM_NAMES:
            s = sel[system]
            first, second = P.SYSTEMS[system]
            if not s["determined"]:
                s["rebuilt"] = None
            elif s["search"] is None:
                s["rebuilt"] = False
            else:
                ff = searches[s["search"]]["first_fit"]
                s["rebuilt"] = None if ff is None else ff == "right"
                fc = searches[s["search"]]["final"] or {}
                s["wrong_only_by_guard_timeout"] = (fc.get("counterexample") or {}).get("note") == "guard timeout"
                s["order_of_sets"] = fc.get("order_of_sets") if s["rebuilt"] else None
            # candidate-set coverage (secondary, never the system's result): either of its two found expressions right
            states = [searches[n]["first_fit"] for n in (first, second)]
            s["oracle_union"] = None if None in states else any(x == "right" for x in states)
        self.done.add("final")

    # ------------------------------------------------------------------ the witness of a control (calibration)
    def step_witness(self):
        """For a control: the evaluator's witness, evaluated over C and the retained operations present for this
        target, on the 36 fit examples and on the complete final panel, each batch under the guard of a final check.
        The manifest is read here, after the selections are sealed and the final panel is open, and nowhere before."""
        self.need("the witness", "selections", done=("final",))
        if not (self.res["control"] or self.res["development_control"]):
            self.res["witness"] = dict(state="not a control")
            return
        if self.incomplete or self.F is None:
            self.res["witness"] = dict(state="not evaluated", valid=False,
                                       reason="the record is incomplete: " + (self.incomplete[0] if self.incomplete else "no final panel"))
            return
        manifest = load_witness_manifest()
        entry = None if manifest is None else manifest.get(self.X)
        if manifest is None or entry is None or not entry.get("tree"):
            self.res["witness"] = dict(state="no manifest entry" if manifest is not None else "no manifest",
                                       note=(entry or {}).get("note") if entry else None)
            return
        w = self.res["witness"] = dict(state="evaluated", declared_nodes=entry.get("nodes"), note=entry.get("note"))
        try:
            tree = B.as_tree(entry["tree"])
            w["expr"] = B.render(tree)
            w["nodes"] = B.check_tree(tree, [a for _, a in LIB["sigs"][self.X]])
        except ValueError as e:
            w.update(state="static check failed", error=str(e)[:300], valid=False)
            return
        if w["nodes"] != entry.get("nodes"):
            w.update(state="static check failed", error="the manifest declares %s nodes, the tree has %d" % (entry.get("nodes"), w["nodes"]), valid=False)
            return
        fit36 = self.rec.get("fit36")
        eval_counts = BB.new_counts()
        _, _, _, op_ns, leaf_ns, consts = G.call_checked(BB.build, "C", self.hidden, fit36, eval_counts=eval_counts)
        fn = self.candidate(tree, op_ns, leaf_ns, consts)
        F = self.fin()
        try:
            cf = check_batch(fn, [a for a, _ in fit36], [y for _, y in fit36], P.FINAL_GUARD_S)
            self.memory_check("witness on the fit examples")
            cp = check_batch(fn, F["args"], F["x"], P.FINAL_GUARD_S)
            self.memory_check("witness on the final panel")
        except G.ResourceStop as e:
            w.update(state="memory failure", error=str(e), valid=False)
            self.incomplete.append("witness: memory failure (%s)" % e)
            self.memory_check("witness")
            return
        for c in (cf, cp):
            c.pop("oks")
        w.update(fit36=cf, final=cp, agrees_on_all_36=cf["right"], agrees_on_the_final_panel=cp["right"],
                 unsupported_results=cf["unsupported"] + cp["unsupported"], guard_timeout=cf["guard_timeout"] or cp["guard_timeout"],
                 first_mismatch=cf["counterexample"] or cp["counterexample"], refused_by_the_wrappers=dict(eval_counts))
        w["valid"] = bool(cf["right"] and cp["right"])

    # ------------------------------------------------------------------ the episode
    def run(self):
        t_all = time.process_time()
        if self.setup() is not None:
            self.res["setup_view"] = self.setup_view()
            self.res["cpu_s_total"] = round(time.process_time() - t_all, 2)
            return self.res
        self.res["setup_view"] = self.setup_view()
        self.step_nine()
        self.step_thirty_six()
        self.step_select()
        self.step_final()
        self.step_witness()
        self.res["seals"] = dict(self.sealed)
        self.res["opened_roles"] = list(self.rec.opened)
        searches = self.res["searches"]
        self.res["cpu"] = dict(
            searches_s=round(sum(a["cpu_s"] for a in searches.values()), 2),
            by_system_s={s: round(sum(searches[n]["cpu_s"] for n in P.SYSTEMS[s]), 2) for s in P.SYSTEM_NAMES},
            final_checks_s=round(sum((a.get("final") or {}).get("cpu_s", 0.0) for a in searches.values()), 3))
        self.res["cpu_s_total"] = round(time.process_time() - t_all, 2)
        self.res["cpu"]["other_s"] = round(self.res["cpu_s_total"] - self.res["cpu"]["searches_s"] - self.res["cpu"]["final_checks_s"], 2)
        if self.incomplete:
            self.res.update(status="incomplete", reason="; ".join(self.incomplete)[:600], incomplete_because=list(self.incomplete))
        else:
            self.res["status"] = "done"
        self.log(self.res["status"], cpu_s_total=self.res["cpu_s_total"])
        return self.res


def write_record(path, res):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True, default=str)
    os.replace(tmp, path)


def run_target(X, outdir):
    """Run one target to completion and write targets/<X>.json (atomically) and journal/<X>.jsonl. A target whose
    record exists is not run again (a development run can be started again; the all-roster run starts in a new
    folder). An infrastructure stop anywhere gives status "incomplete" with the reason, never "none". When the
    address space is near the ceiling the record is written and guards_bl.NearCeiling is raised again: the caller
    must end the process."""
    os.makedirs(os.path.join(outdir, "targets"), exist_ok=True)
    os.makedirs(os.path.join(outdir, "journal"), exist_ok=True)
    final = os.path.join(outdir, "targets", X + ".json")
    if os.path.exists(final):
        with open(final) as f:
            return json.load(f)
    j = Journal(os.path.join(outdir, "journal", X + ".jsonl"))
    ep = Episode(X, outdir, j)
    j.log("start", target=X, dev=ep.res["dev"], label=LABEL)
    stop = None
    try:
        res = ep.run()
    except G.NearCeiling as e:
        stop = e
        res = dict(ep.res, status="incomplete", stop_class="address_space_near_ceiling", reason=str(e))
    except G.ResourceStop as e:
        res = dict(ep.res, status="incomplete", stop_class="memory_failure", reason="memory failure: %s" % e)
    except G.GuardTimeout:
        res = dict(ep.res, status="incomplete", stop_class="infrastructure_failure", reason="a guard timeout outside a guarded batch")
    except S.Hard:
        res = dict(ep.res, status="incomplete", stop_class="hard_stop", reason="the enumerator's hard stop outside a search")
    except MemoryError:
        res = dict(ep.res, status="incomplete", stop_class="memory_failure", reason="memory failure (MemoryError)")
    except Exception as e:                                       # noqa: BLE001  (infrastructure: incomplete, never "none")
        res = dict(ep.res, status="incomplete", stop_class="infrastructure_failure", reason="%s: %s" % (type(e).__name__, str(e)[:300]),
                   trace=traceback.format_exc()[-1500:])
    if res.get("status") == "incomplete":
        res.setdefault("setup_view", ep.setup_view() if "setup" in ep.done else None)
        res["seals"] = dict(ep.sealed)
        j.log("incomplete", reason=res.get("reason"))
    write_record(final, res)
    if stop is not None:
        raise stop
    return res


def setup_only(X):
    """The setup step alone (no search; no fit role and no final role is opened): the committed view of the target."""
    ep = Episode(X)
    t = time.process_time()
    ep.setup()
    view = ep.setup_view()
    view.update(target=X, cpu_s=round(time.process_time() - t, 2), opened_roles=list(getattr(getattr(ep, "rec", None), "opened", [])),
                memory=ep.res["memory"])
    return view
