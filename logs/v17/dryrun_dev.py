"""Dry run of the acceptance per-task path on DEVELOPMENT fixture 0 only."""
import json, sys, time
R = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
sys.path.insert(0, R); sys.path.insert(0, R + "/scripts"); sys.path.insert(0, R + "/tests")
import v17_acceptance as A
from test_v17_compiler import fixture
schema, train, held = fixture(0)
t = {"seed": 810000100, "family": "(1,0)", "schema": schema, "train": train, "held": held}
M, _ = A.X._meta()
s0 = A.X.state_snapshot(); t0 = time.time()
row = A.run_task(0, t, M)
row["ablation"].pop("with_program", None)
print(json.dumps({"row": row, "snapshot_equal": s0 == A.X.state_snapshot(), "seconds": round(time.time() - t0, 1)}, default=str, indent=1))
