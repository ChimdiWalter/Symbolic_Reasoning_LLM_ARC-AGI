"""U5 failure records from the frozen CORA component (PROTOCOL.md section 8.2-8.3), calibration only.
    u5probe.py build DS ROLE      (<python environment>) probe tasks from ROLE parents (induction) of DS -> work/DS/probes/
    u5probe.py run DS             (<second python environment>, -I -B) cast_selective_v2.evaluate on every task in a forked child
    u5probe.py summarize DS       (<python environment>) failure records, expressibility per class
Windows use U1's frozen adapter (window_ids, colours, scale_of) unchanged; target windows sample the corrected label
image at the same centre and scale (U1's rule that forces the centre object applies to the input window only, and to
neither window for ADD, which has no centre object in S)."""
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R = "/path/to/repository"
U1 = os.path.join(R, "experiments/universality_submitted_pkg_20261101/scripts")
U2 = os.path.join(R, "experiments/universality_similar_problems_20261102")
DATA = "/path/to/bio_data"
W = os.path.join(DATA, "work")
ORDER = ("SPLIT", "MERGE", "FILL", "GROW", "SHRINK", "DELETE", "ADD")
MAX_TASKS, GROUP, MIN_INST = 40, 6, 12


def h8(s):
    return hashlib.sha256(s.encode()).hexdigest()


# ------------------------------------------------------------------------------------------------ build ------------
def _window_at(lab, y, x, s, AD):
    """U1's window sampling and gap rule (window_ids) without its centre-object rule."""
    Wn, HALF = AD.W, AD.HALF
    off = (np.arange(Wn) - HALF) / s
    rr, cc = np.rint(y + off).astype(int), np.rint(x + off).astype(int)
    okr, okc = (rr >= 0) & (rr < lab.shape[0]), (cc >= 0) & (cc < lab.shape[1])
    win = np.zeros((Wn, Wn), np.int64)
    win[np.ix_(okr, okc)] = lab[np.ix_(rr[okr], cc[okc])]
    diff = np.zeros((Wn, Wn), bool)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sh = np.zeros_like(win)
        sh[max(-dy, 0):Wn + min(-dy, 0), max(-dx, 0):Wn + min(-dx, 0)] = win[max(dy, 0):Wn + min(dy, 0),
                                                                             max(dx, 0):Wn + min(dx, 0)]
        diff |= (sh != 0) & (sh != win) & (win != 0)
    win[diff] = 0
    return win


def _means(lab, I):
    n = int(lab.max())
    a = np.maximum(np.bincount(lab.ravel(), minlength=n + 1), 1)
    return np.bincount(lab.ravel(), I.ravel().astype(np.float64), n + 1) / a


