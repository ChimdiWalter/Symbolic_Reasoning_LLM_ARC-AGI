"""One episode (target X taken away with its family, observed, repaired, admitted, reused) with a JSONL journal.
Author: Chimdi Walter Ndubuisi

Development study, stage A: CPU only, invented inputs, no model. The operations study's outcomes for these same
operations were known before this protocol was frozen, so this is not an untouched confirmation over operations.
Bottom-up enumerative synthesis with observational equivalence is standard (TRANSIT, 2013; Escher, 2013); completing a
program with a hole is program sketching; the library is arc-dsl by Michael Hodel (MIT). Nothing new is claimed
about the method.

FIVE DISJOINT RECORD SETS per target (generator examples 0-65), used in this order, each sealed (sha256 journalled)
before the next step:
  setup 18-35 (chooses the three post operations only) -> acquisition 0-2 (the three shown examples) ->
  [searches; candidates sealed] -> admission grid 3-14 and pooled stream A (opened only after the candidates are sealed)
  -> [libraries written and sealed] -> reuse support 15-17 (opened only after the libraries are sealed) ->
  final 36-65 and pooled stream B (produced and read ONLY in the last step).
The true operation X is used only by the evaluator parts and never reaches a search. Redraws and exclusions happen
only at setup, before any search. The first fit of an arm is frozen; failing the rule ends that arm for that target.
"""
import hashlib
import json
import os
import random
import time

import frozen  # noqa: F401
import core
import dslx
import gen
import search as S
import vsearch as VS
import consumers as C
import gate as G
import library as LIB
import presets_vf1 as V

L = dslx.load()
LABEL = "development study (the operations study's outcomes for these operations were known before this protocol was frozen)"


def short(v, n=1200):
    c = dslx.canon(v)
    return c if len(c) <= n else c[:n] + "...#" + hashlib.sha256(c.encode()).hexdigest()[:8]


class Journal:
    def __init__(self, path):
        self.path = path
        open(path, "w").close()

    def log(self, event, **kw):
        with open(self.path, "a") as f:
            f.write(json.dumps(dict(event=event, **kw), sort_keys=True, default=str) + "\n")


def stop_class(stop, hits, cap=False):
    """fit / complete_negative (exhausted to its size limit) / size_limit_with_function_cap (ended at its size limit but
    the cap on function-valued entries was reached, so NOT exhaustive) / allowance_used_up / incomplete."""
    if hits:
        return "fit"
    if stop in ("size_exhausted", "size_exhausted_function_cap"):
        return "size_limit_with_function_cap" if (cap or stop == "size_exhausted_function_cap") else "complete_negative"
    if stop in ("budget_cpu", "budget_bank"):
        return "allowance_used_up"
    return "incomplete"


def post_accept(post_fn, finals):
    fc = [dslx.canon(f) for f in finals]

    def accept(vals):
        for v, f in zip(vals, fc):
            if dslx.canon(C.apply_post(post_fn, v)) != f:
                return False
        return True
    return accept


def _timed(fn):
    t = time.process_time()
    r = fn()
    return r, time.process_time() - t


