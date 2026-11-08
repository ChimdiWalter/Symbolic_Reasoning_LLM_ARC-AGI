"""T3 chemistry adapter, molecule layer: canonical forms, the main substrate and product of a mapped
enzymatic reaction, the reaction centre, rule extraction at a fixed list of specificity levels, and rule
application with an exact canonical product check.

A rule is a single-substrate forward rule: (part of) the main substrate >> (part of) the main product.
Atoms that the main product receives from a co-substrate (water oxygen, phosphate, sugar, methyl ...) are
"added" atoms written in full in the product side. Atoms of the main substrate that do not reach the main
product are deleted, together with everything that hangs only on them.
"""
from rdkit import Chem, RDLogger
from rdkit.Chem import rdChemReactions

RDLogger.DisableLog("rdApp.*")

BOND_SMARTS = {Chem.BondType.SINGLE: "-", Chem.BondType.DOUBLE: "=", Chem.BondType.TRIPLE: "#",
               Chem.BondType.AROMATIC: ":"}

# Specificity levels, most general first. Each is (radius, centre features, context features by distance).
# Features: e = element, a = aromatic flag, c = formal charge, h = total hydrogen count, d = heavy degree,
# r = ring membership.
LEVELS = {
    "L0": (0, "ea", {}),
    "L1": (0, "each", {}),
    "L2": (0, "eachdr", {}),
    "L3": (1, "eachdr", {1: "ea"}),
    "L4": (1, "eachdr", {1: "eachdr"}),
    "L5": (2, "eachdr", {1: "eachdr", 2: "ea"}),
    "L6": (2, "eachdr", {1: "eachdr", 2: "eachdr"}),
}
LEVEL_ORDER = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]


def strip_maps(m):
    m = Chem.Mol(m)
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return m


def canon(x, stereo=False):
    """Canonical SMILES (round trip, so aromaticity and hydrogens are normalised). None if invalid."""
    try:
        m = Chem.MolFromSmiles(x) if isinstance(x, str) else strip_maps(x)
        if m is None:
            return None
        s = Chem.MolToSmiles(m, isomericSmiles=stereo)
        m2 = Chem.MolFromSmiles(s)
        return None if m2 is None else Chem.MolToSmiles(m2, isomericSmiles=stereo)
    except Exception:
        return None


def main_pair(mapped, cofactors, min_heavy=3):
    """Main product = the largest product (heavy atoms) that is not a cofactor and has >= min_heavy heavy
    atoms; main substrate = the non-cofactor reactant giving most mapped heavy atoms to it. Ties drop the
    reaction. Returns (dict, None) or (None, reason)."""
    try:
        lhs, rhs = mapped.split(">>")
    except ValueError:
        return None, "format"
    R = [Chem.MolFromSmiles(s) for s in lhs.split(".")]
    P = [Chem.MolFromSmiles(s) for s in rhs.split(".")]
    if any(m is None for m in R + P):
        return None, "parse"
    pc = []
    for i, m in enumerate(P):
        c = canon(m)
        if c is None or c in cofactors or m.GetNumHeavyAtoms() < min_heavy:
            continue
        pc.append((m.GetNumHeavyAtoms(), i, c))
    if not pc:
        return None, "no_main_product"
    pc.sort(key=lambda t: (-t[0], t[1]))
    if len(pc) > 1 and pc[0][0] == pc[1][0] and pc[0][2] != pc[1][2]:
        return None, "tied_product"
    prod = P[pc[0][1]]
    pmaps = {a.GetAtomMapNum() for a in prod.GetAtoms() if a.GetAtomMapNum() > 0}
    rc = []
    for i, m in enumerate(R):
        c = canon(m)
        if c is None or c in cofactors:
            continue
        n = sum(1 for a in m.GetAtoms() if a.GetAtomMapNum() in pmaps)
        if n > 0:
            rc.append((n, i, c))
    if not rc:
        return None, "no_main_substrate"
    rc.sort(key=lambda t: (-t[0], t[1]))
    if len(rc) > 1 and rc[0][0] == rc[1][0] and rc[0][2] != rc[1][2]:
        return None, "tied_substrate"
    sub = R[rc[0][1]]
    smaps = [a.GetAtomMapNum() for a in sub.GetAtoms()]
    if 0 in smaps or len(set(smaps)) != len(smaps):
        return None, "unmapped_substrate_atoms"
    sub_ns, prod_ns = canon(sub), canon(prod)
    if sub_ns is None or prod_ns is None:
        return None, "canon"
    if sub_ns == prod_ns:
        return None, "no_change_without_stereo"
    return {"mapped_sub": Chem.MolToSmiles(sub), "mapped_prod": Chem.MolToSmiles(prod),
            "sub": canon(sub, stereo=True), "sub_ns": sub_ns, "prod_ns": prod_ns,
            "prod_st": canon(prod, stereo=True)}, None


