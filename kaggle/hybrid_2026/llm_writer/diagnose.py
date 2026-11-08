"""CORA's diagnosis of a program that does not reproduce the demonstrations, at the level that failed, and the two
feedback texts derived from it (arm H1: the diagnosis; arm H2: only which examples are wrong).

Demonstrations only (never a test output). Levels, each tied to an observable in CORA's execution:
- syntax / type: CORA's parser or type checker rejected the text (its message);
- execution: no output on some example or test input (a native runtime failure);
- shape: an output of the wrong size;
- selection_too_general: a rule picks objects that must stay unchanged and changes them (broken cells);
- selection_too_specific: objects that change in the output are picked by no rule (or a delete default removes
  objects that must stay);
- action: a rule picks the right objects but does the wrong kind of change (recolour vs move vs delete);
- parameters: the right kind of change with the wrong value (colour, offset, table entry, binding);
- composition: cells that must change lie outside every picked object (cells to draw), so another rule or a
  different combination is needed;
- representation: the changes do not align with the objects of the program's view (objects change only in part,
  or another view explains the changes as whole-object changes).

Selection is read from native CORA (`cora_neural_v2g3.scene.selections`, version 4's `_picks`), fates from
`cora_neural_v2g3.scene.analyse`, cell counts from the execution deltas, residual locality from
`cora_neural_hybrid.feedback.locality` and the competing hypotheses from `cora_neural_hybrid.diagnosis.score`
(kept in the record). Nothing here changes a program; the writer revises it (H1's revisions are prompted, not a
trained controller).
"""
from dataclasses import dataclass

import numpy as np

from cora_neural_v2.rast import N, to_sexpr
from cora_neural_v2g3 import scene as SC
from cora_neural_v2g4 import program as PG
from cora_neural_v2g4 import search as S4
from cora_neural_hybrid import diagnosis as DG
from cora_neural_hybrid import feedback as FB
from llm_writer import perceive as PC

MOVE_OPS = {"translate", "move_to", "move_until_adjacent", "move_until_adjacent_to"}
FAMILY = {"recolor": "recoloured", "paint": "recoloured", "delete": "deleted", "keep": "unchanged"}
SHOW_GRID_MAX = 15
MAX_ITEMS = 4


@dataclass
class Finding:
    level: str
    cells: int
    message: str


def _obj_text(i, j, cells, colour):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return f"example {i + 1} #{j} (colour {colour}, size {len(cells)}, rows {min(rs)}-{max(rs)} cols {min(cs)}-{max(cs)})"


def _fate_text(o):
    if o.fate == "recoloured":
        return f"becomes colour {o.to_colour}"
    if o.fate == "moved":
        return f"moves by ({o.vector[0]},{o.vector[1]})"
    if o.fate == "deleted":
        return "is deleted"
    if o.fate == "unchanged":
        return "stays unchanged"
    return "changes in a more complex way"


def _family(action):
    if not isinstance(action, N):
        return None
    if action.op in FAMILY:
        return FAMILY[action.op]
    if action.op in MOVE_OPS:
        return "moved"
    return None


def _outputs(prog, train):
    outs = []
    for a, _ in train:
        try:
            o = S4._execute(prog, a)
        except Exception:                                  # noqa: BLE001
            o = None
        outs.append(None if o is None else np.asarray(o))
    return outs


def _rules(prog):
    """[(selector, action)] of a native object program, or None."""
    if not (isinstance(prog, N) and prog.op == "program"):
        return None
    out = []
    for r in prog.args[1]:
        if r.op == "rule":
            out.append((r.args[0], r.args[1]))
        elif r.op == "rule_with":
            out.append((r.args[1], r.args[2]))
    return out


