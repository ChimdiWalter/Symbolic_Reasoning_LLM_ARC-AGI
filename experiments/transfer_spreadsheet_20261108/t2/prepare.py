"""Build the task list and the development split from the pinned SyGuS benchmark snapshot.

Usage: python3 -I t2/prepare.py <study folder>
Reads data/raw/extracted/lib/PBE_SLIA_Track/{euphony,from_2018}/*.sl (the repository's "latest snapshot" folder).
Writes data/prepared/tasks.json (benchmark content, not committed) and split/DEV_SPLIT.json (task names only).

Rules (fixed before any task content was read; revision 1 of the eligibility rule, made after seeing only the
aggregate counts of revision 0 (48 eligible base problems): at least 3 examples instead of 4, and the single-file
fallback on conflicts):
- base problem: file stem without a trailing "-long-repeat", "-long", "_short", "-short" or "_small"; all files of one
  base problem are merged (distinct examples, in file order; grammar constants united);
- conflict: one input with two outputs, or two signatures, across the files of a base problem: the base problem
  keeps only its file with the most distinct inputs among the files that do not conflict by themselves (ties: first
  path), and is dropped if every file conflicts by itself;
  a base problem with any constraint that is not an example is dropped;
- group: phone* -> "phone"; firstname, lastname, initials, dr-name, reverse-name, name-combine* -> "person-name";
  univ_* -> "univ"; otherwise the base name without a trailing "_<digits>"; groups that share an identical
  (input, output) example are merged;
- eligible: String output, String or Int arguments, at least 3 distinct examples; the training set is 3 examples
  when there are 4 or more, otherwise 2 (the rest are the task's held checks);
- development groups: u(group) < 0.30, u = first 12 hex digits of sha256("transfer-spreadsheet-20261108|dev|" +
  group) / 16**12. Every other eligible base problem is in the held pool.
"""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from t2.sl_parse import read_sl  # noqa: E402

SUFFIXES = ("-long-repeat", "-long", "_short", "-short", "_small")
DEV_FRACTION = 0.30
DEV_SALT = "transfer-spreadsheet-20261108|dev|"
MIN_EXAMPLES = 3
SOURCES = ("lib/PBE_SLIA_Track/euphony", "lib/PBE_SLIA_Track/from_2018")


def base_name(stem):
    for s in SUFFIXES:
        if stem.endswith(s):
            return stem[: -len(s)]
    return stem


def group_of(base):
    if base.startswith("phone"):
        return "phone"
    if base in ("firstname", "lastname", "initials", "dr-name", "reverse-name") or base.startswith("name-combine"):
        return "person-name"
    if base.startswith("univ_"):
        return "univ"
    return re.sub(r"_\d+$", "", base)


def u_of(group):
    return int(hashlib.sha256((DEV_SALT + group).encode()).hexdigest()[:12], 16) / 16 ** 12


