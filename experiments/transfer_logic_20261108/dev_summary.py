"""Summarise a development results file (labelled development). Usage: python3 -I dev_summary.py <label>"""
import collections, json, os, sys
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dev_results", sys.argv[1] + ".jsonl")
rows = [json.loads(l) for l in open(p)]
for dom in ("circuit", "policy"):
    rs = [r for r in rows if r["domain"] == dom]
    if not rs:
        continue
    arms = list(rs[0]["arms"])
    line = [f"{dom} development n={len(rs)}"]
    for a in arms:
        ex = sum(r["arms"][a]["exact"] for r in rs)
        ver = [r["arms"][a].get("verified") for r in rs if "verified" in r["arms"][a]]
        vx = sum(1 for r in rs if r["arms"][a].get("verified") == 1 and r["arms"][a]["exact"] == 1)
        cpu = sum(r["arms"][a]["cpu_s"] for r in rs)
        s = f"{a}: exact {ex}/{len(rs)}"
        if ver:
            s += f", verified {sum(ver)} (exact among verified {vx}/{sum(ver)})"
        s += f", cpu {cpu:.1f}s"
        line.append(s)
    print(" | ".join(line))
    g = {r["id"]: r["arms"] for r in rs}
    for a, b in (("grown", "static"), ("grown", "shuffled")):
        b10 = sum(1 for v in g.values() if v[a]["exact"] and not v[b]["exact"])
        b01 = sum(1 for v in g.values() if v[b]["exact"] and not v[a]["exact"])
        print(f"  discordant {a} only {b10}, {b} only {b01}")
    if "grown_active" in arms:
        b10 = sum(1 for v in g.values() if v["grown_active"]["exact"] and not v["grown"]["exact"])
        b01 = sum(1 for v in g.values() if v["grown"]["exact"] and not v["grown_active"]["exact"])
        print(f"  discordant active only {b10}, random only {b01}")
