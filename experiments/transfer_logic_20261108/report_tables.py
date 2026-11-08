"""Descriptive tables for RESULT.md, read from results/ after the scored run. Not part of the frozen run; it computes
no new test. Usage: python3 -I report_tables.py"""
import collections
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in open(os.path.join(HERE, "results", "held.jsonl"))]
S = json.load(open(os.path.join(HERE, "results", "summary.json")))


def sel(dom, frac):
    return [r for r in rows if r["domain"] == dom and r["fraction"] == frac]


def counts(rs):
    arms = list(rs[0]["arms"])
    return {a: sum(r["arms"][a]["exact"] for r in rs) for a in arms}, len(rs)


print("salt", S["salt"], "freeze_commit", S["freeze_commit"], "cpu_s", S["cpu_seconds"],
      "held circuits", S["held_circuit_items"], "held policies", S["held_policy_items"])
for dom, fracs in (("circuit", (0.125, 0.25, 0.5)), ("policy", (0.25,))):
    for f in fracs:
        c, n = counts(sel(dom, f))
        print(f"{dom} {f}: n={n}", c)


def show(name, v):
    ci = v["cluster_bootstrap_ci95"]
    h = v.get("holm", {})
    print(f"{name}: {v['exact'][0]} vs {v['exact'][1]} of {v['items']} ({v['clusters']} clusters); only first "
          f"{v['only_first']}, only second {v['only_second']}; McNemar p {v['mcnemar_exact_p']:.4g}; Holm p "
          f"{h.get('p_holm')}; reject {h.get('reject')}; diff {v['difference']}; ci95 {ci}"
          + (f"; supported {v['supported']}" if "supported" in v else ""))


for k, v in S["primary"].items():
    show("PRIMARY " + k, v)
for k, v in S["secondary"].items():
    show("SECONDARY " + k, v)
for k, v in S["reference_not_gate"].items():
    show("REFERENCE " + k, v)
print("verify", S["verify_flag"])

prim = sel("circuit", 0.25)
by_file = collections.defaultdict(collections.Counter)
by_fam = collections.defaultdict(collections.Counter)
for r in prim:
    name = r["cluster"].split("/", 1)[1]
    fam = re.sub(r"\d+$", "", name.split(".")[0])
    for tgt in (by_file[name], by_fam[fam]):
        tgt["items"] += 1
        for a in ("static", "grown", "shuffled", "espresso_like", "cart", "grown_active"):
            tgt[a] += r["arms"][a]["exact"]
gt = sum(1 for c in by_file.values() if c["grown"] > c["shuffled"])
lt = sum(1 for c in by_file.values() if c["grown"] < c["shuffled"])
gs = sum(1 for c in by_file.values() if c["grown"] > c["static"])
print(f"files: grown>shuffled {gt}, grown<shuffled {lt}, grown>static {gs}, of {len(by_file)}")
print("per file (items static grown shuffled espresso cart active):")
print("; ".join(f"{k} {c['items']} {c['static']} {c['grown']} {c['shuffled']} {c['espresso_like']} {c['cart']} "
                f"{c['grown_active']}" for k, c in sorted(by_file.items()) if c["grown"] or c["shuffled"]
                or c["static"] or c["cart"] or c["espresso_like"] or c["grown_active"]))
print("files with no recovery by any arm:", sum(1 for c in by_file.values() if not any(
    c[a] for a in ("static", "grown", "shuffled", "espresso_like", "cart", "grown_active"))))
print("per family (items static grown shuffled):")
print("; ".join(f"{k} {c['items']} {c['static']} {c['grown']} {c['shuffled']}" for k, c in sorted(by_fam.items())
                if c["items"] > 1 or c["grown"]))
pol = sel("policy", 0.25)
by_seed = collections.defaultdict(collections.Counter)
for r in pol:
    for a in ("static", "grown", "shuffled", "full", "cart", "grown_active"):
        by_seed[r["cluster"].split("/")[1]][a] += r["arms"][a]["exact"]
print("seeds grown>shuffled", sum(1 for c in by_seed.values() if c["grown"] > c["shuffled"]),
      "grown<shuffled", sum(1 for c in by_seed.values() if c["grown"] < c["shuffled"]), "of", len(by_seed))
for dom, f in (("circuit", 0.25), ("policy", 0.25)):
    rs = sel(dom, f)
    for a in rs[0]["arms"]:
        errs = sorted(r["arms"][a]["held_errors"] for r in rs if r["arms"][a]["held_errors"] is not None)
        nofit = sum(1 for r in rs if r["arms"][a]["held_errors"] is None)
        if errs:
            print(f"{dom} {a}: median held errors {errs[len(errs) // 2]}, no program {nofit}")
