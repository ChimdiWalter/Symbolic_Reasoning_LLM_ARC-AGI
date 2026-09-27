"""v1.4 static feasibility smoke: admission mechanics and parse checks only.
Seeds from SMOKE_BASE, disjoint from the experiment. No distance between any
two episodes is computed, so no identifiability value exists."""
import json, os, sys, time
sys.path.insert(0, os.getcwd())
from cora_arc2026 import v14_loc as L
G = L.G
man = G.manifest()
budgets = man["budgets"]
gate = {"require": "frontier_term_count >= 2"}
fams = [G.parse_family(f) for f in ["(0,0)", "(1,0)", "(0,1)", "(1,1)", "(0,0,0)"]]
elig = [f for f in fams if G.contrast_target(G.CD.sample_target(999983, f), "FEATURE") is not None]
print("eligible FEATURE anchor families", [G.CV.family_text(f) for f in elig], flush=True)
codes, admitted, t0 = {}, [], time.monotonic()
deadline = t0 + float(sys.argv[1])
attempt = 0
while time.monotonic() < deadline and len(admitted) < 3:
    fam = elig[attempt % len(elig)]
    seed = L.SMOKE_BASE + attempt * 100
    anchor = G.CD.sample_target(seed, fam)
    contrast = G.contrast_target(anchor, "FEATURE", rotation=attempt)
    attempt += 1
    if contrast is None:
        codes["CONTRAST_ILLEGAL"] = codes.get("CONTRAST_ILLEGAL", 0) + 1
        continue
    s = time.monotonic()
    code, out = L.make_twin_replicate(anchor, contrast, seed + 1, budgets, gate, ("smoke", attempt))
    codes[code] = codes.get(code, 0) + 1
    print(f"attempt {attempt} {G.CV.family_text(fam)} mdl {G.CV.mdl(anchor)}/{G.CV.mdl(contrast)} -> {code} {time.monotonic()-s:.1f}s", flush=True)
    if out:
        for t in (0, 1):
            ep = out[t]
            v = L.model_view(ep)
            sizes = {st: sum(L.stage_multiset(v, st).values()) for st in ("S2","S3","S4","S5","S6","S7a")}
            outcomes = {}
            for _, o in ep["trajectory"]:
                outcomes[o] = outcomes.get(o, 0) + 1
            print(f"   target {t}: events {len(ep['trajectory'])} {outcomes} stage sizes {sizes} near misses {len(ep['mismatch'])}", flush=True)
        admitted.append(attempt)
print("SMOKE_DONE", json.dumps({"attempts": attempt, "codes": codes, "admitted_twin_replicates": len(admitted), "seconds": round(time.monotonic()-t0,1)}), flush=True)
