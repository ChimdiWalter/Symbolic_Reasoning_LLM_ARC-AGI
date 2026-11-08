"""Test S1 (protocols/TEST_S1_PROTOCOL.md): specification-guided symbolic construction over SIGMA.

    python -m cgrow.s1 prep RUN_ID                 form-proposal jobs (S1F)
    python -m cgrow.s1 run RUN_ID GEN_ID           all arms (system side), runs/RUN_ID/units.json
    python -m cgrow.s1 evaluate RUN_ID S1RUN       evaluator scoring, results.json, reports/TEST_S1_REPORT.md
"""
import hashlib
import json
import os
import pickle
import re
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, experiment as X, naming as NM, prompts as PM, schema as SG, search as S   # noqa: E402
from cgrow import lang0 as L0, episode as EP, evaluate as EV, testib_rest as TR                         # noqa: E402
from a2 import arcdsl as D                                                                              # noqa: E402

SEEDS = (0, 1, 2)
ARMS = ("S1F", "S-hole", "S-demo", "S-shuffled", "S-enum")
M_RETRIES = 3
ENUM_CPU = 60.0
FAMILY_OF = {"A": "SEL", "B": "MAP", "C": "BLOCK", "D": "COLOUR"}
MENU = """YOUR TASK
Do not write code. Say which kind of grid operation is missing, choosing one family:
A: keep some rows and columns, chosen by a property of each row or column;
B: each output cell copies one input cell at a position computed from its own position (for example a mirror image);
C: cut the grid into equal square blocks and turn each block into one cell;
D: change colours by a fixed rule;
E: none of these.
Also say whether the operation needs an integer parameter.
Reply with exactly one line: FAMILY: <A|B|C|D|E>; PARAMETER: <yes|no>"""