def sha_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(study):
    raw = os.path.join(study, "data", "raw", "extracted")
    byb, files = {}, []
    for src in SOURCES:
        d = os.path.join(raw, src)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".sl"):
                continue
            rel = f"{src}/{fn}"
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                fun, exs = read_sl(f.read())
            files.append({"path": rel, "sha256": sha_file(os.path.join(d, fn)), "examples": len(exs)})
            byb.setdefault(base_name(fn[:-3]), []).append({"path": rel, "fun": fun, "examples": exs})

    def merge(recs):
        out = {"sig": None, "str_consts": set(), "int_consts": set(), "examples": [], "conflict": False,
               "non_pbe": 0, "sources": []}
        seen = {}
        for r in recs:
            fun = r["fun"]
            sig = [[t for _, t in fun["args"]], fun["ret"]]
            if out["sig"] is None:
                out["sig"] = sig
            elif out["sig"] != sig:
                out["conflict"] = True
            out["non_pbe"] += fun["non_example_constraints"]
            out["sources"].append(r["path"])
            out["str_consts"].update(fun["str_consts"])
            out["int_consts"].update(fun["int_consts"])
            for inp, o in r["examples"]:
                k = json.dumps(inp)
                if k in seen:
                    if seen[k] != o:
                        out["conflict"] = True
                    continue
                seen[k] = o
                out["examples"].append([inp, o])
        return out
    probs = {}
    for b, recs in sorted(byb.items()):
        m = merge(recs)
        m["fallback_single_file"] = False
        if m["conflict"] and not m["non_pbe"] and len(recs) > 1:
            for r in sorted(recs, key=lambda r: (-len({json.dumps(e[0]) for e in r["examples"]}), r["path"])):
                m1 = merge([r])
                if not m1["conflict"]:
                    m = m1
                    break
            m["fallback_single_file"] = True
        m.update(id=b, group=group_of(b))
        probs[b] = m
    # merge groups that share an identical example
    parent = {}

    def find(g):
        while parent.setdefault(g, g) != g:
            g = parent[g]
        return g
    owner = {}
    for b in sorted(probs):
        for inp, out in probs[b]["examples"]:
            k = json.dumps([inp, out])
            g = probs[b]["group"]
            if k in owner and find(owner[k]) != find(g):
                parent[find(g)] = find(owner[k])
            owner.setdefault(k, g)
    tasks, excluded = [], {}
    for b in sorted(probs):
        p = probs[b]
        p["group"] = find(p["group"])
        why = None
        if p["non_pbe"]:
            why = "not_input_output_examples"
        elif p["conflict"]:
            why = "conflicting_examples_or_signature"
        elif p["sig"][1] != "String":
            why = "output_not_string"
        elif any(t not in ("String", "Int") for t in p["sig"][0]):
            why = "argument_type"
        elif len(p["examples"]) < MIN_EXAMPLES:
            why = "fewer_than_3_examples"
        if why:
            excluded[b] = why
            continue
        tasks.append({"id": b, "group": p["group"], "arg_types": p["sig"][0], "ret": p["sig"][1],
                      "str_consts": sorted(p["str_consts"]), "int_consts": sorted(p["int_consts"]),
                      "examples": p["examples"], "sources": sorted(p["sources"]),
                      "fallback_single_file": p["fallback_single_file"],
                      "k_train": 3 if len(p["examples"]) >= 4 else 2})
    groups = sorted({t["group"] for t in tasks})
    dev_groups = [g for g in groups if u_of(g) < DEV_FRACTION]
    dev = sorted(t["id"] for t in tasks if t["group"] in dev_groups)
    pool = sorted(t["id"] for t in tasks if t["group"] not in dev_groups)
    os.makedirs(os.path.join(study, "data", "prepared"), exist_ok=True)
    tp = os.path.join(study, "data", "prepared", "tasks.json")
    with open(tp, "w") as f:
        json.dump({"source_files": files, "tasks": tasks}, f, indent=0, sort_keys=True)
    split = {"rule": __doc__.split("Rules")[1].strip(), "dev_fraction": DEV_FRACTION, "dev_salt": DEV_SALT,
             "tasks_json_sha256": sha_file(tp), "n_files": len(files), "n_base_problems": len(probs),
             "excluded": excluded, "n_eligible": len(tasks), "n_groups": len(groups),
             "dev_groups": dev_groups, "dev_tasks": dev, "held_pool_tasks": pool,
             "held_pool_groups": [g for g in groups if g not in dev_groups]}
    with open(os.path.join(study, "split", "DEV_SPLIT.json"), "w") as f:
        json.dump(split, f, indent=1, sort_keys=True)
    ex = {}
    for v in excluded.values():
        ex[v] = ex.get(v, 0) + 1
    print(json.dumps({"files": len(files), "base_problems": len(probs), "eligible": len(tasks), "excluded": ex,
                      "groups": len(groups), "dev_groups": len(dev_groups), "dev_tasks": len(dev),
                      "held_pool": len(pool)}))


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]))
