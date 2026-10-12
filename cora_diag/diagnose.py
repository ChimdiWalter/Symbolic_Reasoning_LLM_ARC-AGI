"""Domain-neutral core: observations -> hypotheses (with status) -> decision.

Observation keys (all optional, all from recorded traces of the attempt):
  repairs_proposed           int   repairs the constructor produced from permitted evidence
  repair_support_ok          bool  the constructor's evidence met its support minimum
  verdict_reached            bool  the reasoner returned accept/reject before any budget event
  hard_cap_hit               bool  a hard wall-clock cap ended the attempt
  deadline_hits              int   deadline events anywhere in the attempt
  accepted                   bool  the reasoner accepted a program
  top_level_fit              bool  a program fitting every training example was found
  rederivations              int   independent re-derivations attempted (inner leave-one-out folds)
  rederivations_failed       int   of those, how many failed
  rederivation_changed_program bool a failed re-derivation produced a different program
  evidence_unit_excluded_in_failed_rederivation  bool  the representation unit carrying the
                                   repair's evidence was cut or ineligible in a failed re-derivation's subset
  competing_repairs          int   repairs fitting all permitted evidence
  competing_repairs_disagree bool  they predict differently on a permitted unlabelled input
"""
CATEGORIES = ("REPAIR_NOT_GENERATED", "REPRESENTATION_EXCLUDED", "MULTIPLE_PLAUSIBLE_REPAIRS", "ENGINE_REJECTED",
              "CERTIFICATION_UNSTABLE", "RESOURCE_EXHAUSTED", "UNKNOWN")
DECISION = {"REPAIR_NOT_GENERATED": "CONSTRUCT_WITH_MORE_EVIDENCE_OR_ABSTAIN", "REPRESENTATION_EXCLUDED": "NO_ACTION",
            "MULTIPLE_PLAUSIBLE_REPAIRS": "ABSTAIN", "ENGINE_REJECTED": "NO_ACTION_INVESTIGATE",
            "CERTIFICATION_UNSTABLE": "NO_ACTION_INVESTIGATE", "RESOURCE_EXHAUSTED": "SEARCH_MORE_AT_MATCHED_ACCOUNTING_OR_NO_ACTION",
            "UNKNOWN": "NO_ACTION"}


def diagnose(obs: dict) -> dict:
    h = []

    def add(cat, status, because):
        h.append({"category": cat, "status": status, "because": because})
    g = obs.get
    if g("repairs_proposed") == 0:
        add("REPAIR_NOT_GENERATED", "ESTABLISHED", "repairs_proposed == 0")
    if g("hard_cap_hit"):
        add("RESOURCE_EXHAUSTED", "ESTABLISHED", "hard_cap_hit")
    elif (g("deadline_hits") or 0) > 0 and not g("accepted"):
        add("RESOURCE_EXHAUSTED", "SUSPECTED", "deadline_hits > 0 without acceptance")
    if g("evidence_unit_excluded_in_failed_rederivation"):
        add("REPRESENTATION_EXCLUDED", "ESTABLISHED", "evidence unit cut or ineligible in a failed re-derivation")
    if (g("competing_repairs") or 0) >= 2:
        if g("competing_repairs_disagree"):
            add("MULTIPLE_PLAUSIBLE_REPAIRS", "ESTABLISHED", "two or more fitting repairs disagree on a permitted input")
        elif g("competing_repairs_disagree") is None:
            add("MULTIPLE_PLAUSIBLE_REPAIRS", "SUSPECTED", "two or more fitting repairs; disagreement not computed")
    if g("verdict_reached") and g("accepted") is False:
        add("ENGINE_REJECTED", "ESTABLISHED", "a verdict was reached and it was a rejection")
    if g("top_level_fit") and (g("rederivations_failed") or 0) > 0 and g("rederivation_changed_program"):
        add("CERTIFICATION_UNSTABLE", "ESTABLISHED", "fitting program, failed re-derivation with a different program")
    if not h and not g("accepted"):
        add("UNKNOWN", "OBSERVED", "no predicate holds")
    established = [x["category"] for x in h if x["status"] == "ESTABLISHED"]
    order = ["MULTIPLE_PLAUSIBLE_REPAIRS", "REPAIR_NOT_GENERATED", "REPRESENTATION_EXCLUDED", "RESOURCE_EXHAUSTED",
             "CERTIFICATION_UNSTABLE", "ENGINE_REJECTED", "UNKNOWN"]
    primary = next((c for c in order if c in established), "UNKNOWN" if not g("accepted") else None)
    return {"hypotheses": h, "established": sorted(established),
            "decision": DECISION.get(primary, "NONE") if primary else "NONE", "primary": primary}
