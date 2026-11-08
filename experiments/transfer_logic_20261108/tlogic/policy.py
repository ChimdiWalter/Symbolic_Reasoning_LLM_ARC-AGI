"""Access-control and firewall policies, synthetic from real seeds (ClassBench parameter files).

Header space: 12 bits. src address 3 bits (inputs 0-2, most significant first), dst address 3 bits (3-5), protocol
code 2 bits (6-7: TCP 0, UDP 1, ICMP 2, other 3), source-port code 2 bits (8-9) and destination-port code 2 bits
(10-11), port codes 0 [0,511], 1 [512,1023], 2 [1024,49151], 3 [49152,65535].
Field tests: address prefixes of length 0-3; protocol wildcard or one code; port-code intervals [lo, hi].
A rule is one test per field (wildcards allowed); its arity is its number of non-wildcard fields. A policy is a
first-match list of (rule, action) with default deny (0).

Generator (a simplified re-implementation, not ClassBench's db_generator): per rule, the protocol and port-pair class
are drawn from the seed's protocol section, arbitrary ranges and exact ports from its port sections, and the (source,
destination) prefix-length pair from the seed's section for that port-pair class; lengths are reduced to one header
bit per octet (min(3, length // 8)); prefix bits are uniform; the action is permit with probability one half.

Decision-list learning (Rivest's greedy scheme): repeatedly add the pure rule (all covered remaining probes share one
label) that covers the most remaining probes (ties: fewer fields, then canonical order); the default is the label of
the remaining probes.
- static: single-field rules only; no fit means no program;
- grown: when no pure rule of the current arity exists, the failure description names the field implicated by the
  closest conflicting probe pairs (fewest differing fields), and the missing piece is the best pure rule of the next
  arity that tests that field; the language keeps the larger arity afterwards;
- shuffled: the named field is replaced by a seeded random permutation of the fields;
- full: every arity allowed from the start (the standard greedy decision-list learner; a reference).
"""
import hashlib
import random

from .core import masks

N_IN = 12
FIELDS = (("src", (0, 1, 2), "prefix"), ("dst", (3, 4, 5), "prefix"), ("proto", (6, 7), "code"),
          ("sport", (8, 9), "range"), ("dport", (10, 11), "range"))
PPC = ("wc_wc", "wc_hi", "hi_wc", "hi_hi", "wc_lo", "lo_wc", "hi_lo", "lo_hi", "lo_lo", "wc_ar", "ar_wc", "hi_ar",
       "ar_hi", "lo_ar", "ar_lo", "ar_ar", "wc_em", "em_wc", "hi_em", "em_hi", "lo_em", "em_lo", "ar_em", "em_ar",
       "em_em")
PROTO_CODE = {6: 0, 17: 1, 1: 2}


def port_code(p):
    return 0 if p <= 511 else 1 if p <= 1023 else 2 if p <= 49151 else 3


def _value_mask(vars_, value):
    full, V, NV, _ = masks(N_IN)
    m = full
    for k, v in enumerate(vars_):
        m &= V[v] if (value >> (len(vars_) - 1 - k)) & 1 else NV[v]
    return m


def _build_tests():
    """Per field: list of (test, mask), non-wildcard tests only, canonical order."""
    out = []
    for name, vars_, kind in FIELDS:
        tests = []
        if kind == "prefix":
            for l in range(1, 4):
                for p in range(1 << l):
                    tests.append(((l, p), _value_mask(vars_[:l], p)))
        elif kind == "code":
            for c in range(4):
                tests.append((c, _value_mask(vars_, c)))
        else:
            for lo in range(4):
                for hi in range(lo, 4):
                    if (lo, hi) != (0, 3):
                        m = 0
                        for c in range(lo, hi + 1):
                            m |= _value_mask(vars_, c)
                        tests.append(((lo, hi), m))
        out.append(tests)
    return out


_TESTS = None


def tests():
    global _TESTS
    if _TESTS is None:
        _TESTS = _build_tests()
    return _TESTS


def rule_mask(rule):
    """rule: tuple of five tests, None meaning wildcard."""
    full = masks(N_IN)[0]
    m = full
    for f, t in enumerate(rule):
        if t is not None:
            m &= dict(tests()[f])[t]
    return m


def evaluate(rules, default=0):
    """Truth table of a first-match list [(rule, action)]."""
    full = masks(N_IN)[0]
    rem, out = full, 0
    for rule, act in rules:
        m = rule_mask(rule) & rem
        if act:
            out |= m
        rem &= ~m
    return out | (rem if default else 0)


# ---------- seeds and generator ----------

def parse_seed(text):
    sec, cur = {}, None
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("-") and not s[1:2].isdigit():
            cur = s[1:]
            sec[cur] = []
        elif s == "#":
            cur = None
        elif cur is not None:
            sec[cur].append(s)
    return sec


