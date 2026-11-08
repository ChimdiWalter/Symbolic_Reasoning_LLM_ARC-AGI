"""Freeze the expected registries and digests of every grown arm (amendment 2), so that the report can check each
row's provenance against a frozen value rather than against the other rows.

    python -I run.py object_registries OUT_JSON

Per benchmark: the library arm's operations (programs) and digest, the shuffled library's, the object registry's
(own holes) operation identifiers and digest, the shuffled registry's with its shortfall, and for the ARC-AGI-2
check the union library's and union registry's digests; plus the G0 digest. Digests are `held.registry_digest`
(sha256 over the operations' programs or identifiers), the values the rows carry.
"""
import os
import sys

from ngb import env as E, ops as OP, held as HB, arc2 as A2, object_arm as OA
from ngrow import data as DT

LIB = os.path.join(E.STUDY, "feasibility", "library")


def main(out_path):
    g0b = OP.G0Builder()
    out = {"g0_sha256": g0b.sha, "benchmarks": {}, "arc2": {}}
    for b in DT.BENCHMARKS:
        lib = HB.library_ops(LIB, b, "lib", g0b)
        shuf = HB.library_ops(LIB, b, "shuf", g0b)
        obj = OA.ops(b)
        oshuf, short = OA.shuffled_ops(b)
        out["benchmarks"][b] = {
            "lib": {"operations": [o.text for o in lib], "digest": HB.registry_digest(lib)},
            "shuf": {"operations": [o.text for o in shuf], "digest": HB.registry_digest(shuf)},
            "obj": {"operations": [o.sid for o in obj], "digest": HB.registry_digest(obj)},
            "obj_shuf": {"operations": [o.sid for o in oshuf], "digest": HB.registry_digest(oshuf), "shortfall": short},
            "construct": {"operations": [o.sid for o in obj], "digest": HB.registry_digest(obj)},
            "construct_shuf": {"operations": [o.sid for o in obj], "digest": HB.registry_digest(obj)},
            "G0": {"operations": [], "digest": None},
            "static_lib": {"digest": None}, "static_obj": {"digest": None}, "static_construct": {"digest": None}}
    ulib = A2.union_library(LIB, g0b)
    uobj = OA.union_ops()
    out["arc2"] = {"lib": {"operations": [o.text for o in ulib], "digest": HB.registry_digest(ulib)},
                   "obj": {"operations": [o.sid for o in uobj], "digest": HB.registry_digest(uobj)},
                   "construct": {"operations": [o.sid for o in uobj], "digest": HB.registry_digest(uobj)},
                   "G0": {"digest": None}, "static_lib": {"digest": None}, "static_obj": {"digest": None},
                   "static_construct": {"digest": None}}
    E.dump(os.path.abspath(out_path), out)
    print({b: {a: (len(v.get("operations", [])), (v.get("digest") or "")[:12]) for a, v in r.items()
               if "operations" in v} for b, r in out["benchmarks"].items()})


if __name__ == "__main__":
    main(*sys.argv[1:])
