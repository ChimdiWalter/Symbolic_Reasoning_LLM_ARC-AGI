"""Development check of Amendment 2 (development families only; labelled development).

Compares the rule extractor of the Amendment 1 freeze (t3chem/chem.py at commit 4eae13e5, read with git show) with
the amended extractor (stereochemistry cleared before cutting fragments; any remaining RDKit failure gives no rule)
on 1,500 development items at the seven levels, and repeats the synthetic test of RDKit's fragment writer on five
small E/Z molecules (every atom subset). Writes dev/amendment2_check_development.json."""
import gzip, importlib.util, itertools, json, os, subprocess, sys, tempfile, time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDY)
from rdkit import Chem  # noqa: E402
from t3chem.chem import LEVEL_ORDER, extract_rule  # noqa: E402

FROZEN = "4eae13e5cf2c88ff8a43c7fec47cd440500f2014"
src = subprocess.run(["git", "-C", STUDY, "show", FROZEN + ":experiments/transfer_chemistry_20261108/t3chem/chem.py"],
                     capture_output=True, check=True).stdout
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "frozen_chem.py")
open(path, "wb").write(src)
spec = importlib.util.spec_from_file_location("frozen_chem", path)
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)


def ser(r):
    if r is None:
        return None
    return [r["smarts"], sorted((k, sorted(v.items())) for k, v in r["centre"].items()),
            sorted((k, sorted(v.items())) for k, v in r["added"].items()), r["kept"]]


t0 = time.process_time()
items = []
with gzip.open(os.path.join(STUDY, "data", "cache", "items.jsonl.gz"), "rt") as fh:
    for line in fh:
        it = json.loads(line)
        if it["dev_family"]:
            items.append(it)
items.sort(key=lambda it: (it["fam"], it["pair"]))
items = items[::max(1, len(items) // 1500)][:1500]
n = same = frozen_fail = fixed_rule_where_failed = fixed_none_where_failed = differ = 0
for it in items:
    for L in LEVEL_ORDER:
        n += 1
        try:
            a = ser(frozen.extract_rule(it["mapped_sub"], it["mapped_prod"], L))
            failed = False
        except Exception:
            failed = True
        b = ser(extract_rule(it["mapped_sub"], it["mapped_prod"], L))
        if failed:
            frozen_fail += 1
            fixed_rule_where_failed += b is not None
            fixed_none_where_failed += b is None
        elif a == b:
            same += 1
        else:
            differ += 1


def frag(m, use):
    bonds = [bd.GetIdx() for bd in m.GetBonds() if bd.GetBeginAtomIdx() in use and bd.GetEndAtomIdx() in use]
    sym = ["[#%d:%d]" % (at.GetAtomicNum(), at.GetIdx() + 1) for at in m.GetAtoms()]
    bsym = ["-" if bd.GetBondType() == Chem.BondType.SINGLE else "=" for bd in m.GetBonds()]
    return Chem.MolFragmentToSmiles(m, atomsToUse=sorted(use), bondsToUse=bonds, atomSymbols=sym, bondSymbols=bsym,
                                    allBondsExplicit=True, isomericSmiles=False, canonical=True)


def clear(m):
    m = Chem.Mol(m)
    for at in m.GetAtoms():
        at.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
    for bd in m.GetBonds():
        bd.SetBondDir(Chem.BondDir.NONE)
        bd.SetStereo(Chem.BondStereo.STEREONONE)
    return m


subsets = crash_before = crash_after = 0
for smi in ["C/C=C/C=C/C", "OC/C=C(/C)C=O", "C/C=C/C(=O)O", "C/C=C\\C=C\\C(C)=O", "C1CC/C=C/CC1"]:
    m = Chem.MolFromSmiles(smi)
    for k in range(1, m.GetNumAtoms() + 1):
        for use in itertools.combinations(range(m.GetNumAtoms()), k):
            subsets += 1
            for mol, which in ((m, "before"), (clear(m), "after")):
                try:
                    frag(mol, set(use))
                except RuntimeError:
                    if which == "before":
                        crash_before += 1
                    else:
                        crash_after += 1
out = {"label": "development", "frozen_commit": FROZEN, "development_items": len(items), "extractions": n,
       "identical_where_frozen_works": same, "differ_where_frozen_works": differ,
       "frozen_failures": frozen_fail, "amended_rule_where_frozen_failed": fixed_rule_where_failed,
       "amended_none_where_frozen_failed": fixed_none_where_failed,
       "synthetic_subsets": subsets, "synthetic_failures_frozen_path": crash_before,
       "synthetic_failures_after_clearing": crash_after, "cpu_seconds": round(time.process_time() - t0, 1)}
json.dump(out, open(os.path.join(STUDY, "dev", "amendment2_check_development.json"), "w"), indent=1)
print(json.dumps(out))
