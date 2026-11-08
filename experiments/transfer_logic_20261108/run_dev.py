"""Development runs (development items only; labelled development). Usage:
python3 -I run_dev.py <label> [circuit|policy|both] [max_items] [--no-verify] [--no-active]"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tlogic import arms, data

label, which = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "both")
cap = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else None
cfg = data.load_config()
dev_c, dev_p = data.dev_items(cfg)
todo = (dev_c if which in ("circuit", "both") else []) + (dev_p if which in ("policy", "both") else [])
if cap:
    todo = todo[:cap]
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dev_results", label + ".jsonl")
os.makedirs(os.path.dirname(out), exist_ok=True)
t0 = time.process_time()
with open(out, "w") as f:
    for it in todo:
        r = arms.run_item(it, cfg, cfg[it["domain"]]["arms"], "--no-verify" not in sys.argv, "--no-active" not in sys.argv)
        r["label"] = "development"
        f.write(json.dumps(r) + "\n"); f.flush()
print(json.dumps({"label": label, "items": len(todo), "cpu_s": round(time.process_time() - t0, 1)}))
