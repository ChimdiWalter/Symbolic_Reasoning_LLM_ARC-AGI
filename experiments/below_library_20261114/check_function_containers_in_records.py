"""Would the rule "a container never holds a function" have touched an expression found in the earlier studies?

A static reading of saved records; nothing is searched and no operation is run. Every string that has the form of an
expression (names, commas, spaces and brackets, with at least one call) is taken from every JSON record of the
operations study, stage A and the run of 14 November. Two questions are asked of each distinct expression:

  1. does it pass one of the seven function-making operations (chain, compose, fork, lbind, matcher, power, rbind) as
     a VALUE, that is, name it without calling it? Only then can a called function return a function, and only
     then can an operation that applies a function to the elements of a container build a container of functions;
  2. does it use `rapply`, the library operation whose first argument is a container of functions?

Stage A also records, under the key `consumers`, the text of the surrounding programs through which a hidden
operation was observed. Those texts name the hidden operation itself and were written by the evaluator, not found by
a search. They are counted apart. Any such text recorded under another key is read with the expressions, which can
only make this reading stricter.

What this does not show: it is a reading of the text of expressions. It does not evaluate them, and it cannot see a
function that an example passes in as the value of a function-typed parameter.

    python3 check_function_containers_in_records.py <out.json>          Author: Chimdi Walter Ndubuisi
"""
import glob
import json
import os
import re
import sys

ROOT = "/path/to/repository"
FOLDERS = {
    "operations study": "experiments/core_operations_20261113/full_out",
    "stage A": "experiments/visible_failure_20261113/full_out",
    "run of 14 November": "experiments/evidence_across_failures_20261114/full_out",
}
MAKERS = ("chain", "compose", "fork", "lbind", "matcher", "power", "rbind")
EXPRESSION = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\([A-Za-z0-9_,() ]*\)$")
MAKER_AS_VALUE = re.compile(r"(?<![A-Za-z0-9_])(%s)(?![A-Za-z0-9_(])" % "|".join(MAKERS))
RAPPLY = re.compile(r"(?<![A-Za-z0-9_])rapply\(")


def strings(node, out, surrounding, inside=False):
    """Every string of a record into `out`, or into `surrounding` when it sits under a key named `consumers`."""
    if isinstance(node, str):
        (surrounding if inside else out).add(node)
    elif isinstance(node, dict):
        for k, v in node.items():
            strings(v, out, surrounding, inside or k == "consumers")
    elif isinstance(node, (list, tuple)):
        for v in node:
            strings(v, out, surrounding, inside)


def main(argv):
    body = dict(author="Chimdi Walter Ndubuisi",
                what="static reading of saved records; nothing searched, no operation run; not a result", studies={})
    clean = True
    for study, rel in FOLDERS.items():
        folder = os.path.join(ROOT, rel)
        files = sorted(glob.glob(os.path.join(folder, "**", "*.json"), recursive=True))
        found, around, unread = set(), set(), 0
        for f in files:
            try:
                with open(f) as fh:
                    strings(json.load(fh), found, around)
            except (ValueError, OSError):
                unread += 1
        exprs = sorted(s for s in found if EXPRESSION.match(s) and s.count("(") == s.count(")"))
        texts = sorted(s for s in around if EXPRESSION.match(s) and s.count("(") == s.count(")"))
        maker = [e for e in exprs if MAKER_AS_VALUE.search(e)]
        rap = [e for e in exprs if RAPPLY.search(e)]
        calls = [e for e in exprs if any(re.search(r"(?<![A-Za-z0-9_])%s\(" % m, e) for m in MAKERS)]
        body["studies"][study] = dict(folder=rel, json_files=len(files), files_not_read=unread,
                                      distinct_expressions=len(exprs), calling_a_function_maker=len(calls),
                                      naming_a_function_maker_as_a_value=maker, using_rapply=rap,
                                      surrounding_program_texts_counted_apart=len(texts),
                                      surrounding_program_texts_using_rapply=[e for e in texts if RAPPLY.search(e)])
        clean = clean and not maker and not rap and unread == 0 and len(files) > 0
        print("%s: %d files, %d distinct expressions, %d call a function maker, %d name one as a value, %d use rapply"
              " | surrounding program texts counted apart: %d"
              % (study, len(files), len(exprs), len(calls), len(maker), len(rap), len(texts)))
    body["no_expression_touched_by_the_rule"] = clean
    print("no expression touched by the rule:", clean)
    if argv:
        with open(argv[0], "x") as fh:
            json.dump(body, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
