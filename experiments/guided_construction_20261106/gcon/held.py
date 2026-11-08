"""The held run (PROTOCOL.md section 7). Refused without the GO (gate.py); in rehearsal mode (GC_REHEARSAL=1) the
same path runs on a fixed list of SOURCE tasks standing in for the held tasks and never opens a held task.

    python -s -B run.py held OUT_DIR SET I/K        SET: 1d_arc, concept_arc, mini_arc (held halves) or arc2

Per task: the reference `objgrow.arm.construction_answers(task, ops=(), g0b=<seed-independent builder>)`; when its
base search fails and the task has at least two demonstrations, the three holes (the controller's sketches, as the
reference builds them) and every arm of config/CONFIG.json through the test's constructor (`engine.run_hole`), the
retries shared through one cache seeded with the reference's retries. Writes OUT_DIR/<SET>/rows.I.jsonl, one line
per task (appended; a task already in the file is skipped).
"""
import json
import os
import sys
import time
import traceback

from gcon import env as E, gate as GT, engine as EN, features as FT, model as MD, policy as PO, units as UN
from objgrow import env as OE, arm as OA, grow as GR
from ngrow import data as DT
from cgrow import controller as CT
from a2 import arcdsl as D

CONFIG = os.path.join(E.STUDY, "config", "CONFIG.json")
BENCHES = ("1d_arc", "concept_arc", "mini_arc")
#: rehearsal stand-ins: source tasks only (the first units of each benchmark in sha256 order)
REHEARSAL_PER_BENCH = 2


def rnd(xs):
    return [round(x, 5) for x in xs]


def config():
    c = E.load(CONFIG)
    return c


def load_models(c):
    md = os.path.join(E.STUDY, "models")
    full = E.load(os.path.join(md, "full.json"))
    M = {"guide": MD.Model.from_json(full["guide"]), "linear": MD.Model.from_json(full["linear"]),
         "frequency": MD.Frequency.from_json(full["frequency"])}
    M["lobo"] = {b: MD.Model.from_json(E.load(os.path.join(md, f"lobo_{b}.json"))["guide"]) for b in BENCHES}
    return M


def arc2_tasks():
    from ngrow import score as SA
    path = SA.ARC2_CHALLENGES
    if E.sha_file(path) != SA.ARC2_SHA256["arc-agi_evaluation_challenges.json"]:
        raise GT.GateRefused("ARC-AGI-2 evaluation challenges changed")
    with open(path, encoding="utf-8") as f:
        ch = json.load(f)
    return {t: {"train": [(DT.grid(p["input"]), DT.grid(p["output"])) for p in v["train"]],
                "test_inputs": [DT.grid(p["input"]) for p in v["test"]]} for t, v in sorted(ch.items())}


def task_list(name):
    """[(bench or 'arc2', family, id)] and {id: task}; behind the GO (rehearsal: source stand-ins)."""
    GT.require_go()
    if GT.REHEARSAL:
        import hashlib
        out, tasks = [], {}
        benches = BENCHES if name == "arc2" else (name,)
        for b in benches:
            src = sorted(DT.half("source", (b,)), key=lambda r: hashlib.sha256(f"rehearsal:{r[2]}".encode()).hexdigest())
            pick = src[:REHEARSAL_PER_BENCH]
            out += [(b, f, t) for _, f, t in pick]
            tasks.update({t: DT.tasks(b)[t] for _, _, t in pick})
        return out, tasks
    if name == "arc2":
        tasks = arc2_tasks()
        return [("arc2", "arc2", t) for t in sorted(tasks)], tasks
    rows = DT.half("held", (name,))
    all_t = DT.tasks(name)
    return rows, {t: all_t[t] for _, _, t in rows}


def slim_ref(ref):
    return {k: ref.get(k) for k in ("fit", "preds", "program", "stage", "candidates", "candidates_loo", "retries",
                                    "op", "cpu_s", "base_cpu_s", "construction_cpu_s", "counts")}


def slim_cand(c):
    return {"sid": c["op"].sid, "spec": c["op"].to_json()["spec"], "loo": bool(c["loo"]), "proposing": c["proposing"],
            "group": c["group"], "simplicity": list(c["simplicity"]), "view": c.get("view")}


