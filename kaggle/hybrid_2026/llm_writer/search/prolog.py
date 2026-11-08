"""The SWI-Prolog / CLP(FD) backend of the relational completion (`relational.py` defines the encoding).

Safety. Plain Prolog execution is not a sandbox, so this backend never runs text it did not build itself:
- the program is ONE trusted template (the constant TEMPLATE below: an interpreter of the restricted rule AST that
  never calls data as a goal: no call/N, no =.. followed by a call, no assert/retract, no I/O except printing
  results, no file, process, module or flag operations) followed by generated FACTS;
- the facts are printed by this module from integers and allowlisted atoms only, and the whole generated part is
  re-validated before it is written: every line must be a fact of an allowlisted predicate, the text may contain
  only lower-case letters, digits, `_ ( ) [ ] , - .`, and every atom must be allowlisted; no variables, directives,
  quotes, operators or clause bodies can appear;
- the process runs with `-f none --no-packs` (no init file, no packs), an empty working directory, a minimal
  environment, stdin closed, and kernel limits: CPU seconds, address space, no file writes (RLIMIT_FSIZE 0), no
  new processes or threads beyond its own (RLIMIT_NPROC 0), few file descriptors, no core files;
- every sketch runs under `call_with_inference_limit` (deterministic, so runs are reproducible; no alarm
  thread is needed, which RLIMIT_NPROC 0 forbids anyway), with solution caps, and the process under RLIMIT_CPU;
  recursion is bounded by the finite rule lists.
CPU is the child's own CPU (RUSAGE_CHILDREN), charged to the caller's budget by `common.cpu_now`.
"""
import os
import re
import resource
import shutil
import subprocess
import tempfile

from llm_writer.search.common import cpu_now
from llm_writer.search import relational as RL