def _count(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


def _size(t):
    return 1 + sum(_size(c) for c in t[2:]) if t[0] == "L" else 1


class Episode:
    def __init__(self, X, outdir, B=None, journal=None, hide="family"):
        self.X, self.outdir = X, outdir
        self.B = V.B if B is None else B
        self.fam = list(L["fam_of"][X])
        self.hide = hide                 # 'family' (the protocol) or 'self' (only used by a test of a known acquisition)
        self.hidden = list(self.fam) if hide == "family" else [X]
        self.params = L["sigs"][X]
        self.pnames = [p for p, _ in self.params]
        self.j = journal
        self.F = None                    # final evaluation data: None until open_final()
        self.sealed = {}
        self.res = dict(target=X, label=LABEL, family=L["fam_label"][X], family_size=len(self.fam), B=self.B,
                        dev=X in V.DEV_ROSTER, held_out_family=X in dslx.held_out_names(), development_only=X in V.DEV_ROSTER)

    def log(self, event, **kw):
        if self.j:
            self.j.log(event, target=self.X, **kw)

    def seal(self, name, obj):
        sha = LIB.sha256_json(obj)
        self.sealed[name] = sha
        self.log("seal", name=name, sha256=sha)
        return sha

    def exclude(self, reason, **kw):
        self.res.update(status="excluded", reason=reason, **kw)
        self.log("excluded", reason=reason)
        return self.res

    # ------------------------------------------------------------------ setup (before any search)
    def setup(self):
        X = self.X
        g = gen.gen_examples(X, n_total=V.N_GEN)
        if g["status"] != "ok":
            return self.exclude("generator: " + str(g["reason"]))
        self.g = g["examples"]
        assert len(self.g) == V.N_GEN
        self.full = dslx.full_ns()
        self.ns_les = dslx.library_namespace(self.hidden)
        self.env_full, self.env_les = C.make_env(self.full), C.make_env(self.ns_les)
        self.bank_base = C.bank_baseline(self.ns_les)
        self.res["preservation_bank"] = dict(successful_entries=len(self.bank_base))
        if not self.bank_base:
            return self.exclude("preservation bank has no successful baseline entry")
        ffull = lambda p: None if p is None else self.full[p]
        fles = lambda p: None if p is None else self.ns_les[p]
        # ---- the three post operations, chosen on the setup examples (generator 18-35) and nothing else
        setup_ex = self.g[V.SETUP_FROM:V.SETUP_TO]
        setup_args = [a for a, _ in setup_ex]
        cinfo = C.candidate_posts(X, [o for _, o in setup_ex], dslx.reverse_closure(self.hidden))
        chosen, skipped = [], []
        for p in cinfo["cands"]:
            r = G.check(X, p, setup_args, self.env_les, self.env_full, fles(p))
            if r["ok"]:
                chosen.append(p)
            else:
                skipped.append(dict(post=p, reason=("trivial repair passes" if r["trivial_passing"] else "; ".join(r["failed"]))[:90]))
            if len(chosen) == V.N_CONSUMERS:
                break
        self.res["consumers"] = dict(n_candidates=len(cinfo["cands"]), n_skipped=len(skipped), skipped=skipped[:80],
                                     skipped_by_reason=_count([x["reason"] for x in skipped]), chosen=chosen)
        if len(chosen) < V.N_CONSUMERS:
            return self.exclude("fewer than three consumers (%d eligible of %d candidates)" % (len(chosen), len(cinfo["cands"])))
        self.post_name = dict(zip(("acq", "adm", "reuse"), chosen))
        self.post_full = {r: ffull(p) for r, p in self.post_name.items()}
        self.post_les = {r: fles(p) for r, p in self.post_name.items()}
        roles = {}
        for r, p in self.post_name.items():
            finals = G.required_outputs(X, p, setup_args, self.env_full)
            roles[r] = dict(post=p, distinct_final_outputs_on_setup_examples=len({dslx.canon(f) for f in finals}))
        self.res["consumers"].update(post=self.post_name, roles=roles, flags=[],
                                     text={r: C.consumer_text(X, p) for r, p in self.post_name.items()})
        self.log("consumers", **self.res["consumers"])
        self.seal("setup_set", [dslx.canon(tuple(a)) for a in setup_args])
        # ---- pooled sequence: unique, disjoint from every generator tuple of X; slices R, A, B are disjoint
        self.seq = C.pooled_sequence(X, self.g[:V.SETUP_TO], C.gen_keys(self.g), V.SEQ_TOTAL)
        n = len(self.seq)
        nr, na, nb = int(n * V.SEQ_FRAC_R), int(n * V.SEQ_FRAC_A), int(n * V.SEQ_FRAC_B)
        cuts = [0, nr, nr + na, nr + 2 * na, nr + 2 * na + nb, nr + 2 * na + 2 * nb]
        (self.slice_R, self.slice_A, self.slice_UA, self.slice_B, self.slice_UB) = [self.seq[cuts[i]:cuts[i + 1]] for i in range(5)]
        self.res["pooled_sequence"] = dict(unique_tuples=n, R=len(self.slice_R), A=len(self.slice_A), UA=len(self.slice_UA),
                                           B=len(self.slice_B), UB=len(self.slice_UB))
        # ---- usability of pooled inputs, checked at setup on streams UA and UB (disjoint from A and B, same numbers of draws)
        ua = C.stream_usable(X, self.slice_UA, [self.post_full["adm"]])
        ub = C.stream_usable(X, self.slice_UB, [self.post_full["acq"], self.post_full["reuse"]])
        self.res["setup_pooled_usability"] = dict(admission_usable=len(ua), admission_draws=len(self.slice_UA),
                                                  acq_and_reuse_usable=len(ub), acq_and_reuse_draws=len(self.slice_UB))
        self.log("setup_pooled_usability", **self.res["setup_pooled_usability"])
        if len(ua) < V.N_ADM_POOL or len(ub) < V.MIN_FINAL_POOL:
            return self.exclude("too few usable pooled inputs (admission consumer: %d of %d draws, need %d; acquisition and reuse "
                                "consumers together: %d of %d draws, need %d)" % (len(ua), len(self.slice_UA), V.N_ADM_POOL,
                                                                                  len(ub), len(self.slice_UB), V.MIN_FINAL_POOL))
        # ---- acquisition gate on the three shown examples; redraw from the setup stream R only at setup
        gate = dict(attempts=[])
        acq = [a for a, _ in self.g[:V.N_ACQ]]
        r = G.check(X, self.post_name["acq"], acq, self.env_les, self.env_full, self.post_les["acq"])
        gate["attempts"].append(dict(source="generator", ok=r["ok"], failed=r["failed"], trivial_passing=r["trivial_passing"]))
        if not r["ok"] and r["trivial_passing"] and len(r["failed"]) == 1:
            Ru = C.stream_usable(X, self.slice_R, [self.post_full["acq"]])
            for i in range(V.MAX_REDRAW):
                chunk = [a for a, _ in Ru[i * V.N_ACQ:(i + 1) * V.N_ACQ]]
                if len(chunk) < V.N_ACQ:
                    break
                r = G.check(X, self.post_name["acq"], chunk, self.env_les, self.env_full, self.post_les["acq"])
                gate["attempts"].append(dict(source="setup_redraw_%d" % (i + 1), ok=r["ok"], failed=r["failed"], trivial_passing=r["trivial_passing"]))
                if r["ok"]:
                    acq = chunk
                    break
        self.res["gate"] = gate
        self.log("gate", **gate)
        if not r["ok"]:
            return self.exclude("gate (acquisition): " + "; ".join(r["failed"]))
        self.acq_args = acq
        self.acq_final = G.required_outputs(X, self.post_name["acq"], acq, self.env_full)
        self.acq_x = [self.full[X](*a) for a in acq]
        self.seal("acquisition_set", [dslx.canon(tuple(a)) + "->" + dslx.canon(f) for a, f in zip(acq, self.acq_final)])
        return None

    # ------------------------------------------------------------------ evaluator
    def cand_fn(self, tree):
        def f(*args):
            return S.eval_tree(tree, self.ns_les, L["consts"], dict(zip(self.pnames, args)))
        return f

    def whole_fn(self, tree):
        return self.cand_fn(tree)

    def match_list(self, fn, argsets, xouts, role, whole=False):
        """EVALUATOR. For each tuple: does post_role(fn(args)) equal post_role(X(args))? whole=True: fn is a whole
        program (already includes post). Returns (list of bool, first_bad, n_errors). A guard timeout fails the rest."""
        oks = []
        first = None
        err = 0
        try:
            with C.guard():
                for i, (a, xo) in enumerate(zip(argsets, xouts)):
                    try:
                        want = C.apply_post(self.post_full.get(role), xo)
                        v = fn(*a)
                        if not whole:
                            v = C.apply_post(self.post_les.get(role), v)
                        ok = C.same(v, want)
                    except Exception:                          # noqa: BLE001
                        ok, err, v, want = False, err + 1, "ERR", "ERR"
                    oks.append(ok)
                    if not ok and first is None:
                        first = dict(index=i, args=[short(x, 160) for x in a], want=want if want == "ERR" else short(want, 160),
                                     got=v if v == "ERR" else short(v, 160))
        except C.GuardTimeout:
            first = first or dict(index=-1, note="guard timeout")
        oks += [False] * (len(argsets) - len(oks))
        return oks, first, err

    def match(self, fn, argsets, xouts, role, whole=False):
        oks, first, err = self.match_list(fn, argsets, xouts, role, whole)
        return dict(ok=bool(oks) and all(oks), n=len(argsets), equal=sum(oks), errors=err, first_bad=first)

    def post_ok(self, role, xo):
        """Is post_role(X's result) a usable value? (A post may raise on some results; such examples are left out.)"""
        try:
            return C.usable(C.apply_post(self.post_full[role], xo))
        except Exception:                                      # noqa: BLE001
            return False

    def usable_pairs(self, pairs, roles):
        return [(a, y) for a, y in pairs if all(self.post_ok(r, y) for r in roles)]

    # ---- final data: a single loader, called once, in the last step
    def fin(self):
        if self.F is None:
            raise RuntimeError("final inputs are opened only in the last step")
        return self.F

    def open_final(self):
        """Produce and read the final evaluation data: generator 36-65 and pooled stream B (usable for X and for both the
        acquisition and the reuse post). Called ONCE, after every candidate, admission decision and library is sealed."""
        X = self.X
        gfin = self.usable_pairs(self.g[V.FINAL_FROM:V.FINAL_FROM + V.N_FINAL_GEN], ('acq', 'reuse'))
        Bu = C.stream_usable(X, self.slice_B, [self.post_full["acq"], self.post_full["reuse"]])
        gargs = [a for a, _ in gfin]
        self.F = dict(gen_args=gargs, gen_x=[y for _, y in gfin], pool_args=[a for a, _ in Bu], pool_x=[y for _, y in Bu])
        self.F["args"] = self.F["gen_args"] + self.F["pool_args"]
        self.F["x"] = self.F["gen_x"] + self.F["pool_x"]
        self.res["final_panel"] = dict(generator=len(gargs), pooled=len(Bu), pooled_short=len(Bu) < V.MIN_FINAL_POOL)
        self.seal("final_set", [dslx.canon(tuple(a)) for a in self.F["args"]])
        self.log("final_opened", **self.res["final_panel"])

    def exact(self, fn, role, whole=False):
        F = self.fin()
        oks, first, err = self.match_list(fn, F["args"], F["x"], role, whole)
        n = len(F["gen_args"])
        return dict(ok=bool(oks) and all(oks), gen=[sum(oks[:n]), n], pooled=[sum(oks[n:]), len(oks) - n], first_bad=first)

    # ---- admission evidence (opened after the candidates are sealed)
    def open_admission(self):
        X = self.X
        gg = self.usable_pairs(self.g[V.GRID_FROM:V.GRID_FROM + V.N_GRID], ('acq', 'adm'))
        Au = C.stream_usable(X, self.slice_A, [self.post_full["adm"]])
        self.adm = dict(gen_args=[a for a, _ in gg], gen_x=[y for _, y in gg], pool_args=[a for a, _ in Au[:V.N_ADM_POOL]],
                        pool_x=[y for _, y in Au[:V.N_ADM_POOL]])
        self.res["admission_evidence"] = dict(generator=len(gg), pooled=len(self.adm["pool_args"]),
                                              pooled_short=len(self.adm["pool_args"]) < V.N_ADM_POOL)
        self.seal("admission_set", [dslx.canon(tuple(a)) for a in self.adm["gen_args"] + self.adm["pool_args"]])

    def admission(self, fn, tree):
        """Admission standards, each at n = 3, 6 and 12 (nested prefixes), all on the same frozen candidate: "more of the
        same" (acquisition consumer on generator inputs 3-14), the admission consumer on generator inputs 3-14, the
        admission consumer on pooled inputs; "adm_both" (the admission consumer on generator inputs AND on pooled inputs,
        n of each, passing only if both pass); and none. THE RULE: adm_both at n = 6 (six generator plus six pooled
        examples of the admission consumer) and the preservation bank. Uses only admission evidence. A shortage of pooled inputs makes the rule fail (recorded)."""
        t0 = time.process_time()
        out = dict(none=True)
        A = self.adm
        for name, args, xo, role in (("same_kind", A["gen_args"], A["gen_x"], "acq"),
                                     ("adm_generator", A["gen_args"], A["gen_x"], "adm"),
                                     ("adm_pooled", A["pool_args"], A["pool_x"], "adm")):
            oks = self.match_list(fn, args, xo, role)[0]
            out[name] = {str(n): (len(oks) >= n and all(oks[:n])) for n in V.GRID_NS}
        out["adm_both"] = {str(n): bool(out["adm_generator"][str(n)] and out["adm_pooled"][str(n)]) for n in V.GRID_NS}
        cpu_std = time.process_time() - t0
        (bank_ok, cpu_bank) = _timed(lambda: C.bank_check(self.ns_les, LIB.neutral_name("probe", S.render(tree)), fn, self.bank_base))
        out.update(bank_ok=bank_ok, bank_successful_entries=len(self.bank_base), rule_standard="adm_both@%d + bank" % V.RULE_N,
                   rule=bool(out["adm_both"][str(V.RULE_N)] and bank_ok), cpu_standards_s=round(cpu_std, 4), cpu_preservation_s=round(cpu_bank, 4))
        return out

    # ------------------------------------------------------------------ searches
    def build(self, examples, hidden, ns):
        return core.build(self.X, hidden, examples, ns)

    def search_v(self, examples, budget, collect, post_role):
        """Failure-visible search: the missing call only, size limit 4, accepted through the consumer."""
        ops, leaves, Y = self.build(examples, self.hidden, self.ns_les)
        acc = post_accept(self.post_les[post_role], Y)
        return VS.search(ops, leaves, acc, len(Y), budget, V.SIZE_V, V.MAX_FN, V.MAX_BANK, collect=collect)

    def search_s(self, examples, budget, size=None, hidden=None, ns=None):
        """Ordinary synthesis: the whole program from the examples, the frozen search, no old program."""
        ops, leaves, Y = self.build(examples, self.hidden if hidden is None else hidden, self.ns_les if ns is None else ns)
        return S.search(ops, leaves, Y, budget, size or V.SIZE_S, V.MAX_FN, V.MAX_BANK)

    def search_t(self, budget):
        """Declared teacher examples: X's own outputs on the six generator inputs 0-5 (evaluator supplied)."""
        ex = [(a, self.full[self.X](*a)) for a, _ in self.g[:V.N_TEACH]]
        return self.search_s(ex, budget, size=V.SIZE_V)

    def derive(self, tree):
        """A sub-expression of a whole program that could stand in for the missing call: the child of the acquisition
        post at the root. None when the program is not of that form."""
        p = self.post_name["acq"]
        if tree[0] == "L" and tree[1] == p and len(tree) == 3:
            return tree[2]
        return None

    def arm_record(self, kind, r, budget):
        hits = r.get("hits")
        nh = len(hits) if hits is not None else (1 if r["found"] else 0)
        return dict(stop=r["stop"], stop_class=stop_class(r["stop"], nh, r["function_cap_reached"]), cpu_s=round(r["cpu_s"], 3),
                    cpu_s_physical=round(r["cpu_s"], 3), bank=r["bank"], level_completed=r["level"], allowance=budget,
                    fit=nh > 0, n_hits=nh, function_cap_reached=r["function_cap_reached"])

    def safely(self, kind, budget, fn):
        try:
            return fn()
        except Exception as e:                                  # noqa: BLE001 (infrastructure failure: incomplete)
            return dict(found=None, hits=[], stop="incomplete:%s" % type(e).__name__, level=0, bank=0,
                        function_cap_reached=False, cpu_s=0.0, error=str(e)[:300])

    # ------------------------------------------------------------------ admit: the frozen candidate meets the rule
    def admit(self, arm, tree, write=True):
        """The frozen candidate (a replacement for the missing call) goes through the four standards; if the rule passes
        it is written to a read-only library file and sealed. Nothing else is ever tried for this arm."""
        rec = dict(expr=S.render(tree), size=_size(tree))
        fn = self.cand_fn(tree)
        adm = self.admission(fn, tree)
        rec.update(admission=adm, admitted=adm["rule"], cpu_admission_s=round(adm["cpu_standards_s"] + adm["cpu_preservation_s"], 4))
        if adm["rule"] and write:
            acq_rec = dict(arm=arm, expr=rec["expr"], examples=[dslx.canon(tuple(a)) for a in self.acq_args])
            adm_rec = dict(admission=adm, examples=self.sealed["admission_set"])
            d = os.path.join(self.outdir, "library")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "%s__%s.json" % (self.X, arm))
            (nm_sha, cpu_w) = _timed(lambda: LIB.write_library_file(path, self.X + ":" + arm, self.X, tree, acq_rec, adm_rec))
            name, sha = nm_sha
            rec["library"] = dict(path=os.path.relpath(path, self.outdir), name=name, sha256=sha, cpu_write_s=round(cpu_w, 4),
                                  mode=oct(os.stat(path).st_mode & 0o777))
            self.seal("library_" + arm, sha)
        return rec

    # ------------------------------------------------------------------ the last step: evaluator readings
    def final_eval_candidate(self, rec, tree):
        """Direct equality with X (correct), the acquisition task with the candidate composed with the retained post, the
        reuse task by the library operation (no search) when admitted. Never feeds anything back."""
        fn = self.cand_fn(tree)
        cor = self.exact(fn, None)
        acq = self.exact(fn, "acq")
        rua = self.exact(fn, "reuse")
        rec.update(correct=cor["ok"], correct_detail=dict(gen=cor["gen"], pooled=cor["pooled"]), counterexample=None if cor["ok"] else cor["first_bad"],
                   task_acq_exact=acq["ok"], reuse_exact_any=rua["ok"], reused=False)
        if rec.get("library"):
            lib = rec["library"]
            path = os.path.join(self.outdir, lib["path"])
            ok_before = LIB.verify_library_file(path, lib["sha256"])
            (lo, cpu_l) = _timed(lambda: LIB.load_operation(path, lib["sha256"], self.ns_les))
            fnl = lo[1]
            (rr, cpu_d) = _timed(lambda: self.exact(fnl, "reuse"))
            ok_after = LIB.verify_library_file(path, lib["sha256"])
            rec.update(reused=bool(rr["ok"] and ok_before and ok_after), reuse_cpu_s=round(cpu_d, 4))
            lib.update(hash_ok_before=ok_before, hash_ok_after=ok_after, cpu_load_s=round(cpu_l, 4), cpu_deployment_s=round(cpu_d, 4))
        return rec

    # ------------------------------------------------------------------ the episode
    def run(self):
        t_all = time.process_time()
        ex0 = self.setup()
        if ex0 is not None:
            return ex0
        X, B = self.X, self.B
        self.res["status"] = "done"
        acq_ex = list(zip(self.acq_args, self.acq_final))
        # 2. observe
        fails = [G.run_lesioned(X, self.post_name["acq"], a, self.env_les) for a in self.acq_args]
        f0 = fails[0]
        self.res["failure"] = dict(
            error_type=f0.get("error_type"), error_text=f0.get("error_text"),
            failing_step="step 1 of 2: the call of %s" % f0.get("missing_name"), missing_name=f0.get("missing_name"),
            all_examples_fail=all(f["failed"] for f in fails),
            arguments=[[short(x, 600) for x in a] for a in self.acq_args],
            argument_tags=[[dslx.tag(x) for x in a] for a in self.acq_args],
            required_outputs=[short(f, 600) for f in self.acq_final])
        self.log("observed_failure", **self.res["failure"])
        # 3. decide
        localised = bool(f0.get("missing_name")) and f0["error_type"] == "NameError"
        self.res["decision"] = dict(rule="construct at the failing step when the failure is localised (a NameError naming "
                                         "the missing operation), else search for a whole program", localised=localised,
                                    chosen="V" if localised else "S", both_actions_run=True)
        arms = {}
        # 4. propose: V (collect up to 20), S (acquisition task), T
        rv = self.safely("V", B, lambda: self.search_v(acq_ex, B, V.N_COLLECT, "acq"))
        rs = self.safely("S", B, lambda: self.search_s(acq_ex, B))
        rt = self.safely("T", B, lambda: self.search_t(B))
        hits = rv.get("hits", [])
        a = self.arm_record("V", rv, B)
        a.update(cpu_to_first_fit=round(hits[0][3], 3) if hits else None, bank_at_first_fit=hits[0][4] if hits else None,
                 fits=[dict(expr=h[0], size=h[1], cpu_s=round(h[3], 3)) for h in hits], error=rv.get("error"),
                 note="physical CPU is the whole collecting run; the counterfactual CPU to the first fit is cpu_to_first_fit")
        arms["V"] = a
        b = self.arm_record("S", rs, B)
        b.update(cpu_to_first_fit=b["cpu_s"] if rs["found"] else None, error=rs.get("error"),
                 expr=rs["found"][0] if rs["found"] else None, size=rs["found"][1] if rs["found"] else None)
        arms["S"] = b
        c = self.arm_record("T", rt, B)
        c.update(cpu_to_first_fit=c["cpu_s"] if rt["found"] else None, error=rt.get("error"),
                 declared="teacher examples (extra supervision); inputs 0-2 are the acquisition examples, 3-5 are shared with the admission grid, so T's admission is reported apart")
        arms["T"] = c
        for k in ("V", "S", "T"):
            self.log("arm_" + k, **arms[k])
        # the frozen candidates are sealed before any admission, reuse-support or final evidence is opened
        s_tree = rs["found"][2] if rs["found"] else None
        t_tree = rt["found"][2] if rt["found"] else None
        v_tree = hits[0][2] if hits else None
        self.seal("candidates", dict(V=[h[0] for h in hits], S=arms["S"]["expr"], T=S.render(t_tree) if t_tree else None))
        arms["H"] = self.arm_h(arms, rv, rs)
        h_src = arms["H"].get("source")
        # diagnosis (exploratory): arm S on the acquisition task with nothing hidden
        self.res["diagnosis_pending"] = True
        diag = self.diagnosis(acq_ex)
        # 5-6. verify and admit (admission evidence opened here)
        self.open_admission()
        if v_tree is not None:
            arms["V"].update(self.admit("V", v_tree))
        if t_tree is not None:
            arms["T"].update(self.admit("T", t_tree))
        s_stand = self.derive(s_tree) if s_tree is not None else None
        arms["S"]["standin"] = dict(contains_standin=s_stand is not None, expr=S.render(s_stand) if s_stand is not None else None)
        if s_stand is not None:
            sa = self.admit("S", s_stand, write=False)
            arms["S"]["standin"].update(admitted=sa["admitted"], admission=sa["admission"])
        arms["S"].update(admitted=False, correct=False, reused=False, note="S is scored at task level only; no capability reading")
        h_tree = None
        if h_src == "V half":
            arms["H"].update({k: v for k, v in arms["V"].items() if k in ("expr", "size", "admission", "admitted", "cpu_admission_s", "library")})
            h_tree = v_tree
        elif h_src == "S half" and s_stand is not None:
            arms["H"].update(self.admit("H", s_stand))
            h_tree = s_stand
        elif h_src == "S half":
            arms["H"].update(expr=arms["S"]["expr"], admitted=False, note="S half found a program with no stand-in for the call")
        # selection controls: admission of every collected fit (measurement only; the rule's candidate is the first)
        hit_adm = [self.admission(self.cand_fn(h[2]), h[2]) for h in hits]
        for k in ("V", "T", "H"):
            for fld in ("admitted",):
                arms[k].setdefault(fld, False)
        self.log("libraries_sealed", libraries={k: arms[k].get("library", {}).get("sha256") for k in ("V", "T", "H")})
        # 7. reuse support (opened only after the libraries are sealed) and the reuse-task searches
        sup = self.usable_pairs(self.g[V.SUPPORT_FROM:V.SUPPORT_FROM + V.N_SUPPORT], ("reuse",))
        three = [(a_, C.apply_post(self.post_full["reuse"], y)) for a_, y in sup]
        self.res["reuse_support"] = dict(usable=len(three), of=V.N_SUPPORT)
        self.seal("reuse_support_set", [dslx.canon(tuple(a_)) + "->" + dslx.canon(f) for a_, f in three])
        rc = self.reuse_searches(arms, three)
        # 8. the last step: final inputs and everything read from them
        self.open_final()
        for k, tree in (("V", v_tree), ("T", t_tree), ("H", h_tree)):
            if tree is not None:
                self.final_eval_candidate(arms[k], tree)
        for k in ("V", "T", "H"):
            for fld in ("correct", "reused", "task_acq_exact", "reuse_exact_any"):
                arms[k].setdefault(fld, False)
        if arms["H"].get("source") == "V half":
            for fld in ("correct", "reused", "task_acq_exact", "reuse_exact_any", "counterexample", "correct_detail", "reuse_cpu_s"):
                if fld in arms["V"]:
                    arms["H"][fld] = arms["V"][fld]
        # S: whole programs evaluated directly
        if s_tree is not None:
            e = self.exact(self.whole_fn(s_tree), "acq", whole=True)
            arms["S"]["task_acq_exact"] = e["ok"]
            arms["S"]["task_acq_detail"] = dict(gen=e["gen"], pooled=e["pooled"])
        arms["S"].setdefault("task_acq_exact", False)
        self.final_reuse_controls(rc, arms)
        for k in ("V", "S", "H", "T"):
            self.log("outcome_" + k, **{k2: v for k2, v in arms[k].items() if k2 != "fits"})
        self.res["arms"] = arms
        self.res["selection"] = self.selection(hits, hit_adm)
        self.res["repair_choice"] = self.repair_choice(arms)
        self.res["reuse_controls"] = rc
        self.res["diagnosis"] = diag
        self.res.pop("diagnosis_pending", None)
        self.res["late_gate_flags"] = self.late_gate()
        self.res["primary"] = self.primary(arms, rc)
        self.res["cpu_s_total"] = round(time.process_time() - t_all, 2)
        self.log("done", cpu_s_total=self.res["cpu_s_total"])
        return self.res

    def arm_h(self, arms, rv, rs):
        """H (failure hidden; its program text names the missing operation, so it is a budget mixture of V and S, not a
        clean test of localisation): half of B on the inner call, half on the whole program, no error used. Derived from the
        V and S runs, which are deterministic searches in the same order: a fit found within B/2 of CPU by one of them is
        what a B/2 run of it would have found. The inner-call half comes first."""
        half = self.B / 2
        va, sa = arms["V"], arms["S"]
        h = dict(derived_from_arm_runs=True, allowance=self.B, half=half)
        spent = min(rv["cpu_s"], half) if not va["fit"] else (va["cpu_to_first_fit"] if va["cpu_to_first_fit"] <= half else half)
        if va["fit"] and va["cpu_to_first_fit"] <= half:
            h.update(source="V half", fit=True, cpu_s=round(spent, 3), cpu_s_physical=round(spent, 3), stop="found", stop_class="fit")
            return h
        spent_s = sa["cpu_to_first_fit"] if (sa["fit"] and sa["cpu_to_first_fit"] <= half) else min(rs["cpu_s"], half)
        h["cpu_s"] = h["cpu_s_physical"] = round(spent + spent_s, 3)
        if sa["fit"] and sa["cpu_to_first_fit"] <= half:
            h.update(source="S half", fit=True, stop="found", stop_class="fit", expr=sa["expr"])
        else:
            h.update(source=None, fit=False, stop="allowance_split_used_up", stop_class="allowance_used_up")
        return h

    # ------------------------------------------------------------------ reuse task and controls
    def reuse_searches(self, arms, three):
        """Searches on the reuse task from the three reuse-support examples. S: whole program, allowance B (this is the
        fixed-library search); no retention: a fresh V with allowance B; the 10 B search only where V admitted
        something (conditional comparison). Cost counted."""
        out = {}
        if len(three) < V.N_SUPPORT:                  # the reuse post raised on a support example: the controls cannot run
            un = dict(stop="support_unavailable", stop_class="incomplete", cpu_s=0.0, cpu_s_physical=0.0, bank=0, level_completed=0,
                      allowance=self.B, fit=False, n_hits=0, function_cap_reached=False, tree=None, expr=None, cost_cpu_s=self.B)
            out = dict(no_retention=dict(un), fixed_library_B=dict(un), conditional_comparison_fixed_library_10B=None)
            return out
        r = self.safely("noret", self.B, lambda: self.search_v(three, self.B, 0, "reuse"))
        rec = self.arm_record("noret", r, self.B)
        rec["tree"] = r["found"][2] if r["found"] else None
        rec["expr"] = r["found"][0] if r["found"] else None
        rec["cost_cpu_s"] = rec["cpu_s"]
        out["no_retention"] = rec

        def fixed(budget):
            rr = self.safely("fixed", budget, lambda: self.search_s(three, budget))
            rc = self.arm_record("fixed", rr, budget)
            rc["tree"] = rr["found"][2] if rr["found"] else None
            rc["expr"] = rr["found"][0] if rr["found"] else None
            return rc
        out["fixed_library_B"] = fixed(self.B)
        if arms["V"].get("admitted"):
            c = fixed(V.FIXED_LIB_BIG * self.B)
            c["label"] = "conditional comparison (run only where V admitted something)"
            out["conditional_comparison_fixed_library_10B"] = c
        else:
            out["conditional_comparison_fixed_library_10B"] = None
        for k, v in out.items():
            self.log("reuse_search_" + k, value={a: b for a, b in (v or {}).items() if a != "tree"})
        return out

    def final_reuse_controls(self, rc, arms):
        """Final panel readings of the reuse-task searches (same panel for every arm). The reuse task of S is the
        fixed-library search."""
        for k in ("no_retention", "fixed_library_B", "conditional_comparison_fixed_library_10B"):
            c = rc.get(k)
            if not c:
                continue
            tree = c.pop("tree", None)
            if tree is None:
                c["exact_on_final"] = False
                continue
            fn = self.cand_fn(tree)
            c["exact_on_final"] = self.exact(fn, "reuse", whole=(k != "no_retention"))["ok"]
        va = arms["V"]
        costs = dict(
            retained_parts=dict(acquisition_to_first_fit_cpu_s=va.get("cpu_to_first_fit"), admission_cpu_s=va.get("cpu_admission_s"),
                                preservation_cpu_s=(va.get("admission") or {}).get("cpu_preservation_s"),
                                library_write_cpu_s=(va.get("library") or {}).get("cpu_write_s"),
                                library_load_cpu_s=(va.get("library") or {}).get("cpu_load_s"),
                                deployment_at_reuse_cpu_s=(va.get("library") or {}).get("cpu_deployment_s")),
            retained_parts_note="admission_cpu_s includes preservation_cpu_s (nested); add the parts once, never the inclusive total with its own parts",
            retained_available=bool(va.get("admitted") and va.get("reused")),
            no_retention_per_reuse_cpu_s=rc["no_retention"]["cost_cpu_s"], fixed_library_B_cpu_s=rc["fixed_library_B"]["cpu_s"])
        rc["costs"] = costs

    def primary(self, arms, rc):
        """PRIMARY: exact outputs of the ACQUISITION task on its final panel, the same panel for V and S, each at allowance
        B. V: its first fit in place of the missing call, composed with the retained acquisition post (no admission
        needed). S: its whole program, evaluated directly. SECONDARY on reuse (same final panel for every arm): V's
        admitted operation from the frozen library (no search, no support examples) against S's fresh synthesis from the
        reuse-support examples and against the no-retention control."""
        v, s = arms["V"], arms["S"]
        return dict(
            acquisition_task=dict(V=bool(v.get("task_acq_exact")), S=bool(s.get("task_acq_exact")),
                                  V_cpu_counterfactual_s=v.get("cpu_to_first_fit") if v.get("fit") else v["cpu_s"],
                                  V_cpu_physical_s=v["cpu_s_physical"], S_cpu_physical_s=s["cpu_s_physical"]),
            reuse_task_secondary=dict(retained_V=bool(v.get("reused")), S_fresh=bool(rc["fixed_library_B"].get("exact_on_final")),
                                      no_retention=bool(rc["no_retention"].get("exact_on_final")),
                                      V_admitted=bool(v.get("admitted")), S_fresh_cpu_physical_s=rc["fixed_library_B"]["cpu_s"],
                                      no_retention_cpu_physical_s=rc["no_retention"]["cpu_s"]))

    def late_gate(self):
        """Flags only (never used to change anything): do trivial repairs pass on the admission and final evidence?"""
        out = {}
        try:
            a = self.adm
            out["admission_generator_acq_post"] = G.check(self.X, self.post_name["acq"], a["gen_args"], self.env_les, self.env_full, self.post_les["acq"])["ok"]
            out["admission_generator_adm_post"] = G.check(self.X, self.post_name["adm"], a["gen_args"], self.env_les, self.env_full, self.post_les["adm"])["ok"]
            if a["pool_args"]:
                out["admission_pooled_adm_post"] = G.check(self.X, self.post_name["adm"], a["pool_args"], self.env_les, self.env_full, self.post_les["adm"])["ok"]
            F = self.fin()
            out["final_acq_post"] = G.check(self.X, self.post_name["acq"], F["args"], self.env_les, self.env_full, self.post_les["acq"])["ok"]
            out["final_reuse_post"] = G.check(self.X, self.post_name["reuse"], F["args"], self.env_les, self.env_full, self.post_les["reuse"])["ok"]
        except Exception as e:                                  # noqa: BLE001
            out["error"] = type(e).__name__
        return out

    # ------------------------------------------------------------------ controls
    def behaviour(self, fn):
        sig = []
        try:
            with C.guard():
                for a in self.fin()["args"]:
                    try:
                        sig.append(dslx.canon(fn(*a)))
                    except Exception:                          # noqa: BLE001
                        sig.append("E")
        except C.GuardTimeout:
            sig.append("T")
        return hashlib.sha256("|".join(sig).encode()).hexdigest()[:16]

    def selection(self, hits, hit_adm):
        """Selection on V's candidates (measurement only): the rule (first fit, frozen), random among the first 20 fits
        (5 seeds), census of distinct behaviours. Nothing here changes the candidate of any arm."""
        recs = []
        for h, adm in zip(hits, hit_adm):
            fn = self.cand_fn(h[2])
            recs.append(dict(expr=h[0], size=h[1], admitted=adm["rule"], correct=self.exact(fn, None)["ok"],
                             reuse_exact_any=self.exact(fn, "reuse")["ok"], behaviour=self.behaviour(fn)))
        out = dict(n_fits=len(recs), fits=recs, distinct_behaviours=len({r["behaviour"] for r in recs}),
                   correct_among_fits=sum(r["correct"] for r in recs), admitted_among_fits=sum(r["admitted"] for r in recs))
        if recs:
            out["first_fit"] = dict(admitted=recs[0]["admitted"], correct=recs[0]["correct"])
            seeds = []
            for s in range(V.N_SEEDS):
                i = random.Random("%d:%s:select:%d" % (V.SEED, self.X, s)).randrange(len(recs))
                seeds.append(dict(seed=s, index=i, admitted=recs[i]["admitted"], correct=recs[i]["correct"]))
            out["random_seeds"] = seeds
        return out

    def repair_choice(self, arms):
        """Allowance 2 B: two repair methods (V: the missing call; S: a stand-in carried by its whole program), tried one
        after the other. Computed from the arm runs, each capped at B, so the total never exceeds 2 B. CPU until an
        admitted candidate (counterfactual CPU to the first fit)."""
        def method(k):
            a = arms[k]
            if k == "S":
                st = a.get("standin") or {}
                return dict(admitted=bool(st.get("admitted")), until=a.get("cpu_to_first_fit"), spent=a["cpu_s"] if not a["fit"] else a["cpu_to_first_fit"])
            return dict(admitted=bool(a.get("admitted")), until=a.get("cpu_to_first_fit"), spent=a["cpu_s"] if not a["fit"] else a["cpu_to_first_fit"])

        def cost(order):
            total = 0.0
            for k in order:
                m = method(k)
                if m["admitted"]:
                    return dict(order=order, reached=True, cpu_s=round(total + m["until"], 3))
                total += m["spent"]
            return dict(order=order, reached=False, cpu_s=round(total, 3))
        rule_order = ["V", "S"] if self.res["decision"]["localised"] else ["S", "V"]
        out = dict(allowance=2 * self.B, rule=cost(rule_order), v_then_s=cost(["V", "S"]), s_then_v=cost(["S", "V"]), random=[])
        for s in range(V.N_SEEDS):
            order = ["V", "S"] if random.Random("%d:%s:order:%d" % (V.SEED, self.X, s)).random() < .5 else ["S", "V"]
            out["random"].append(dict(seed=s, **cost(order)))
        return out

    def diagnosis(self, acq_ex):
        """EXPLORATORY. Arm S on the acquisition task with NOTHING hidden, at a tenth of B. Same signals are journalled
        for both kinds of failure; no conclusion is computed from them."""
        budget = self.B * V.DIAG_FRACTION
        ops, leaves, Y = core.build(self.X, set(), acq_ex, self.full)
        near = dict(n=0, best=0)
        base = VS.plain_accept(Y)
        cy = [dslx.canon(y) for y in Y]

        def acc(vals):
            m = sum(1 for v, c in zip(vals, cy) if dslx.canon(v) == c)
            if m >= len(Y) - 1 and m < len(Y):
                near["n"] += 1
            near["best"] = max(near["best"], m)
            return base(vals)
        r = self.safely("diag", budget, lambda: VS.search(ops, leaves, acc, len(Y), budget, V.SIZE_S, V.MAX_FN, V.MAX_BANK))
        rec = self.arm_record("diag", r, budget)
        rec.update(expr=r["found"][0] if r["found"] else None, nearly_fitting_candidates=near["n"],
                   best_examples_matched=near["best"], of=len(Y), note="exploratory; no conclusion is computed from it",
                   error_kind_when_missing=self.res["failure"]["error_type"])
        self.log("diagnosis", **rec)
        return rec


def run_target(X, outdir, B=None, hide="family"):
    """Run one target to completion; finished targets (targets/<X>.json) are skipped. Returns the result record."""
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
    except Exception as e:                                      # noqa: BLE001  infrastructure failure
        import traceback
        res = dict(ep.res, status="incomplete", reason="%s: %s" % (type(e).__name__, str(e)[:300]), trace=traceback.format_exc()[-1500:])
        j.log("incomplete", reason=res["reason"])
    tmp = final + ".tmp"
    with open(tmp, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True, default=str)
    os.replace(tmp, final)
    return res