def _object_findings(prog, view, rules, default, train, outs, label="rule"):
    """Selection, action and parameter findings for a native object program (same-shape demonstrations)."""
    sc = SC.analyse(train, view)
    if sc is None:
        return [], set()
    sels = [s for s, _ in rules]
    picks = SC.selections(view, sels, train) if sels else {}
    natives = [SC.native_objects(a, view) for a, _ in train]
    general, specific, action, params, default_del = {}, [], {}, {}, []
    covered = set()                       # (demo, cell) lying on an analysed object
    for i, ((a, b), out) in enumerate(zip(train, outs)):
        if out is None or out.shape != np.asarray(b).shape:
            continue
        A, B = np.asarray(a), np.asarray(b)
        objs, _bg = natives[i]
        for o in sc.objects[i]:
            cells = sorted(o.cells)
            colour = int(objs[o.index].color)
            covered.update((i, x) for x in cells)
            dest = cells
            if o.fate == "moved":
                dest = [(r + o.vector[0], c + o.vector[1]) for r, c in cells]
                covered.update((i, x) for x in dest)
            wrong = sum(bool(out[x] != B[x]) for x in set(cells) | set(dest)
                        if 0 <= x[0] < B.shape[0] and 0 <= x[1] < B.shape[1])
            owner = None
            for k, s in enumerate(sels):
                p = picks.get(s, [None] * len(train))[i]
                if p is not None and o.index in p:
                    owner = k
                    break
            desc = _obj_text(i, o.index, cells, colour)
            if owner is None:
                if o.fate != "unchanged" and default == "keep" and wrong:
                    specific.append((wrong, desc, _fate_text(o)))
                elif o.fate == "unchanged" and default == "delete" and wrong:
                    default_del.append((wrong, desc))
                continue
            act = rules[owner][1]
            if not wrong:
                continue
            if o.fate == "unchanged":
                general.setdefault(owner, []).append((wrong, desc))
                continue
            fam = _family(act)
            if fam is not None and fam != o.fate and o.fate != "other":
                action.setdefault(owner, []).append((wrong, desc, _fate_text(o), act.op))
            else:
                params.setdefault(owner, []).append((wrong, desc, _fate_text(o), act.op))
    found = []

    def items(lst, k=MAX_ITEMS):
        lst = sorted(lst, key=lambda t: -t[0])
        more = f" and {len(lst) - k} more" if len(lst) > k else ""
        return lst[:k], more
    for k, lst in general.items():
        top, more = items(lst)
        found.append(Finding("selection_too_general", sum(t[0] for t in lst),
                             f"{label.capitalize()} {k + 1} {to_sexpr(sels[k])} also changes objects that must stay "
                             f"unchanged: " + "; ".join(t[1] for t in top) + more + "."))
    if specific:
        top, more = items(specific)
        found.append(Finding("selection_too_specific", sum(t[0] for t in specific),
                             "No rule picks these objects, but they change: " +
                             "; ".join(f"{t[1]} {t[2]}" for t in top) + more + "."))
    if default_del:
        top, more = items(default_del)
        found.append(Finding("selection_too_specific", sum(t[0] for t in default_del),
                             "The default `delete` removes objects that must stay; no rule keeps them: " +
                             "; ".join(t[1] for t in top) + more + "."))
    for k, lst in action.items():
        top, more = items(lst)
        found.append(Finding("action", sum(t[0] for t in lst),
                             f"{label.capitalize()} {k + 1} picks objects that change, but its action "
                             f"({lst[0][3]}) is the wrong kind of change: " +
                             "; ".join(f"{t[1]} {t[2]}" for t in top) + more + "."))
    for k, lst in params.items():
        top, more = items(lst)
        found.append(Finding("parameters", sum(t[0] for t in lst),
                             f"{label.capitalize()} {k + 1} ({lst[0][3]}) picks the right objects but produces the "
                             f"wrong result on them (check its colour, offset, table or reference): " +
                             "; ".join(f"{t[1]} {t[2]}" for t in top) + more + "."))
    return found, covered


def _layer_findings(prog, train, outs):
    """Findings for version 4 part and ray rules. A picked object none of whose cells (nor the cells the rule paints
    from it) change is a selection error; a picked object that does change but gets wrong cells points at the
    rule's parameters (part kind, direction, stop or colour), not at its selector (fault-injection audit, 26 Oct)."""
    found = []
    for k, rule in enumerate(prog.rules):
        bad_sel, bad_par, good, objs_sel, objs_par = 0, 0, 0, [], []
        for i, ((a, b), out) in enumerate(zip(train, outs)):
            A, B = np.asarray(a), np.asarray(b)
            if A.shape != B.shape:
                continue
            gkey = PG._key(A)
            cells, colours, bg = PG._objects(prog.view, gkey)
            picked = PG._picks(prog.view, rule.sel, gkey)
            if picked is None:
                continue
            diff = A != B
            for j in sorted(picked):
                colour = colours[j] if rule.colour == "own" else int(rule.colour)
                painted = PG.rule_cells(rule, cells[j], A, bg)
                nb = sum(1 for x in painted if B[x] != colour)
                good += len(painted) - nb
                if not nb:
                    continue
                touched = any(diff[x] for x in set(cells[j]) | set(painted))
                desc = _obj_text(i, j, sorted(cells[j]), colours[j])
                if touched:
                    bad_par += nb
                    objs_par.append((nb, desc))
                else:
                    bad_sel += nb
                    objs_sel.append((nb, desc))
        kind = rule.kind if isinstance(rule, PG.PartRule) else "ray"
        what = "part kind or colour" if isinstance(rule, PG.PartRule) else "direction, stop or colour"
        for level, nbad, objs, text in (("selection_too_general", bad_sel, objs_sel,
                                         "it picks objects that do not change at all"),
                                        ("parameters", bad_par, objs_par,
                                         f"its objects do change, but not as painted: check its {what}")):
            if nbad:
                objs.sort(key=lambda t: -t[0])
                more = f" and {len(objs) - MAX_ITEMS} more" if len(objs) > MAX_ITEMS else ""
                found.append(Finding(level, nbad, f"Part/ray rule {k + 1} ({kind}) paints {nbad} cells that must not "
                                     f"get that colour; {text} (" + "; ".join(t[1] for t in objs[:MAX_ITEMS]) + more +
                                     f"). {good} of its painted cells are right."))
    return found