TEMPLATE = r"""
:- use_module(library(clpfd)).
:- use_module(library(lists)).
:- use_module(library(apply)).
:- dynamic objects/1, fate/3, col1/3, ocol/3, pick/3, feat/4, rel/4, afate/4, uncovered/2, dom/2, sketch/2,
           limits/4, explain_job/2.

main :-
    limits(MaxSol, MaxPer, Inf, Sec),
    forall(sketch(Id, Sk), run_sketch(Id, Sk, MaxSol, MaxPer, Inf, Sec)),
    forall(explain_job(Id, P), explain(Id, P)),
    format("end.~n").

run_sketch(Id, Sk, MaxSol, MaxPer, Inf, _Sec) :-
    statistics(cputime, T0), statistics(inferences, I0),
    nb_setval(nsol, 0), nb_setval(status, complete), nb_setval(percap, 0),
    (   uncovered_any
    ->  nb_setval(status, unsat_uncovered)
    ;   catch(call_with_inference_limit(search(Id, Sk, MaxSol, MaxPer), Inf, R), E, true),
        (   nonvar(E) -> exc_status(E, S), nb_setval(status, S)
        ;   R == inference_limit_exceeded -> nb_setval(status, inference_limit)
        ;   true
        )
    ),
    statistics(cputime, T1), statistics(inferences, I1),
    T is round((T1 - T0) * 1000000), NI is I1 - I0,
    nb_getval(nsol, N), nb_getval(status, St), nb_getval(percap, PC),
    format("done(~w,~w,~w,~w,~w,~w).~n", [Id, St, N, PC, T, NI]).

exc_status(time_limit_exceeded, time_limit) :- !.
exc_status(_, error).

uncovered_any :- uncovered(_, N), N > 0, !.

search(Id, Sk, MaxSol, MaxPer) :-
    catch(search_all(Id, Sk, MaxSol, MaxPer), cap, nb_setval(status, cap)).

search_all(Id, Sk, MaxSol, MaxPer) :-
    (   structure(Sk, Prog, Vars),
        nb_setval(nper, 0),
        catch(label_struct(Id, Prog, Vars, MaxPer, MaxSol), per_cap, nb_setval(percap, 1)),
        fail
    ;   true
    ).

label_struct(Id, Prog, Vars, MaxPer, MaxSol) :-
    post(Prog),
    labeling([], Vars),
    emit(Id, Prog),
    nb_getval(nsol, N), ( N >= MaxSol -> throw(cap) ; true ),
    nb_getval(nper, P), ( P >= MaxPer -> throw(per_cap) ; true ),
    fail.
label_struct(_, _, _, _, _).

emit(Id, Prog) :-
    nb_getval(nsol, N), N1 is N + 1, nb_setval(nsol, N1),
    nb_getval(nper, P), P1 is P + 1, nb_setval(nper, P1),
    format("sol(~w,~q).~n", [Id, Prog]).

% ---------- structural choices, in domain order (holes are data: h(...) terms)
structure(sk(Rules0, Def0), prog(Rules, Def), Vars) :-
    maplist(fill_rule, Rules0, Rules),
    fill_default(Def0, Def),
    term_variables(Rules, Vars).

fill_rule(rule(S0, A0), rule(S, A)) :- fill_sel(S0, S), fill_act(A0, A).

fill_sel(h(sel), S) :- !, dom(sel, D), member(S0, D), inst_sel(S0, S).
fill_sel(S0, S) :- inst_sel(S0, S).
inst_sel(thr(F, Op, h(int, Lo, Hi)), thr(F, Op, V)) :- !, V in Lo..Hi.
inst_sel(and(A0, B0), and(A, B)) :- !, inst_sel(A0, A), inst_sel(B0, B).
inst_sel(S, S).

fill_act(h(act), A) :- !, dom(act, D), member(A0, D), inst_act(A0, A).
fill_act(A0, A) :- inst_act(A0, A).
inst_act(recolor(h(colour)), recolor(C)) :- !, C in 0..9.
inst_act(translate(h(vec, R)), translate(DR, DC)) :- !, NR is -R, DR in NR..R, DC in NR..R, (DR #\= 0 #\/ DC #\= 0).
inst_act(fmap(F, h(table, F, Keys)), fmap(F, Pairs)) :- !, maplist(key_var, Keys, Pairs).
inst_act(cmap(h(table, color, Keys)), cmap(Pairs)) :- !, maplist(key_var, Keys, Pairs).
inst_act(A, A).
key_var(K, kc(K, C)) :- C in 0..9.

fill_default(h(default), D) :- !, member(D, [keep, delete]).
fill_default(D, D).

% ---------- first-match semantics, reified per object
post(prog(Rules, Def)) :- objects(L), maplist(post_obj(Rules, Def), L).

post_obj(Rules, Def, D-O) :- fate(D, O, F), post_rules(Rules, Def, D, O, F, 1).

% ground cases are checked directly (no reified constraint is posted); CLP(FD) reification only when an earlier
% selector or this selector depends on an integer variable (a threshold)
post_rules([], Def, D, O, F, Prev) :-
    (   Prev == 0 -> true
    ;   Prev == 1 -> ok_true(Def, D, O, F)
    ;   ok(Def, D, O, F, Ok), Prev #==> Ok
    ).
post_rules([rule(S, A)|Rs], Def, D, O, F, Prev) :-
    (   Prev == 0 -> Next = 0
    ;   sel_b(S, D, O, B),
        (   B == 0 -> Next = Prev
        ;   Prev == 1, B == 1 -> ok_true(A, D, O, F), Next = 0
        ;   ok(A, D, O, F, Ok),
            (Prev #/\ B) #==> Ok,
            Next #<==> (Prev #/\ #\ B)
        )
    ),
    post_rules(Rs, Def, D, O, F, Next).

% the action must explain the observed fate (non-reified)
ok_true(_, _, _, other) :- !, fail.
ok_true(keep, _, _, F) :- !, F == unchanged.
ok_true(delete, _, _, F) :- !, F == deleted.
ok_true(recolor(C), D, O, F) :- !,
    (   F = recoloured(C0) -> C #= C0
    ;   F == unchanged, col1(D, O, K) -> C #= K
    ).
ok_true(translate(DR, DC), _, _, F) :- !, F = moved(V1, V2), DR #= V1, DC #= V2.
ok_true(a(J), D, O, F) :- !, afate(J, D, O, F0), F0 == F.
ok_true(fmap(G, Pairs), D, O, F) :- !, feat(G, D, O, X), memberchk(kc(X, C), Pairs), ok_true(recolor(C), D, O, F).
ok_true(cmap(Pairs), D, O, F) :- !, ocol(D, O, K), memberchk(kc(K, C), Pairs), ok_true(recolor(C), D, O, F).

sel_b(true, _, _, 1).
sel_b(s(I), D, O, B) :- ( pick(I, D, O) -> B = 1 ; B = 0 ).
sel_b(and(X, Y), D, O, B) :- sel_b(X, D, O, BX), sel_b(Y, D, O, BY), B #<==> (BX #/\ BY).
sel_b(thr(F, Op, V), D, O, B) :- ( feat(F, D, O, X) -> cmp_b(Op, X, V, B) ; B = 0 ).
sel_b(ex(R, A), D, O, B) :- ( rel(R, D, O, O2), O2 \== O, sel_b(A, D, O2, 1) -> B = 1 ; B = 0 ).

cmp_b(ge, X, V, B) :- B #<==> (X #>= V).
cmp_b(le, X, V, B) :- B #<==> (X #=< V).

ok(_, _, _, other, 0) :- !.
ok(keep, _, _, F, Ok) :- !, ( F == unchanged -> Ok = 1 ; Ok = 0 ).
ok(delete, _, _, F, Ok) :- !, ( F == deleted -> Ok = 1 ; Ok = 0 ).
ok(recolor(C), D, O, F, Ok) :- !,
    (   F = recoloured(C0) -> Ok #<==> (C #= C0)
    ;   F == unchanged, col1(D, O, K) -> Ok #<==> (C #= K)
    ;   Ok = 0
    ).
ok(translate(DR, DC), _, _, F, Ok) :- !,
    ( F = moved(V1, V2) -> Ok #<==> (DR #= V1 #/\ DC #= V2) ; Ok = 0 ).
ok(a(J), D, O, F, Ok) :- !, ( afate(J, D, O, F0), F0 == F -> Ok = 1 ; Ok = 0 ).
ok(fmap(G, Pairs), D, O, F, Ok) :- !,
    ( feat(G, D, O, X), memberchk(kc(X, C), Pairs) -> ok(recolor(C), D, O, F, Ok) ; Ok = 0 ).
ok(cmap(Pairs), D, O, F, Ok) :- !,
    ( ocol(D, O, K), memberchk(kc(K, C), Pairs) -> ok(recolor(C), D, O, F, Ok) ; Ok = 0 ).
ok(_, _, _, _, 0).

% ---------- derivation traces of ground programs: tr(Id, Demo, Object, Fate, Rule, Ok)
explain(Id, prog(Rules, Def)) :-
    objects(L),
    forall(member(D-O, L), explain_obj(Id, Rules, Def, D, O)).

explain_obj(Id, Rules, Def, D, O) :-
    fate(D, O, F),
    first_fire(Rules, D, O, 1, K, A),
    ( K == 0 -> A1 = Def ; A1 = A ),
    ok(A1, D, O, F, Ok),
    format("tr(~w,~w,~w,~q,~w,~w).~n", [Id, D, O, F, K, Ok]).

first_fire([], _, _, _, 0, none).
first_fire([rule(S, A)|Rs], D, O, I, K, Act) :-
    sel_b(S, D, O, B),
    ( B == 1 -> K = I, Act = A ; I1 is I + 1, first_fire(Rs, D, O, I1, K, Act) ).
"""

