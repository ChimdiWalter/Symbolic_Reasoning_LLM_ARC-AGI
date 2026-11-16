"""One target of the evidence-across-failures experiment (EAF1): setup, acquisition, five arm searches, admission,
libraries, reuse, final reading. Author: Chimdi Walter Ndubuisi

A development comparison on a known benchmark (stage A and the operations study ran on these same operations and their
outcomes are known). CPU only, invented inputs, no model. Bottom-up enumerative synthesis with observational
equivalence is standard (TRANSIT, 2013; Escher, 2013); completing a program with a hole is program sketching;
constraining a component by several specifications is standard; the library is arc-dsl by Michael Hodel (MIT).
Nothing new is claimed about the method.

A target operation X is removed with its whole family. A "wrapper" is the one-argument library operation `post` around
the missing call in a consumer `post(X(arguments))`. Five arms see different demonstrated outputs over the SAME nine
argument tuples (generator inputs 0 to 8); a candidate for the missing call is accepted in an arm when every
demonstrated output of that arm is reproduced, each position through its own wrapper.

Record roles over the 66 generator examples are opened one step at a time (class Records), in this order, each step's
record sealed (sha256 journalled) before the next one opens:
  setup (24-35; pooled setup slices) -> acquisition (0-8; the nine tuples and demonstrated outputs) ->
  five arm searches -> ALL five first-fit-or-none records sealed -> admission (9-20 and pooled slice A) ->
  libraries written read-only and ALL sealed -> reuse support (21-23) and the two reuse controls ->
  final (36-65 and pooled slice B), opened last; the loader raises if called earlier.
The true operation X reaches no search; the evaluator alone holds it. Every arm is its own search (its own search
state, same order, size limit, caps and allowance B); nothing built for one arm or target is used by another.
The order of a target's wrappers and its pooled inputs are drawn under this experiment's own seed tags (presets_eaf),
not stage A's; the 66 generator examples of a target are the same as in stage A (one generator). Pooled tuples in
which a container argument holds a function are dropped (a set of functions iterates in memory-address order).
"""
import hashlib
import json
import os
import random
import time

import eaf_frozen  # noqa: F401
import core
import dslx
import gen
import search as S
import vsearch as VS
import consumers as C
import gate as G
import library as LIB
import episode as SA          # stage A's episode module, read-only: stop_class, Journal, short, helpers
import presets_eaf as P

L = dslx.load()
LABEL = P.LABEL
ROLE_RANGES = dict(acquisition=P.ACQ, admission=P.ADM, reuse_support=P.SUPPORT, setup=P.SETUP, final=P.FINAL)
Journal = SA.Journal
stop_class = SA.stop_class
short = SA.short


class OrderError(RuntimeError):
    """A step was asked for before the steps it must follow were sealed."""


class Records:
    """The 66 generator examples of one target, readable by role only after the role was opened."""

    def __init__(self, examples):
        self._ex = list(examples)
        self.opened = []

    def open(self, role):
        if role not in ROLE_RANGES:
            raise KeyError(role)
        if role not in self.opened:
            self.opened.append(role)

    def get(self, role):
        if role not in self.opened:
            raise OrderError("record role '%s' is not open" % role)
        a, b = ROLE_RANGES[role]
        return self._ex[a:b]

    def keys(self):
        """Canonical argument keys of ALL records: used only to keep pooled tuples disjoint from them."""
        return {dslx.canon(tuple(a)) for a, _ in self._ex}


def make_accept(posts, want, count=None):
    """Acceptance of an arm: position i of the candidate's values, through ITS wrapper posts[i], must equal want[i]
    (canonical text of the demonstrated output). A wrapper that raises rejects (the search catches it)."""
    def accept(vals):
        if count is not None:
            count[0] += 1
        for v, post, c in zip(vals, posts, want):
            if dslx.canon(post(v)) != c:
                return False
        return True
    return accept


def _first_nontrivial(failed):
    return [f for f in failed if not f.startswith("a trivial repair passes")]


def holds_function(v):
    """True when a value that is not itself a function holds a function anywhere inside it."""
    if isinstance(v, (tuple, frozenset, list, set)):
        return any(callable(x) or holds_function(x) for x in v)
    return False


def wrapper_order(X, names):
    """This experiment's own seeded order of the candidate wrappers of X: the names sorted, then shuffled by a seed made
    from P.WRAPPER_TAG and X's name. Stage A's order is not reused (its three consumers and their outcomes are known)."""
    out = sorted(names)
    random.Random(int.from_bytes(hashlib.sha256((P.WRAPPER_TAG + X).encode()).digest()[:8], "big")).shuffle(out)
    return out


