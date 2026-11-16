"""Development only. Author: Chimdi Walter Ndubuisi.

Compares two output folders of run_bl.py made from the same code and the same setup record under different
concurrent loads: every target record and SUMMARY.json, field by field. Every difference is listed and put in one
of two classes by a rule fixed here before the comparison is read:
  time or memory: some key on the path names processor or wall time, a memory reading, a start or end time, or the
                  costs of the whole job (regex TIME_OR_MEMORY below);
  other:          everything else, including every ending, count of combinations, level, bank size, expression,
                  verdict, guard timeout, selection and table.
The check passes only if no difference is of the class "other". It also gives, for each search, the ratio of the
processor seconds in the second folder to those in the first, so that the record shows how different the loads were.

Usage: python -s -B compare_runs.py <first outdir> <second outdir> <record.json>
"""
import json, os, re, statistics, sys

TIME_OR_MEMORY = re.compile(r"(^|_)cpu(_|$)|(^|_)wall(_|$)|peak_kb|^memory$|^costs_of_the_whole_job$|^started$|^ended$"
                            r"|^(final_checks|other|searches|targets_total|by_system)_s$")
POLICY_KEYS = ("cpu_budget_s", "cpu_budget_is", "time_safety_limit_s", "processor_seconds_safety_limit_per_search")   # values of the policy: never treated as time readings


def is_time_or_memory(path):
    return any(k not in POLICY_KEYS and TIME_OR_MEMORY.search(k) for k in path)


def diff(a, b, path=(), out=None):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append((path + (k,), a.get(k, "<absent>"), b.get(k, "<absent>")))
            else:
                diff(a[k], b[k], path + (k,), out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, path + ("[%d]" % i,), out)
    elif a != b or type(a) is not type(b):
        out.append((path, a, b))
    return out


def main(first, second, record):
    names = sorted(set(os.listdir(os.path.join(first, "targets"))) | set(os.listdir(os.path.join(second, "targets"))))
    files = [os.path.join("targets", n) for n in names] + ["SUMMARY.json"]
    other, timemem, missing, ratios = [], 0, [], {}
    for f in files:
        pa, pb = os.path.join(first, f), os.path.join(second, f)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            missing.append(f)
            continue
        a, b = json.load(open(pa)), json.load(open(pb))
        for path, x, y in diff(a, b):
            if is_time_or_memory(path):
                timemem += 1
            else:
                other.append(dict(file=f, path="/".join(path), first=x, second=y))
        if f.startswith("targets"):
            for k, s in (a.get("searches") or {}).items():
                t = (b.get("searches") or {}).get(k) or {}
                if s.get("cpu_s") and t.get("cpu_s"):
                    ratios.setdefault(k, []).append(t["cpu_s"] / s["cpu_s"])
    rat = {k: dict(n=len(v), median=round(statistics.median(v), 3), smallest=round(min(v), 3), largest=round(max(v), 3))
           for k, v in sorted(ratios.items())}
    res = dict(author="Chimdi Walter Ndubuisi", label="development only: never a result",
               what="the same development run under two concurrent loads, compared field by field",
               first=first, second=second, files_compared=len(files) - len(missing), files_missing=missing,
               differences_time_or_memory=timemem, differences_other=len(other), other=other[:200],
               passed=not other and not missing, rule=TIME_OR_MEMORY.pattern, policy_keys_never_time=list(POLICY_KEYS),
               processor_seconds_ratio_second_over_first=rat)
    with open(record, "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    print("files compared %d, missing %d; differences: time or memory %d, other %d; passed %s"
          % (res["files_compared"], len(missing), timemem, len(other), res["passed"]))
    for k, v in rat.items():
        print("  %-7s processor seconds, second over first: median %.3f (%.3f to %.3f), n %d"
              % (k, v["median"], v["smallest"], v["largest"], v["n"]))
    for o in other[:20]:
        print("  OTHER", o["file"], o["path"], json.dumps(o["first"], default=str)[:80], json.dumps(o["second"], default=str)[:80])
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