class Runner:
    def __init__(self, set_name, out_path, c, M):
        self.set, self.c, self.M = set_name, c, M
        self.g0b = E.g0_builder()
        self.fns = D.guarded(D.load()[0])
        self.R = UN.Retrier(self.g0b, path=None)
        self.out_path = out_path
        self.donor_cache = {}
        self.go_sha = GT.require_go()
        self.freeze_sha = E.sha_file(GT.FREEZE)

    def arms(self):
        return self.c["arms_arc2"] if self.set == "arc2" else self.c["arms_held"]

    def holes(self, task):
        """[(HoleState, features)] of the task's holes, and the work: the sketches and the pair analysis (shared by
        every arm) and the features (used by the learned arms only), with the features' content comparisons."""
        w = {"sketches_cpu_s": 0.0, "pair_analysis_cpu_s": 0.0, "features_cpu_s": 0.0, "feature_comparisons": 0}
        t0 = time.process_time()
        plug_g = OA.GT.ObjPlugin(self.g0b).g0()
        sks, _ = CT.sketches(task["train"], plug_g)
        skd = [{"form": c["form"], "outer": c["outer"], "inner": c["inner"], "score": c["score"], "pairs": c["pairs"]}
               for c in sks]
        w["sketches_cpu_s"] = time.process_time() - t0
        out = []
        for rank, sk in enumerate(skd):
            pairs = [(OE.grid(a), OE.grid(b)) for a, b in sk["pairs"]]
            ti = GR.hole_test_inputs(sk, task, self.fns)
            a0 = time.process_time()
            hs = EN.HoleState(pairs, ti, meta={"rank": rank, "inner": sk.get("inner"), "outer": sk.get("outer")})
            a1 = time.process_time()
            c0 = FT.CMP["n"]
            fe = FT.hole_features(hs)
            w["pair_analysis_cpu_s"] += a1 - a0
            w["features_cpu_s"] += time.process_time() - a1
            w["feature_comparisons"] += FT.CMP["n"] - c0
            out.append((hs, {b: rnd(x) for b, x in fe.items()}))
        return out, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in w.items()}

    def donor_holes(self, bench, tid, tasks_all):
        from ngb import object_arm as NOA
        d = NOA.donor_of(bench, tid, half="source" if GT.REHEARSAL else "held")
        if d is None:
            return None
        if d not in self.donor_cache:
            t = tasks_all(bench).get(d)
            self.donor_cache[d] = self.holes(t) if t is not None and len(t["train"]) >= 2 else ([], {})
            return self.donor_cache[d][0], self.donor_cache[d][1]
        return self.donor_cache[d][0], {}

    def sequence(self, arm, hs, fe, bench, donor, rank):
        blocks = hs.blocks
        if arm == "hand":
            return PO.hand(blocks)
        if arm == "hand_rule":
            return PO.hand_rule(blocks, [vs.rec for vs in hs.views])
        X = [fe[b] for b in blocks]
        if arm == "guide":
            return PO.by_scores(blocks, self.M["guide"].scores(X))
        if arm == "linear":
            return PO.by_scores(blocks, self.M["linear"].scores(X))
        if arm == "frequency":
            return PO.by_scores(blocks, self.M["frequency"].scores_keys([list(hs.block_key(b)) for b in blocks]))
        if arm == "lobo":
            return PO.by_scores(blocks, self.M["lobo"][bench].scores(X))
        if arm == "donor":
            if not donor:
                return PO.hand(blocks)
            dhs, dfe = donor[rank] if rank < len(donor) else donor[-1]
            dX = [dfe[b] for b in dhs.blocks]
            ds = self.M["guide"].scores(dX) if dX else []
            dkeys = [list(dhs.block_key(b)) for b in dhs.blocks]
            return PO.by_scores(blocks, PO.donor_scores([list(hs.block_key(b)) for b in blocks], list(zip(dkeys, ds))))
        raise ValueError(arm)

    def task(self, bench, family, tid, task, tasks_all):
        t0 = time.process_time()
        row = {"task": tid, "bench": bench, "family": family, "go_sha256": self.go_sha,
               "freeze_sha256": self.freeze_sha, "n_test": len(task["test_inputs"]),
               "n_demos": len(task["train"]), "arms": {}}
        try:
            ref = OA.construction_answers(task, ops=(), g0b=self.g0b)
        except Exception as e:                                           # noqa: BLE001
            # the reference raised: the task abstains in every arm; the evidence is the exception itself
            row["ref_error"] = {"type": type(e).__name__, "message": str(e)[:500],
                                "traceback_tail": traceback.format_exc()[-1500:]}
            row["cpu_s"] = round(time.process_time() - t0, 3)
            return row
        row["ref"] = slim_ref(ref)
        if ref["stage"] == "base" and ref["fit"]:
            row["shared"] = "base_fit"
            return dict(row, cpu_s=round(time.process_time() - t0, 3))
        if len(task["train"]) < 2:
            row["shared"] = "under_two_demonstrations"
            return dict(row, cpu_s=round(time.process_time() - t0, 3))
        for r in ref["retries"]:
            fit_here = bool(r["fit"]) and ref.get("op") and ref["op"]["sid"] == r["sid"]
            self.R.seed(tid, r["sid"], {"fit": bool(r["fit"]), "preds": ref["preds"] if fit_here else None,
                                        "program": ref["program"] if fit_here else None, "cpu_s": r["cpu_s"]})
        h0 = time.process_time()
        holes, hw = self.holes(task)
        row["holes_setup_cpu_s"] = round(time.process_time() - h0, 3)
        row.update(hw)
        row["n_holes"] = len(holes)
        donor = None
        if any(a == "donor" for a, _ in self.arms()):
            dh = self.donor_holes(bench, tid, tasks_all)
            donor = None if dh is None else dh[0]
            row["donor"] = None if donor is None else len(donor)
            if dh is not None and dh[1]:
                row["donor_features_cpu_s"] = round(dh[1]["sketches_cpu_s"] + dh[1]["pair_analysis_cpu_s"] +
                                                    dh[1]["features_cpu_s"], 3)
                row["donor_feature_comparisons"] = dh[1]["feature_comparisons"]
        for arm, budget in self.arms():
            key = f"{arm}@{budget}"
            a0 = time.process_time()
            try:
                tops, hrec = [], []
                for rank, (hs, fe) in enumerate(holes):
                    seq = self.sequence(arm, hs, fe, bench, donor, rank)
                    c0 = time.process_time()
                    top, rec = EN.run_hole(hs, seq, budget)
                    tops.append([slim_cand(c) for c in top])
                    hrec.append({"capped": rec["capped"], "ops": rec["counts"]["op"], "segment": rec["counts"]["segment"],
                                 "compare": rec["counts"]["compare"],
                                 "edit": rec["counts"]["edit"], "cpu_s": round(time.process_time() - c0, 3),
                                 "top": [[c["sid"], c["loo"], c["group"]] for c in tops[-1]]})
                ans = UN.answer(tops, tid, task, self.R)
                row["arms"][key] = dict(ans, holes=hrec, cpu_s=round(time.process_time() - a0, 3))
            except Exception:                                            # noqa: BLE001
                row["arms"][key] = {"error": traceback.format_exc()[-2000:]}
        row["retry_cpu_s"] = round(sum(v.get("cpu_s", 0) for k, v in self.R.cache.items()
                                       if k[0] == tid and not v.get("seeded")), 3)
        row["cpu_s"] = round(time.process_time() - t0, 3)
        return row


