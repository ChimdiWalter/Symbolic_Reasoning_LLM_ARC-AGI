"""Lists every found expression of a run for reading by a person. Author: Chimdi Walter Ndubuisi.

The protocol requires that the found expressions are read before any count is reported. This script only prints
what the records hold: for each target its stratum and role, the true operation's source, each system's selected
expression with its stage and its verdict on the final panel, and every other first fit of the six searches with
its own verdict. It computes nothing and changes nothing. Not part of the freeze: it takes no part in the run and
in no decision.

    python3 -I read_expressions_bl.py <outdir> <reading.md>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.join(HERE, "..", "proposer_20261109", "selflesion", "library", "LIBRARY.json")


def sources():
    """{operation: source text} from the library text that runs, when it can be read; {} otherwise."""
    try:
        lib = json.load(open(LIBRARY))
    except (OSError, ValueError):
        return {}
    items = lib.get("entries") or lib.get("definitions") or lib.get("operations") or lib
    out = {}
    if isinstance(items, dict):
        for k, v in items.items():
            out[k] = v if isinstance(v, str) else (v.get("source") or v.get("text") or "") if isinstance(v, dict) else ""
    elif isinstance(items, list):
        for v in items:
            if isinstance(v, dict) and v.get("name"):
                out[v["name"]] = v.get("source") or v.get("text") or ""
    return out


def main(outdir, out_path):
    src = sources()
    tdir = os.path.join(outdir, "targets")
    lines = ["# Found expressions of %s, for reading" % outdir, "",
             "Author: Chimdi Walter Ndubuisi. Printed from the records; nothing computed. \"right\" and \"wrong\" are the "
             "records' verdicts on the final panel.", ""]
    n_sel = 0
    for name in sorted(os.listdir(tdir)):
        r = json.load(open(os.path.join(tdir, name)))
        X = r.get("target")
        role = ", ".join(k for k, v in (("development", r.get("dev")), ("control", r.get("control"))) if v) or "outside development"
        head = "## %s (%s; stratum %s; %s)" % (X, r.get("status"), r.get("stratum"), role)
        if r.get("status") != "done":
            lines += [head, "", "%s" % (r.get("reason") or ""), ""]
            continue
        lines += [head, ""]
        body = (src.get(X) or "").strip()
        if body:
            lines += ["```", body, "```", ""]
        for system in ("library_only", "smaller_blocks"):
            s = (r.get("selection") or {}).get(system) or {}
            if s.get("expr"):
                n_sel += 1
                lines.append("- **%s** selected `%s` (%s, %s nodes): **%s**" % (system, s["expr"], s.get("search"), s.get("size"),
                                                                             "right" if s.get("rebuilt") else "wrong"))
            else:
                lines.append("- **%s** selected nothing (%s)" % (system, s.get("reason")))
        for k, a in sorted((r.get("searches") or {}).items()):
            if a.get("expr"):
                fin = a.get("final") or {}
                extra = "" if fin.get("right") or not fin else " (agree %s of %s; errors %s; guard timeout %s)" % (
                    fin.get("agree"), fin.get("n"), fin.get("errors"), fin.get("guard_timeout"))
                lines.append("  - %s: `%s` (%s nodes): %s%s" % (k, a["expr"], a.get("size"), a.get("first_fit"), extra))
            else:
                lines.append("  - %s: none (%s)" % (k, a.get("stop_class")))
        w = r.get("witness") or {}
        if w.get("state") not in (None, "no manifest", "no manifest entry", "not a control"):
            lines.append("  - witness `%s`: %s; agrees on all 36: %s; on the final panel: %s" % (
                w.get("expr"), w.get("state"), w.get("agrees_on_all_36"), w.get("agrees_on_the_final_panel")))
        lines.append("")
    with open(out_path, "x") as f:
        f.write("\n".join(lines) + "\n")
    print("written: %s (%d selected expressions to read)" % (out_path, n_sel))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