def _choice(rng, pairs):
    tot = sum(p for _, p in pairs)
    if tot <= 0:
        return None
    r = rng.random() * tot
    for x, p in pairs:
        r -= p
        if r < 0:
            return x
    return pairs[-1][0]


def _ports(sec, name):
    out = []
    for s in sec.get(name, []):
        p, rng_ = s.split()
        lo, hi = rng_.split(":")
        out.append(((int(lo), int(hi)), float(p)))
    return out


def gen_rule(sec, rng):
    prots = []
    for s in sec.get("prots", []):
        f = s.split()
        prots.append(((int(f[0]), [float(x) for x in f[2:]]), float(f[1])))
    proto, ppc_p = _choice(rng, prots) or (0, [1.0] + [0.0] * 24)
    ppc = _choice(rng, list(zip(range(25), ppc_p[:25]))) or 0
    s_cls, d_cls = PPC[ppc].split("_")

    def port(cls, ar, em):
        if cls == "hi":
            return (2, 3)
        if cls == "lo":
            return (0, 1)
        pool = _ports(sec, ar if cls == "ar" else em) if cls in ("ar", "em") else []
        r = _choice(rng, pool) if pool else None
        if r is None:
            return None
        lo, hi = port_code(r[0]), port_code(r[1])
        return None if (lo, hi) == (0, 3) else (lo, hi)

    sport = port(s_cls, "spar", "spem")
    dport = port(d_cls, "dpar", "dpem")
    lens = []
    for s in sec.get(PPC[ppc], []):
        f = s.split()
        tot, p = f[0].split(",")
        cond = [(int(a), float(b)) for a, b in (x.split(",") for x in f[1:])]
        lens.append(((int(tot), cond), float(p)))
    tl = _choice(rng, lens)
    if tl is None:
        sl = dl = 0
    else:
        sl = _choice(rng, tl[1]) or 0
        dl = tl[0] - sl
    sl, dl = min(3, sl // 8), min(3, dl // 8)
    src = (sl, rng.getrandbits(sl)) if sl else None
    dst = (dl, rng.getrandbits(dl)) if dl else None
    pc = None if proto == 0 else PROTO_CODE.get(proto, 3)
    return (src, dst, pc, sport, dport), int(rng.random() < 0.5)


def gen_policy(sec, stream, m_min, m_max):
    rng = random.Random(int.from_bytes(hashlib.sha256(stream.encode()).digest()[:8], "big"))
    m = rng.randint(m_min, m_max)
    return [gen_rule(sec, rng) for _ in range(m)]


def items(seed_texts, stream, per_seed, m_min, m_max, exclude=frozenset()):
    """per_seed policies per seed file; constant and repeated functions (or functions in exclude) are skipped."""
    full = masks(N_IN)[0]
    out, account, seen = [], [], set(exclude)
    for name in sorted(seed_texts):
        sec = parse_seed(seed_texts[name])
        made, tries = 0, 0
        while made < per_seed and tries < 20 * per_seed:
            sid = f"{stream}|{name}|{tries}"
            tries += 1
            rules = gen_policy(sec, sid, m_min, m_max)
            T = evaluate(rules)
            if T in (0, full):
                account.append({"stream_id": sid, "excluded": "constant"})
                continue
            if T in seen:
                account.append({"stream_id": sid, "excluded": "repeated function"})
                continue
            seen.add(T)
            iid = "policy/" + hashlib.sha256(sid.encode()).hexdigest()[:16]
            out.append({"id": iid, "domain": "policy", "cluster": "seed/" + name, "n": N_IN, "T": T,
                        "rules": len(rules), "stream_id": sid, "ones": T.bit_count()})
            made += 1
    return out, account


# ---------- decision-list learning ----------

def _bits(x):
    out = []
    while x:
        low = x & -x
        out.append(low.bit_length() - 1)
        x ^= low
    return out


FIELD_BITS = tuple(sum(1 << v for v in vars_) for _, vars_, _ in FIELDS)


def describe_failure(O, Z):
    """Fields implicated by the closest conflicting probe pairs (fewest differing fields)."""
    best, counts = 99, [0] * 5
    zs = _bits(Z)
    for o in _bits(O):
        for z in zs:
            x = o ^ z
            diff = [f for f in range(5) if x & FIELD_BITS[f]]
            d = len(diff)
            if d < best:
                best, counts = d, [0] * 5
            if d == best:
                for f in diff:
                    counts[f] += 1
    return counts, best


def best_rule(O, Z, kmax, need=None, allowed=(0, 1, 2, 3, 4)):
    """Pure rule with the most covered remaining probes (ties: fewer fields, canonical order).

    Only fields in allowed may be tested; when need is given the rule must test that field."""
    T = tests()
    full = masks(N_IN)[0]
    best = [0, 99, None, None]          # coverage, arity, rule, label

    def dfs(f, mask, arity, chosen):
        o, z = O & mask, Z & mask
        cov = (o | z).bit_count()
        if cov == 0 or cov < best[0] or (cov == best[0] and arity >= best[1]):
            return
        if (not o or not z) and arity > 0 and (need is None or chosen[need] is not None):
            best[:] = [cov, arity, tuple(chosen), 1 if o else 0]
            return
        if f == 5 or arity == kmax:
            return
        for g in range(f, 5):
            if g not in allowed:
                continue
            for t, m in T[g]:
                chosen[g] = t
                dfs(g + 1, mask & m, arity + 1, chosen)
                chosen[g] = None
            if need is not None and g == need:
                break                   # the needed field may not be left as a wildcard

    dfs(0, full, 0, [None] * 5)
    return None if best[2] is None else (best[2], best[3])


def _key_rng(key, step):
    return random.Random(int.from_bytes(hashlib.sha256(f"shuffled|{key}|{step}".encode()).digest()[:8], "big"))


def learn_templates(O, Z, mode, key, max_rules=512):
    """Template growth (development version 2). The library starts with the five single-field templates. When no
    pure rule fits any template, the failure description names a field (shuffled: a seeded permutation of it), and
    the missing piece is the best pure rule over the fewest fields that include it; its field set joins the library
    as a new template. Returns (rules or None, default, status, number of templates)."""
    lib = [(f,) for f in range(5)]
    rules, step = [], 0
    o, z = O, Z
    while o and z:
        if len(rules) >= max_rules:
            return None, 0, "EXHAUSTED", len(lib)
        best = None
        for tpl in lib:
            r = best_rule(o, z, len(tpl), allowed=tpl)
            if r is not None:
                cov = (rule_mask(r[0]) & (o | z)).bit_count()
                ar = sum(t is not None for t in r[0])
                if best is None or (cov, -ar) > best[0]:
                    best = ((cov, -ar), r)
        r = None if best is None else best[1]
        if r is None:
            counts, _ = describe_failure(o, z)
            f = min(range(5), key=lambda g: (-counts[g], g))
            if mode == "shuffled":
                perm = list(range(5))
                _key_rng(key, step).shuffle(perm)
                f = perm[f]
            elif mode != "grown":
                raise ValueError(mode)
            for k2 in range(2, 6):
                r = best_rule(o, z, k2, need=f)
                if r is not None:
                    break
            if r is None:
                return None, 0, "NO_FIT_IN_LANGUAGE", len(lib)
            tpl = tuple(g for g in range(5) if r[0][g] is not None)
            if tpl not in lib:
                lib.append(tpl)
        rule, lab = r
        m = rule_mask(rule)
        rules.append((rule, lab))
        o &= ~m
        z &= ~m
        step += 1
    default = 1 if o else 0 if z else (1 if O.bit_count() > Z.bit_count() else 0)
    return rules, default, "FIT", len(lib)


def learn(O, Z, mode, key, max_rules=512):
    """Arity growth (development version 1; modes static, grown_arity, shuffled_arity, full); grown and shuffled
    use template growth. Returns (rules or None, default, status, final arity or template count)."""
    if mode in ("grown", "shuffled"):
        return learn_templates(O, Z, mode, key, max_rules)
    mode = {"grown_arity": "grown", "shuffled_arity": "shuffled"}.get(mode, mode)
    k = 5 if mode == "full" else 1
    rules, step = [], 0
    o, z = O, Z
    while o and z:
        if len(rules) >= max_rules:
            return None, 0, "EXHAUSTED", k
        r = best_rule(o, z, k)
        if r is None:
            if mode in ("static", "full"):
                return None, 0, "NO_FIT_IN_LANGUAGE", k
            counts, _ = describe_failure(o, z)
            f = min(range(5), key=lambda g: (-counts[g], g))
            if mode == "shuffled":
                perm = list(range(5))
                _key_rng(key, step).shuffle(perm)
                f = perm[f]
            elif mode != "grown":
                raise ValueError(mode)
            for k2 in range(k + 1, 6):
                r = best_rule(o, z, k2, need=f)
                if r is not None:
                    k = k2
                    break
            if r is None:
                return None, 0, "NO_FIT_IN_LANGUAGE", k
        rule, lab = r
        m = rule_mask(rule)
        rules.append((rule, lab))
        o &= ~m
        z &= ~m
        step += 1
    default = 1 if o else 0 if z else (1 if O.bit_count() > Z.bit_count() else 0)
    return rules, default, "FIT", k