def _nbrs(atom, known):
    mol = atom.GetOwningMol()
    out = []
    for n in atom.GetNeighbors():
        k = n.GetAtomMapNum() if n.GetAtomMapNum() in known else -1
        out.append((k, str(mol.GetBondBetweenAtoms(atom.GetIdx(), n.GetIdx()).GetBondType())))
    return sorted(out)


def reaction_centre(sub, prod):
    """What changed. sub, prod: mapped mols. Returns dict of map sets and the per-atom edits."""
    sm = {a.GetAtomMapNum(): a for a in sub.GetAtoms()}
    pm = {a.GetAtomMapNum(): a for a in prod.GetAtoms() if a.GetAtomMapNum() > 0}
    kept = set(sm) & set(pm)
    lost = set(sm) - set(pm)
    added_idx = [a.GetIdx() for a in prod.GetAtoms() if a.GetAtomMapNum() not in sm]
    changed = set()
    for m in kept:
        a, b = sm[m], pm[m]
        if (a.GetFormalCharge() != b.GetFormalCharge() or a.GetTotalNumHs() != b.GetTotalNumHs()
                or a.GetIsAromatic() != b.GetIsAromatic() or _nbrs(a, sm) != _nbrs(b, sm)):
            changed.add(m)
    lost_boundary = {m for m in lost if any(n.GetAtomMapNum() in kept for n in sm[m].GetNeighbors())}
    edits = {m: {"dH": pm[m].GetTotalNumHs() - sm[m].GetTotalNumHs(),
                 "dC": pm[m].GetFormalCharge() - sm[m].GetFormalCharge(),
                 "arom": bool(pm[m].GetIsAromatic())} for m in changed}
    return {"kept": kept, "lost": lost, "lost_boundary": lost_boundary, "changed": changed,
            "added_idx": added_idx, "edits": edits}


def describe_centre(sub, prod, cen):
    """Plain description of the change, used as the failure description and in logs."""
    sm = {a.GetAtomMapNum(): a for a in sub.GetAtoms()}
    el = sorted(sm[m].GetSymbol() for m in cen["changed"])
    lb = sorted(sm[m].GetSymbol() for m in cen["lost_boundary"])
    added = sorted(prod.GetAtomWithIdx(i).GetSymbol() for i in cen["added_idx"])
    return {"changed_atoms": "".join(el), "bond_broken_to_lost": "".join(lb),
            "added_atoms": "".join(added), "n_lost": len(cen["lost"])}


def _atom_smarts(a, feats, mapno):
    parts = ["#%d" % a.GetAtomicNum()]
    if "a" in feats:
        parts.append("a" if a.GetIsAromatic() else "A")
    if "c" in feats:
        parts.append("%+d" % a.GetFormalCharge())
    if "h" in feats:
        parts.append("H%d" % a.GetTotalNumHs())
    if "d" in feats:
        parts.append("D%d" % a.GetDegree())
    if "r" in feats:
        parts.append("R" if a.IsInRing() else "!R")
    return "[" + ";".join(parts) + ":%d]" % mapno


def extract_rule(mapped_sub, mapped_prod, level):
    """Forward rule from one example at one specificity level. Returns a rule dict or None."""
    sub = Chem.MolFromSmiles(mapped_sub)
    prod = Chem.MolFromSmiles(mapped_prod)
    if sub is None or prod is None:
        return None
    # Amendment 2: rules carry no stereochemistry, so clear it before cutting fragments (RDKit's fragment writer
    # can fail on bond directions next to a stereo double bond that the fragment does not contain).
    for m in (sub, prod):
        for a in m.GetAtoms():
            a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
        for b in m.GetBonds():
            b.SetBondDir(Chem.BondDir.NONE)
            b.SetStereo(Chem.BondStereo.STEREONONE)
    try:
        return _extract(sub, prod, level)
    except Exception:  # any remaining RDKit failure: no rule at this level
        return None


