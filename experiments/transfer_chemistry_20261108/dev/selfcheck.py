"""Development check of the rule extractor and applier on development families only: does the rule extracted
from one example, at each level, give back that example's product (exactly and only it)? Also times the
static library scan on the same substrates. Output labelled development."""
import collections, gzip, json, os, sys, time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDY)
from rdkit import Chem  # noqa: E402
from t3chem.chem import LEVEL_ORDER, apply_rule, extract_rule  # noqa: E402
from t3chem.library import load_library  # noqa: E402

n_max = int(sys.argv[1]) if len(sys.argv) > 1 else 200
N_LIB = int(sys.argv[2]) if len(sys.argv) > 2 else 5
items = []
with gzip.open(os.path.join(STUDY, "data", "cache", "items.jsonl.gz"), "rt") as fh:
    for line in fh:
        it = json.loads(line)
        if it["dev_family"]:
            items.append(it)
items.sort(key=lambda it: (it["fam"], it["pair"]))
step = max(1, len(items) // n_max)
items = items[::step][:n_max]
t0 = time.process_time()
res = {L: collections.Counter() for L in LEVEL_ORDER}
fails = collections.Counter()
for it in items:
    mol = Chem.MolFromSmiles(it["sub"])
    for L in LEVEL_ORDER:
        r = extract_rule(it["mapped_sub"], it["mapped_prod"], L)
        if r is None:
            res[L]["no_rule"] += 1
            continue
        o = apply_rule(r, mol)
        if o == {it["prod_ns"]}:
            res[L]["exact"] += 1
        elif it["prod_ns"] in o:
            res[L]["cover_not_unique"] += 1
        elif o:
            res[L]["wrong"] += 1
        else:
            res[L]["no_outcome"] += 1
            if L == "L6":
                fails[it["fam"]] += 1
t1 = time.process_time()
lib, info = load_library(os.path.join(STUDY, "data/raw/pickaxe/metacyc_generalized_rules.tsv"))
t2 = time.process_time()
lib_stats = collections.Counter()
for it in items[:N_LIB]:
    mol = Chem.MolFromSmiles(it["sub"])
    best = 0
    for r in lib:
        o = apply_rule(r, mol)
        if o == {it["prod_ns"]}:
            lib_stats["exact_rules"] += 1
            best = 2
        elif it["prod_ns"] in o:
            best = max(best, 1)
    lib_stats[["none", "cover_only", "exact"][best]] += 1
t3 = time.process_time()
out = {"label": "development", "items": len(items), "levels": {L: dict(c) for L, c in res.items()},
       "extract_apply_cpu_s": round(t1 - t0, 1), "library": info, "library_load_cpu_s": round(t2 - t1, 1),
       "library_scan_items": dict(lib_stats), "library_scan_cpu_s_per_item": round((t3 - t2) / max(1, N_LIB), 2),
       "no_outcome_at_L6_by_family": dict(fails.most_common(10))}
os.makedirs(os.path.join(STUDY, "dev"), exist_ok=True)
json.dump(out, open(os.path.join(STUDY, "dev", "selfcheck_development.json"), "w"), indent=1)
print(json.dumps(out))
