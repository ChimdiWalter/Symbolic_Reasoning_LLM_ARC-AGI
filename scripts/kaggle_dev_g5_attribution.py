"""Attribution for the G5 Kaggle development run (exposed public evaluation puzzles: development evidence only).

Reads the run's downloaded output (dev_score.json, cora_rows.json, execution_manifest.json) and the public evaluation
solutions, and reports, per test output: which variant-G5 search attempts are exact, and whether the program behind
each exact attempt contains a version 5 rule (stamp, ray with obstacles, segment, relational fill). The entry labels
the search's two attempt slots G3_FIT_1 and G3_FIT_2 for every variant, so attribution reads the programs instead.
Also reports puzzles whose chosen attempts use a version 5 rule (right or wrong on the test; the entry records
only the two attempt programs, not every fitting program), the search status counts and the run time, i.e. what the engineering gate in records/NEURAL_CORA_V2G5_ENGINEERING_20261025.md
needs.
The solutions file must be the one the run scored with (its sha256 is checked against dev_score.json).
  python scripts/kaggle_dev_g5_attribution.py SOLUTIONS_JSON [OUTPUT_DIR [VARIANT]]   # defaults outputs/kaggle_dev_g5/output, G5
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V5_TEXT = ("(stamp_rule", "(ray2_rule", "(segment_rule", "(fill_rule")


def main(sol_path, out_dir, variant="G5"):
    score = json.load(open(os.path.join(out_dir, "dev_score.json")))
    rows = json.load(open(os.path.join(out_dir, "cora_rows.json")))
    man = json.load(open(os.path.join(out_dir, "execution_manifest.json")))
    if hashlib.sha256(open(sol_path, "rb").read()).hexdigest() != score["solutions_sha256"]:
        sys.exit("solutions file differs from the one the run scored with")
    sol = json.load(open(sol_path))
    g5 = rows["search"].get(variant, {})
    uses_v5 = lambda p: bool(p) and any(t in p for t in V5_TEXT)             # noqa: E731
    exact, generated, v5_attempt = [], [], []
    for tid, r in sorted(g5.items()):
        if r.get("status") != "ok":
            continue
        progs = r.get("attempt_programs") or []
        if r.get("n_consistent") and any(uses_v5(p) for p in progs):
            v5_attempt.append(tid)
        for i, truth in enumerate(sol[tid]):
            atts = (r.get("attempts_by_test") or [])[i] if i < len(r.get("attempts_by_test") or []) else []
            for j, a in enumerate(atts[:2]):
                if a == truth:
                    exact.append({"task": tid, "test": i, "slot": j + 1,
                                  "program": progs[j] if j < len(progs) else None,
                                  "version5_rule": uses_v5(progs[j] if j < len(progs) else None)})
                    break
        if any(p == sol[tid][0] for p in r.get("predictions") or []):
            generated.append(tid)
    rep = {"label": "exposed public evaluation, development evidence, not a competition score",
           "scores": {k: {"score_pct": v["score_pct"], "tasks_with_a_correct_output": v["tasks_with_a_correct_output"],
                          "correct_by_source": v.get("correct_by_source", {}), "solved": v["solved"]}
                      for k, v in score.items() if isinstance(v, dict) and "score_pct" in v},
           "variant": variant, "search": man.get(f"search_{variant}"), "elapsed_s": man.get("elapsed_s"),
           "search_exact_outputs": exact, "search_generated_test0": generated,
           "puzzles_whose_attempts_use_a_version5_rule": v5_attempt,
           "gate_condition_1_new_exact_prediction_from_a_version5_rule": any(e["version5_rule"] for e in exact)}
    json.dump(rep, open(os.path.join(out_dir, f"{variant.lower()}_attribution.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "outputs", "kaggle_dev_g5", "output"),
         sys.argv[3] if len(sys.argv) > 3 else "G5")