def _residual_findings(task, prog, ex, outs, covered, view):
    """Composition and representation findings from the cells still wrong."""
    train = task["train"]
    found = []
    add_cells, add_colours, boxes = 0, {}, []
    for i, ((a, b), out) in enumerate(zip(train, outs)):
        A, B = np.asarray(a), np.asarray(b)
        if out is None or A.shape != B.shape or out.shape != B.shape:
            continue
        miss = (out != B) & (A != B)
        objs, bg = SC.native_objects(A, view)
        onobj = np.zeros(A.shape, bool)
        for o in objs:
            for x in o.cells:
                onobj[x] = True
        drawn = miss & ~onobj
        for x in zip(*np.nonzero(drawn)):
            if (i, (int(x[0]), int(x[1]))) in covered:
                drawn[x] = False
        n = int(drawn.sum())
        if n:
            add_cells += n
            for c in B[drawn]:
                add_colours[int(c)] = add_colours.get(int(c), 0) + 1
            rs, cs = np.nonzero(drawn)
            boxes.append(f"example {i + 1}: {n} cells in rows {rs.min()}-{rs.max()} cols {cs.min()}-{cs.max()}")
    if add_cells:
        cols = ", ".join(f"{c} ({n})" for c, n in sorted(add_colours.items(), key=lambda t: -t[1]))
        found.append(Finding("composition", add_cells,
                             f"{add_cells} background cells must change (to colours {cols}) and the program does "
                             f"not draw them: " + "; ".join(boxes[:3]) + ". Another rule (for example a part, ray, "
                             "copy or fill rule) or another combination of rules is needed."))
    try:
        if ex is not None and ex.deltas and all(d.shape_ok and d.remaining is not None for d in ex.deltas):
            a_, p_, w_ = FB.locality(ex, task, view)
            if p_ and p_ >= max(a_, w_):
                best, share = PC.choose_view(train)
                alt = f" In view {best} {round(100 * share)}% of the changed cells are whole-object changes." \
                    if best != view and share > 0 else ""
                found.append(Finding("representation", p_,
                                     f"{p_} still-wrong cells are on objects of view {view} that change only in part:"
                                     f" the changes do not follow these objects. Consider part rules (border, "
                                     f"interior, endpoints, corners, contact, holes) or another view.{alt}"))
    except Exception:                                      # noqa: BLE001
        pass
    return found


def _demo_lines(ex, train):
    lines = []
    for i, (p, (a, b)) in enumerate(zip(ex.per_demo or [], train)):
        if not p.get("shape_ok", True):
            gs = p.get("got_shape")
            lines.append(f"Example {i + 1}: expected a {p['expected_shape'][0]}x{p['expected_shape'][1]} output, got "
                         + (f"{gs[0]}x{gs[1]}." if gs else "no output (CORA could not execute it)."))
        elif p["wrong"] == 0:
            lines.append(f"Example {i + 1}: correct.")
        elif p.get("fixed") is not None:
            need = p["fixed"] + p["remaining"]
            lines.append(f"Example {i + 1}: {need} cells had to change; the program got {p['fixed']} right, left "
                         f"{p['remaining']} wrong, and changed {p['broken']} cells that had to stay.")
        else:
            lines.append(f"Example {i + 1}: {p['wrong']} of {p['cells']} cells wrong.")
    return lines


def _show_output(ex, train, outs, sep=""):
    for i, (p, (a, b), out) in enumerate(zip(ex.per_demo or [], train, outs)):
        if out is None or not p.get("shape_ok", True) or not p.get("wrong"):
            continue
        B = np.asarray(b)
        if max(out.shape) <= SHOW_GRID_MAX:
            return f"The program's output for example {i + 1} (compare with the expected output above):\n" + \
                PC.grid_text(out, sep)
        rs, cs = np.nonzero(out != B)
        pairs = [f"({r},{c}) expected {B[r, c]} got {out[r, c]}" for r, c in list(zip(rs, cs))[:12]]
        return f"Wrong cells in example {i + 1} (row, column): " + "; ".join(pairs)
    return ""


