"""The four arms of T3 and the loop.

Loop (the adapter's version of propose, check, describe, build, check, keep):
1. propose: the best rule of the static library on the k examples;
2. check: exact canonical product, and only that product, on each of the k examples;
3. describe: on failure, the reaction centre of each example (atoms whose bonds, charge or hydrogens change,
   bonds broken to atoms that leave, atoms added from a co-substrate);
4. build: a rule from the observed centre, at the fixed specificity levels L0 (centre atoms, element only)
   to L6 (radius 2, full atom features); at each level the first single example rule that passes every
   check example is taken, else the union of the example rules if the union passes;
5. check again: the built piece must reproduce all k examples exactly;
6. keep: the level with the most leave-one-out exact predictions is chosen (ties: config level_tie_break),
   and the piece is kept only if that leave-one-out count beats the static rule's exact count on the k.

Arms: static (steps 1 and 2 only), grown (all steps), shuffled (as grown, but step 4 builds from another
family's examples), nearest neighbour (classical reference: the rule of the most similar example).
"""
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from .chem import _key, apply_rule, check_exact, composition, describe_centre, extract_rule, reaction_centre, scan_static

_FPGEN = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


class Family:
    """Holds one family's k examples and a per-family memo of rule applications."""

    def __init__(self, fam, train):
        self.fam = fam
        self.train = train
        for e in train:
            e["mol"] = Chem.MolFromSmiles(e["sub"])
            e["comp"] = composition(e["prod_ns"])
        self.rule_cache = {}
        self.memo = {}

    def rule(self, ex, level):
        k = (ex["pair"], level)
        if k not in self.rule_cache:
            self.rule_cache[k] = extract_rule(ex["mapped_sub"], ex["mapped_prod"], level)
        return self.rule_cache[k]

    def is_exact(self, rules, ex):
        """True when the rule list gives the example's product and nothing else (memoised, early exit)."""
        hit = False
        for r in rules:
            k = (id(r), ex["pair"])
            if k not in self.memo:
                self.memo[k] = check_exact(r, ex["mol"], ex["prod_ns"], ex["comp"])
            if self.memo[k] == "other":
                return False
            hit = hit or self.memo[k] == "truth_only"
        return hit


def exact(outs, truth):
    return outs == {truth}


def static_proposal(fam, library):
    """Best library rule on the k examples: most exact, then most covering, then fewest raw products, then name."""
    best, best_key = None, None
    for r in library:
        ex = cov = nout = 0
        for e in fam.train:
            x, c, n = scan_static(r, e["mol"], e["prod_ns"], e["comp"])
            ex += x
            cov += c
            nout += n
        if cov == 0:
            continue
        key = (-ex, -cov, nout, r["name"])
        if best_key is None or key < best_key:
            best, best_key = r, key
    if best is None:
        return None, 0, 0
    return best, -best_key[0], -best_key[1]


def build(fam, build_set, check_set, level, own_rule=None):
    """Step 4 and 5: a piece from the observed change of build_set, checked on check_set."""
    cands, seen = [], set()
    for e in build_set:
        r = own_rule(e, level) if own_rule else fam.rule(e, level)
        if r is None:
            continue
        kk = _key(r)
        if kk in seen:
            continue
        seen.add(kk)
        cands.append(r)
    for r in cands:
        if all(fam.is_exact([r], c) for c in check_set):
            return [r]
    if len(cands) > 1 and all(fam.is_exact(cands, c) for c in check_set):
        return cands
    return None


def grow(fam, static_rule, static_exact, levels, tie_break, partner=None):
    """Grown arm (partner None) or shuffled arm (partner = another Family whose examples feed step 4)."""
    k = len(fam.train)
    fallback = [static_rule] if static_rule else []
    if static_exact == k:
        return {"status": "static_sufficient", "rules": fallback}
    src = partner.train if partner is not None else fam.train
    own = partner.rule if partner is not None else None
    desc = []
    for e in src:
        s, p = Chem.MolFromSmiles(e["mapped_sub"]), Chem.MolFromSmiles(e["mapped_prod"])
        desc.append(describe_centre(s, p, reaction_centre(s, p)))
    cands = []
    for L in levels:
        piece = build(fam, src, fam.train, L, own)
        if piece is None:
            continue
        loo = 0
        for i in range(k):
            rest = fam.train[:i] + fam.train[i + 1:]
            bset = rest if partner is None else src
            p = build(fam, bset, rest, L, own)
            if p and fam.is_exact(p, fam.train[i]):
                loo += 1
        cands.append((L, piece, loo))
    info = {"failure_description": desc, "levels_passing": [(c[0], c[2]) for c in cands]}
    if not cands:
        return dict(info, status="no_piece", rules=fallback)
    top = max(c[2] for c in cands)
    tied = [c for c in cands if c[2] == top]
    pick, alt = (tied[-1], tied[0]) if tie_break == "most_specific" else (tied[0], tied[-1])
    L, piece, loo = pick
    info["alt_level"] = alt[0]
    info["alt_rules"] = alt[1] if alt[2] > static_exact else fallback
    if loo > static_exact:
        return dict(info, status="piece_kept", level=L, loo=loo, n_rules=len(piece), rules=piece)
    return dict(info, status="piece_not_kept", level=L, loo=loo, rules=fallback)


def nn_predict(fam, sub_mol, level):
    """Classical reference: apply the rule of the most similar example (Morgan r2 Tanimoto); back off to the
    next most similar example when the rule does not match."""
    fp = _FPGEN.GetFingerprint(sub_mol)
    sims = []
    for i, e in enumerate(fam.train):
        if "fp" not in e:
            e["fp"] = _FPGEN.GetFingerprint(e["mol"])
        sims.append((-DataStructs.TanimotoSimilarity(fp, e["fp"]), i))
    for _, i in sorted(sims):
        r = fam.rule(fam.train[i], level)
        if r is None:
            continue
        o = apply_rule(r, sub_mol)
        if o:
            return o, i
    return set(), None