class Episode:
    def __init__(self, X, outdir, B=None, journal=None, hide="family"):
        self.X, self.outdir = X, outdir
        self.B = P.B if B is None else B
        self.fam = list(L["fam_of"][X])
        self.hidden = list(self.fam) if hide == "family" else [X]
        self.params = L["sigs"][X]
        self.pnames = [p for p, _ in self.params]
        self.j = journal
        self.F = None
        self.sealed = {}
        self.done = set()
        self.fit_tree = {}
        self.res = dict(target=X, label=LABEL, family=L["fam_label"][X], family_size=len(self.fam), B=self.B,
                        dev=X in P.DEV_ROSTER, held_out_family=X in dslx.held_out_names(), development_only=X in P.DEV_ROSTER)

    # ------------------------------------------------------------------ bookkeeping
    def log(self, event, **kw):
        if self.j:
            self.j.log(event, target=self.X, **kw)

    def seal(self, name, obj):
        sha = LIB.sha256_json(obj)
        self.sealed[name] = sha
        self.log("seal", name=name, sha256=sha)
        return sha

    def need(self, step, *sealed, done=()):
        missing = [s for s in sealed if s not in self.sealed] + [d for d in done if d not in self.done]
        if missing:
            raise OrderError("%s cannot open before %s" % (step, missing))

    def exclude(self, reason, kind, **kw):
        self.res.update(status="excluded", reason=reason, reason_kind=kind, **kw)
        self.log("excluded", reason=reason)
        return self.res

    # ------------------------------------------------------------------ evaluator helpers
    def post_ok(self, w, xo):
        try:
            return C.usable(C.apply_post(self.w_full[w], xo))
        except Exception:                                      # noqa: BLE001
            return False

    def usable_pairs(self, pairs, ws):
        return [(a, y) for a, y in pairs if all(self.post_ok(w, y) for w in ws)]

    def cand_fn(self, tree):
        def f(*args):
            return S.eval_tree(tree, self.ns_les, L["consts"], dict(zip(self.pnames, args)))
        return f

    def match_list(self, fn, argsets, xouts, w, whole=False):
        """For each tuple: does wrapper-w(fn(args)) equal wrapper-w(X(args))? w=None: fn(args) against X(args).
        whole=True: fn is a whole program (already includes its wrapper). Returns (list of bool, first_bad, errors).

        The batch runs under one guard of 30 CPU seconds (protocol section 6). The guard's timeout is an Exception, so it is
        re-raised before the handler of ordinary errors wherever it is delivered (inside the candidate, a wrapper or the
        comparison) and always reaches the outer handler: the batch ends there and every tuple not yet checked counts as
        not matching. With no counterexample before it, first_bad is dict(index=-1, note="guard timeout"), the mark that
        the summary reads as a wrong found only by the timeout; a real counterexample found before it stays first_bad and
        is marked guard_timeout_after_this. (Correction of 14 November 2026 after the independent review, 0736: before it,
        the timeout was caught as an ordinary error of one tuple and the batch went on without its guard.)"""
        oks, first, err = [], None, 0
        try:
            with C.guard():
                for i, (a, xo) in enumerate(zip(argsets, xouts)):
                    try:
                        want = xo if w is None else C.apply_post(self.w_full[w], xo)
                        v = fn(*a)
                        if not whole and w is not None:
                            v = C.apply_post(self.w_les[w], v)
                        ok = C.same(v, want)
                    except C.GuardTimeout:
                        raise                                  # never an ordinary error: to the outer handler
                    except Exception:                          # noqa: BLE001
                        ok, err, v, want = False, err + 1, "ERR", "ERR"
                    oks.append(ok)
                    if not ok and first is None:
                        first = dict(index=i, args=[short(x, 160) for x in a], want=want if want == "ERR" else short(want, 160),
                                     got=v if v == "ERR" else short(v, 160))
        except C.GuardTimeout:
            if first is None:
                first = dict(index=-1, note="guard timeout")
            else:
                first["guard_timeout_after_this"] = True
        oks += [False] * (len(argsets) - len(oks))
        return oks, first, err

    # ------------------------------------------------------------------ setup (before any search)
    def check_acquisition(self, tuples):
        """The acquisition check on nine tuples. Each wrapper is checked on the tuples it is used on in some arm (wrapper 1:
        0-8, 2: 3-5, 3: 6-8): the lesioned consumer fails on the missing operation, the intact one passes, the true
        operation bound through the mechanism passes, and every demonstrated output is a usable typed value. A trivial
        repair must not reproduce wrapper 1 on tuples 0-2 (every arm contains those three demonstrations)."""
        failed, trivial = [], []
        spans = {1: (0, 9), 2: (3, 6), 3: (6, 9)}
        for w, (a, b) in spans.items():
            r = G.check(self.X, self.wname[w], tuples[a:b], self.env_les, self.env_full, self.w_les[w])
            real = _first_nontrivial(r["failed"])
            failed += ["wrapper %d: %s" % (w, f) for f in real]
            if not real:                                       # every demonstrated output must be a usable typed value
                bad = []
                for i in range(a, b):
                    try:
                        ok = self.post_ok(w, self.full[self.X](*tuples[i]))
                    except Exception:                          # noqa: BLE001
                        ok = False
                    if not ok:
                        bad.append(i)
                if bad:
                    failed.append("wrapper %d: a demonstrated output is not a usable value (tuples %s)" % (w, bad))
        r0 = G.check(self.X, self.wname[1], tuples[0:3], self.env_les, self.env_full, self.w_les[1])
        trivial = list(r0["trivial_passing"])
        if trivial:
            failed.append("a trivial repair passes: " + ", ".join(trivial))
        return dict(ok=not failed, failed=failed, trivial_passing=trivial)

    def setup(self):
        """Wrappers, cohorts, pooled slices, usability and the acquisition check, on setup records only. No search."""
        X = self.X
        g = gen.gen_examples(X, n_total=P.N_GEN)
        if g["status"] != "ok":
            return self.exclude("generator: " + str(g["reason"]), "generator")
        if len(g["examples"]) != P.N_GEN:
            return self.exclude("generator gave %d examples" % len(g["examples"]), "generator")
        self.rec = Records(g["examples"])
        self.rec.open("setup")
        self.rec.open("acquisition")
        self.full = dslx.full_ns()
        self.ns_les = dslx.library_namespace(self.hidden)
        self.env_full, self.env_les = C.make_env(self.full), C.make_env(self.ns_les)
        self.bank_base = C.bank_baseline(self.ns_les)
        S_ = self.res["setup"] = dict(preservation_bank_entries=len(self.bank_base), opened_roles=self.rec.opened)
        # ---- wrappers: first five eligible in the seeded order, on setup inputs only
        setup_ex = self.rec.get("setup")
        setup_args = [a for a, _ in setup_ex]
        cinfo = C.candidate_posts(X, [o for _, o in setup_ex], dslx.reverse_closure(self.hidden))
        order = wrapper_order(X, cinfo["cands"])               # this experiment's own order, not stage A's
        chosen, skipped = [], []
        for p in order:
            r = G.check(X, p, setup_args, self.env_les, self.env_full, self.ns_les[p])
            if r["ok"]:
                chosen.append(p)
            else:
                skipped.append(dict(post=p, reason=("trivial repair passes" if r["trivial_passing"] else "; ".join(r["failed"]))[:90]))
            if len(chosen) == P.N_WRAPPERS:
                break
        S_["wrappers"] = dict(n_candidates=len(order), n_skipped=len(skipped), skipped=skipped[:80], chosen=chosen,
                              n_eligible=len(chosen), order_tag=P.WRAPPER_TAG)
        if len(chosen) < P.MIN_WRAPPERS:
            return self.exclude("fewer than three eligible wrappers (%d of %d candidates)" % (len(chosen), len(cinfo["cands"])),
                                "fewer_than_three_wrappers")
        self.wname = {i + 1: p for i, p in enumerate(chosen)}
        self.w_full = {i: self.full[p] for i, p in self.wname.items()}
        self.w_les = {i: self.ns_les[p] for i, p in self.wname.items()}
        S_["wrappers"]["by_number"] = {str(i): p for i, p in self.wname.items()}
        coh = dict(construction=True, admission=len(chosen) >= P.ADM_WRAPPER, reuse=len(chosen) >= P.REUSE_WRAPPER)
        why = {}
        if not coh["admission"]:
            why["admission"] = "no fourth eligible wrapper"
        if not coh["reuse"]:
            why["reuse"] = "no fifth eligible wrapper"
        if coh["admission"] and not self.bank_base:
            coh["admission"] = False
            why["admission"] = "preservation bank has no successful baseline entry"
        self.log("wrappers", **S_["wrappers"])
        # ---- pooled sequence: unique, disjoint from every generator tuple of X (keys only); own = setup and acquisition args
        own = self.rec.get("acquisition") + self.rec.get("setup")
        seq = C.pooled_sequence(X, own, self.rec.keys(), P.SEQ_TOTAL, tag=P.SEQ_TAG)        # own tag: not stage A's pooled inputs
        # Input hygiene. A set that holds functions iterates in an order that depends on memory addresses, so a result on
        # such an input (for example first(combine(set, tuple of functions))) can differ between two processes. A pooled
        # tuple in which a container argument holds a function is dropped; an argument that IS a function is untouched.
        self.seq = [t for t in seq if not any(holds_function(v) for v in t)]
        n = len(self.seq)
        nr, na, nb = int(n * P.SEQ_FRAC_R), int(n * P.SEQ_FRAC_A), int(n * P.SEQ_FRAC_B)
        cuts = [0, nr, nr + na, nr + 2 * na, nr + 2 * na + nb, nr + 2 * na + 2 * nb]
        (self.slice_R, self.slice_A, self.slice_UA, self.slice_B, self.slice_UB) = [self.seq[cuts[i]:cuts[i + 1]] for i in range(5)]
        S_["pooled_sequence"] = dict(unique_tuples=n, dropped_holding_functions=len(seq) - n, R=len(self.slice_R), A=len(self.slice_A),
                                     UA=len(self.slice_UA), B=len(self.slice_B), UB=len(self.slice_UB), tag=P.SEQ_TAG,
                                     own_tuples_holding_functions=sum(any(holds_function(v) for v in a) for a, _ in own))
        # ---- usability at setup, on the usability slices UA and UB (disjoint from A and B)
        u = S_["usability"] = dict(UB_draws=len(self.slice_UB))
        ub = C.stream_usable(X, self.slice_UB, [self.w_full[w] for w in (1, 2, 3)])
        u["UB_usable_wrappers_1_to_3"] = len(ub)
        if len(ub) < P.MIN_FINAL_POOL:
            S_["cohorts"] = dict(coh, unavailable=why)
            return self.exclude("too few usable pooled inputs (slice UB: %d of %d draws usable for the missing operation and wrappers 1 to 3, "
                                "need %d)" % (len(ub), len(self.slice_UB), P.MIN_FINAL_POOL), "too_few_usable_pooled_inputs")
        if coh["reuse"]:
            ub5 = C.stream_usable(X, self.slice_UB, [self.w_full[w] for w in (1, 2, 3, 5)])
            u["UB_usable_wrappers_1_to_3_and_5"] = len(ub5)
            if len(ub5) < P.MIN_FINAL_POOL:
                coh["reuse"] = False
                why["reuse"] = "slice UB: fewer than %d tuples usable with wrapper 5 as well (%d)" % (P.MIN_FINAL_POOL, len(ub5))
        if coh["admission"]:
            u["UA_draws"] = len(self.slice_UA)
            ua = C.stream_usable(X, self.slice_UA, [self.w_full[P.ADM_WRAPPER]])
            u["UA_usable_wrapper_4"] = len(ua)
            if len(ua) < P.N_ADM_POOL:
                coh["admission"] = False
                why["admission"] = "slice UA: fewer than %d tuples usable for wrapper 4 (%d)" % (P.N_ADM_POOL, len(ua))
        if not coh["admission"]:
            coh["reuse"] = False                              # nested: the reuse cohort lies inside the admission cohort
            why.setdefault("reuse", "admission role unavailable")
        S_["cohorts"] = dict(coh, unavailable=why)
        self.coh = coh
        self.log("setup_usability", **u)
        # ---- the acquisition check on the nine tuples; redraw all nine from slice R (at most 5 times) only on a trivial repair
        tuples = [a for a, _ in self.rec.get("acquisition")]
        attempts = []
        r = self.check_acquisition(tuples)
        attempts.append(dict(source="generator", ok=r["ok"], failed=r["failed"], trivial_passing=r["trivial_passing"]))
        if not r["ok"] and r["trivial_passing"] and len(r["failed"]) == 1:
            Ru = C.stream_usable(X, self.slice_R, [self.w_full[w] for w in (1, 2, 3)])
            for i in range(P.MAX_REDRAW):
                chunk = [a for a, _ in Ru[i * P.N_TUPLES:(i + 1) * P.N_TUPLES]]
                if len(chunk) < P.N_TUPLES:
                    break
                r = self.check_acquisition(chunk)
                attempts.append(dict(source="setup_redraw_%d" % (i + 1), ok=r["ok"], failed=r["failed"], trivial_passing=r["trivial_passing"]))
                if r["ok"]:
                    tuples = chunk
                    break
        S_["acquisition_check"] = dict(attempts=attempts)
        self.log("acquisition_check", attempts=attempts)
        if not r["ok"]:
            return self.exclude("acquisition check: " + "; ".join(r["failed"]), "acquisition_check")
        self.tuples = tuples
        S_["acquisition_source"] = attempts[-1]["source"]
        self.seal("setup_record", dict(wrappers=chosen, cohorts=S_["cohorts"], usability=u, pooled=S_["pooled_sequence"],
                                       setup_set=[dslx.canon(tuple(a)) for a in setup_args],
                                       acquisition_tuples=[dslx.canon(tuple(a)) for a in tuples]))
        self.done.add("setup")
        return None

    def setup_view(self):
        """What a setup-only pass commits: decisions, and (apart) counts."""
        s = self.res.get("setup", {})
        w = s.get("wrappers", {})
        c = s.get("cohorts", {})
        ex = self.res.get("status") == "excluded"
        dec = dict(status="excluded" if ex else "eligible", reason_kind=self.res.get("reason_kind"),
                   wrappers=w.get("chosen"), n_eligible_wrappers=w.get("n_eligible"),
                   cohort_construction=bool(c.get("construction")) and not ex, cohort_admission=bool(c.get("admission")) and not ex,
                   cohort_reuse=bool(c.get("reuse")) and not ex, unavailable=c.get("unavailable"),
                   acquisition_source=s.get("acquisition_source"))
        cnt = dict(pooled_sequence=s.get("pooled_sequence"), usability=s.get("usability"),
                   preservation_bank_entries=s.get("preservation_bank_entries"), reason=self.res.get("reason"))
        return dict(decision=dec, counts=cnt)

    # ------------------------------------------------------------------ acquisition
    def step_acquisition(self):
        """The nine tuples and the outputs each arm demonstrates, sealed."""
        self.need("acquisition", done=("setup",))
        X = self.X
        self.demo = {}
        pairs = sorted({(i, w) for plan in P.ARMS.values() for i, w in plan})
        for i, w in pairs:
            self.demo[(i, w)] = G.required_outputs(X, self.wname[w], [self.tuples[i]], self.env_full)[0]
        fails = [G.run_lesioned(X, self.wname[1], a, self.env_les) for a in self.tuples]
        f0 = fails[0]
        self.res["failure"] = dict(error_type=f0.get("error_type"), error_text=f0.get("error_text"), missing_name=f0.get("missing_name"),
                                   all_tuples_fail=all(f["failed"] for f in fails))
        rec = dict(tuples=[dslx.canon(tuple(a)) for a in self.tuples],
                   demonstrated={"%d:%d" % k: dslx.canon(v) for k, v in sorted(self.demo.items())})
        self.res["acquisition"] = dict(tuples=[[short(x, 300) for x in a] for a in self.tuples], demonstrated_n=len(self.demo))
        self.seal("acquisition_record", rec)
        self.done.add("acquisition")

    # ------------------------------------------------------------------ the five arm searches
    def search_arm(self, plan):
        """One arm: its own build (leaves and Y from ITS tuples), its own acceptance function and counter, its own search."""
        examples = [(self.tuples[i], self.demo[(i, w)]) for i, w in plan]
        ops, leaves, Y = core.build(self.X, self.hidden, examples, self.ns_les)
        count = [0]
        accept = make_accept([self.w_les[w] for _, w in plan], [dslx.canon(y) for y in Y], count)
        r = VS.search(ops, leaves, accept, len(Y), self.B, P.SIZE_V, P.MAX_FN, P.MAX_BANK, collect=0)
        r["candidates_tested"] = count[0]
        return r

    @staticmethod
    def safely(fn):
        try:
            return fn()
        except Exception as e:                                  # noqa: BLE001 (infrastructure failure: incomplete)
            return dict(found=None, hits=[], stop="incomplete:%s" % type(e).__name__, level=0, bank=0, function_cap_reached=False,
                        cpu_s=0.0, candidates_tested=0, error=str(e)[:300])

    def arm_record(self, name, plan, r):
        hits = r.get("hits") or []
        fit = bool(hits)
        a = dict(tuples=[i for i, _ in plan], wrappers=[self.wname[w] for _, w in plan], wrapper_numbers=[w for _, w in plan],
                 allowance=self.B, stop=r["stop"], stop_class=stop_class(r["stop"], len(hits), r["function_cap_reached"]),
                 cpu_s=round(r["cpu_s"], 3), cpu_to_first_fit=round(hits[0][3], 3) if fit else None, bank=r["bank"],
                 bank_at_first_fit=hits[0][4] if fit else None, level_completed=r["level"], function_cap_reached=r["function_cap_reached"],
                 candidates_tested=r.get("candidates_tested"), fit=fit, expr=hits[0][0] if fit else None, size=hits[0][1] if fit else None,
                 error=r.get("error"))
        return a

    def step_arms(self):
        self.need("arm searches", "acquisition_record")
        arms = self.res["arms"] = {}
        for name in P.ARM_ORDER:
            plan = P.ARMS[name]
            r = self.safely(lambda: self.search_arm(plan))
            arms[name] = self.arm_record(name, plan, r)
            self.fit_tree[name] = r["hits"][0][2] if r.get("hits") else None
            self.log("arm", arm=name, **arms[name])
        self.seal("first_fit_records", {n: dict(expr=a["expr"], stop=a["stop"], stop_class=a["stop_class"]) for n, a in arms.items()})
        self.done.add("arms")

    # ------------------------------------------------------------------ admission (stage A's rule, unchanged)
    def step_admission(self):
        """Opens the admission evidence ONLY when all five first-fit records are sealed. A failed admission ends that arm's
        candidate; nothing else is tried."""
        self.need("admission", "first_fit_records")
        arms = self.res["arms"]
        if not self.coh["admission"]:
            self.res["admission_evidence"] = dict(available=False, why=self.res["setup"]["cohorts"]["unavailable"].get("admission"))
            for a in arms.values():
                a.update(admission=None, admitted=None)
            self.done.add("admission")
            return
        self.rec.open("admission")
        X, w4 = self.X, P.ADM_WRAPPER
        gg = self.usable_pairs(self.rec.get("admission"), [w4])
        Au = C.stream_usable(X, self.slice_A, [self.w_full[w4]])[:P.N_ADM_POOL]
        self.adm = dict(gen_args=[a for a, _ in gg], gen_x=[y for _, y in gg], pool_args=[a for a, _ in Au], pool_x=[y for _, y in Au])
        self.res["admission_evidence"] = dict(available=True, generator=len(gg), pooled=len(Au), pooled_short=len(Au) < P.N_ADM_POOL)
        self.seal("admission_set", [dslx.canon(tuple(a)) for a in self.adm["gen_args"] + self.adm["pool_args"]])
        n = P.RULE_N
        for name, a in arms.items():
            tree = self.fit_tree.get(name)
            if tree is None:
                a.update(admission=None, admitted=False)
                continue
            fn = self.cand_fn(tree)
            t0 = time.process_time()
            go = self.match_list(fn, self.adm["gen_args"], self.adm["gen_x"], w4)[0]
            po = self.match_list(fn, self.adm["pool_args"], self.adm["pool_x"], w4)[0]
            bank_ok = C.bank_check(self.ns_les, LIB.neutral_name("probe", S.render(tree)), fn, self.bank_base)
            gen_ok, pool_ok = len(go) >= n and all(go[:n]), len(po) >= n and all(po[:n])
            adm = dict(generator_exact_at_6=bool(gen_ok), pooled_exact_at_6=bool(pool_ok), bank_ok=bool(bank_ok),
                       bank_successful_entries=len(self.bank_base), rule=bool(gen_ok and pool_ok and bank_ok),
                       cpu_s=round(time.process_time() - t0, 4))
            a.update(admission=adm, admitted=adm["rule"])
        self.done.add("admission")

    def step_libraries(self):
        """Admitted candidates are written read-only, one file per (target, arm); ALL sealed together."""
        self.need("libraries", done=("admission",))
        shas = {}
        for name, a in self.res["arms"].items():
            shas[name] = None
            if not a.get("admitted"):
                continue
            tree = self.fit_tree[name]
            acq_rec = dict(arm=name, expr=a["expr"], tuples=[dslx.canon(tuple(self.tuples[i])) for i in a["tuples"]], wrappers=a["wrappers"])
            adm_rec = dict(admission=a["admission"], examples=self.sealed["admission_set"])
            d = os.path.join(self.outdir, "library")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "%s__%s.json" % (self.X, name))
            nm, sha = LIB.write_library_file(path, self.X + ":" + name, self.X, tree, acq_rec, adm_rec)
            a["library"] = dict(path=os.path.relpath(path, self.outdir), name=nm, sha256=sha, mode=oct(os.stat(path).st_mode & 0o777))
            shas[name] = sha
        self.seal("libraries", shas)
        self.done.add("libraries")

    # ------------------------------------------------------------------ reuse support and the two reuse controls
    def step_reuse(self):
        self.need("reuse support", "libraries")
        if not self.coh["reuse"]:
            self.res["reuse"] = dict(available=False, why=self.res["setup"]["cohorts"]["unavailable"].get("reuse"))
            self.done.add("reuse")
            return
        self.rec.open("reuse_support")
        X, w5 = self.X, P.REUSE_WRAPPER
        sup = self.usable_pairs(self.rec.get("reuse_support"), [w5])
        three = [(a, C.apply_post(self.w_full[w5], y)) for a, y in sup]
        rr = self.res["reuse"] = dict(available=True, support_usable=len(three), support_of=P.SUPPORT[1] - P.SUPPORT[0])
        self.seal("reuse_support_set", [dslx.canon(tuple(a)) + "->" + dslx.canon(f) for a, f in three])
        self.ctrl_tree = {}
        if len(three) < P.SUPPORT[1] - P.SUPPORT[0]:
            rr["controls"] = {k: dict(stop="support_unavailable", stop_class="unavailable", fit=False) for k in ("fresh_synthesis", "fresh_repair")}
            self.done.add("reuse")
            return

        def synth():
            ops, leaves, Y = core.build(X, self.hidden, three, self.ns_les)
            return S.search(ops, leaves, Y, self.B, P.SIZE_S, P.MAX_FN, P.MAX_BANK)

        def repair():
            ops, leaves, Y = core.build(X, self.hidden, three, self.ns_les)
            want = [dslx.canon(y) for y in Y]
            post = self.w_les[w5]
            cnt = [0]

            def accept(vals):
                cnt[0] += 1
                return all(dslx.canon(post(v)) == c for v, c in zip(vals, want))
            r = VS.search(ops, leaves, accept, len(Y), self.B, P.SIZE_V, P.MAX_FN, P.MAX_BANK, collect=0)
            r["candidates_tested"] = cnt[0]
            return r
        rr["controls"] = {}
        for key, fn in (("fresh_synthesis", synth), ("fresh_repair", repair)):
            r = self.safely(fn)
            found = r["found"]
            c = dict(stop=r["stop"], stop_class=stop_class(r["stop"], 1 if found else 0, r["function_cap_reached"]), cpu_s=round(r["cpu_s"], 3),
                     bank=r["bank"], level_completed=r["level"], function_cap_reached=r["function_cap_reached"], allowance=self.B,
                     size_limit=P.SIZE_S if key == "fresh_synthesis" else P.SIZE_V, fit=bool(found), expr=found[0] if found else None,
                     candidates_tested=r.get("candidates_tested"), error=r.get("error"))
            rr["controls"][key] = c
            self.ctrl_tree[key] = found[2] if found else None
            self.log("reuse_control", control=key, **c)
        self.done.add("reuse")

    # ------------------------------------------------------------------ final evaluation (opened last)
    def fin(self):
        if self.F is None:
            raise OrderError("final inputs are opened only in the last step")
        return self.F

    def open_final(self):
        self.need("final evaluation", "libraries", done=("reuse",))
        self.rec.open("final")
        ws = [1, 2, 3] + ([P.REUSE_WRAPPER] if self.coh["reuse"] else [])
        gfin = self.usable_pairs(self.rec.get("final"), ws)
        Bu = C.stream_usable(self.X, self.slice_B, [self.w_full[w] for w in ws])
        F = dict(gen_args=[a for a, _ in gfin], gen_x=[y for _, y in gfin], pool_args=[a for a, _ in Bu], pool_x=[y for _, y in Bu])
        F["args"], F["x"] = F["gen_args"] + F["pool_args"], F["gen_x"] + F["pool_x"]
        self.F = F
        self.res["final_panel"] = dict(generator=len(gfin), pooled=len(Bu), pooled_short=len(Bu) < P.MIN_FINAL_POOL, wrappers_usable_for=ws)
        self.seal("final_set", [dslx.canon(tuple(a)) for a in F["args"]])
        self.log("final_opened", **self.res["final_panel"])
        if not F["args"]:
            raise RuntimeError("the final panel is empty")

    def exact(self, fn, w, whole=False):
        F = self.fin()
        oks, first, err = self.match_list(fn, F["args"], F["x"], w, whole)
        n = len(F["gen_args"])
        return dict(ok=bool(oks) and all(oks), gen=[sum(oks[:n]), n], pooled=[sum(oks[n:]), len(oks) - n], first_bad=first)

    def step_final(self):
        self.open_final()
        arms = self.res["arms"]
        for name, a in arms.items():
            tree = self.fit_tree.get(name)
            if tree is None:
                a.update(first_fit="none", task_exact={}, reuse_exact=False if self.coh["reuse"] else None)
                continue
            fn = self.cand_fn(tree)
            cor = self.exact(fn, None)
            a.update(first_fit="right" if cor["ok"] else "wrong", right_detail=dict(gen=cor["gen"], pooled=cor["pooled"]),
                     counterexample=None if cor["ok"] else cor["first_bad"],
                     task_exact={str(w): self.exact(fn, w)["ok"] for w in (1, 2, 3)})
            a["reuse_exact"] = None
            if self.coh["reuse"]:
                a["reuse_exact"] = False
                lib = a.get("library")
                if lib:
                    path = os.path.join(self.outdir, lib["path"])
                    before = LIB.verify_library_file(path, lib["sha256"])
                    _, fnl, _ = LIB.load_operation(path, lib["sha256"], self.ns_les)
                    t0 = time.process_time()
                    rr = self.exact(fnl, P.REUSE_WRAPPER)
                    after = LIB.verify_library_file(path, lib["sha256"])
                    a["reuse_exact"] = bool(rr["ok"] and before and after)
                    lib.update(hash_ok_before=before, hash_ok_after=after, cpu_deployment_s=round(time.process_time() - t0, 4))
        if self.coh["reuse"] and self.res["reuse"].get("controls"):
            for key, c in self.res["reuse"]["controls"].items():
                tree = getattr(self, "ctrl_tree", {}).get(key)
                c["exact_on_final"] = False if tree is None else self.exact(self.cand_fn(tree), P.REUSE_WRAPPER, whole=(key == "fresh_synthesis"))["ok"]
        self.done.add("final")

    # ------------------------------------------------------------------ the episode
    def run(self):
        t_all = time.process_time()
        ex = self.setup()
        if ex is not None:
            return ex
        self.res["status"] = "done"
        self.step_acquisition()
        self.step_arms()
        self.step_admission()
        self.step_libraries()
        self.step_reuse()
        self.step_final()
        self.res["seals"] = dict(self.sealed)
        self.res["cohorts"] = dict(self.res["setup"]["cohorts"])
        self.res["setup_view"] = self.setup_view()
        self.res["cpu_s_total"] = round(time.process_time() - t_all, 2)
        self.log("done", cpu_s_total=self.res["cpu_s_total"])
        return self.res