FACT_NAMES = ("objects", "fate", "col1", "ocol", "pick", "feat", "rel", "afate", "uncovered", "dom", "sketch", "limits",
              "explain_job")
FUNCTORS = {"unchanged", "deleted", "recoloured", "moved", "other", "s", "and", "thr", "ex", "true", "keep",
            "delete", "recolor", "translate", "a", "h", "sel", "act", "colour", "vec", "int", "default", "rule", "sk",
            "prog", "ge", "le", "none", "fmap", "cmap", "kc", "table", "color", "ocol"}
_SAFE_TEXT = re.compile(r"^[a-z0-9_(),\[\]\-.\n]*$")
_ATOM = re.compile(r"[a-z][a-z0-9_]*")


def swipl_path():
    p = os.environ.get("CORA_SWIPL")
    if p and os.path.exists(p):
        return p
    venv = os.path.expanduser("swipl")
    if os.path.exists(venv):
        return venv
    return shutil.which("swipl")


# ------------------------------------------------------------------ terms
def term(x):
    """Prolog text of a rule-AST value (Python tuples/lists/ints/allowlisted atoms)."""
    if isinstance(x, bool):
        raise ValueError("booleans are not part of the encoding")
    if isinstance(x, int):
        return str(int(x))
    if isinstance(x, str):
        if not _ATOM.fullmatch(x):
            raise ValueError(f"not an atom: {x!r}")
        return x
    if isinstance(x, list):
        return "[" + ",".join(term(y) for y in x) + "]"
    if isinstance(x, tuple):
        head = x[0]
        if head in ("fmap", "cmap") and isinstance(x[-1], tuple) and x[-1] and isinstance(x[-1][0], tuple):
            pairs = "[" + ",".join(f"kc({int(k)},{int(c)})" for k, c in x[-1]) + "]"
            return f"{head}(" + ",".join([term(y) for y in x[1:-1]] + [pairs]) + ")"
        if head == "h" and len(x) == 4 and x[1] == "table":
            return f"h(table,{term(x[2])},[" + ",".join(str(int(k)) for k in x[3]) + "])"
        if head == "h":
            return "h(" + ",".join(term(y) for y in x[1:]) + ")" if len(x) > 2 else f"h({x[1]})"
        if len(x) == 1:
            return term(head)
        return f"{term(head)}(" + ",".join(term(y) for y in x[1:]) + ")"
    raise ValueError(f"cannot encode {x!r}")


