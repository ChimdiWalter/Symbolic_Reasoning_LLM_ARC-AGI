"""The Phase 7 offline scaffold: the validator catches malformed submissions; the driver always writes a valid one,
including when a task raises, when the deadline is reached, and for tasks with several test inputs."""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "kaggle", "cora_g3_scaffold"))
import scaffold as SC                                                    # noqa: E402
from cora_neural_v2g2 import families as F                               # noqa: E402

GRID = [[1, 0], [0, 1]]


def challenge_from(task):
    return {"train": [{"input": a, "output": b} for a, b in task["train"]], "test": [{"input": x} for x in task["test_inputs"]]}


def test_validator_catches_malformed_entries():
    ch = {"t": {"train": [], "test": [{"input": GRID}, {"input": GRID}]}}
    assert SC.validate(SC.fallback(ch), ch) == []
    assert SC.validate({"t": [{"attempt_1": GRID, "attempt_2": GRID}]}, ch)                       # one entry short
    assert SC.validate({"t": [{"attempt_1": GRID}] * 2}, ch)                                      # attempt_2 missing
    assert SC.validate({"t": [{"attempt_1": [[10]], "attempt_2": GRID}] * 2}, ch)                # colour out of range
    assert SC.validate({"t": [{"attempt_1": [[1, 2], [3]], "attempt_2": GRID}] * 2}, ch)         # ragged grid
    assert SC.validate({}, ch)


def test_driver_writes_a_valid_submission_and_survives_errors(tmp_path):
    task, _ = F.make_task("negated_selector_delete", 2)
    ch = {"ok": challenge_from(task), "boom": challenge_from(task)}
    ch["boom"]["test"].append({"input": GRID})
    path = tmp_path / "challenges.json"
    path.write_text(json.dumps(ch))

    def solve(t, budget, cap):
        if len(t["test"]) == 2:
            raise RuntimeError("simulated failure")
        return SC.solve_task(t, 400, cap)
    sub, prov = SC.run(str(path), str(tmp_path / "out"), deadline_h=1.0, solve=solve)
    assert SC.validate(sub, ch) == [] and SC.validate(json.load(open(tmp_path / "out" / "submission.json")), ch) == []
    assert prov["tasks"]["boom"]["status"] == "error" and prov["tasks"]["ok"]["status"] == "ok"
    assert sub["boom"] == SC.fallback({"boom": ch["boom"]})["boom"]
    assert prov["tasks"]["ok"]["origins"][0][0] != "fallback"


def test_deadline_skips_tasks_but_keeps_the_file_valid(tmp_path):
    ch = {f"t{i}": {"train": [], "test": [{"input": GRID}]} for i in range(3)}
    path = tmp_path / "c.json"
    path.write_text(json.dumps(ch))
    clock = iter([0.0] + [3600.0 * 2] * 10).__next__                    # the deadline has passed after start
    sub, prov = SC.run(str(path), str(tmp_path / "o"), deadline_h=1.0, solve=lambda *a: None, clock=clock)
    assert SC.validate(sub, ch) == [] and all(v["status"] == "skipped_deadline" for v in prov["tasks"].values())