def failing_examples(ex, n_train):
    if ex is None or ex.status in ("INVALID",) or not ex.per_demo:
        return list(range(n_train))
    return [i for i, p in enumerate(ex.per_demo) if not p.get("shape_ok", True) or p.get("wrong")]


def diagnose(task, prog=None, ex=None, error=None, sep=""):
    """{status, levels, findings, hypotheses, text (H1), blind (H2)} for one failed program."""
    train = task["train"]
    if error is not None or prog is None:
        level = "type" if (error or "").startswith("does not type-check") else "syntax"
        return {"status": "INVALID", "levels": [level], "findings": [{"level": level, "cells": 0, "message": error}],
                "hypotheses": [], "text": f"CORA could not use it: {error}",
                "blind": "CORA could not use it: the program is not valid."}
    if ex.status == "INVALID":
        return {"status": "INVALID", "levels": ["type"], "findings": [{"level": "type", "cells": 0,
                                                                      "message": ex.reason}],
                "hypotheses": [], "text": f"CORA could not compile it: {ex.reason}",
                "blind": "CORA could not use it: the program is not valid."}
    bad = failing_examples(ex, len(train))
    blind = ("CORA ran it: the output is wrong on example" + ("s " if len(bad) > 1 else " ") +
             ", ".join(str(i + 1) for i in bad) + ".") if bad else "CORA ran it: the output is wrong on a test input."
    findings, levels = [], []
    outs = getattr(ex, "outs", None) or _outputs(prog, train)
    if ex.status == "ERROR":
        if (ex.reason or "").startswith("no output on a test input"):
            detail = ex.reason[len("no output on a test input"):].strip(" ()")
            findings.append(Finding("execution", 0, "It reproduces every example but CORA cannot execute it on the "
                                    "test input" + (f": {detail}" if detail else "") + ". Make the program cover what "
                                    "the test input contains (for example every colour a table needs, or a "
                                    "reference that exists)."))
        elif "exceeded" in (ex.reason or ""):
            findings.append(Finding("execution", 0, "Its execution took too long."))
        else:
            for i, p in enumerate(ex.per_demo or []):
                if not p.get("shape_ok", True):
                    lev = "execution" if p.get("got_shape") is None else "shape"
                    err = f" CORA reports: {p['error']}." if p.get("error") else ""
                    findings.append(Finding(lev, int(np.prod(p["expected_shape"])),
                                            f"Example {i + 1}: " + (f"CORA could not execute it (no output).{err}"
                                                                    if lev == "execution" else
                                                                    f"output {p['got_shape'][0]}x{p['got_shape'][1]}"
                                                                    f", expected {p['expected_shape'][0]}x"
                                                                    f"{p['expected_shape'][1]}.")))
    else:
        view = getattr(prog, "view", None) or (prog.args[0] if isinstance(prog, N) and prog.op == "program" else "S1")
        covered = set()
        try:
            base = prog.base if isinstance(prog, PG.G4Program) else prog
            rules = _rules(base) if base is not None else None
            same = all(np.asarray(a).shape == np.asarray(b).shape for a, b in train)
            render_same = rules is not None and base.args[3] == N("same_as_input", ())
            if rules is not None and same and render_same:
                f, covered = _object_findings(base, base.args[0], rules, base.args[2], train,
                                              _outputs(base, train) if isinstance(prog, PG.G4Program) else outs)
                findings += f
            if isinstance(prog, PG.G4Program) and same:
                findings += _layer_findings(prog, train, outs)
            if same:
                findings += _residual_findings(task, prog, ex, outs, covered, view)
        except Exception as e:                             # noqa: BLE001 (diagnosis is best effort)
            findings.append(Finding("execution", 0, f"(diagnosis incomplete: {type(e).__name__})"))
    findings.sort(key=lambda f: -f.cells)
    levels = list(dict.fromkeys(f.level for f in findings))
    hyps = []
    try:
        fb = FB.from_execution(ex, task) if ex.status == "INCOMPLETE" else None
        if fb is not None:
            hyps = [{"hypothesis": d.hypothesis, "score": round(d.score, 3)} for d in DG.score(fb)]
    except Exception:                                      # noqa: BLE001
        pass
    lines = ["CORA ran it."] + _demo_lines(ex, train)
    if findings:
        lines.append("Diagnosis, largest problem first:")
        for n, f in enumerate(findings[:5]):
            lines.append(f"{n + 1}. [{f.level.replace('_', ' ')}] {f.message}")
    shown = _show_output(ex, train, outs, sep)
    if shown:
        lines.append(shown)
    return {"status": ex.status, "levels": levels,
            "findings": [{"level": f.level, "cells": f.cells, "message": f.message} for f in findings],
            "hypotheses": hyps, "text": "\n".join(lines), "blind": blind}