def run_target(X, outdir, B=None, hide="family"):
    """Run one target to completion; finished targets (targets/<X>.json) are skipped on a resume."""
    os.makedirs(os.path.join(outdir, "targets"), exist_ok=True)
    os.makedirs(os.path.join(outdir, "journal"), exist_ok=True)
    final = os.path.join(outdir, "targets", X + ".json")
    if os.path.exists(final):
        with open(final) as f:
            return json.load(f)
    j = Journal(os.path.join(outdir, "journal", X + ".jsonl"))
    ep = Episode(X, outdir, B, j, hide)
    j.log("start", target=X, B=ep.B, dev=ep.res["dev"], label=LABEL)
    try:
        res = ep.run()
        if res.get("status") == "excluded":
            res["setup_view"] = ep.setup_view()
    except Exception as e:                                      # noqa: BLE001  infrastructure failure
        import traceback
        res = dict(ep.res, status="incomplete", reason="%s: %s" % (type(e).__name__, str(e)[:300]), trace=traceback.format_exc()[-1500:])
        j.log("incomplete", reason=res["reason"])
    tmp = final + ".tmp"
    with open(tmp, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True, default=str)
    os.replace(tmp, final)
    return res


def setup_only(X):
    """The setup step alone (no search; the final role is never opened): returns the committed view of the target."""
    ep = Episode(X, None, None, None)
    t = time.process_time()
    ep.setup()
    view = ep.setup_view()
    view.update(target=X, dev=ep.res["dev"], held_out_family=ep.res["held_out_family"], cpu_s=round(time.process_time() - t, 2),
                opened_roles=list(getattr(getattr(ep, "rec", None), "opened", [])))
    if "setup" in ep.res:
        view["detail"] = ep.res["setup"]
    return view
