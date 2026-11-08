"""Pilot (phase 1): task-filter yield and CPU per unit on the pilot pool only. No arm runs on any pilot task.

    python -m cas.pilot CONFIG.json OUT_DIR [WORLD ...]

For each world and family, S1's slot procedure (cas/generate.py, Builder.build_family) fills the pilot quota
(config "pilot_quota", by default one T1, one T2 and one T3 slot) from the pilot pool, with one used-set per world.
Recorded per family and template: candidates tried, the filter stage that rejected each candidate, kept tasks,
unfilled slots and the filter's CPU. Then CORA's controller (S1's cgrow/controller.py analyze, which is the base
search, the 4x deeper probe and the typed-hole sketches; it is the failure analysis every specification method
reads, not a method) runs on every kept pilot task under the world's G0, to measure the share of tasks the
controller sends to construction (decision INVENT_NEW_OPERATION) and its CPU. Pilot tasks are written to OUT_DIR
and are never used by the study.
"""
import json
import os
import sys
import time

from cas import env as E                                                       # noqa: F401
from cas import generate as G                                                   # noqa: E402
from cgrow import controller as CT, lang0 as L0                                # noqa: E402


def as_task(t):
    return {"train": [(a, b) for a, b in t["train"]], "test_inputs": list(t["test_inputs"])}


def main(config_path, out_dir, worlds=None):
    cfg = E.load(config_path)
    pool = G.pool_ids(cfg, "pilot")
    res = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pool": "pilot",
           "pool_size": len(pool), "quota": cfg["pilot_quota"], "worlds": {}}
    out_path = os.path.join(out_dir, "PILOT_RESULTS.json")
    for world in worlds or cfg["world_order"]:
        wcfg = cfg["worlds"][world]
        t0 = time.process_time()
        b = G.Builder(world, wcfg, cfg, pool, set(), set())
        tasks = []
        fam_cpu = {}
        for x in wcfg["families"]:
            c0 = b.log["cpu_s"]
            parts = b.build_family(x, {"M": cfg["pilot_quota"], "V": [], "E": []})
            fam_cpu[x] = round(b.log["cpu_s"] - c0, 2)
            tasks += parts["M"]
        gen_cpu = round(time.process_time() - t0, 1)
        g0 = L0.build_g0(tuple(wcfg["removed"]))
        ctrl = []
        for t in tasks:
            c0 = time.process_time()
            rec = CT.analyze(as_task(t), g0)
            ctrl.append({"family": t["family"], "template": t["template"], "op": t["op"], "params": t["params"],
                         "program": t["program"], "source": t["source"], "decision": rec["decision"],
                         "base_level": rec["base"]["level_complete"],
                         "deeper_level": (rec.get("probe_deeper_search") or {}).get("level_complete"),
                         "deeper_fit": (rec.get("probe_deeper_search") or {}).get("fit"),
                         "n_sketches": len(rec.get("sketches") or []),
                         "sketch_forms": [(s["form"], s["outer"], s["inner"]) for s in rec.get("sketches") or []],
                         "cpu_s": round(time.process_time() - c0, 2)})
            print(json.dumps({"world": world, "pilot_task": t["program"], "decision": rec["decision"]}), flush=True)
        res["worlds"][world] = {
            "removed": wcfg["removed"], "families": wcfg["families"], "unary_ops": list(b.unary),
            "filter_log": b.log | {"cpu_s": round(b.log["cpu_s"], 1)}, "family_filter_cpu_s": fam_cpu,
            "generation_process_cpu_s": gen_cpu, "kept": len(tasks), "controller": ctrl,
            "controller_cpu_s": round(sum(c["cpu_s"] for c in ctrl), 1),
            "invent_share": round(sum(c["decision"] == "INVENT_NEW_OPERATION" for c in ctrl) / len(ctrl), 3)
            if ctrl else None}
        E.dump(os.path.join(out_dir, f"pilot_tasks_{world}.json"),
               [{k: v for k, v in t.items()} for t in tasks])
        E.dump(out_path, res)
    res["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    E.dump(out_path, res)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:] or None)
