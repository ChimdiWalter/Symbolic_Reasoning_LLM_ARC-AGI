"""A2 abstraction cycle: candidate typed definitions, rewriting, description length, proposers, controls, gate.

A definition is (name, arity, body, param tags): `body` is a tree over arc-dsl primitives, constants and function
leaves whose parameters are #0..#k-1 (the input grid I is always a parameter). Bodies are kept FLAT (primitives
only), so rewriting a program with a library is one optimal dynamic programme over the original tree.

Proposers (all produce candidates from S_train material only):
  compression   repeated fragments and pairwise anti-unifications of all programs (success compression; MDL greedy)
  authentic     fragments of the UNREACHED CONE of each program whose task the base search failed on: the part of
                the verified program that the search never built, cut at subprograms it did build (those become
                typed parameters), plus anti-unifications of such fragments across failed tasks
  shuffled      the same machinery with the (task -> trace) assignment permuted: task A receives task B's outcome
                and relative cone depth (marginals kept, correspondence broken)
  blind         fragments at uniformly random nodes of all programs with random cut depth (no failure information)
Control: random valid typed bodies matched to a selected library (arity, body size, parameter tags, prior cost).
Lint: no grid constants (only arc-dsl's scalar/tuple constants exist as leaves), no task-id branch (no task data
reaches a body), arity 1..3, body 3..MAX_BODY nodes, >= 2 primitive applications, root not a parameter.
"""
import collections
import itertools
import os
import random

from a2 import arcdsl as D
from a2 import bus as B

#: v2 (A2_DL=dag): description length = DAG size of each program (a shared subprogram counts once, as in the
#: original straight-line solver), utilities count each distinct subprogram once per program, and a definition must
#: be reused by >= MIN_REUSE distinct S_train programs. v1 measured inlined tree size (dominated by duplication
#: inside a few large programs).
DAG = os.environ.get("A2_DL") == "dag"
MIN_REUSE = 2 if DAG else 1
MAX_BODY = 12
MAX_ARITY = 3
MIN_PRIMS = 2


# ------------------------------------------------------------------ matching, rewriting, description length
def match(body, t, binds):
    h = body[0]
    if h[0] == "#":
        if h in binds:
            return binds[h] == t
        binds[h] = t
        return True
    if h != t[0] or len(body) != len(t):
        return False
    for b, c in zip(body[1:], t[1:]):
        if not match(b, c, binds):
            return False
    return True


def by_head(lib):
    idx = collections.defaultdict(list)
    for d in lib:
        idx[d[2][0]].append(d)
    return idx


def rewrite(t, idx, memo):
    """Optimal rewrite of `t` with the library index: (tree, cost) with cost = node count (a call is one node)."""
    r = memo.get(t)
    if r is not None:
        return r
    kids = [rewrite(c, idx, memo) for c in t[1:]]
    best = ((t[0],) + tuple(k[0] for k in kids), 1 + sum(k[1] for k in kids))
    for name, ar, body, _ in idx.get(t[0], ()):
        binds = {}
        if match(body, t, binds) and len(binds) == ar:
            args = [rewrite(binds["#%d" % i], idx, memo) for i in range(ar)]
            c = 1 + sum(a[1] for a in args)
            if c < best[1]:
                best = (("L:" + name,) + tuple(a[0] for a in args), c)
    memo[t] = best
    return best


def corpus_dl(trees, lib):
    idx, memo = by_head(lib), {}
    if DAG:
        return sum(len(set(B.subtrees(rewrite(t, idx, memo)[0]))) for t in trees)
    return sum(rewrite(t, idx, memo)[1] for t in trees)


def uses(t, out):
    if t[0].startswith("L:"):
        out[t[0][2:]] += 1
    for c in t[1:]:
        uses(c, out)
    return out


