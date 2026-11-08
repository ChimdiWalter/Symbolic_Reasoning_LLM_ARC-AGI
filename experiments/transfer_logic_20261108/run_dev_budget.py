"""Development budget sweep (development items only). Usage: python3 -I run_dev_budget.py <label> <domain> <fraction>"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tlogic import arms, data
label, dom, frac = sys.argv[1], sys.argv[2], float(sys.argv[3])
cfg = data.load_config()
cfg["budget"][dom] = {"fraction": frac}
dev_c, dev_p = data.dev_items(cfg)
todo = dev_c if dom == "circuit" else dev_p
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dev_results", label + ".jsonl")
t0 = time.process_time()
with open(out, "w") as f:
    for it in todo:
        r = arms.run_item(it, cfg, cfg[dom]["arms"], True, True)
        r["label"] = "development"; r["fraction"] = frac
        f.write(json.dumps(r) + "\n")
print(json.dumps({"label": label, "items": len(todo), "cpu_s": round(time.process_time() - t0, 1)}))
