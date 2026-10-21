"""syn-v4 generator and the ncv2-g4 study runner (records/NEURAL_CORA_V2G4_PROTOCOL_20261021.md): generator
determinism and certification, the custom executors, DEV/HELDOUT separation, the solve refusal, lock-check detection
on a temporary copy, and a DEV-only smoke of every arm through `run_arm` (not the frozen solve command). No HELDOUT
task is solved here.
"""
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
import neural_cora_v2g4_eval as E                                        # noqa: E402
from cora_neural_v2.rast import to_sexpr                                 # noqa: E402
from cora_neural_v2g2 import families as F2                              # noqa: E402
from cora_neural_v2g2 import grammar as G                                # noqa: E402
from cora_neural_v2g3 import families_v3 as V                            # noqa: E402
from cora_neural_v2g4 import program as PG                               # noqa: E402
from cora_neural_v2g4_eval import families_v4 as F4                      # noqa: E402

PY = sys.executable


# ------------------------------------------------------------------ generator
@pytest.mark.parametrize("name", F4.names("dev"))
def test_generator_is_deterministic_and_every_grid_changes(name):
    a, b = F4.make_task(name, 1), F4.make_task(name, 1)
    assert a is not None and a[0] == b[0] and np.array_equal(a[1], b[1])
    task, ans = a
    for x, y in task["train"]:
        assert not np.array_equal(np.asarray(x), np.asarray(y))
    assert not np.array_equal(np.asarray(task["test_inputs"][0]), ans)


def test_ambiguity_alternative_fits_and_disagrees():
    task, ans = F4.make_task("v4d_amb_border_or_whole", 1)
    alt = F4.alternative("v4d_amb_border_or_whole")
    assert F4._fits("g4", alt, task["train"])
    assert not np.array_equal(F4.run("g4", alt, task["test_inputs"][0]), ans)


def test_trap_memorizer_fits_and_mispredicts():
    task, ans = F4.make_task("v4d_trap_interior_size", 1)
    assert V.certify_trap(task, ans)


def test_mixed_program_needs_its_base_and_its_rule():
    name = "v4d_mix_recolour_then_interior"
    task, _ = F4.make_task(name, 1)
    prog = F4.FAMILIES[name][3]
    assert F4._fits("g4", prog, task["train"])
    assert not F4._fits("g4", PG.make(prog.view, None, prog.rules), task["train"])
    assert not F4._fits("g4", PG.make(prog.view, prog.base, ()), task["train"])
    assert F4.certify_necessary(task, "g4", prog)


def test_custom_executors():
    g = np.zeros((5, 4), dtype=int)
    g[0, 1] = 3
    g[1, 1:3] = 4
    out = F4.gravity_down(g)
    assert out[4, 1] == 4 and out[4, 2] == 4 and out[3, 1] == 3 and out.sum() == g.sum()
    b = np.zeros((6, 6), dtype=int)
    b[1:5, 1:5] = 7                                                       # interior (2,2) (2,3) (3,2) (3,3)
    c = F4.checker_interior(b)
    assert c[2, 2] == 0 and c[3, 3] == 0 and c[2, 3] == 7 and c[1, 1] == 7
    m = F4.top_left_marker(b)
    assert m[1, 1] == 1 and (m == 1).sum() == 1


def test_dev_and_heldout_semantics_are_disjoint_and_new():
    def key(f):
        _, _, kind, prog, _, _ = F4.FAMILIES[f]
        return (kind, prog.__name__ if kind == "custom" else repr(prog))
    dev = {key(f) for f in F4.names("dev")}
    held = {key(f) for f in F4.names("heldout")}
    assert not dev & held
    old = set()
    for src in [s for _, s, *_ in F2.FAMILIES.values()] + [s for _, _, s, *_ in V.FAMILIES.values()]:
        old.add(to_sexpr(G.parse(src)))
    for f, (_, _, kind, prog, _, _) in F4.FAMILIES.items():
        if kind == "native":
            assert to_sexpr(prog) not in old, f


def test_parity_with_native_where_g4_can_express_it():
    for name in F4.PARITY:
        for s in (1, 2):
            task, ans = F4.make_task(name, s)
            assert F4.parity(name, task, ans)


# ------------------------------------------------------------------ runner
def test_solve_refuses_without_authorization():
    rows = os.path.join(E.OUT, "rows.jsonl")
    before = os.path.exists(rows)
    r = subprocess.run([PY, os.path.join(HERE, "scripts", "neural_cora_v2g4_eval.py"), "solve"], cwd=HERE,
                       capture_output=True, text=True)
    assert r.returncode != 0 and "needs --authorized" in (r.stderr + r.stdout)
    assert os.path.exists(rows) == before


def test_lock_check_detects_a_modified_file(tmp_path):
    for rel in list(E.code_hashes(HERE)) + [E.PROTOCOL]:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(os.path.join(HERE, rel), dst)
    man = {"code": E.code_hashes(str(tmp_path)), "protocol_sha256": E.sha_file(str(tmp_path / E.PROTOCOL))}
    assert E.lock_problems(str(tmp_path), man, check_tasks=False) == []
    with open(tmp_path / "cora_neural_v2g4" / "construct.py", "a") as fh:
        fh.write("\n# changed\n")
    with open(tmp_path / E.PROTOCOL, "a") as fh:
        fh.write("\nchanged\n")
    probs = E.lock_problems(str(tmp_path), man, check_tasks=False)
    assert "code differs: cora_neural_v2g4/construct.py" in probs and f"protocol differs: {E.PROTOCOL}" in probs


def test_dev_smoke_of_every_arm_and_the_scorer():
    rows = []
    for name, seed in (("v4d_mix_recolour_then_interior", 1), ("v4d_ray_right_dots", 2)):
        t, _ = F4.make_task(name, seed)
        task = dict(t, seed=seed)
        g4 = None
        for arm in E.ARMS_PHASE1 + E.ARMS_PHASE2:
            paired = None if arm in E.ARMS_PHASE1 else E.paired_info(g4)
            rec = E.run_arm(task, arm, budget=150, paired=paired)
            assert "predictions" in rec and "cpu_s" in rec
            if arm == "g4":
                g4 = rec
            if arm == "g4_random":
                assert rec["head"]["by_origin"]["g4_geometry"] == g4["head"]["by_origin"]["g4_geometry"]
                assert rec["head"]["by_origin"]["g4_construct"] == rec["head"]["by_origin"]["g4_invert"] == 0
            if arm == "g3_cpu":
                assert rec["cpu_cap_used"] <= E.CPU_CAP_S
            rows.append({"task_id": task["task_id"], "family": name, "group": task["group"], "seed": seed, "arm": arm,
                         "rec": rec, "peak_rss_mb": 1.0})
    res = E.score_rows(rows, E._answer, E._alt)
    s = res["summary"]
    assert s["n"] == 2 and set(s["criteria"]) == {"G1_target_coverage", "G2_target_pass2", "G3_compute_attribution",
                                                    "G4_candidate_attribution", "G5_losses", "G6_control_no_regression",
                                                    "G7_beyond_false_fits", "G8_trap_top1", "G9_resources"}
    assert s["decision"] in ("NO_GAIN", "NO_GO_REGRESSION", "GAIN_NOT_ATTRIBUTED", "SELECTION_GAP", "GO_ENGINEERING")
