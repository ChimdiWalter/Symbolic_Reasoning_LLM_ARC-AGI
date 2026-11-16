"""Is the library text that runs the same as the downloaded source that the census read? A static comparison.

The searches run the text in selflesion/library/LIBRARY.json (through the frozen loader, dslx). The census of this
folder (census_source.py) parsed the downloaded dsl.py. Both are parsed here and nothing is executed: for every
definition of the library text, annotations and docstrings are removed from both forms and the syntax trees are
compared.

    python3 -I check_library_text_against_download.py <out.json>          Author: Chimdi Walter Ndubuisi
"""
import ast
import hashlib
import json
import sys

ROOT = "/path/to/repository/"
TEXT = ROOT + "experiments/proposer_20261109/selflesion/library/LIBRARY.json"
DOWNLOAD = ROOT + "outputs/search_components/resources_20261026/github/arc-dsl/dsl.py"
# the roster of this experiment, as literals in presets_bl.py (parsed, not imported)
PRESETS = ROOT + "experiments/below_library_20261114/presets_bl.py"


def bare(f):
    f = ast.parse(ast.unparse(f)).body[0]
    f.returns = None
    for a in f.args.args:
        a.annotation = None
    b = f.body
    if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) and isinstance(b[0].value.value, str):
        f.body = b[1:]
    return ast.dump(f)


def roster():
    names = []
    for n in ast.parse(open(PRESETS).read()).body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in (
                "STRATUM_SHORT", "STRATUM_LONGER_7_TO_15", "STRATUM_LONGER_OVER_15"):
            names += list(ast.literal_eval(n.value))
    return names


def main(argv):
    raw_text, raw_dl = open(TEXT, "rb").read(), open(DOWNLOAD, "rb").read()
    entries = json.loads(raw_text)["entries"]
    orig = {f.name: f for f in ast.parse(raw_dl.decode("utf-8")).body if isinstance(f, ast.FunctionDef)}
    same, different, absent = [], [], []
    for name, e in entries.items():
        mod = ast.parse(e["source"])
        if name not in orig:
            absent.append(name)
        elif len(mod.body) == 1 and isinstance(mod.body[0], ast.FunctionDef) and bare(mod.body[0]) == bare(orig[name]):
            same.append(name)
        else:
            different.append(name)
    ros = roster()
    body = dict(author="Chimdi Walter Ndubuisi", what="static comparison of two source texts; nothing executed; not a result",
                library_text_sha256=hashlib.sha256(raw_text).hexdigest(), download_sha256=hashlib.sha256(raw_dl).hexdigest(),
                definitions_in_the_library_text=len(entries), same_as_the_download=len(same), different=sorted(different),
                different_text={n: entries[n]["source"] for n in sorted(different)},
                not_in_the_download=sorted(absent), in_the_download_only=sorted(set(orig) - set(entries)),
                roster=len(ros), roster_names_missing_from_the_library_text=sorted(set(ros) - set(entries)),
                roster_names_whose_text_differs=sorted(set(ros) & set(different)))
    print(json.dumps({k: v for k, v in body.items() if k not in ("different_text",)}, indent=1))
    if argv:
        with open(argv[0], "x") as fh:
            json.dump(body, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
