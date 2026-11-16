"""Static check of the lead's witness draft against the catalogue. Nothing is run on any example.

For every witness: the tree is checked with blocks_c.check_tree (every name exists, every application has the arity
of its block, every child can lie in the domain of its parameter as far as annotations tell) against the annotations
of the target's parameters in the library, and the node count that check_tree returns is compared with the count
written in the draft. The witness file is evaluator-only: this script prints names, counts and verdicts, never a tree.

    python3 check_witness_draft.py <witness json> [out.json]          Author: Chimdi Walter Ndubuisi
"""
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blocks_c as B          # noqa: E402  (also runs the hash check of the frozen files)
import dslx                   # noqa: E402
import presets_bl as P        # noqa: E402


def main(argv):
    raw = open(argv[0], "rb").read()
    draft = json.loads(raw)
    lib = dslx.load()
    rows, bad = {}, 0
    for name in sorted(draft):
        w = draft[name]
        anns = [a for _, a in lib["sigs"][name]]
        try:
            nodes = B.check_tree(w["tree"], anns)
            ok = nodes == w["nodes"]
            why = None if ok else "the draft says %s nodes, the check counts %s" % (w["nodes"], nodes)
        except ValueError as e:
            nodes, ok, why = None, False, str(e)
        bad += not ok
        rows[name] = dict(parameters=anns, nodes_in_draft=w["nodes"], nodes_counted=nodes, passes=ok, reason=why)
    controls = set(P.CONTROL_NAMES)
    dev_control = P.DEV_CONTROL
    hist = collections.Counter(r["nodes_counted"] for n, r in rows.items() if r["passes"] and n in controls)
    body = dict(author="Chimdi Walter Ndubuisi", what="static check of the witness draft; nothing run on any example",
                witness_file_sha256=hashlib.sha256(raw).hexdigest(), witnesses=len(rows), failing=bad,
                names_in_draft_not_pinned=sorted(set(rows) - controls - {dev_control}),
                pinned_controls_without_a_witness=sorted(controls - set(rows)),
                controls_by_node_count={str(k): v for k, v in sorted(hist.items())}, per_name=rows)
    for name, r in rows.items():
        print("%-13s %s nodes %s%s" % (name, r["nodes_counted"], "ok" if r["passes"] else "FAIL", "" if r["passes"] else ": " + r["reason"]))
    print("witnesses %d, failing %d | controls by node count %s | not pinned: %s | pinned without a witness: %s" % (
        len(rows), bad, body["controls_by_node_count"], body["names_in_draft_not_pinned"], body["pinned_controls_without_a_witness"]))
    if len(argv) > 1:
        with open(argv[1], "x") as fh:
            json.dump(body, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