# ------------------------------------------------------------------ candidate construction
def generalize_I(body):
    """Replace the input grid by a parameter and renumber parameters in first-occurrence order."""
    order = {}

    def walk(t):
        h = t[0]
        if h == "I" or h[0] == "#":
            key = h
            if key not in order:
                order[key] = "#%d" % len(order)
            return (order[key],)
        return (h,) + tuple(walk(c) for c in t[1:])
    b = walk(body)
    return b, len(order)


def anti_unify(a, b, pairs):
    if a == b:
        return a
    if a[0] == b[0] and len(a) == len(b) and a[0][0] != "#":
        return (a[0],) + tuple(anti_unify(x, y, pairs) for x, y in zip(a[1:], b[1:]))
    key = (a, b)
    if key not in pairs:
        pairs[key] = "#p%d" % len(pairs)
    return (pairs[key],)


def canon(body):
    """Canonical candidate: I and every hole become #0.. in first-occurrence order; None if outside the limits."""
    def walk(t, order):
        h = t[0]
        if h == "I" or h[0] == "#":
            if h not in order:
                order[h] = "#%d" % len(order)
            return (order[h],)
        return (h,) + tuple(walk(c, order) for c in t[1:])
    order = {}
    b = walk(body, order)
    if not ok_shape(b, len(order)):
        return None
    return b, len(order)


def ok_shape(body, arity):
    if body[0][0] == "#" or not 1 <= arity <= MAX_ARITY:
        return False
    sz = D.size(body)
    if sz < 3 or sz > MAX_BODY:
        return False
    return sum(1 for s in B.subtrees(body) if s[0].startswith("f:") or s[0] == "@") >= MIN_PRIMS


def lint(body):
    """No grid constants, no task data, no unknown leaves (bodies are built from arc-dsl names only)."""
    for s in B.subtrees(body):
        h = s[0]
        if not (h[0] == "#" or h.startswith(("f:", "c:", "fn:")) or h == "@"):
            return False
    return True


def cut(t, reached):
    """Fragment rooted at `t`, cut at non-leaf subtrees for which `reached` is true (they become holes #xk)."""
    holes = []

    def walk(s, top):
        if not top and len(s) > 1 and reached(s):
            if s not in holes:
                holes.append(s)
            return ("#x%d" % holes.index(s),)
        if len(s) == 1:
            return s
        return (s[0],) + tuple(walk(c, False) for c in s[1:])
    return walk(t, True), {"#x%d" % i: h for i, h in enumerate(holes)}


def fragment(t, reached):
    """Canonical cone fragment rooted at t; while outside the limits, inline the smallest hole (or give up)."""
    body, hs = cut(t, reached)
    while True:
        cb = canon(body)
        if cb is not None:
            return cb
        if D.size(body) > MAX_BODY or not hs:
            return None
        name = min(hs, key=lambda k: (D.size(hs[k]), k))
        body = _inline(body, name, hs.pop(name))


def _inline(body, name, sub):
    if body[0] == name:
        return sub
    if len(body) == 1:
        return body
    return (body[0],) + tuple(_inline(c, name, sub) for c in body[1:])


def depths(t):
    d = {}

    def walk(s, k):
        if k < d.get(s, 1 << 30):
            d[s] = k
        for c in s[1:]:
            walk(c, k + 1)
    walk(t, 0)
    return d


