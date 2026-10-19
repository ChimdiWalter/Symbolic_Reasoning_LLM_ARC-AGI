"""Learning-data audit for the Neural-CORA v1 pilot (generator side; it never reads an answers file).

    python -m cora_neural_v1.pilot audit

It regenerates every task deterministically with `generator.make_task(family, seed)` and checks:
- **Execution validity.** The generating program, re-run through the native interpreter, reproduces every
  demonstration and the test output. Every demonstration changes the grid. Every output keeps the input's shape.
- **Uniqueness and overlap.** It counts distinct program instances (canonical `program_sha`) per split, and the
  instances shared between splits.
- **Exact duplicate tasks** (identical demonstrations and test input) across splits. There must be none.
- **Composition signatures.** A signature is the selector types and action types per rule, with the default. No
  held-out family's signature may occur among the training families.
- **Template aliases (the held-out primary set).** A held-out task is *template-aliased* if a program with a training
  family's structure, under any parameters in the task's pruned domains, reproduces all of its demonstrations. Such a
  task could be solved without composing anything new. The decision reads demonstrations only.
  Aliased tasks are excluded from the primary held-out set, reported separately, and fixed before any arm runs.
"""
import hashlib
import json
from collections import Counter, defaultdict

import numpy as np

from cora_neural_v1 import generator as G
from cora_neural_v1 import interp as I
from cora_neural_v1 import space as SP
from cora_neural_v1.ir import LINE_AXES, VECTORS, DIRECTIONS, Hypothesis, Rule


