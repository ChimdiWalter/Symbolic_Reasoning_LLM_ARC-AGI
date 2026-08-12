import json, argparse

VALID = {"global_geom_palette", "component_mapping"}

def norm_family(s: str):
    s = (s or "").strip().lower()
    if "component" in s: return "component_mapping"
    if "global" in s or "palette" in s: return "global_geom_palette"
    if s in VALID: return s
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_jsonl", required=True, help="collect_llm_responses.jsonl")
    ap.add_argument("--out_json", default="llm_hints.json")
    args = ap.parse_args()

    hints = {}
    skipped = 0
    with open(args.in_jsonl, "r") as f:
        for line in f:
            if not line.strip(): continue
            rec = json.loads(line)
            tid = rec["task_id"]
            resp = rec.get("response")
            if isinstance(resp, str):
                try:
                    resp = json.loads(resp)
                except:
                    resp = {"family": resp}
            fam = norm_family(resp.get("family") if isinstance(resp, dict) else None)
            if not fam:
                skipped += 1; continue
            hints[tid] = {"family": fam}
    with open(args.out_json, "w") as f:
        json.dump(hints, f)
    print(f"Wrote {args.out_json} with {len(hints)} entries; skipped {skipped} lines.")

if __name__ == "__main__":
    main()
