"""Build the item pool from EnzymeMap (run with python -I; the study folder is put on sys.path below).

Item = one (main substrate, main product) pair of one family; family = EC number + EnzymeMap rule id.
Writes data/cache/items.jsonl.gz (all items, local only) and data/POOL.json (family counts, the development
families, the scoring pool and the drop reasons). No rule is applied here and no arm runs here.
"""
import collections, csv, gzip, hashlib, json, os, sys, time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDY)
from t3chem.chem import canon, main_pair  # noqa: E402


def h01(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16) / float(16 ** 12)


def cofactor_set(cfg):
    names = json.load(open(os.path.join(STUDY, cfg["data"]["compound_names"])))
    out, missing = set(), []
    for n in cfg["cofactor_names"]:
        v = names.get(n)
        if not v:
            missing.append(n)
            continue
        for s in (v if isinstance(v, list) else [v]):
            c = canon(s)
            if c:
                out.add(c)
    with open(os.path.join(STUDY, cfg["data"]["coreactants_tsv"])) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                c = canon(parts[2])
                if c:
                    out.add(c)
    out.add(canon("[H+]") or "[H+]")
    return out, missing


def main():
    t0 = time.process_time()
    cfg = json.load(open(os.path.join(STUDY, "config", "T3_CONFIG.json")))
    cof, missing = cofactor_set(cfg)
    src, steps = set(cfg["data"]["rows_source"]), set(cfg["data"]["rows_steps"])
    fam_rxns = collections.defaultdict(set)
    n_rows = 0
    with gzip.open(os.path.join(STUDY, cfg["data"]["enzymemap_csv"]), "rt") as fh:
        for r in csv.DictReader(fh):
            n_rows += 1
            if r["source"] in src and r["steps"] in steps:
                fam_rxns[r["ec_num"] + "|" + r["rule_id"]].add(r["mapped"])
    cache, reasons = {}, collections.Counter()
    items = collections.defaultdict(dict)
    for fam in sorted(fam_rxns):
        for mapped in sorted(fam_rxns[fam]):
            if mapped not in cache:
                cache[mapped] = main_pair(mapped, cof, cfg["main_product_min_heavy_atoms"])
            it, why = cache[mapped]
            if it is None:
                reasons[why] += 1
                continue
            key = it["sub_ns"] + ">>" + it["prod_ns"]
            if key not in items[fam]:
                items[fam][key] = dict(it, fam=fam, pair=key, source_mapped=mapped)
    dev_salt, frac = cfg["dev"]["salt"], cfg["dev"]["fraction"]
    dev = sorted(f for f in items if h01(dev_salt + "|" + f) < frac)
    dev_pairs = set()
    for f in dev:
        dev_pairs |= set(items[f])
    need = cfg["min_items_per_family"]
    pool = {}
    for f in sorted(items):
        if f in dev:
            continue
        keep = [p for p in items[f] if p not in dev_pairs]
        if len(keep) >= need:
            pool[f] = len(keep)
    os.makedirs(os.path.join(STUDY, "data", "cache"), exist_ok=True)
    with gzip.open(os.path.join(STUDY, "data", "cache", "items.jsonl.gz"), "wt") as out:
        for f in sorted(items):
            for p in sorted(items[f]):
                it = items[f][p]
                it["dev_family"] = f in dev
                it["in_dev_pair_set"] = p in dev_pairs
                out.write(json.dumps(it, sort_keys=True) + "\n")
    summary = {
        "rows_read": n_rows, "families_with_rows": len(fam_rxns),
        "unique_mapped_reactions": len(cache), "drop_reasons": dict(reasons),
        "cofactor_names_missing": missing, "cofactor_smiles": len(cof),
        "families_with_items": len(items), "items": sum(len(v) for v in items.values()),
        "dev_salt": dev_salt, "dev_fraction": frac,
        "dev_families": {f: len(items[f]) for f in dev},
        "dev_families_eligible": sorted(f for f in dev if len(items[f]) >= need),
        "scoring_pool": pool, "scoring_pool_families": len(pool),
        "min_items_per_family": need, "cpu_seconds": round(time.process_time() - t0, 1),
    }
    json.dump(summary, open(os.path.join(STUDY, "data", "POOL.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("dev_families", "scoring_pool",
                                                                     "dev_families_eligible")}))


if __name__ == "__main__":
    main()