def run(out_dir, set_name, shard):
    i, k = (int(x) for x in shard.split("/"))
    GT.require_go()
    c = config()
    M = load_models(c)
    rows, tasks = task_list(set_name)
    by_bench = {}

    def tasks_all(bench):
        """Demonstrations and test inputs of a benchmark's tasks (donors come from the same half as the task)."""
        if bench not in by_bench:
            by_bench[bench] = DT.tasks(bench) if bench in BENCHES else {}
        return by_bench[bench]
    mine = [r for n, r in enumerate(rows) if n % k == i]
    path = E.check_write(os.path.join(out_dir, set_name, f"rows.{i}.jsonl"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            done = {json.loads(x)["task"] for x in f if x.strip()}
    run = Runner(set_name, path, c, M)
    with open(path, "a", encoding="utf-8") as f:
        for b, fam, tid in mine:
            if tid in done:
                continue
            bench = b if b != "arc2" else "arc2"
            row = run.task(bench, fam, tid, tasks[tid], tasks_all)
            f.write(json.dumps(row, sort_keys=True, default=list) + "\n")
            f.flush()
            print(json.dumps({"task": tid, "cpu_s": row.get("cpu_s"), "shared": row.get("shared"),
                              "ref_fit": (row.get("ref") or {}).get("fit")}), flush=True)


def main(out_dir, set_name, shard):
    return run(os.path.abspath(out_dir), set_name, shard)
