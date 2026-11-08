"""The static library: the published generalized enzymatic reaction rules of Ni et al. 2021 as shipped with
Pickaxe (MINE-Database, metacyc_generalized_rules.tsv), turned into single-substrate forward rules.

Each published rule names its reactant and product slots ("Any", or a cofactor such as NAD_CoF). For every
pair (reactant slot "Any" i, product slot "Any" j) that shares mapped atoms, the variant "rule:RiPj" keeps
reactant template i and product template j. Product atoms that the published rule takes from another slot
(a cofactor or a second substrate) become new atoms written by the rule, exactly as in the published
template. Hydrogens on atoms whose bonds or charge change are set by valence after the rule is applied
("valence" mode), which is how the published templates are meant to be used (they carry no hydrogens).
"""
import csv

from rdkit import Chem
from rdkit.Chem import rdChemReactions


def _nb(mol, a, shared):
    out = []
    for n in a.GetNeighbors():
        m = n.GetAtomMapNum()
        b = mol.GetBondBetweenAtoms(a.GetIdx(), n.GetIdx())
        out.append((m if m in shared else -1, b.GetSmarts()))
    return sorted(out)


def load_library(path):
    variants, n_rules, skipped = [], 0, 0
    with open(path) as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            n_rules += 1
            rl, pl = row["Reactants"].split(";"), row["Products"].split(";")
            try:
                rxn = rdChemReactions.ReactionFromSmarts(row["SMARTS"])
            except Exception:
                skipped += 1
                continue
            if rxn.GetNumReactantTemplates() != len(rl) or rxn.GetNumProductTemplates() != len(pl):
                skipped += 1
                continue
            for i, lab in enumerate(rl):
                if lab != "Any":
                    continue
                R = rxn.GetReactantTemplate(i)
                rmaps = {a.GetAtomMapNum() for a in R.GetAtoms() if a.GetAtomMapNum() > 0}
                for j, labp in enumerate(pl):
                    if labp != "Any":
                        continue
                    P = rxn.GetProductTemplate(j)
                    pmaps = {a.GetAtomMapNum() for a in P.GetAtoms() if a.GetAtomMapNum() > 0}
                    shared = rmaps & pmaps
                    if not shared:
                        continue
                    ra = {a.GetAtomMapNum(): a for a in R.GetAtoms()}
                    pa = {a.GetAtomMapNum(): a for a in P.GetAtoms()}
                    vm = sorted(m for m in shared
                                if _nb(R, ra[m], shared) != _nb(P, pa[m], shared)
                                or ra[m].GetFormalCharge() != pa[m].GetFormalCharge())
                    smarts = "(" + Chem.MolToSmarts(R) + ")>>(" + Chem.MolToSmarts(P) + ")"
                    try:
                        t = rdChemReactions.ReactionFromSmarts(smarts)
                        t.Initialize()
                        if t.GetNumReactantTemplates() != 1:
                            continue
                    except Exception:
                        continue
                    variants.append({"name": "%s:R%dP%d" % (row["Name"], i, j), "smarts": smarts,
                                     "mode": "valence", "valence_maps": vm, "kept": sorted(shared)})
    return variants, {"published_rules": n_rules, "unparsed_rules": skipped, "variants": len(variants)}