def _hole(x):
    """Rule-AST holes as Prolog data: ("h","sel","SEL") -> h(sel) (the domain is the dom/2 fact)."""
    if isinstance(x, tuple):
        if len(x) >= 2 and x[0] == "h":
            if x[1] in ("sel", "act"):
                return ("h", x[1])
            return x
        return tuple(_hole(y) for y in x)
    if isinstance(x, list):
        return [_hole(y) for y in x]
    return x


def fate_term(f):
    if f[0] == "recoloured":
        return f"recoloured({int(f[1])})"
    if f[0] == "moved":
        return f"moved({int(f[1])},{int(f[2])})"
    return f[0]


def facts_text(facts, sketches, limits, explain=()):
    """The generated part of the program: facts of the observations, the domains, the sketches and the limits."""
    L = []
    L.append("objects([" + ",".join(f"{d}-{o}" for d, o in facts.object_list()) + "]).")
    for d in range(facts.n_demos):
        for o, f in enumerate(facts.fates[d]):
            L.append(f"fate({d},{o},{fate_term(f)}).")
    for d in range(facts.n_demos):
        for o in range(len(facts.fates[d])):
            if facts.col1[d][o] is not None:
                L.append(f"col1({d},{o},{int(facts.col1[d][o])}).")
    for d in range(facts.n_demos):
        for o, c in enumerate(facts.ocolor[d]):
            L.append(f"ocol({d},{o},{int(c)}).")
    for d in range(facts.n_demos):
        L.append(f"uncovered({d},{int(facts.uncovered[d])}).")
    for i, per in enumerate(facts.picks):
        for d, objs in enumerate(per):
            for o in sorted(objs):
                L.append(f"pick({i},{d},{int(o)}).")
    for f in sorted(facts.feats):
        name = term(f)
        for d, row in enumerate(facts.feats[f]):
            for o, v in enumerate(row):
                L.append(f"feat({name},{d},{o},{int(v)}).")
    for r in sorted(facts.rels):
        name = term(r)
        for d, pairs in enumerate(facts.rels[r]):
            for a, b in sorted(pairs):
                L.append(f"rel({name},{d},{int(a)},{int(b)}).")
    for j, per in enumerate(facts.afates):
        for d, row in enumerate(per):
            for o, f in enumerate(row):
                L.append(f"afate({j},{d},{o},{fate_term(f)}).")
    doms = RL.domains(facts)
    L.append("dom(sel," + term([_hole(s) for s in doms["SEL"]]) + ").")
    L.append("dom(act," + term([_hole(a) for a in doms["ACT"]]) + ").")
    for k, sk in enumerate(sketches):
        L.append(f"sketch({k},sk(" + term(_hole(sk.rules)) + "," + term(_hole(sk.default)) + ")).")
    for k, prog in enumerate(explain):
        L.append(f"explain_job({k},prog(" + term(prog[1]) + "," + term(prog[2]) + ")).")
    max_sol, max_per, inf, sec = limits
    L.append(f"limits({int(max_sol)},{int(max_per)},{int(inf)},{int(max(1, sec))}).")
    text = "\n".join(L) + "\n"
    validate(text, facts)
    return text


