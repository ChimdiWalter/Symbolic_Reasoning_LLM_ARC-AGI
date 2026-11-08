"""Package-mode smoke test, run inside an extracted archive (ngb/kaggle_build.py check): the kernel's import
closure, the gate's freeze check and refusal, the grammar with sorted tags, the library and registry binding, every
input of every static allowance (the matched arms' source costs; amendment 3), the builder's reuse and construction
functions on one source task per benchmark, the provenance of every loaded project module, and a sweep for any
solution file in the package.

    python -I run.py package_smoke OUT_JSON        (with NG_PACKAGE=1 and the package roots in the environment)
"""
import importlib
import json
import os
import sys


def main(out_path):
    res = {"imports": {}, "problems": []}
    for name in ("ngb.env", "ngb.gate", "ngb.ops", "ngb.held", "ngb.arc2", "ngb.phase2", "ngb.bench_probe",
                 "ngb.object_arm", "ngb.score", "ngrow.bench", "ngrow.data", "ngrow.plugin", "cgrow.search",
                 "cgrow.controller", "cgrow.selfext_core", "a2.bus"):
        try:
            importlib.import_module(name)
            res["imports"][name] = "ok"
        except Exception as e:                                             # noqa: BLE001
            res["imports"][name] = f"{type(e).__name__}: {e}"
            res["problems"].append(f"import {name}: {type(e).__name__}: {e}")
    from ngb import env as E, gate as GT, ops as OP, held as HB, object_arm as OA
    from ngrow import data as DT
    try:
        fr = GT.check_freeze()
        res["freeze_check"] = f"ok ({len(fr['files_sha256'])} files)"
    except Exception as e:                                                 # noqa: BLE001
        res["freeze_check"] = f"{type(e).__name__}: {e}"
        res["problems"].append(f"freeze check: {e}")
    try:
        GT.require_go()
        res["gate_without_go"] = "OPEN"
        res["problems"].append("gate open without a GO")
    except GT.GateRefused:
        res["gate_without_go"] = "refused"
    try:
        g = OP.G0Builder()()
        res["grammar"] = {"productions": len(g.prods), "sorted_tags": all(isinstance(t, OP.SortedTags)
                                                                             for p in g.prods for t in p.argtags)}
        if not res["grammar"]["sorted_tags"]:
            res["problems"].append("grammar tags are not sorted")
    except Exception as e:                                                 # noqa: BLE001
        res["problems"].append(f"grammar: {e}")
    lib = os.path.join(E.STUDY, "feasibility", "library")
    for b in DT.BENCHMARKS:
        try:
            HB.bind_library(lib, b)
            res[f"library_bound_{b}"] = True
        except Exception as e:                                             # noqa: BLE001
            res["problems"].append(f"library binding {b}: {e}")
    try:
        g0b = OP.G0Builder()
        for b in DT.BENCHMARKS:
            for arm in ("lib", "shuf", "obj", "obj_shuf", "construct"):
                ops = HB.library_ops(lib, b, arm, g0b)
                if ops and arm in ("lib", "shuf"):
                    OP.grammar_with(g0b, ops)
                res.setdefault("arm_registries", {})[f"{b}/{arm}"] = len(ops)
    except Exception as e:                                                 # noqa: BLE001
        res["problems"].append(f"arm registry loading: {type(e).__name__}: {e}")
    try:                                        # every input of every static allowance (amendment 3)
        res["source_costs"] = {f"{b}/{arm}": HB.source_cost(lib, b, arm) for b in DT.BENCHMARKS
                               for arm in ("lib", "obj", "construct")}
    except Exception as e:                                                 # noqa: BLE001
        res["problems"].append(f"allowance inputs: {type(e).__name__}: {e}")
    try:                                        # the builder's two functions on one source task per benchmark
        calls = {}
        for b in DT.BENCHMARKS:
            t = DT.half("source", (b,))[0][2]
            task = DT.tasks(b)[t]
            r1, r2 = OA.reuse(task, OA.ops(b)), OA.construct(task, OA.ops(b))
            calls[b] = {"task": t, "reuse": {"fit": r1.get("fit"), "stage": r1.get("stage"), "cpu_s": r1.get("cpu_s")},
                        "construct": {"fit": r2.get("fit"), "stage": r2.get("stage"), "cpu_s": r2.get("cpu_s")}}
        res["builder_calls"] = calls
    except Exception as e:                                                 # noqa: BLE001
        res["problems"].append(f"builder calls: {type(e).__name__}: {e}")
    try:
        res["object_contract_available"] = OA.available()
        if OA.available():
            res["object_registry_sizes"] = {b: len(OA.ops(b)) for b in DT.BENCHMARKS}
            res["builder_module"] = os.path.relpath(OA._mod().__file__, E.REPO)
    except Exception as e:                                                 # noqa: BLE001
        res["problems"].append(f"object contract: {e}")
    root = os.path.realpath(E.REPO)
    prov = {}
    for name, mod in sorted(sys.modules.items()):
        if name.split(".")[0] in ("ngb", "ngrow", "cgrow", "a2", "harness", "objgrow") and getattr(mod, "__file__", None):
            f = os.path.realpath(mod.__file__)
            prov[name] = os.path.relpath(f, root)
            if not f.startswith(root + os.sep):
                res["problems"].append(f"module {name} loaded from outside the package: {f}")
    res["module_provenance"] = prov
    found = []
    for d, _, files in os.walk(root):
        for f in files:
            if "solution" in f.lower() and f.endswith(".json"):
                found.append(os.path.relpath(os.path.join(d, f), root))
    res["solution_files_in_package"] = found
    if found:
        res["problems"].append(f"solution files in the package: {found}")
    res["ok"] = not res["problems"]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True, default=str)
    print(json.dumps({"ok": res["ok"], "problems": res["problems"]}))


if __name__ == "__main__":
    main(*sys.argv[1:])