def _task_hash(t):
    blob = json.dumps({"train": t["train"], "test_in": t["test"][0][0]}, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def signature(program):
    h = Hypothesis.from_dict(program)
    return (tuple((r.selector[0], r.action[0]) for r in h.rules), h.default)


def train_templates(train):
    """Every program with a TRAIN family's structure over the task's pruned domains (view S1, as generated)."""
    d = SP.domains(train)
    cols = [s[1] for s in d["selectors"] if s[0] == "color"]
    sizes = [s[1] for s in d["selectors"] if s[0] == "size"]
    outc = [a[1] for a in d["actions"] if a[0] == "recolor"]
    R = Rule
    T = defaultdict(list)
    for c in cols:
        for t in outc:
            T["T_recolor_by_colour"].append(((R(("color", c), ("recolor", t)),), "keep"))
        for v in VECTORS:
            T["T_translate_by_colour"].append(((R(("color", c), ("translate",) + tuple(v)),), "keep"))
        for ax in LINE_AXES:
            for t in outc:
                T["T_line_by_colour"].append(((R(("color", c), ("fill_line", ax, t)),), "keep"))
        T["T_keep_only_colour"].append(((R(("color", c), ("keep",)),), "delete"))
        T["T_delete_by_colour"].append(((R(("color", c), ("delete",)),), "keep"))
        for k in sizes:
            for t in outc:
                T["T_recolor_then_delete"].append(((R(("color", c), ("recolor", t)), R(("size", k), ("delete",))), "keep"))
            for v in VECTORS:
                T["T_translate_then_delete"].append(((R(("color", c), ("translate",) + tuple(v)),
                                                      R(("size", k), ("delete",))), "keep"))
        for ax in LINE_AXES:
            for t in outc:
                for t2 in outc:
                    T["T_line_then_recolor"].append(((R(("color", c), ("fill_line", ax, t)),
                                                      R(("true", None), ("recolor", t2))), "keep"))
    for k in sizes:
        T["T_delete_by_size"].append(((R(("size", k), ("delete",)),), "keep"))
    for t in outc:
        T["T_recolor_largest"].append(((R(("size_rank", 0), ("recolor", t)),), "keep"))
    for dd in DIRECTIONS:
        T["T_slide_all"].append(((R(("true", None), ("slide", dd)),), "keep"))
    assert set(T) <= set(G.TRAIN_FAMILIES)
    return T


def template_aliases(train):
    """The TRAIN families with at least one instance that reproduces every demonstration (demonstrations only)."""
    hits = []
    for fam, progs in train_templates(train).items():
        for rules, dflt in progs:
            if I.fit(Hypothesis("S1", rules, dflt), train)[0]:
                hits.append(fam)
                break
    return sorted(hits)


def _validate(t):
    h = Hypothesis.from_dict(t["program"])
    problems = []
    for k, (a, b) in enumerate(t["train"] + t["test"]):
        out = I.run(h, a)
        if out is None or not np.array_equal(out, np.asarray(b)):
            problems.append(f"pair {k}: program does not reproduce the stored output")
        if np.array_equal(np.asarray(a), np.asarray(b)):
            problems.append(f"pair {k}: unchanged grid")
        if np.asarray(a).shape != np.asarray(b).shape:
            problems.append(f"pair {k}: shape changes")
    return problems


def run_audit(splits, fams):
    """splits: {name: (family-set name, seeds)}; fams: {family-set name: families}. Returns the audit record and the
    held-out primary-set flags {task index in eval_heldout order: aliased families}."""
    rec, tasks_by_split = {"splits": {}}, {}
    for split, (fs, seeds) in splits.items():
        rows = []
        for fam in fams[fs]:
            for s in seeds:
                t = G.make_task(fam, s)
                if t is not None:
                    rows.append(t)
        tasks_by_split[split] = rows
        probs = {t["task_id"]: p for t in rows if (p := _validate(t))}
        shapes = Counter(f"{len(t['train'][0][0])}x{len(t['train'][0][0][0])}" for t in rows)
        rec["splits"][split] = {
            "n_tasks": len(rows), "families": dict(Counter(t["family"] for t in rows)),
            "n_distinct_program_instances": len({Hypothesis.from_dict(t["program"]).program_sha() for t in rows}),
            "n_signatures": len({signature(t["program"]) for t in rows}),
            "execution_problems": probs, "n_execution_problems": len(probs),
            "demos_per_task": dict(Counter(len(t["train"]) for t in rows)),
            "first_demo_shapes_top5": dict(shapes.most_common(5))}
    # cross-split overlap of program instances and exact duplicate tasks
    inst = {s: {Hypothesis.from_dict(t["program"]).program_sha() for t in r} for s, r in tasks_by_split.items()}
    th = {s: {_task_hash(t) for t in r} for s, r in tasks_by_split.items()}
    names = list(tasks_by_split)
    rec["overlap"] = {f"{a}~{b}": {"shared_program_instances": len(inst[a] & inst[b]),
                                   "exact_duplicate_tasks": len(th[a] & th[b])}
                      for i, a in enumerate(names) for b in names[i + 1:]}
    tr_sig = {signature(t["program"]) for t in tasks_by_split["train"]}
    rec["heldout_signatures_in_train"] = sorted(str(signature(t["program"])) for t in tasks_by_split["eval_heldout"]
                                                if signature(t["program"]) in tr_sig)
    # template aliases: held-out tasks a TRAIN-structure program explains from the demonstrations
    flags = {}
    for i, t in enumerate(tasks_by_split["eval_heldout"]):
        flags[i] = template_aliases(t["train"])
    by_fam = defaultdict(lambda: [0, 0])
    for i, t in enumerate(tasks_by_split["eval_heldout"]):
        by_fam[t["family"]][0] += 1
        by_fam[t["family"]][1] += bool(flags[i])
    rec["heldout_template_aliased"] = {f: {"n": n, "aliased": a, "primary": n - a} for f, (n, a) in sorted(by_fam.items())}
    rec["heldout_primary_n"] = sum(1 for v in flags.values() if not v)
    rec["heldout_aliased_by_template"] = dict(Counter(f for v in flags.values() for f in v))
    return rec, flags, tasks_by_split