def validate(text, facts=None):
    """Refuse any generated text that is not a list of allowlisted facts over integers and allowlisted atoms."""
    if not _SAFE_TEXT.match(text):
        bad = sorted(set(re.sub(r"[a-z0-9_(),\[\]\-.\n]", "", text)))
        raise ValueError(f"generated Prolog text has disallowed characters: {bad[:8]}")
    allowed = set(FUNCTORS) | set(FACT_NAMES) | set(RL.THR_FEATS) | set(RL.RELATIONS)
    if facts is not None:
        allowed |= set(facts.feats) | set(facts.rels)
    for line in text.split("\n"):
        if not line:
            continue
        m = re.match(r"([a-z][a-z0-9_]*)\(.*\)\.$", line)
        if not m or m.group(1) not in FACT_NAMES:
            raise ValueError(f"not an allowlisted fact: {line[:60]!r}")
        for a in _ATOM.findall(line):
            if a not in allowed:
                raise ValueError(f"atom {a!r} is not allowlisted")
    return True


# ------------------------------------------------------------------ output parsing (no eval)
_TOK = re.compile(r"\s*(-?\d+|[a-z][a-z0-9_]*|[\[\](),])")


def parse_term(s):
    toks, pos = [], 0
    s = s.strip()
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m:
            raise ValueError(f"cannot parse Prolog output at {s[pos:pos + 20]!r}")
        toks.append(m.group(1))
        pos = m.end()
    i = 0

    def read():
        nonlocal i
        t = toks[i]
        i += 1
        if t == "[":
            items = []
            if toks[i] == "]":
                i += 1
                return items
            while True:
                items.append(read())
                t2 = toks[i]
                i += 1
                if t2 == "]":
                    return items
                if t2 != ",":
                    raise ValueError("bad list")
        if re.fullmatch(r"-?\d+", t):
            return int(t)
        if i < len(toks) and toks[i] == "(":
            i += 1
            args = []
            while True:
                args.append(read())
                t2 = toks[i]
                i += 1
                if t2 == ")":
                    return (t,) + tuple(args)
                if t2 != ",":
                    raise ValueError("bad compound")
        return t
    out = read()
    if i != len(toks):
        raise ValueError("trailing tokens")
    return out


def _sel(x):
    if x == "true":
        return ("true",)
    if x[0] == "s":
        return ("s", x[1])
    if x[0] == "and":
        return ("and", _sel(x[1]), _sel(x[2]))
    if x[0] == "thr":
        return ("thr", x[1], x[2], x[3])
    if x[0] == "ex":
        return ("ex", x[1], _sel(x[2]))
    raise ValueError(x)


def _act(x):
    if x in ("keep", "delete"):
        return (x,)
    if x[0] == "fmap":
        return ("fmap", x[1], tuple((kc[1], kc[2]) for kc in x[2]))
    if x[0] == "cmap":
        return ("cmap", tuple((kc[1], kc[2]) for kc in x[1]))
    if x[0] == "recolor":
        return ("recolor", x[1])
    if x[0] == "translate":
        return ("translate", x[1], x[2])
    if x[0] == "a":
        return ("a", x[1])
    raise ValueError(x)


def to_rule_ast(t):
    """prog([rule(S, A), ...], Def) parsed from Prolog -> ("prog", [("rule", S, A)], Def)."""
    _, rules, default = t
    return ("prog", [("rule", _sel(r[1]), _act(r[2])) for r in rules], default)


# ------------------------------------------------------------------ running
def _limits(cpu_s, as_mb):
    def pre():
        cpu = int(cpu_s) + 2
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        resource.setrlimit(resource.RLIMIT_AS, (as_mb << 20, as_mb << 20))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        os.setsid()
    return pre


