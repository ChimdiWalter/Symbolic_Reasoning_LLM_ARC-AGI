"""Convert the downloaded BIG-bench list_functions files into examples only (run ONLY as: python3 -I prepare_data.py
RAW_DIR OUT_JSON). Reads raw/cNNN/task.json, parses each example's input and target strings as lists of integers,
and writes {concept: [[input, output], ... 32]} with no descriptions, names or other fields, so that no later step
can see a concept's natural-language description. Uses only the standard library.
"""
import ast
import hashlib
import json
import os
import sys


def main(raw, out):
    res = {}
    for i in range(1, 251):
        c = f"c{i:03d}"
        with open(os.path.join(raw, c, "task.json"), encoding="utf-8") as f:
            t = json.load(f)
        ex = []
        for e in t["examples"]:
            a, b = ast.literal_eval(e["input"]), ast.literal_eval(e["target"])
            if not (isinstance(a, list) and isinstance(b, list) and all(type(v) is int for v in a + b)):
                raise ValueError(c)
            ex.append([a, b])
        res[c] = ex
    s = json.dumps(res, sort_keys=True, separators=(",", ":"))
    with open(out, "w", encoding="utf-8") as f:
        f.write(s)
    print(json.dumps({"concepts": len(res), "sha256": hashlib.sha256(s.encode()).hexdigest()}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