def _extract(sub, prod, level):
    cen = reaction_centre(sub, prod)
    centre = cen["changed"] | cen["lost_boundary"]
    if not cen["changed"] and not cen["added_idx"]:
        return None
    radius, cfeat, ctx = LEVELS[level]
    m2i = {a.GetAtomMapNum(): a.GetIdx() for a in sub.GetAtoms()}
    dist = {m2i[m]: 0 for m in centre}
    frontier = list(dist)
    for d in range(1, radius + 1):
        nxt = []
        for i in frontier:
            for n in sub.GetAtomWithIdx(i).GetNeighbors():
                if n.GetIdx() not in dist:
                    dist[n.GetIdx()] = d
                    nxt.append(n.GetIdx())
        frontier = nxt
    use = sorted(dist)
    sym = [""] * sub.GetNumAtoms()
    for i in use:
        a = sub.GetAtomWithIdx(i)
        feats = cfeat if dist[i] == 0 else ctx[dist[i]]
        sym[i] = _atom_smarts(a, feats, a.GetAtomMapNum())
    bonds = [b.GetIdx() for b in sub.GetBonds() if b.GetBeginAtomIdx() in dist and b.GetEndAtomIdx() in dist]
    bsym = [BOND_SMARTS.get(b.GetBondType(), "~") for b in sub.GetBonds()]
    lhs = Chem.MolFragmentToSmiles(sub, atomsToUse=use, bondsToUse=bonds or None, atomSymbols=sym,
                                   bondSymbols=bsym, allBondsExplicit=True, isomericSmiles=False,
                                   canonical=True) if bonds else ".".join(sym[i] for i in use)
    # product side: template atoms that survive, plus every added atom (new map numbers 5000+)
    used_maps = {sub.GetAtomWithIdx(i).GetAtomMapNum() for i in use}
    keep_p = [a.GetIdx() for a in prod.GetAtoms() if a.GetAtomMapNum() in used_maps]
    added = cen["added_idx"]
    newmap = {i: 5000 + k for k, i in enumerate(added)}
    puse = sorted(set(keep_p) | set(added))
    psym = [""] * prod.GetNumAtoms()
    for i in puse:
        a = prod.GetAtomWithIdx(i)
        mp = newmap.get(i, a.GetAtomMapNum())
        psym[i] = "[#%d:%d]" % (a.GetAtomicNum(), mp)
    pset = set(puse)
    pbonds = [b.GetIdx() for b in prod.GetBonds() if b.GetBeginAtomIdx() in pset and b.GetEndAtomIdx() in pset]
    pbsym = [BOND_SMARTS.get(b.GetBondType(), "~") for b in prod.GetBonds()]
    rhs = Chem.MolFragmentToSmiles(prod, atomsToUse=puse, bondsToUse=pbonds or None, atomSymbols=psym,
                                   bondSymbols=pbsym, allBondsExplicit=True, isomericSmiles=False,
                                   canonical=True) if pbonds else ".".join(psym[i] for i in puse)
    if not keep_p:
        return None
    spec_c = {int(m): cen["edits"][m] for m in cen["changed"] if m in used_maps}
    spec_a = {}
    for i in added:
        a = prod.GetAtomWithIdx(i)
        spec_a[newmap[i]] = {"H": a.GetTotalNumHs(), "chg": a.GetFormalCharge(), "arom": bool(a.GetIsAromatic())}
    kept_maps = sorted(int(m) for m in used_maps if m in cen["kept"])
    return {"smarts": "(" + lhs + ")>>(" + rhs + ")", "mode": "delta", "centre": spec_c, "added": spec_a,
            "kept": kept_maps, "level": level}


def _key(rule):
    """Identity of a rule up to atom-map renumbering: the reactant pattern and the product pattern with the
    map numbers removed, plus the edits in a map-free form."""
    def demap(s):
        out, i = [], 0
        while i < len(s):
            if s[i] == ":" and i + 1 < len(s) and s[i + 1].isdigit():
                j = i + 1
                while j < len(s) and s[j].isdigit():
                    j += 1
                if j < len(s) and s[j] == "]":
                    i = j
                    continue
            out.append(s[i])
            i += 1
        return "".join(out)
    l, r = rule["smarts"].split(">>")
    return demap(l) + ">>" + demap(r) + "|" + ",".join(sorted("%d%+d%d" % (e["dH"], e["dC"], e["arom"])
                                                            for e in rule["centre"].values()))


_RXN_CACHE = {}


def _rxn(smarts):
    r = _RXN_CACHE.get(smarts)
    if r is None:
        try:
            r = rdChemReactions.ReactionFromSmarts(smarts)
            r.Initialize()
            if r.GetNumReactantTemplates() != 1:
                r = False
        except Exception:
            r = False
        if len(_RXN_CACHE) > 200000:
            _RXN_CACHE.clear()
        _RXN_CACHE[smarts] = r
    return r


def prep_substrate(smiles):
    return Chem.MolFromSmiles(smiles)


def _run(rule, sub, max_products=500):
    """Raw RunReactants output of one rule on a substrate mol (empty tuple when it does not match)."""
    rxn = _rxn(rule["smarts"])
    if not rxn:
        return ()
    try:
        if not sub.HasSubstructMatch(rxn.GetReactantTemplate(0)):
            return ()
        return rxn.RunReactants((sub,), max_products)
    except Exception:
        return ()


