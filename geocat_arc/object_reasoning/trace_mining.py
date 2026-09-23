"""Round-9 lever 4/1 shared logic: classify LOO fold-divergence traces.

A trace entry (LOOReport.divergence, persisted in near-solve records under
residual["loo_divergence"]) pairs the full-data program with the program a
fold reinduced.  Classification names WHY the fold diverged; the categories
are the mining vocabulary of the parameter-expression loop:

  param_value_diff:<action>.<param>:<op>   same structure and expression
      kind, different args — the memorized-constant signature; the fix is
      a relational spelling for exactly this parameter
  param_kind_diff:<action>.<param>:<a>-><b> the fold picked a different
      expression kind — ranking instability or a missing forced spelling
  param_missing:<param>  parameter present on one side only
  selector_diff          same actions, different selector
  structure_diff         different rule count / action sequence
  no_fold_program        reinduction returned nothing
  eval_error             the fold program crashed on the held-out pair
  identical_program_diverged  same serialized program, different outcome
      (environment- or ranking-order-sensitivity — a fold-invariance bug)
"""


def _rules(prog):
    if not prog:
        return None
    return prog.get("rules") or []


def _sig(rule):
    return (rule.get("action") or {}).get("delta_type")


def classify_divergence(full_prog, trace):
    if trace.get("error"):
        return ["eval_error"]
    fold_prog = trace.get("fold_program")
    if fold_prog is None:
        return ["no_fold_program"]
    fr, gr = _rules(full_prog), _rules(fold_prog)
    if fr is None:
        return ["no_full_program"]
    if len(fr) != len(gr) or [_sig(r) for r in fr] != [_sig(r) for r in gr]:
        return ["structure_diff"]
    kinds = []
    for rf, rg in zip(fr, gr):
        if rf.get("selector") != rg.get("selector"):
            kinds.append("selector_diff")
        pf = (rf.get("action") or {}).get("params") or {}
        pg = (rg.get("action") or {}).get("params") or {}
        for name in set(pf) | set(pg):
            ef, eg = pf.get(name), pg.get(name)
            if ef == eg:
                continue
            if ef is None or eg is None:
                kinds.append(f"param_missing:{name}")
            elif ef.get("op") == eg.get("op"):
                kinds.append(f"param_value_diff:{_sig(rf)}.{name}"
                             f":{ef.get('op')}")
            else:
                kinds.append(f"param_kind_diff:{_sig(rf)}.{name}"
                             f":{ef.get('op')}->{eg.get('op')}")
    return kinds or ["identical_program_diverged"]
