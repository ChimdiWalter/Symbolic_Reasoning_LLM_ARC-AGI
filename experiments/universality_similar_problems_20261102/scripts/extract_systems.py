"""Extract the three submitted CORA systems byte-for-byte from their entry notebooks into systems/, and verify every
package file against its frozen MANIFEST. Writes SYSTEMS_MANIFEST.json. Run: python3 -I extract_systems.py"""
import hashlib
import json
import os
import re
import sys

R = "/path/to/repository"
E = os.path.join(R, "experiments/universality_similar_problems_20261102")
K = os.path.join(R, "outputs/score_first/kernels")
PKG = os.path.join(R, "experiments/cora_cast_20261026/kaggle_pkg")
R29 = os.path.join(R, "kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101")
NB = {"oplus": ("cora-cast-r29-v2-arc-agi-2", "f683136c2b15d94d7624d236f1b844eb0875dbd989fd748fe7b0fe8350d8b096", 0, "FILES"),
      "h": ("sf-h-c4-cast-arc-agi-2", "0e09afd478126d93da2fbd3e79c2063fc45df62ff84ede0a12790cda1dfc99c0", 1, "_files"),
      "o": ("cora-cast-only-arc-agi-2", "f2019b5d4f61b7dde0ab2fb15f339af25ce9e472f56250713f02bff9f9eabe56", 0, "FILES")}
MAN = {"cast_v1": (os.path.join(PKG, "MANIFEST.json"), "acd57e12f6d7b2735821c06d9dfbcfafd3eaf5754383bd62a92956fd5d2d8f7a"),
       "cast_selective_v2": (os.path.join(PKG, "cast_selective_v2", "MANIFEST.json"),
                             "aa8551ad935722ed0775570ff1bb1173108a777d3befead17eaf5ce57251f7d0"),
       "r29_cpu_package_20261101": (os.path.join(R29, "MANIFEST.json"),
                                    "11eb2ee9cd10f1507a0ffdcc6ae069de2efed79eb569788888aebcc3fd685ef7")}
sha = lambda b: hashlib.sha256(b).hexdigest()      # noqa: E731


def main():
    out = {"notebooks": {}, "systems": {}, "package_checks": {}}
    for sysname, (kern, want, cell, var) in NB.items():
        p = os.path.join(K, kern, "notebook.ipynb")
        b = open(p, "rb").read()
        assert sha(b) == want, f"{kern} notebook hash differs"
        src = json.loads(b)["cells"][cell]["source"]
        src = src if isinstance(src, str) else "".join(src)
        m = re.search(r"^\s*" + re.escape(var) + r" = json\.loads\((.*)\)$", src, re.M)
        files = json.loads(eval(m.group(1), {"__builtins__": {}}))
        keep = {k: v for k, v in files.items() if not k.startswith("sf/")}       # C4's neural files are not CORA
        d = os.path.join(E, "systems", sysname)
        for rel, text in keep.items():
            q = os.path.join(d, rel)
            os.makedirs(os.path.dirname(q), exist_ok=True)
            with open(q, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        out["notebooks"][sysname] = {"kernel": kern, "notebook_sha256": want, "cell": cell, "n_files": len(keep)}
        out["systems"][sysname] = {rel: sha(open(os.path.join(d, rel), "rb").read()) for rel in sorted(keep)}
    for pk, (mp, want) in MAN.items():
        assert sha(open(mp, "rb").read()) == want, f"{pk} manifest hash differs"
        listed = json.load(open(mp))["files"]
        for sysname, fl in out["systems"].items():
            got = {rel[len(pk) + 1:]: h for rel, h in fl.items() if rel.startswith(pk + "/")}
            if not got:
                continue
            bad = [f for f, h in listed.items() if f.startswith(pk + "/") is False and
                   (f.split("/", 1)[-1] if f.startswith(pk + "/") else f) in got and False]
            mism, missing = [], []
            for f, h in listed.items():
                key = f[len(pk) + 1:] if f.startswith(pk + "/") else f
                if key in ("README.md",) or key.startswith("tests/") or f.startswith("tests/"):
                    continue
                if key not in got:
                    missing.append(f)
                elif got[key] != h:
                    mism.append(f)
            out["package_checks"][f"{sysname}:{pk}"] = {"manifest_sha256": want, "checked": len(got),
                                                       "mismatches": mism, "missing_from_notebook": missing,
                                                       "unused": bad}
    json.dump(out, open(os.path.join(E, "SYSTEMS_MANIFEST.json"), "w"), indent=1)
    for k, v in out["package_checks"].items():
        print(k, "checked", v["checked"], "mismatches", v["mismatches"], "missing", v["missing_from_notebook"][:5])
    ok = all(not v["mismatches"] for v in out["package_checks"].values())
    print("ALL PACKAGE FILES MATCH" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
