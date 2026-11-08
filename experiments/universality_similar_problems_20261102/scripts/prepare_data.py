"""U2 data preparation (PROTOCOL.md sections 3-5), run once with python3 -I after the freeze:
- DATA_MANIFEST.json: source URL, commit, licence and sha256 of every file used;
- validity filter (parse, test outputs present, grids 1..30 x 1..30 with values 0..9);
- freshness against ARC-AGI-2 training + evaluation (challenges and solutions): exclusion rules (i) and (ii);
- REAL and SHUFFLED challenge files (demonstrations and test inputs only), solutions apart, task metadata."""
import hashlib
import json
import os
import subprocess
from collections import Counter

import numpy  # noqa: F401  (not needed; the donor draw below uses the same generator as the protocol)

R = "/path/to/repository"
E = os.path.join(R, "experiments/universality_similar_problems_20261102")
D = "/path/to/benchmark_data"
SRC, PREP = os.path.join(D, "src"), os.path.join(D, "prepared")
ARC2 = os.path.join(R, "outputs/score_first/data")
BENCH = [  # (name, folder, url, licence file, licence name, task glob root, group rule)
    ("1d_arc", "1d_arc", "https://github.com/khalil-research/1D-ARC", "LICENSE.md", "MIT", "dataset", "dir"),
    ("mini_arc", "mini_arc", "https://github.com/KSB21ST/MINI-ARC", "LICENSE", "Apache-2.0", "data/MiniARC", None),
    ("concept_arc", "concept_arc", "https://github.com/victorvikram/ConceptARC", "LICENSE", "MIT", "corpus", "dir")]
sha = lambda b: hashlib.sha256(b).hexdigest()      # noqa: E731


def gkey(g):
    return sha(json.dumps(g, separators=(",", ":")).encode())


def valid(g):
    return (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) for r in g) and
            1 <= len(g[0]) <= 30 and all(len(r) == len(g[0]) for r in g) and
            all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


def nontrivial(g):
    return len({v for r in g for v in r}) >= 2 and len(g) * len(g[0]) >= 10


def arc2_sets():
    pairs, grids, big = set(), set(), set()
    for split in ("training", "evaluation"):
        ch = json.load(open(os.path.join(ARC2, f"arc-agi_{split}_challenges.json")))
        so = json.load(open(os.path.join(ARC2, f"arc-agi_{split}_solutions.json")))
        for tid, t in ch.items():
            ps = [(p["input"], p["output"]) for p in t["train"]] + list(zip([x["input"] for x in t["test"]], so[tid]))
            for a, b in ps:
                pairs.add(gkey([a, b]))
                for g in (a, b):
                    grids.add(gkey(g))
                    if nontrivial(g):
                        big.add(gkey(g))
    return pairs, grids, big


