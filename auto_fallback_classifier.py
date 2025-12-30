import json, argparse, numpy as np

def decide_family(pairs):
    # Simple rules: if sizes are equal across pairs and component counts are steady -> global
    size_equal = all(p["in_size"]==p["out_size"] for p in pairs) if pairs else True
    deltas = [p["out_components"]-p["in_components"] for p in pairs]
    var = np.std(deltas) if deltas else 0.0
    if size_equal and var < 0.5:
        return "global_geom_palette"
    return "component_mapping"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--llm_hints", required=True)
    ap.add_argument("--out", default="llm_hints_completed.json")
    args=ap.parse_args()
    feats=json.load(open(args.features))
    hints=json.load(open(args.llm_hints))
    filled=0
    for tid,pairs in feats.items():
        if tid not in hints:
            hints[tid]={"family":decide_family(pairs)}
            filled += 1
    json.dump(hints, open(args.out, "w"))
    print(f"Wrote {args.out}. Added {filled} hints; total {len(hints)}.")
if __name__=="__main__": main()