def run_program(facts_part, cpu_s=10.0, as_mb=2048):
    """Run TEMPLATE + facts in a fresh SWI-Prolog process under the limits; (stdout lines, stderr tail, cpu)."""
    exe = swipl_path()
    if exe is None:
        raise FileNotFoundError("SWI-Prolog (swipl) not found")
    validate(facts_part)
    t0 = cpu_now()
    with tempfile.TemporaryDirectory(prefix="cora_pl_") as d:
        path = os.path.join(d, "job.pl")
        with open(path, "w") as f:
            f.write(TEMPLATE)
            f.write(facts_part)
        argv = [exe, "-q", "-f", "none", "--no-packs", "--on-error=halt", "--stack-limit=512m",
                "-g", "main", "-t", "halt", path]
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": d}
        try:
            cp = subprocess.run(argv, cwd=d, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=max(30.0, 6 * cpu_s), preexec_fn=_limits(cpu_s, as_mb))
            out, err, code = cp.stdout.decode("utf-8", "replace"), cp.stderr.decode("utf-8", "replace"), cp.returncode
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode("utf-8", "replace")
            err, code = "wall-clock backstop", -9
    return out.splitlines(), err[-400:], code, cpu_now() - t0


def solve(facts, sketches, max_sol=32, max_per=8, cpu_s=10.0, inferences=None, explain=()):
    """Solve every sketch in one SWI-Prolog process. Returns ([relational.Completion per sketch], traces, info).
    `cpu_s` is the time limit per sketch inside Prolog and, times the number of sketches, the process CPU cap."""
    inf = int(inferences or 40_000_000 * max(1.0, cpu_s))
    n = max(1, len(sketches) + (1 if explain else 0))
    text = facts_text(facts, sketches, (max_sol, max_per, inf, cpu_s), explain)
    lines, err, code, cpu = run_program(text, cpu_s=cpu_s * n + 2, as_mb=2048)
    sols = {k: [] for k in range(len(sketches))}
    done, traces = {}, {}
    bad = 0
    for ln in lines:
        ln = ln.strip()
        if not ln.endswith("."):
            continue
        try:
            t = parse_term(ln[:-1])
        except (ValueError, IndexError):
            bad += 1
            continue
        if isinstance(t, tuple) and t[0] == "sol":
            sols[t[1]].append(to_rule_ast(t[2]))
        elif isinstance(t, tuple) and t[0] == "done":
            done[t[1]] = t
        elif isinstance(t, tuple) and t[0] == "tr":
            traces.setdefault(t[1], []).append(t[2:])
    truncated = facts.sel_truncated or facts.act_truncated
    out = []
    for k, sk in enumerate(sketches):
        d = done.get(k)
        if d is None:
            out.append(RL.Completion("EXECUTION_ERROR", "prolog", sols[k], False,
                                     f"no result line (exit {code}): {err[-160:]}", 0.0))
            continue
        status, percap, t = d[2], d[4], d[5] / 1e6
        infer = d[6] if len(d) > 6 else None
        s = sols[k]
        if status == "unsat_uncovered":
            c = RL.Completion("PROVED_UNSAT_IN_ENCODING", "prolog", [], True, "uncovered changes", t)
        elif status == "complete":
            if s:
                c = RL.Completion("FIT_FOUND", "prolog", s, percap == 0, "per-structure cap" if percap else "", t)
            else:
                c = RL.Completion("NO_FIT_IN_ENUMERATED_DOMAIN" if truncated else "PROVED_UNSAT_IN_ENCODING",
                                  "prolog", [], True, "domain exhausted", t)
        elif status == "cap":
            c = RL.Completion("FIT_FOUND", "prolog", s, False, "solution cap", t)
        elif status in ("inference_limit", "time_limit"):
            c = RL.Completion("FIT_FOUND" if s else "BUDGET_EXHAUSTED", "prolog", s, False, status, t)
        else:
            c = RL.Completion("EXECUTION_ERROR", "prolog", s, False, f"prolog status {status}", t)
        out.append(c)
    info = {"cpu_s": round(cpu, 4), "exit": code, "stderr": err[-200:] if code else "", "unparsed": bad,
            "lines": len(lines)}
    return out, traces, info