def motivating():
    ev = X.eval_tasks()
    with open(os.path.join(P.RUNS, "prep_v4", "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    tids = sorted([i for i, t in ev.items() if t["partition"] == "M" and recs[i]["decision"] == "INVENT_NEW_OPERATION"],
                  key=lambda i: (ev[i]["family"], ev[i]["template"], i))
    return ev, recs, tids


def donors(ev):
    fams = sorted({t["family"] for t in ev.values() if t["family"]})
    mts = {f: sorted([i for i, t in ev.items() if t["family"] == f and t["partition"] == "M"],
                     key=lambda i: (ev[i]["template"], X.h(i))) for f in fams}
    return {tid: mts[fams[(fi + 1) % len(fams)]][slot % len(mts[fams[(fi + 1) % len(fams)]])]
            for fi, f in enumerate(fams) for slot, tid in enumerate(mts[f])}


def form_messages(task, names, g, rec):
    parts = [PM.card_block(names, g), "PUZZLE (grids: one row per line, one digit per cell)\n" + PM.puzzle_block(task),
             PM.failure_block(rec, names), MENU]
    text = "\n\n".join(parts)
    PM.scan(text)
    return [{"role": "system", "content": PM.SYSTEM}, {"role": "user", "content": text}]


def prep(run_id):
    ev, recs, tids = motivating()
    g0b = X.G0Builder()
    sys_t = X.system_tasks()
    jobs = []
    for s in SEEDS:
        names = NM.Names(g0b.g, s)
        for tid in tids:
            jobs.append({"job_id": f"S1F_{tid}_s{s}", "messages": form_messages(X.as_task(sys_t[tid]), names, g0b.g,
                                                                               recs[tid]),
                         "n": 1, "max_new": 64, "temperature": 0.8, "top_p": 0.95, "seed": X.seed_of(tid, s)})
    with P.open_write(os.path.join(P.RUNS, run_id, "jobs.jsonl")) as f:
        for j in jobs:
            f.write(json.dumps(j) + "\n")
    print(json.dumps({"jobs": len(jobs)}), flush=True)


FORM_RE = re.compile(r"FAMILY\s*:\s*\**\s*([A-E])\b.*?PARAMETER\s*:\s*\**\s*(yes|no)", re.I | re.S)


def parse_form(text):
    m = FORM_RE.search(text or "")
    if not m:
        return None
    return {"family": m.group(1).upper(), "param": m.group(2).lower() == "yes"}


# ------------------------------------------------------------------ system side
class Gates:
    """Cached, charged gate results for SIGMA structures (deterministic, so caching does not change outcomes; the
    CPU recorded at first computation is charged to every unit that uses the result)."""

    def __init__(self, path):
        self.path = path
        self.g0b = X.G0Builder()
        self.sys_t = X.system_tasks()
        with open(os.path.join(P.RUNS, "prep_v4", "records.pkl"), "rb") as f:
            self.recs = pickle.load(f)
        self.solved = {t: X.as_task(self.sys_t[t]) for t, r in self.recs.items() if r["status"] == "solved"}
        self.base_preds = {t: self.recs[t]["base_preds"][0] for t in self.solved}
        self.pool = sorted([t for t, r in self.recs.items() if r["status"] != "solved"], key=lambda i: X.h("pool:" + i))
        self.c = {"nov": {}, "retry": {}, "reg": {}}
        if os.path.exists(path):
            with open(path, "rb") as f:
                self.c = pickle.load(f)
        self.st = SG.by_sid()
        self.dirty = 0

    def save(self, force=False):
        self.dirty += 1
        if force or self.dirty % 10 == 0:
            with open(P.check_write(self.path), "wb") as f:
                pickle.dump(self.c, f)

    def fn(self, st):
        def f(grid, *ints):
            if D.tag(grid) != "G":
                raise D.Bad("type")
            if st.param and (len(ints) != 1 or type(ints[0]) is not int or ints[0] not in SG.KS):
                raise D.Bad("param")
            out = st(grid, *ints)
            if out is None or not D.valid(out) or D.tag(out) != "G":
                raise D.Bad("undefined")
            return out
        return f

    def g1(self, sid):
        st = self.st[sid]
        g = self.g0b()
        L0.add_production(g, "f:sig_" + sid.replace(":", "_"), self.fn(st), 1 if st.param else 0)
        return g

    def novelty(self, sid):
        if sid not in self.c["nov"]:
            t0 = time.process_time()
            st = self.st[sid]
            wit, defined = [], 0
            for th in st.thetas():
                pairs = [(x, st(x, *th)) for x in EP.SIG_PROBES[:12]]
                pairs = [(x, y) for x, y in pairs if y is not None and D.valid(y)]
                if len(pairs) < 4:
                    continue
                defined += 1
                r = S.run(self.g0b(), pairs[:-1], [pairs[-1][0]], budget=EP.DUP_BUDGET, cpu_cap=10.0, want=1)
                if r["fit"] and r["preds"] and r["preds"][0][0] == pairs[-1][1]:
                    wit.append({"theta": list(th), "g0_program": r["program"]})
            self.c["nov"][sid] = {"duplicate": bool(defined) and len(wit) == defined, "witnesses": wit,
                                  "cpu_s": round(time.process_time() - t0, 3)}
            self.save()
        return self.c["nov"][sid]

    def retry(self, sid, tid):
        k = (sid, tid)
        if k not in self.c["retry"]:
            t = X.as_task(self.sys_t[tid])
            r = S.run(self.g1(sid), t["train"], t["test_inputs"])
            self.c["retry"][k] = {"fit": r["fit"], "preds": r["preds"], "program": r["program"], "cpu_s": r["cpu_s"],
                                  "calls": r["calls"]}
            self.save()
        return self.c["retry"][k]

    def regression(self, sid):
        if sid not in self.c["reg"]:
            t0 = time.process_time()
            lost, changed = [], []
            for tid, t in self.solved.items():
                r = self.retry(sid, tid)
                if not r["fit"]:
                    lost.append(tid)
                elif self.base_preds.get(tid) is not None and (not r["preds"] or self.base_preds[tid] not in r["preds"]):
                    changed.append(tid)
            self.c["reg"][sid] = {"lost_fit": lost, "changed_prediction": changed, "checked": len(self.solved),
                                  "cpu_s": round(time.process_time() - t0, 3)}
            self.save()
        return self.c["reg"][sid]

    def promote(self, sid, tid):
        reg = self.regression(sid)
        cpu = reg["cpu_s"]
        if reg["lost_fit"] or reg["changed_prediction"]:
            return {"decision": "rolled_back", "regression": reg, "validation": None, "cpu_s": cpu}
        tried, first = 0, None
        for p in self.pool:
            if p == tid:
                continue
            tried += 1
            r = self.retry(sid, p)
            cpu += r["cpu_s"]
            if r["fit"]:
                first = {"task": p, "program": r["program"]}
                break
        return {"decision": "promoted" if first else "quarantined", "regression": reg,
                "validation": {"tried": tried, "first_new_fit": first}, "cpu_s": round(cpu, 3)}


def spec_candidates(order, sketches):
    seen, out = set(), []
    for rank, sk in enumerate(sketches):
        pairs = [(EP.grid(a), EP.grid(b)) for a, b in sk["pairs"]]
        for st in order:
            if st.sid in seen:
                continue
            ths = SG.consistent(st, pairs)
            if ths:
                seen.add(st.sid)
                out.append({"sid": st.sid, "thetas": [list(t) for t in ths], "sketch_rank": rank,
                            "sketch_form": sk["form"]})
    return out


def run_spec_unit(G, tid, cands):
    rows, retries, cpu, promoted = [], 0, 0.0, None
    for c in cands:
        nov = G.novelty(c["sid"])
        cpu += nov["cpu_s"]
        row = dict(c, duplicate=nov["duplicate"])
        if nov["duplicate"]:
            row["outcome"] = "search_shortcut"
            rows.append(row)
            continue
        if retries >= M_RETRIES:
            break
        retries += 1
        r = G.retry(c["sid"], tid)
        cpu += r["cpu_s"]
        row.update(fit=r["fit"], preds=r["preds"], program=r["program"])
        if r["fit"]:
            pr = G.promote(c["sid"], tid)
            cpu += pr["cpu_s"]
            row["promotion"] = pr["decision"]
            row["validation"] = pr["validation"]
            row["regression"] = {k: pr["regression"][k] for k in ("lost_fit", "changed_prediction", "checked")}
            row["outcome"] = "fits_motivating_task"
            rows.append(row)
            if pr["decision"] == "promoted":
                promoted = c["sid"]
                break
        else:
            row["outcome"] = "no_fit_on_motivating_task"
            rows.append(row)
    return {"rows": rows, "retries": retries, "cpu_s": round(cpu, 2), "promoted": promoted,
            "n_candidates": len(cands)}


def run_enum_unit(G, tid, order):
    rows, cpu, promoted, retries = [], 0.0, None, 0
    for st in order:
        if cpu >= ENUM_CPU:
            break
        nov = G.novelty(st.sid)
        cpu += nov["cpu_s"]
        if nov["duplicate"]:
            continue
        retries += 1
        r = G.retry(st.sid, tid)
        cpu += r["cpu_s"]
        if r["fit"]:
            pr = G.promote(st.sid, tid)
            cpu += pr["cpu_s"]
            rows.append({"sid": st.sid, "fit": True, "preds": r["preds"], "program": r["program"],
                         "promotion": pr["decision"], "outcome": "fits_motivating_task"})
            if pr["decision"] == "promoted":
                promoted = st.sid
                break
    return {"rows": rows, "retries": retries, "cpu_s": round(cpu, 2), "promoted": promoted,
            "structures_tried": retries}


def run(run_id, gen_id):
    rdir = os.path.join(P.RUNS, run_id)
    out_path = os.path.join(rdir, "units.json")
    units = X.load_json(out_path) if os.path.exists(out_path) else {}
    ev, recs, tids = motivating()
    dn = donors(ev)
    reps = X.load_replies(os.path.join(P.RUNS, gen_id, "replies.jsonl"))
    G = Gates(os.path.join(rdir, "gates.pkl"))
    for s in SEEDS:
        order = SG.seeded_order(s)
        for tid in tids:
            for arm in ARMS:
                key = f"{arm}|{tid}|{s}"
                if key in units:
                    continue
                t0 = time.process_time()
                rec = {"arm": arm, "task": tid, "seed": s}
                if arm == "S-enum":
                    res = run_enum_unit(G, tid, order)
                else:
                    sk = recs[tid]["sketches"]
                    o = order
                    if arm == "S-demo":
                        sk = [x for x in sk if x["form"] == "?(I)"]
                    elif arm == "S-shuffled":
                        sk = recs[dn[tid]]["sketches"]
                        rec["donor"] = dn[tid]
                    elif arm == "S1F":
                        rj = reps.get(f"S1F_{tid}_s{s}")
                        txt = rj["replies"][0]["text"] if rj and rj["replies"] else ""
                        form = parse_form(txt)
                        rec["form"], rec["form_text"] = form, txt[:200]
                        rec["form_leak"] = any(w in txt.lower() for w in PM.BANNED)
                        if form and form["family"] in FAMILY_OF:
                            fam = FAMILY_OF[form["family"]]
                            first = [st for st in order if st.family == fam and st.param == form["param"]]
                            o = first + [st for st in order if not (st.family == fam and st.param == form["param"])]
                    res = run_spec_unit(G, tid, spec_candidates(o, sk))
                rec.update(res)
                rec["wall_cpu_s"] = round(time.process_time() - t0, 2)
                units[key] = rec
                with P.open_write(out_path) as f:
                    json.dump(units, f, default=list)
                print(json.dumps({"unit": key, "promoted": res["promoted"], "retries": res["retries"],
                                  "cpu_s": res["cpu_s"]}), flush=True)
    G.save(force=True)


# ------------------------------------------------------------------ evaluator side
def _cast_verdict(st):
    sys.path.insert(0, os.path.join(P.REPO, "experiments", "cora_cast_20261026"))
    import numpy as np
    from cast import absdom as CD, contract_check as CC
    try:
        return CC.check_operator(SG.CastOp(st, CD, np), level="quick")["verdict"]
    except Exception as e:                                               # noqa: BLE001
        return f"ERROR {type(e).__name__}"


def evaluate(run_id, s1run):
    rdir = os.path.join(P.RUNS, run_id)
    ev, recs, tids = motivating()
    rem = X.load_json(os.path.join(P.EVALUATOR_DIR, "REMOVED.json"))
    units = X.load_json(os.path.join(P.RUNS, s1run, "units.json"))
    c7m = X.load_json(os.path.join(P.RUNS, "ib_c7m", "c7m.json"))
    G = Gates(os.path.join(P.RUNS, s1run, "gates.pkl"))
    e_ids = sorted(i for i, t in ev.items() if t["partition"] == "E")
    cache_path = os.path.join(rdir, "struct_scores.json")
    sc = X.load_json(cache_path) if os.path.exists(cache_path) else {}
    out_units = []
    for s in SEEDS:
        for tid in tids:
            u = {"task": tid, "family": ev[tid]["family"], "seed": s, "template": ev[tid]["template"], "arms": {}}
            for arm in ARMS:
                r = units.get(f"{arm}|{tid}|{s}")
                if r is None:
                    continue
                rec_ok = any(row.get("fit") and EV.correct(row.get("preds"), ev[tid]["test_outputs"]) for row in r["rows"])
                th = next((row.get("thetas") for row in r["rows"] if row.get("sid") == r["promoted"]), []) \
                    if r["promoted"] else []
                u["arms"][arm] = {"recovered": rec_ok, "promoted": r["promoted"] is not None, "structure": r["promoted"],
                                  "theta": th, "retries": r["retries"], "cpu_s": r["cpu_s"],
                                  "form": r.get("form"), "n_candidates": r.get("n_candidates")}
            u["arms"]["C7m"] = {"recovered": bool(c7m[tid]["correct"]), "promoted": False, "structure": None,
                                "theta": [], "retries": 0, "cpu_s": c7m[tid].get("cpu_s")}
            out_units.append(u)
    promoted = sorted({a["structure"] for u in out_units for a in u["arms"].values() if a["structure"]})
    for sid in promoted:
        if sid in sc:
            continue
        st = G.st[sid]
        fam_e = {}
        for t in e_ids:
            r = G.retry(sid, t) if t in G.sys_t else None
            if r is None:
                tk = X.as_task(ev[t])
                rr = S.run(G.g1(sid), tk["train"], tk["test_inputs"])
                r = {"fit": rr["fit"], "preds": rr["preds"]}
            fam_e[t] = bool(r["fit"]) and EV.correct(r["preds"], ev[t]["test_outputs"])
        best_f, agree = None, {}
        for f in rem["removed"]:
            ref = L0.reference_fn(f)
            grids = [EV.g(a) for t in e_ids if ev[t]["family"] == f for a, _ in ev[t]["train"]] + list(EV.REF_PROBES)
            tab = {}
            for p in [tuple(x) for x in rem["params"][f]]:
                ths = [p] if st.param and len(p) == 1 else ([()] if not st.param else [])
                for th in ths:
                    ok = tot = 0
                    for x in grids:
                        try:
                            w = ref(x, *p)
                        except Exception:                                # noqa: BLE001
                            w = None
                        v = st(x, *th)
                        if w is None and v is None:
                            continue
                        tot += 1
                        ok += w == v
                    tab[str(list(p))] = round(ok / tot, 4) if tot else None
            if tab and max(v or 0 for v in tab.values()) > max([v or 0 for v in agree.values()] or [-1]):
                best_f, agree = f, tab
        wit = []
        for th in st.thetas()[:2]:
            pairs = [(x, st(x, *th)) for x in EP.SIG_PROBES[:12]]
            pairs = [(x, y) for x, y in pairs if y is not None]
            if len(pairs) < 4:
                continue
            r = S.run(G.g0b(), pairs[:-1], [pairs[-1][0]], budget=EV.KIND_BUDGET, cpu_cap=30.0, want=1)
            wit.append(bool(r["fit"] and r["preds"] and r["preds"][0][0] == pairs[-1][1]))
        sc[sid] = {"family_best": best_f, "agreement": agree,
                   "e_same": sum(v for t, v in fam_e.items() if ev[t]["family"] == best_f),
                   "e_other": sum(v for t, v in fam_e.items() if ev[t]["family"] != best_f),
                   "e_correct": [t for t, v in fam_e.items() if v],
                   "kind": "macro" if wit and all(wit) else ("expansion" if wit else "undetermined"),
                   "cast": _cast_verdict(st)}
        with P.open_write(cache_path) as f:
            json.dump(sc, f, indent=1)
        print(json.dumps({"structure": sid} | {k: sc[sid][k] for k in ("family_best", "e_same", "kind", "cast")}),
              flush=True)
    G.save(force=True)
    flat = []
    for u in out_units:
        v = {"task": u["task"], "family": u["family"], "seed": u["seed"]}
        for arm, a in u["arms"].items():
            v[arm] = {"recovered": a["recovered"], "promoted": a["promoted"]}
        flat.append(v)
    comp = {"S1F_vs_C7m": TR._compare(flat, "S1F", "C7m")}
    for a, b in (("S1F", "S-hole"), ("S-hole", "S-demo"), ("S-hole", "S-shuffled"), ("S-hole", "S-enum"),
                 ("S1F", "S-enum"), ("S-enum", "C7m"), ("S-hole", "C7m")):
        comp[f"{a}_vs_{b}"] = TR._compare(flat, a, b)
    for a, b in (("S1F", "S-hole"), ("S1F", "S-enum"), ("S-hole", "S-demo")):
        comp[f"{a}_vs_{b}:promoted"] = TR._compare(flat, a, b, "promoted")
    pc = comp["S1F_vs_C7m"]
    if pc:
        if pc["mcnemar_p"] < 0.05 and pc["family_ci95"] and pc["family_ci95"][0] > 0:
            pc["decision"] = "S1F beats matched search"
        elif pc["mcnemar_p"] < 0.05 and pc["family_ci95"] and pc["family_ci95"][1] < 0:
            pc["decision"] = "matched search beats S1F"
        else:
            pc["decision"] = "tie" if pc["only_S1F"] == pc["only_C7m"] else "inconclusive"
    from harness import ledger as LG
    rows = [r for r in LG.read(P.LEDGER) if r.get("family") == "CGROW" and str(r.get("run_id", "")).startswith("s1_")
            and r.get("status") not in ("START",)]
    budget = {"cpu_h": round(sum(r.get("cpu_h") or 0 for r in rows), 3),
              "gpu_h": round(sum(r.get("gpu_wall_h") or 0 for r in rows), 3)}
    res = {"implementation": "capability_growth_20261027 (cgrow/s1.py)", "units": out_units, "structures": sc,
           "comparisons": comp, "budget": budget,
           "forms": {k: v.get("form") for k, v in units.items() if k.startswith("S1F|")},
           "form_leaks": sum(bool(v.get("form_leak")) for k, v in units.items() if k.startswith("S1F|"))}
    with P.open_write(os.path.join(rdir, "results.json")) as f:
        json.dump(res, f, indent=1, default=list)
    write_report(res, ev)
    print(json.dumps({"primary": pc}), flush=True)


def write_report(res, ev):
    comp = res["comparisons"]
    arms = ARMS + ("C7m",)
    L = ["# Test S1 report (written automatically by the detached chain)", "",
         "Protocol `protocols/TEST_S1_PROTOCOL.md` (frozen; sha256 in `partitions/TEST_S1_FREEZE.json`); shared "
         "specification `records/NOV1_S1_SHARED_SPEC.md`. Claim limit: all four removed capabilities are structures "
         "of the schema language, so S1 tests whether CORA's failure-derived specification selects the right member "
         "of a known space, not open invention. Results: `runs/s1_eval/results.json`.", "",
         "## Primary: S1F (CORA hole specification + neural form) vs C7m (matched G0 search, 150 CPU-s)", "",
         f"- {TR._fmt(comp['S1F_vs_C7m'])}.",
         f"- **Decision: {comp['S1F_vs_C7m']['decision'] if comp['S1F_vs_C7m'] else 'n/a'}.**", "",
         "## Secondary (no decision weight)", ""]
    for k, v in comp.items():
        if k != "S1F_vs_C7m":
            L.append(f"- {k}: {TR._fmt(v)}.")
    L += ["", "## Recovered units per family (of 3 seeds x tasks)", "",
          "| family | tasks | " + " | ".join(arms) + " |", "|---|---|" + "---|" * len(arms)]
    fams = sorted({u["family"] for u in res["units"]})
    for f in fams:
        us = [u for u in res["units"] if u["family"] == f]
        L.append(f"| {f} | {len({u['task'] for u in us})} | " +
                 " | ".join(f"{sum(u['arms'][a]['recovered'] for u in us if a in u['arms'])}/{len(us)}" for a in arms)
                 + " |")
    L.append("| all | 11 | " + " | ".join(
        f"{sum(u['arms'][a]['recovered'] for u in res['units'] if a in u['arms'])}/{len(res['units'])}" for a in arms)
        + " |")
    L += ["", "Promoted units: " + ", ".join(
        f"{a} {sum(u['arms'][a]['promoted'] for u in res['units'] if a in u['arms'])}" for a in ARMS) + ".",
          "Mean charged CPU-s per unit: " + ", ".join(
        f"{a} {round(sum(u['arms'][a]['cpu_s'] or 0 for u in res['units'] if a in u['arms']) / len(res['units']), 1)}"
        for a in arms) + ".", "", "## Promoted structures (evaluator)", "",
          "| structure | best-matching removed capability | agreement by parameter | E same family | E other | kind (vs G0) | CAST contract |",
          "|---|---|---|---|---|---|---|"]
    for sid, v in sorted(res["structures"].items()):
        L.append(f"| {sid} | {v['family_best']} | {v['agreement']} | {v['e_same']}/6 | {v['e_other']} | {v['kind']} | "
                 f"{v['cast']} |")
    forms = [v for v in res["forms"].values()]
    fc = {}
    for v in forms:
        k = "unparsed" if v is None else f"{v['family']}/{'param' if v['param'] else 'none'}"
        fc[k] = fc.get(k, 0) + 1
    L += ["", f"Neural forms (S1F, 33 replies): {fc}; replies naming a removed capability: {res['form_leaks']}.",
          f"Budget (ledger, runs s1_*): {res['budget']['cpu_h']} CPU-h, {res['budget']['gpu_h']} GPU-h "
          "(soft ceiling 2.5 CPU-h, 0.5 GPU-h).", ""]
    with P.open_write(os.path.join(P.REPORTS, "TEST_S1_REPORT.md")) as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep":
        prep(sys.argv[2])
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3])
    elif cmd == "evaluate":
        evaluate(sys.argv[2], sys.argv[3])
