"""Are two setup records of the full roster the same cohort? Author: Chimdi Walter Ndubuisi.

A setup record names the code that made it. When a file of the experiment changes, the record is made again; this
script reconciles the new record with the preserved old one: for every operation, the decision (eligible or
excluded and its kind, stratum, control, hidden names, retained operations, hiding, the usability guard) and the
counts (generator draws and rejections, unusable examples, pooled sizes, usability, the reason text) must be
equal. Processor seconds and memory readings are not compared; the hashes of the code that made each record are
listed, since they are expected to differ. Nothing is run on any operation: the two files are read.

    python3 -I compare_setup_records.py <old record> <new record> <out.json>
"""
import json
import sys

NOT_COMPARED = ("memory", "cpu_s")


def differences(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k in NOT_COMPARED:
                continue
            if k not in a or k not in b:
                out.append((path + "/" + k, a.get(k, "<absent>"), b.get(k, "<absent>")))
            else:
                out += differences(a[k], b[k], path + "/" + k)
        return out
    return [] if a == b and type(a) is type(b) else [(path, a, b)]


def main(old_path, new_path, out_path):
    old, new = json.load(open(old_path)), json.load(open(new_path))
    names = sorted(set(old["targets"]) | set(new["targets"]))
    rows = {}
    for t in names:
        d = differences(old["targets"].get(t, {}), new["targets"].get(t, {}))
        if d:
            rows[t] = [dict(path=p, old=x, new=y) for p, x, y in d[:20]]
    ho, hn = old.get("hashes") or {}, new.get("hashes") or {}
    changed = sorted(k for k in set(ho) | set(hn) if ho.get(k) != hn.get(k))
    status = lambda r: {t: (v.get("decision") or v).get("status") for t, v in r["targets"].items()}          # noqa: E731
    so, sn = status(old), status(new)
    res = dict(author="Chimdi Walter Ndubuisi", what="two setup records of the full roster, operation by operation; nothing run",
               old=old_path, new=new_path, operations=len(names), same_names=sorted(old["targets"]) == sorted(new["targets"]),
               same_order=list(old["targets"]) == list(new["targets"]), operations_differing=len(rows), differing=rows,
               counts_old=old.get("counts"), counts_new=new.get("counts"), same_counts=old.get("counts") == new.get("counts"),
               eligible_old=sum(1 for v in so.values() if v == "eligible"), eligible_new=sum(1 for v in sn.values() if v == "eligible"),
               not_compared=list(NOT_COMPARED), files_whose_hash_differs_between_the_two_records=changed,
               the_same_cohort=not rows and sorted(old["targets"]) == sorted(new["targets"]) and old.get("counts") == new.get("counts"))
    with open(out_path, "x") as f:
        json.dump(res, f, indent=1, default=str)
    print("operations %d; differing %d; same summary counts %s; the same cohort: %s; files whose hash differs: %s"
          % (len(names), len(rows), res["same_counts"], res["the_same_cohort"], [k.split("/")[-1] for k in changed]))
    return 0 if res["the_same_cohort"] else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
