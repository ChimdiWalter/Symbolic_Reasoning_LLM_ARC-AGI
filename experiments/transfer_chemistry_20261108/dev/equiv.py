"""Development check that the fast checks give the same verdicts as the full outcome sets (development
families only). Exits 1 on any mismatch."""
import gzip, json, os, sys, time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDY)
from rdkit import Chem  # noqa: E402
from t3chem.chem import LEVEL_ORDER, apply_rule, check_exact, composition, extract_rule, scan_static  # noqa: E402
from t3chem.library import load_library  # noqa: E402

items = []
with gzip.open(os.path.join(STUDY, "data", "cache", "items.jsonl.gz"), "rt") as fh:
    for line in fh:
        it = json.loads(line)
        if it["dev_family"]:
            items.append(it)
items.sort(key=lambda it: (it["fam"], it["pair"]))
items = items[::max(1, len(items) // 15)][:15]
t0 = time.process_time()
bad = 0
n = 0
for it in items:
    mol, comp = Chem.MolFromSmiles(it["sub"]), composition(it["prod_ns"])
    rules = [extract_rule(it["mapped_sub"], it["mapped_prod"], L) for L in LEVEL_ORDER]
    other = items[(items.index(it) + 1) % len(items)]
    rules += [extract_rule(other["mapped_sub"], other["mapped_prod"], L) for L in ("L0", "L2")]
    for r in rules:
        if r is None:
            continue
        o = apply_rule(r, mol)
        full = "other" if (o - {it["prod_ns"]}) else ("truth_only" if o else "empty")
        n += 1
        bad += full != check_exact(r, mol, it["prod_ns"], comp)
lib, _ = load_library(os.path.join(STUDY, "data/raw/pickaxe/metacyc_generalized_rules.tsv"))
for it in items[:2]:
    mol, comp = Chem.MolFromSmiles(it["sub"]), composition(it["prod_ns"])
    for r in lib[::3]:
        o = apply_rule(r, mol)
        x, c, _ = scan_static(r, mol, it["prod_ns"], comp)
        n += 1
        bad += (x, c) != (o == {it["prod_ns"]}, it["prod_ns"] in o)
print(json.dumps({"label": "development", "checks": n, "mismatches": bad,
                  "cpu_s": round(time.process_time() - t0, 1)}))
sys.exit(1 if bad else 0)