def build(ds, role, start="S", records_only=False):
    sys.path.insert(0, HERE)
    sys.path.insert(0, U1)
    import adapter as AD        # U1's frozen adapter (window_ids, colours, scale_of), unchanged
    import u5core as C
    import u5tax as TX
    man = json.load(open(os.path.join(W, ds, "DATA_MANIFEST.json")))
    uids = sorted(u for u, v in man["images"].items() if v["role"] == role)
    inst = {c: [] for c in ORDER}
    store = {}
    for u in uids:
        S = np.load(os.path.join(W, ds, "seg", start, f"{u}.npz"))["labels"]
        z = np.load(os.path.join(W, ds, "ref_cal", f"{u}.npz"))
        ref, ign = z["ref"], z["ign"]
        I = np.load(os.path.join(W, ds, "int", f"{u}.npy")).astype(np.float32)
        info = TX.classify(S, ref, ign)
        store[u] = (S, ref, ign, I, info)
        for o, c in info["cls"].items():
            inst[c].append((u, int(o)))
        for rr in info["missed"]:
            inst["ADD"].append((u, -int(rr)))
    out = {"dataset": ds, "role": role, "start": start, "instances": {c: len(v) for c, v in inst.items()},
           "tasks": {}}
    tasks, targets = {}, {}
    for ci, c in enumerate(ORDER):
        lst = sorted(inst[c], key=lambda x: h8(f"{x[0]}:{x[1]}"))
        if len(lst) < MIN_INST:
            continue
        perm = np.random.default_rng(3000000 + 1000 * ci).permutation(len(lst))
        groups = [[lst[i] for i in perm[k:k + GROUP]] for k in range(0, len(lst) - GROUP + 1, GROUP)][:MAX_TASKS]
        for t, g in enumerate(groups):
            pairs = []
            for (u, o) in g:
                S, ref, ign, I, info = store[u]
                s = AD.scale_of(np.bincount(S.ravel(), minlength=int(S.max()) + 1).astype(float))
                if o > 0:
                    m = S == o
                    sub = {"cls": {o: c}, "missed": []}
                else:
                    m = ref == -o
                    sub = {"cls": {}, "missed": [-o]}
                ys, xs = np.nonzero(m)
                y, x = float(ys.mean()), float(xs.mean())
                info2 = dict(info)
                info2["cls"], info2["missed"] = sub["cls"], sub["missed"]
                if c == "MERGE":                       # every fragment of the reference object is part of the fix
                    rd = [int(info["r"][k]) for k in info["by_p"][o] if info["frac"][k] >= TX.COVER
                          and info["inside_count"][info["r"][k]] >= 2]
                    info2["cls"] = {q: "MERGE" for q, cq in info["cls"].items() if cq == "MERGE" and any(
                        int(info["r"][k]) in rd and info["frac"][k] >= TX.COVER for k in info["by_p"][q])}
                T = TX.corrected(S, ref, info2, {c})
                colS = AD.colours(_means(S, I))
                colT = AD.colours(_means(T, I))
                if o > 0:
                    cy = np.zeros(int(S.max()) + 1)
                    cx = np.zeros(int(S.max()) + 1)
                    cy[o], cx[o] = y, x
                    wi = AD.window_ids(S, o, cy, cx, s)
                else:
                    wi = _window_at(S, y, x, s, AD)
                wt = _window_at(T, y, x, s, AD)
                pairs.append({"input": colS[wi].tolist(), "output": colT[wt].tolist(), "src": [u, o]})
            tid = f"{c.lower()}_{t:03d}"
            tasks[tid] = {"train": [{"input": p["input"], "output": p["output"]} for p in pairs[:4]],
                          "test": [{"input": p["input"]} for p in pairs[4:]]}
            targets[tid] = {"class": c, "query_outputs": [p["output"] for p in pairs[4:]],
                            "src": [p["src"] for p in pairs]}
            out["tasks"][c] = out["tasks"].get(c, 0) + 1
    d = os.path.join(W, ds, "probes", role)
    os.makedirs(d, exist_ok=True)
    json.dump(tasks, open(os.path.join(d, "tasks.json"), "w"))
    json.dump(targets, open(os.path.join(d, "targets.json"), "w"))
    out["tasks_sha256"] = hashlib.sha256(open(os.path.join(d, "tasks.json"), "rb").read()).hexdigest()
    json.dump(out, open(os.path.join(d, "BUILD.json"), "w"), indent=1)
    print(json.dumps(out))


# ------------------------------------------------------------------------------------------------ run --------------
def run(ds, role):
    import resource
    sys.path.insert(0, os.path.join(U2, "systems", "h"))
    import cast_selective_v2 as CS
    d = os.path.join(W, ds, "probes", role)
    tasks = json.load(open(os.path.join(d, "tasks.json")))
    od = os.path.join(d, "runs")
    os.makedirs(od, exist_ok=True)
    for tid in sorted(tasks):
        p = os.path.join(od, f"{tid}.json")
        if os.path.exists(p):
            continue
        rfd, wfd = os.pipe()
        t0 = time.time()
        pid = os.fork()
        if pid == 0:
            os.close(rfd)
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (40, 45))
                c0 = time.process_time()
                rep = CS.evaluate(tasks[tid], cpu_s=15.0, wall_s=30.0)
                rec = {"status": rep.get("status"), "cpu_s": round(time.process_time() - c0, 3),
                       "modules": {m: {k: ev.get(k) for k in ("status", "n_fits", "n_behaviours", "genuine_loo",
                                                             "v1_loo", "restart_stable", "program")}
                                   for m, ev in rep.get("modules", {}).items()},
                       "accepted": [{k: q["accepted"][k] for k in ("B1", "B3")} for q in rep["queries"]],
                       "candidate": [q["candidate"] for q in rep["queries"]]}
            except BaseException as e:                       # noqa: BLE001
                rec = {"status": f"CHILD_ERROR:{type(e).__name__}"}
            os.write(wfd, json.dumps(rec).encode())
            os.close(wfd)
            os._exit(0)
        os.close(wfd)
        chunks = []
        while True:
            b = os.read(rfd, 1 << 20)
            if not b:
                break
            chunks.append(b)
        os.close(rfd)
        _, st, ru = os.wait4(pid, 0)
        try:
            rec = json.loads(b"".join(chunks).decode())
        except Exception:                                    # noqa: BLE001
            rec = {"status": f"CHILD_KILLED:{st}"}
        rec["child_cpu_s"] = round(ru.ru_utime + ru.ru_stime, 3)
        rec["wall_s"] = round(time.time() - t0, 3)
        json.dump(rec, open(p, "w"))
    print("ran", len(tasks), "probe tasks")