def main():
    os.makedirs(PREP, exist_ok=True)
    pairs2, grids2, big2 = arc2_sets()
    man = {"downloaded_utc": "2026-11-02T06:29Z (git clone --depth 1, after the protocol freeze 517d0469)",
           "arc_agi_2_reference": {f: sha(open(os.path.join(ARC2, f), "rb").read()) for f in sorted(os.listdir(ARC2))
                                   if f.endswith(".json") and ("training" in f or "evaluation" in f)},
           "benchmarks": {}}
    overlap = {}
    for b, (name, folder, url, lic, licname, root, grp) in enumerate(BENCH):
        base = os.path.join(SRC, folder)
        commit = subprocess.run(["git", "-C", base, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        files = sorted(os.path.relpath(os.path.join(dp, f), base) for dp, _, fn in os.walk(os.path.join(base, root))
                       for f in fn if f.endswith(".json"))
        tasks, excl, fsha, dup = {}, Counter(), {}, Counter()
        desc = Counter()
        seen = {}
        for rel in files:
            raw = open(os.path.join(base, rel), "rb").read()
            fsha[rel] = sha(raw)
            try:
                t = json.loads(raw)
                tr, te = t["train"], t["test"]
                ok = tr and te and all(valid(p["input"]) and valid(p["output"]) for p in tr + te)
            except Exception:                                     # noqa: BLE001
                ok = False
            if not ok:
                excl["invalid_or_outside_domain"] += 1
                continue
            ps = [(p["input"], p["output"]) for p in tr + te]
            r1 = any(gkey([a, c]) in pairs2 for a, c in ps)
            r2 = any(gkey(p["input"]) in big2 for p in te)
            for p in tr + te:
                for g in (p["input"], p["output"]):
                    desc["grids"] += 1
                    desc["grids_equal_to_an_arc2_grid"] += gkey(g) in grids2
                    desc["nontrivial_grids_equal_to_an_arc2_grid"] += nontrivial(g) and gkey(g) in big2
            desc["pairs"] += len(ps)
            desc["pairs_equal_to_an_arc2_pair"] += sum(gkey([a, c]) in pairs2 for a, c in ps)
            if r1 or r2:
                excl["rule_i_pair" if r1 else "rule_ii_test_input"] += 1
                if r1 and r2:
                    excl["both_rules"] += 1
                continue
            k = gkey([[p["input"], p["output"]] for p in tr + te])
            if k in seen:
                dup["duplicate_of_another_task"] += 1
            seen[k] = rel
            group = rel.split(os.sep)[1] if grp == "dir" else None
            tasks[rel] = {"train": tr, "test": te, "group": group}
        ids = sorted(tasks)
        tid = {rel: f"{name[:2]}{i:04d}" for i, rel in enumerate(ids)}
        rng = __import__("numpy").random.default_rng(20261102 + b)
        donor = {}
        for rel in ids:
            cand = [x for x in ids if x != rel and (tasks[x]["group"] != tasks[rel]["group"] or grp is None)]
            donor[rel] = cand[int(rng.integers(len(cand)))]
        real = {tid[r]: {"train": tasks[r]["train"], "test": [{"input": p["input"]} for p in tasks[r]["test"]]}
                for r in ids}
        shuf = {tid[r]: {"train": tasks[donor[r]]["train"], "test": [{"input": p["input"]} for p in tasks[r]["test"]]}
                for r in ids}
        sol = {tid[r]: [p["output"] for p in tasks[r]["test"]] for r in ids}
        meta = {tid[r]: {"file": r, "group": tasks[r]["group"], "donor": tid[donor[r]], "n_test": len(tasks[r]["test"])}
                for r in ids}
        bdir = os.path.join(PREP, name)
        os.makedirs(os.path.join(bdir, "solutions_scorer_only"), exist_ok=True)
        hs = {}
        for fname, obj in (("real.json", real), ("shuffled.json", shuf), ("meta.json", meta),
                           ("solutions_scorer_only/solutions.json", sol)):
            p = os.path.join(bdir, fname)
            json.dump(obj, open(p, "w"))
            hs[fname] = sha(open(p, "rb").read())
        man["benchmarks"][name] = {"url": url, "commit": commit, "licence": licname,
                                   "licence_file": lic, "licence_sha256": sha(open(os.path.join(base, lic), "rb").read()),
                                   "task_root": root, "n_files": len(files), "files_sha256": fsha,
                                   "n_tasks_used": len(ids), "n_test_outputs": sum(m["n_test"] for m in meta.values()),
                                   "groups": dict(Counter(m["group"] for m in meta.values())), "prepared_sha256": hs}
        overlap[name] = {"files": len(files), "excluded": dict(excl), "used": len(ids), "descriptive": dict(desc),
                         "within_benchmark_duplicates": dict(dup)}
    json.dump(man, open(os.path.join(E, "DATA_MANIFEST.json"), "w"), indent=1)
    json.dump(overlap, open(os.path.join(E, "OVERLAP.json"), "w"), indent=1)
    print(json.dumps(overlap, indent=1))


if __name__ == "__main__":
    main()