def _products(rule, sub, max_products=500, res=None):
    """Yield the main-product fragment (unsanitized RWMol) of every match of one rule on a substrate mol."""
    if res is None:
        res = _run(rule, sub, max_products)
    centre = rule.get("centre", {})
    added = rule.get("added", {})
    vmaps = set(rule.get("valence_maps", []))
    kept = set(rule.get("kept", []))
    for ps in res:
        try:
            rw = Chem.RWMol(ps[0])
            ok = True
            tmpl_atoms = []
            for a in rw.GetAtoms():
                if not a.HasProp("old_mapno"):
                    continue
                t = a.GetIntProp("old_mapno")
                tmpl_atoms.append(a.GetIdx())
                if rule["mode"] == "delta":
                    if t in centre:
                        ra = sub.GetAtomWithIdx(a.GetIntProp("react_atom_idx"))
                        e = centre[t]
                        h = ra.GetTotalNumHs() + e["dH"]
                        if h < 0:
                            ok = False
                            break
                        a.SetFormalCharge(ra.GetFormalCharge() + e["dC"])
                        a.SetNumExplicitHs(h)
                        a.SetNoImplicit(True)
                        a.SetIsAromatic(e["arom"])
                        a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
                    elif t in added:
                        e = added[t]
                        a.SetFormalCharge(e["chg"])
                        a.SetNumExplicitHs(e["H"])
                        a.SetNoImplicit(True)
                        a.SetIsAromatic(e["arom"])
                else:  # valence mode (library rules): hydrogens of changed and new atoms follow valence
                    if t in vmaps or not a.HasProp("react_atom_idx"):
                        a.SetNumExplicitHs(0)
                        a.SetNoImplicit(False)
                        a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
            if not ok:
                continue
            frags = Chem.GetMolFrags(rw, asMols=False, sanitizeFrags=False)
            if len(frags) > 1:
                need = set(tmpl_atoms) if rule["mode"] == "valence" else \
                    {a.GetIdx() for a in rw.GetAtoms() if a.HasProp("old_mapno")
                     and (a.GetIntProp("old_mapno") in kept or a.GetIntProp("old_mapno") in added)}
                hit = [f for f in frags if need & set(f)]
                if len(hit) != 1:
                    if rule["mode"] == "valence" and hit:
                        hit = [max(hit, key=len)]
                    else:
                        continue
                keep = set(hit[0])
                for i in sorted((i for i in range(rw.GetNumAtoms()) if i not in keep), reverse=True):
                    rw.RemoveAtom(i)
            yield rw
        except Exception:
            continue


def _valid(rw):
    try:
        m = rw.GetMol()
        Chem.SanitizeMol(m)
        return m
    except Exception:
        return None


def composition(x):
    m = Chem.MolFromSmiles(x) if isinstance(x, str) else x
    return tuple(sorted(a.GetAtomicNum() for a in m.GetAtoms() if a.GetAtomicNum() > 1))


def apply_rule(rule, sub, max_products=500):
    """Apply one rule to a substrate mol. Returns the set of canonical (no stereo) main-product SMILES."""
    out = set()
    for rw in _products(rule, sub, max_products):
        m = _valid(rw)
        if m is not None:
            c = canon(m)
            if c:
                out.add(c)
    return out


def check_exact(rule, sub, truth, comp, max_products=500):
    """Same verdict as apply_rule(...) == {truth}, with an early exit at the first valid other product.
    Returns 'other' (a valid product that is not the truth), 'truth_only' or 'empty'."""
    seen = False
    for rw in _products(rule, sub, max_products):
        same = composition(rw) == comp
        m = _valid(rw)
        if m is None:
            continue
        c = canon(m) if same else None
        if c is None:
            if not same:
                return "other"
            continue
        if c != truth:
            return "other"
        seen = True
    return "truth_only" if seen else "empty"


def scan_static(rule, sub, truth, comp, max_products=500):
    """(exact, cover, raw product count) of one library rule on one example; stops once both an other
    product and the truth have been seen. Same verdicts as apply_rule."""
    other = cover = False
    res = _run(rule, sub, max_products)
    n = len(res)
    for rw in _products(rule, sub, max_products, res):
        same = composition(rw) == comp
        if not same and other:
            continue
        m = _valid(rw)
        if m is None:
            continue
        if not same:
            other = True
        else:
            c = canon(m)
            if c is None:
                continue
            if c == truth:
                cover = True
            else:
                other = True
        if other and cover:
            break
    return cover and not other, cover, n


def apply_rules(rules, sub):
    out = set()
    for r in rules:
        out |= apply_rule(r, sub)
    return out