def candidates_compression(trees, rng, pairs_per_head=150):
    """Repeated fragments (every subtree within the limits) and pairwise anti-unifications per root head."""
    occ = collections.Counter()
    by_h = collections.defaultdict(list)
    for t in trees:
        for s in set(B.subtrees(t)):
            if len(s) > 1 and D.size(s) <= MAX_BODY:
                occ[s] += 1
                by_h[s[0]].append(s)
    out = set()
    for s in occ:
        c = canon(s)
        if c:
            out.add(c)
    for h, lst in by_h.items():
        lst = sorted(set(lst))
        if len(lst) < 2:
            continue
        for _ in range(min(pairs_per_head, len(lst) * (len(lst) - 1) // 2)):
            a, b = rng.sample(lst, 2)
            c = canon(anti_unify(a, b, {}))
            if c:
                out.add(c)
    return out


def candidates_from_cones(items, rng, pairs=1500, chunk_depths=(2, 3)):
    """items: [(tree, reached-predicate)] -> fragments rooted at UNREACHED nodes, cut at reached subtrees (and, for
    large cones, also at a bounded depth below the root), plus pairwise anti-unifications across tasks."""
    frags = set()
    for t, reached in items:
        for s in set(B.subtrees(t)):
            if len(s) > 1 and not reached(s):
                c = fragment(s, reached)
                if c:
                    frags.add(c)
                ds = depths(s)
                for d in chunk_depths:
                    c = fragment(s, lambda u, _d=d, _ds=ds: reached(u) or _ds.get(u, 99) >= _d)
                    if c:
                        frags.add(c)
    out = set(frags)
    fl = sorted(frags)
    byh = collections.defaultdict(list)
    for b, a in fl:
        byh[b[0]].append(b)
    heads = [h for h, v in byh.items() if len(v) >= 2]
    for _ in range(pairs if heads else 0):
        h = rng.choice(heads)
        a, b = rng.sample(byh[h], 2)
        c = canon(anti_unify(a, b, {}))
        if c:
            out.add(c)
    return out, len(frags)


def candidates_blind(trees, rng, n_frag, pairs=1500, depth_choices=(1, 2, 3, 4)):
    """Fragments at uniformly random non-leaf nodes with a random cut depth (holes below it); no failure input."""
    nodes = [s for t in trees for s in B.subtrees(t) if len(s) > 1]
    frags = set()
    tries = 0
    while len(frags) < n_frag and tries < 50 * n_frag:
        tries += 1
        s = rng.choice(nodes)
        d = rng.choice(depth_choices)
        c = fragment(s, _depth_reached(s, d))
        if c:
            frags.add(c)
    out = set(frags)
    byh = collections.defaultdict(list)
    for b, a in sorted(frags):
        byh[b[0]].append(b)
    heads = [h for h, v in byh.items() if len(v) >= 2]
    for _ in range(pairs if heads else 0):
        h = rng.choice(heads)
        a, b = rng.sample(byh[h], 2)
        c = canon(anti_unify(a, b, {}))
        if c:
            out.add(c)
    return out


def _depth_reached(root, d):
    """Predicate: subtrees at depth >= d below `root` count as reached (become holes)."""
    ds = depths(root)
    return lambda s: ds.get(s, 99) >= d


# ------------------------------------------------------------------ utility on a corpus
def utility(body, arity, idx_nodes):
    """Stitch-style utility: sum over matching occurrences of (occurrence size - call size) - body size."""
    sz = D.size(body)
    gain, progs = 0, set()
    for pid, s, mult, ssz in idx_nodes.get(body[0], ()):
        if ssz < sz:
            continue
        binds = {}
        if match(body, s, binds) and len(binds) == arity:
            g = ssz - 1 - sum(D.size(v) for v in binds.values())
            if g > 0:
                gain += g * mult
                progs.add(pid)
    return gain - sz, len(progs)


def node_index(trees):
    """head -> [(program id, distinct subtree, occurrences in that program, size)]."""
    idx = collections.defaultdict(list)
    for pid, t in enumerate(trees):
        cnt = collections.Counter(s for s in B.subtrees(t) if len(s) > 1)
        for s, m in cnt.items():
            idx[s[0]].append((pid, s, 1 if DAG else m, D.size(s)))
    return idx


def heldout_savings(body, arity, trees):
    """Description-length reduction of held-out programs with this one definition (optimal rewrite)."""
    lib = [("c", arity, body, None)]
    idx = by_head(lib)
    tot, nprog = 0, 0
    for t in trees:
        base = D.size(t)
        new = rewrite(t, idx, {})[1]
        if new < base:
            tot += base - new
            nprog += 1
    return tot, nprog


# ------------------------------------------------------------------ parameter types from verified executions
def param_tags(body, arity, trees, xs_of, ev, max_inst=6):
    """Runtime tags of each parameter at matching occurrences in verified programs (S_train inputs only)."""
    tags = [set() for _ in range(arity)]
    n = 0
    for pid, t in enumerate(trees):
        for s in set(B.subtrees(t)):
            binds = {}
            if s[0] == body[0] and match(body, s, binds) and len(binds) == arity:
                for k in range(arity):
                    sub = binds["#%d" % k]
                    try:
                        v = ev.run(sub, xs_of[pid][0])
                    except Exception:                               # noqa: BLE001
                        continue
                    tags[k].add(D.tag(v))
                n += 1
                if n >= max_inst:
                    return tags
    return tags


def exec_check(body, arity, ptags, probes, fns, consts, need=2):
    """The body executes as defined on probe arguments of its parameter types (S_train values)."""
    f = B.compile_tree(body, fns, consts, {})
    ok = 0
    for args in probes(ptags, arity):
        try:
            v = f(tuple(args))
        except Exception:                                           # noqa: BLE001
            continue
        if D.valid(v) and v is not None:
            ok += 1
            if ok >= need:
                return True
    return False


# ------------------------------------------------------------------ random valid control bodies
def random_body(rng, prims, sigs, fn_leaves, const_names, consts, ptags, target_size, tries=400):
    """A random type-plausible tree of about `target_size` nodes using parameters #0..#k-1 (each at least once)."""
    arity = len(ptags)
    for _ in range(tries):
        params = list(range(arity))
        t = _grow(rng, prims, sigs, fn_leaves, const_names, consts, ptags, target_size, params)
        if t is None:
            continue
        c = canon_keep(t, arity)
        if c is not None and abs(D.size(c) - target_size) <= 1:
            return c
    return None


def canon_keep(t, arity):
    used = {s[0] for s in B.subtrees(t) if s[0][0] == "#"}
    if used != {"#%d" % i for i in range(arity)}:
        return None
    return t if ok_shape(t, arity) else None


def _grow(rng, prims, sigs, fn_leaves, const_names, consts, ptags, budget, params):
    def leaf(tags):
        opts = []
        for k, pt in enumerate(ptags):
            if set(pt) & tags:
                opts.append(("#%d" % k,))
        if "F" in tags:
            opts += [(h,) for h in rng.sample(fn_leaves, min(6, len(fn_leaves)))]
        for c in rng.sample(const_names, min(8, len(const_names))):
            if D.tag(consts[c]) in tags:
                opts.append(("c:" + c,))
        return rng.choice(opts) if opts else None

    def grow(tags, room):
        if room <= 1 or rng.random() < 0.25:
            lf = leaf(tags)
            if lf is not None:
                return lf
        cands = [p for p in prims if len(sigs[p]) <= room - 1]
        rng.shuffle(cands)
        for p in cands[:20]:
            ats = [D.arg_tags(a) for a in sigs[p]]
            kids, left = [], room - 1
            ok = True
            for i, at in enumerate(ats):
                share = max(1, left // (len(ats) - i))
                k = grow(set(at), share)
                if k is None:
                    ok = False
                    break
                kids.append(k)
                left -= D.size(k)
            if ok:
                return ("f:" + p,) + tuple(kids)
        return leaf(tags)
    root_tags = set(D.CONT) | {"I", "B", "G"}
    t = grow(root_tags, budget)
    if t is None or len(t) == 1:
        return None
    # make sure every parameter is used: substitute unused ones for compatible leaves
    used = {s[0] for s in B.subtrees(t)}
    for k in range(len(ptags)):
        if "#%d" % k not in used:
            t = _replace_first_leaf(t, ("#%d" % k,), ptags[k], consts)
    return t


def _replace_first_leaf(t, new, tags, consts):
    done = [False]

    def walk(s):
        if done[0]:
            return s
        if len(s) == 1 and s[0].startswith("c:") and D.tag(consts[s[0][2:]]) in tags:
            done[0] = True
            return new
        if len(s) == 1:
            return s
        return (s[0],) + tuple(walk(c) for c in s[1:])
    return walk(t)
