"""v1.9 audit analysis: rows -> outputs/tti/v19_audit_report.json.

Protocol sections 8 to 13: the rejection events, their codes and
mechanisms, reproducibility (repeat A in process, repeat B in a fresh
process), decision identity under tracing, the clock diagnosis, selection
quality (H4) and the descriptive splits. Reads only the audit's own files.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))
import v19_audit_dev as D                                         # noqa: E402


def sig(run):
    rc = run.get("reason") or {}
    return {"accepted": run["accepted"], "codes": rc.get("codes"),
            "fold_codes": [[f["hold"], f["code"]] for f in rc.get("folds", [])],
            "loo_failed": (run.get("loo") or {}).get("failed")}


def norm(s):
    return json.loads(json.dumps(s))


def main():
    corpus = json.load(open(D.CORPUS_FILE))["tasks"]
    rows = sorted(D.read_rows(D.ROWS), key=lambda r: r["index"])
    m = D.stop_prefix(rows, len(corpus))
    inside = [r for r in rows if m is not None and r["index"] < m]
    audited = [r for r in inside if r.get("status") == "AUDITED"]
    p2 = D.read_rows(D.ROWS2)
    rep_b = {(r["index"], r["run"]): r for r in p2 if r["kind"] == "repeat_B"}
    load = collections.defaultdict(dict)
    for r in p2:
        if r["kind"] == "load":
            load[(r["index"], r["run"])][r["clock"]] = r
    ident = {(r["index"], r["run"]): r for r in p2 if r["kind"] == "identity"}

    statuses = collections.Counter(r.get("status") for r in inside)
    cats = collections.Counter(r["category"] for r in audited)
    seen = {t["index"]: t["seen_v18_dev"] for t in corpus}

    events, runs_rejected, runs_total = [], [], 0
    reproduce = {}
    for r in audited:
        runs = [("FULL", r["audit"]["FULL"])] + [(f"FOLD_{f['fold']}", f) for f in r["audit"]["FOLDS"]]
        for name, run in runs:
            runs_total += 1
            key = (r["index"], name)
            s1 = norm(sig(run))
            ra = r.get("repeat_A", {}).get(name)
            rb = rep_b.get(key, {}).get("signature")
            same_a = None if ra is None else norm({k: ra[k] for k in s1}) == s1
            same_b = None if rb is None else norm({k: rb[k] for k in s1}) == s1
            reproduce[key] = {"A": same_a, "B": same_b}
            if run["accepted"]:
                continue
            runs_rejected.append({"index": r["index"], "run": name, "codes": s1["codes"],
                                  "category": r["category"], "family": r["family"],
                                  "level": (r["proposer"].get("selection") or {}).get("level"),
                                  "repeat_A": same_a, "repeat_B": same_b})
            for f in (run.get("reason") or {}).get("folds", []):
                events.append({"index": r["index"], "run": name, "hold": f["hold"], "code": f["code"],
                               "mechanism": f["mechanism"]["class"],
                               "h1_kind": f["mechanism"].get("h1_kind"),
                               "permissive_predicts": f["mechanism"]["permissive_predicts"],
                               "competitor": f.get("competitor"), "overlay": f.get("overlay"),
                               "fit_detail": f.get("fit_detail"),
                               "reproduces": bool(same_a and same_b),
                               "family": r["family"],
                               "level": (r["proposer"].get("selection") or {}).get("level")})
    n_ev = len(events)
    good = [e for e in events if not e["code"].startswith("OTHER_EXPLICIT_REASON") and e["reproduces"]]
    share = len(good) / n_ev if n_ev else None
    code_dist = collections.Counter(e["code"] for e in events)
    mech_dist = collections.Counter(e["mechanism"] + (f":{e['h1_kind']}" if e["h1_kind"] else "")
                                    for e in events)
    mech_major = collections.Counter(e["mechanism"] for e in events)
    dominant = None
    if n_ev:
        top, cnt = mech_major.most_common(1)[0]
        if cnt * 2 >= n_ev:
            dominant = top
    comp_dist = collections.Counter(
        json.dumps({k: (e["competitor"] or {}).get(k) for k in ("program_class", "split", "mode",
                                                                 "parameter_class")}, sort_keys=True)
        for e in events if e["code"].startswith("RANKED_BELOW_COMPETITOR"))

    #  7 versus 6, same bytes: category A tasks
    seven_six = []
    for r in audited:
        if r["category"] != "A":
            continue
        full = r["audit"]["FULL"]
        for f in r["audit"]["FOLDS"]:
            if f["accepted"]:
                continue
            seven_six.append({
                "index": r["index"], "fold": f["fold"],
                "bytes_identical": f["production_sha256"] == r["production_sha256"],
                "full": {"loo": full["loo"], "top_candidates": full["reason"]["top"]["candidates"],
                         "overlay_rank": full["reason"]["top"]["overlay_rank"],
                         "fits": (full.get("tables") or {}).get("fits"),
                         "phases": [p["phase"] for p in full["reason"]["phases"]],
                         "seconds": full["timing"]["seconds"]},
                "fold_run": {"loo": f["loo"], "top_candidates": f["reason"]["top"]["candidates"],
                             "overlay_rank": f["reason"]["top"]["overlay_rank"],
                             "fits": (f.get("tables") or {}).get("fits"),
                             "phases": [p["phase"] for p in f["reason"]["phases"]],
                             "codes": f["reason"]["codes"], "seconds": f["timing"]["seconds"]}})

    #  descriptive splits: same-e fold rejection by level, family, seen
    def split(keyf):
        out = collections.defaultdict(lambda: {"tasks": 0, "folds": 0, "folds_rejected": 0,
                                               "full_rejected": 0})
        for r in audited:
            k = keyf(r)
            o = out[k]
            o["tasks"] += 1
            o["full_rejected"] += not r["audit"]["FULL"]["accepted"]
            o["folds"] += len(r["audit"]["FOLDS"])
            o["folds_rejected"] += sum(1 for f in r["audit"]["FOLDS"] if not f["accepted"])
        return dict(out)
    by_level = split(lambda r: (r["proposer"].get("selection") or {}).get("level"))
    by_family = split(lambda r: r["family"])
    by_seen = split(lambda r: "seen" if seen.get(r["index"]) else "unseen")

    #  clock diagnosis
    load_rows = []
    for key, clocks in sorted(load.items()):
        r = next(x for x in audited if x["index"] == key[0])
        run = r["audit"]["FULL"] if key[1] == "FULL" else r["audit"]["FOLDS"][int(key[1].split("_")[1])]
        s1 = norm(sig(run))
        entry = {"index": key[0], "run": key[1], "WALL": {"accepted": s1["accepted"], "codes": s1["codes"]}}
        for c, x in clocks.items():
            s = x.get("signature") or {}
            entry[c] = {"accepted": s.get("accepted"), "codes": s.get("codes"),
                        "same_decision": s.get("accepted") == s1["accepted"],
                        "same_codes": norm(s.get("codes")) == s1["codes"],
                        "seconds": x.get("seconds"), "error": x.get("error")}
        load_rows.append(entry)
    load_summary = {c: {"runs": sum(1 for e in load_rows if c in e),
                        "decision_changed": sum(1 for e in load_rows if c in e and not e[c]["same_decision"]),
                        "codes_changed": sum(1 for e in load_rows if c in e and not e[c]["same_codes"])}
                    for c in ("CPU1", "CPU10")}

    #  decision identity under tracing
    id_rows = []
    for key, x in sorted(ident.items()):
        r = next(y for y in audited if y["index"] == key[0])
        run = r["audit"]["FULL"] if key[1] == "FULL" else r["audit"]["FOLDS"][int(key[1].split("_")[1])]
        id_rows.append({"index": key[0], "run": key[1],
                        "same_accepted": x.get("accepted") == run["accepted"],
                        "same_program": x.get("program_sha") == run["program_sha"],
                        "same_events": x.get("events") == run["events"],
                        "same_heldout": x.get("heldout_exact") == run.get("heldout_exact")})

    #  H4
    sq = [r.get("selection_quality") or {} for r in audited]
    h4 = {"tasks": len(sq), "H4": sum(1 for s in sq if s.get("H4")),
          "selected_fails_proxy": sum(1 for s in sq if s.get("selected_proxy") is not None
                                      and not all(s["selected_proxy"])),
          "errors": sum(1 for s in sq if "error" in s),
          "H4_in_category": dict(collections.Counter(r["category"] for r, s in zip(audited, sq)
                                                     if s.get("H4")))}

    success = {
        "rejection_events": n_ev,
        "mechanistic_and_reproducing": len(good),
        "share": share,
        "threshold": 0.90,
        "pass": bool(share is not None and share >= 0.90),
        "identity_all_same": bool(id_rows) and all(all(v for k, v in e.items() if k.startswith("same"))
                                                    for e in id_rows),
        "other_explicit": sum(1 for e in events if e["code"].startswith("OTHER_EXPLICIT_REASON")),
        "not_reproducing": sum(1 for e in events if not e["reproduces"]),
    }
    report = {
        "stop_prefix": m, "statuses": dict(statuses), "audited": len(audited),
        "categories": dict(cats),
        "runs": {"total": runs_total, "rejected": len(runs_rejected)},
        "success": success,
        "codes": dict(code_dist), "mechanisms": dict(mech_dist), "mechanisms_major": dict(mech_major),
        "dominant_mechanism": dominant,
        "competitors": dict(comp_dist),
        "reproduce_runs": {"repeated_A": sum(1 for v in reproduce.values() if v["A"] is not None),
                           "A_false": sum(1 for v in reproduce.values() if v["A"] is False),
                           "repeated_B": sum(1 for v in reproduce.values() if v["B"] is not None),
                           "B_false": sum(1 for v in reproduce.values() if v["B"] is False)},
        "rejected_runs": runs_rejected,
        "seven_versus_six": seven_six,
        "by_level": by_level, "by_family": by_family, "by_seen": by_seen,
        "load": {"summary": load_summary, "runs": load_rows},
        "identity": id_rows,
        "selection_quality": h4,
        "events": events,
    }
    json.dump(report, open(D.REPORT, "w"), indent=1, default=str)
    print(json.dumps({k: report[k] for k in ("stop_prefix", "audited", "categories", "runs", "success",
                                             "codes", "mechanisms", "dominant_mechanism")},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
