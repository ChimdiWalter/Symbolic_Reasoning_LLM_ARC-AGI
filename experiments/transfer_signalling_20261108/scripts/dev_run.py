"""Development runs (labelled development). Modes:
  toy       leave-one-condition-out over the 9 CellNOpt toy conditions (real CellNOpt example data);
  syn_toy   synthetic-from-real-PKN tasks on the toy PKN and design;
  syn_dream synthetic-from-real-PKN tasks on the DREAM liver PKN and design. The DREAM measured values are stripped
            on load (design_only) and never used.
Usage: python -I scripts/dev_run.py <mode> <n_tasks> <out.json> [first_task] [flip]   (flip overrides the noise)"""
import json, os, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from t5.data import Dataset, design_only  # noqa: E402
from t5.tasks import make_task, run_arms, synthetic_task  # noqa: E402

CFG = json.load(open(os.path.join(HERE, "config_dev.json")))
RAW = os.path.join(HERE, "data", "raw")


def main():
    mode, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    first = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    if len(sys.argv) > 5:
        CFG["syn"]["flip"] = float(sys.argv[5])
    t0 = time.process_time()
    results = []
    if mode == "toy":
        ds = Dataset("Toy", os.path.join(RAW, "ToyPKNMMB.sif"), os.path.join(RAW, "ToyDataMMB.csv"))
        for c in range(len(ds.conditions))[first:first + n]:
            train = [i for i in range(len(ds.conditions)) if i != c]
            task = make_task(ds, train, [c], f"dev|toy|loco|{c}")
            results.append(run_arms(task, CFG))
    else:
        if mode == "syn_toy":
            ds = design_only(Dataset("Toy", os.path.join(RAW, "ToyPKNMMB.sif"), os.path.join(RAW, "ToyDataMMB.csv")))
            n_held = 2
        else:
            ds = design_only(Dataset("LiverDREAM", os.path.join(RAW, "LiverPKNDREAM.sif"),
                                     os.path.join(RAW, "LiverDataDREAMMIDAS.csv")))
            n_held = 5
        i = first
        while len(results) < n:
            made = synthetic_task(ds, f"dev|{mode}|{i}", n_held, CFG["syn"]["flip"], CFG["syn"])
            i += 1
            if made is None:
                continue
            task, info = made
            r = run_arms(task, CFG)
            r["synthetic"] = info
            results.append(r)
    json.dump({"label": "development", "mode": mode, "cfg": CFG, "cpu_s": round(time.process_time() - t0, 2),
               "results": results}, open(out, "w"), indent=1)
    agg = {}
    for r in results:
        for arm, info in r["arms"].items():
            a = agg.setdefault(arm, [0, 0, 0, 0])
            for h in info["held"].values():
                a[0] += h["exact"]; a[1] += 1; a[2] += h["measured"] - h["wrong"]; a[3] += h["measured"]
    print(f"development {mode}: tasks={len(results)} cpu_s={time.process_time() - t0:.1f}")
    for arm, a in agg.items():
        print(f"  {arm:9s} exact held conditions {a[0]}/{a[1]}  held data points right {a[2]}/{a[3]}")


if __name__ == "__main__":
    main()
