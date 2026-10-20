"""Post-hoc, answer-free description of G2: which ncv2-g1 programs produced g1's predictions on dev60.

    python scripts/neural_cora_v2_g2_replay_programs.py   # after the G2 solve stage
        -> outputs/neural_cora_v2/g2/g2_attempt_programs.json

The frozen G2 runner records each distinct prediction's candidate position (`pred_at`) but not the program. The
enumeration is deterministic: the same frozen code, the same task and no learned scores. So this script replays
`search.enumerate_programs` and takes the programs at the first two recorded positions, which produced attempts 1
and 2. It executes nothing on test outputs, reads no answers and re-scores nothing. It is a description of the
frozen run, labelled post hoc, and it cannot change the G2 decision.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "neural_cora_v2", "g2")


def main():
    from cora_neural_v2 import search as S
    from cora_neural_v2.rast import to_sexpr
    sys.path.insert(0, os.path.join(HERE, "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("g2", os.path.join(HERE, "scripts", "neural_cora_v2_g2.py"))
    G2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(G2)
    tasks = {t["task_id"]: t for t in G2.dev60_tasks()}
    rows = [json.loads(l) for l in open(os.path.join(OUT, "dev60_g1_solve.jsonl"))]
    res = {}
    for r in sorted(rows, key=lambda x: x["task_id"]):
        at = r["result"]["pred_at"][:2]
        if not at:
            continue
        want, progs = set(at), {}
        for i, (p, _) in enumerate(S.enumerate_programs(tasks[r["task_id"]], max(at)), 1):
            if i in want:
                progs[i] = to_sexpr(p)
        res[r["task_id"]] = [{"attempt": j + 1, "candidate_position": a, "program": progs.get(a)} for j, a in enumerate(at)]
        print(r["task_id"], at, flush=True)
    json.dump({"note": "post-hoc deterministic replay; no answers read; descriptive only", "programs": res},
              open(os.path.join(OUT, "g2_attempt_programs.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