# ------------------------------------------------------------------------------------------------ summarize --------
def summarize(ds, role, relabel=None):
    """Failure records and expressibility. `relabel` maps class -> class (the SHUFFLED arm's derangement)."""
    d = os.path.join(W, ds, "probes", role)
    targets = json.load(open(os.path.join(d, "targets.json")))
    per = {}
    recs = []
    cpu = 0.0
    for tid, tg in sorted(targets.items()):
        p = os.path.join(d, "runs", f"{tid}.json")
        if not os.path.exists(p):
            continue
        r = json.load(open(p))
        cpu += float(r.get("child_cpu_s") or 0)
        c = tg["class"] if relabel is None else relabel[tg["class"]]
        ok = r.get("status") == "OK"
        nofit = ok and all((m.get("n_fits") or 0) == 0 for m in r.get("modules", {}).values())
        acc = [a.get("B3") for a in r.get("accepted", [])] if ok else []
        correct = [a is not None and a == q for a, q in zip(acc, tg["query_outputs"])]
        failure = (not ok) or nofit or not any(a is not None for a in acc) or not all(correct)
        recs.append({"task": tid, "class": c, "status": r.get("status"), "no_fit": nofit,
                     "n_fits": {m: v.get("n_fits") for m, v in r.get("modules", {}).items()},
                     "accepted_B3": [a is not None for a in acc],
                     "accepted_B1": [a.get("B1") is not None for a in r.get("accepted", [])] if ok else [],
                     "query_correct": correct, "failure_record": failure})
        s = per.setdefault(c, {"tasks": 0, "resolved": 0, "unresolved_timeout_or_error": 0, "no_fit": 0,
                               "fit_not_accepted_B3": 0, "accepted_B3_queries": 0, "accepted_B3_correct": 0,
                               "accepted_B3_incorrect": 0, "failure_records": 0})
        s["tasks"] += 1
        s["resolved"] += int(ok)
        s["unresolved_timeout_or_error"] += int(not ok)
        s["no_fit"] += int(nofit)
        s["fit_not_accepted_B3"] += int(ok and not nofit and not any(a is not None for a in acc))
        s["accepted_B3_queries"] += sum(a is not None for a in acc)
        s["accepted_B3_correct"] += sum(bool(x) for x in correct)
        s["accepted_B3_incorrect"] += sum(a is not None for a in acc) - sum(bool(x) for x in correct)
        s["failure_records"] += int(failure)
    for c, s in per.items():
        s["no_fit_rate"] = s["no_fit"] / s["resolved"] if s["resolved"] else None
        # Amendment 3: a bounded search that finds no fitting program is NOT_FOUND_WITHIN_BUDGET (15 CPU-s, the frozen
        # package's own search, U1's window encoding); it is not a proof that the frozen language cannot express it.
        s["not_found_within_budget"] = bool(s["resolved"] >= 6 and s["no_fit"] >= 0.5 * s["resolved"])
    return {"per_class": per, "records": recs, "probe_cpu_s": round(cpu, 1)}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build(sys.argv[2], sys.argv[3])
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3])
    elif cmd == "summarize":
        out = summarize(sys.argv[2], sys.argv[3])
        p = os.path.join(W, sys.argv[2], "probes", sys.argv[3], "FAILURE_RECORDS.json")
        json.dump(out, open(p, "w"), indent=1)
        print(json.dumps(out["per_class"]))
