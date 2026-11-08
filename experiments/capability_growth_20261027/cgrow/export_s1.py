"""Source-only S1 export for the independent partial replication (new files only; nothing frozen is edited).

    python -m cgrow.export_s1 exports/s1_source_only_v1

Scope: tasks whose source ARC id is in S_train (the 520-task split) only. Nothing derived from S_select, the
evaluation set or sealed data. System views hold demonstrations, query inputs and CORA's failure records without
any query prediction; the evaluator file holds the hidden outputs (and G0's own first prediction for solved tasks,
needed by the regression rule).
"""
import hashlib
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P     # noqa: E402

SRC = {"tasks_system": "partitions/TASKS_SYSTEM.json", "tasks_eval": "evaluator_only/TASKS_EVAL.json",
       "records": "runs/prep_v4/records.pkl", "form_replies": "runs/s1_gen/replies.jsonl",
       "c7m": "runs/ib_c7m/c7m.json"}
DROP = ("base_preds", "probe_deeper_preds")          # query predictions: never in a system view
SEEDS = (0, 1, 2)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def dump(path, obj):
    with P.open_write(path) as f:
        json.dump(obj, f, sort_keys=True, indent=1, default=list)


def main(out_rel):
    out = os.path.join(P.HERE, out_rel)
    os.makedirs(out, exist_ok=True)
    src = {k: os.path.join(P.HERE, v) for k, v in SRC.items()}
    ev = json.load(open(src["tasks_eval"], encoding="utf-8"))
    sy = json.load(open(src["tasks_system"], encoding="utf-8"))
    with open(src["records"], "rb") as f:
        recs = pickle.load(f)
    elig = sorted(i for i, t in ev.items() if t["source_split"] == "S_train")
    sys_ids = [i for i in elig if i in sy]
    mot = sorted(i for i in sys_ids if ev[i]["partition"] == "M" and recs[i]["decision"] == "INVENT_NEW_OPERATION")
    assert all(ev[i]["source_split"] == "S_train" for i in elig + mot)
    dump(os.path.join(out, "system_tasks.json"), {i: sy[i] for i in sys_ids})
    dump(os.path.join(out, "system_records.json"), {i: {k: v for k, v in recs[i].items() if k not in DROP}
                                                    for i in sys_ids})
    evx = {}
    for i in elig:
        e = dict(ev[i])
        if i in recs and recs[i]["status"] == "solved":
            e["g0_first_prediction"] = recs[i]["base_preds"][0]
        evx[i] = e
    dump(os.path.join(out, "evaluator_tasks.json"), evx)
    rows = [json.loads(x) for x in open(src["form_replies"], encoding="utf-8") if x.strip()]
    keep = {f"S1F_{t}_s{s}" for t in mot for s in SEEDS}
    with P.open_write(os.path.join(out, "form_replies.jsonl")) as f:
        for r in rows:
            if r["job_id"] in keep:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    c7 = json.load(open(src["c7m"], encoding="utf-8"))
    fields = ("fit", "correct", "cpu_s", "calls", "level_complete", "stop", "closure_capped", "program")
    dump(os.path.join(out, "c7m_eligible.json"), {t: {k: c7[t].get(k) for k in fields} for t in mot})
    mapping = "".join(f"{i} {ev[i]['source']} {ev[i]['source_split']} {ev[i]['partition']} "
                      f"{'real' if ev[i].get('real') else 'derived'}\n" for i in elig)
    with P.open_write(os.path.join(out, "source_mapping.txt")) as f:
        f.write(mapping)
    counts = {"eligible_tasks": len(elig), "system_tasks": len(sys_ids),
              "system_by_partition": {p: sum(ev[i]["partition"] == p for i in sys_ids) for p in ("U", "M", "V", "D")},
              "excluded_E": sum(ev[i]["partition"] == "E" for i in elig), "eligible_motivating": len(mot),
              "units": len(mot) * len(SEEDS), "form_replies": len(keep),
              "distinct_S_train_sources": len({ev[i]["source"] for i in elig})}
    files = sorted(f for f in os.listdir(out) if f not in ("MANIFEST.json",))
    man = {"export": "s1_source_only_v1", "scope": "tasks derived from S_train source ids only",
           "counts": counts, "eligible_motivating": mot,
           "files_sha256": {f: sha(os.path.join(out, f)) for f in files},
           "originals_sha256": {k: sha(v) for k, v in src.items()},
           "full_62_row_mapping_sha256": "e08751b51db6b6e569430679074b4bf0fcb551b2efcd688d698531e34f07593d",
           "builder": {"file": "cgrow/export_s1.py", "sha256": sha(os.path.abspath(__file__))},
           "dropped_from_system_records": list(DROP)}
    dump(os.path.join(out, "MANIFEST.json"), man)
    print(json.dumps(counts))


if __name__ == "__main__":
    main(sys.argv[1])
