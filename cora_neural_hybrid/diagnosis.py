"""Competing diagnostic hypotheses about WHY an explanation is inadequate. Never a single label: every hypothesis gets
an evidence score from observable execution, and the scores order the revision actions. Every revision is then
executed (revision.py), so a wrong diagnosis costs budget but can never certify anything.

| hypothesis | observable evidence (demonstrations only) | revision actions it suggests |
|---|---|---|
| REPRESENTATION_INADEQUATE | still-wrong cells fall on parts of objects or on background, not whole objects | REVISE_REPRESENTATION, REVISE_OBJECT_PARTS |
| OPERATIONS_INSUFFICIENT | no candidate edit of the current program reduces the wrong cells; whole objects still wrong | REVISE_OBJECT_PARTS, ADD_RULE |
| NOT_GENERATED | the program is close (few wrong cells, nothing broken) and the edit space is not exhausted | REVISE_SELECTOR, REVISE_ACTION, REVISE_BINDINGS |
| BUDGET_INSUFFICIENT | the search used its whole budget without a fit | ALLOCATE_MORE_SEARCH |
| WEAK_SUPPORT | a fit exists but rests on thin evidence (leave-one-out instability or single-demonstration table entries) | KEEP_ALTERNATIVES, ABSTAIN |
| AMBIGUOUS_DEMONSTRATIONS | several fits predict different test outputs | KEEP_ALTERNATIVES |

The scores below are hand-set (a rule-based diagnostician, ledger level L1). A learned diagnostician would replace
`score` with a trained model over feedback.vector; that is the M9 hypothesis and is untested.
"""
from dataclasses import dataclass

HYPOTHESES = ("REPRESENTATION_INADEQUATE", "OPERATIONS_INSUFFICIENT", "NOT_GENERATED", "BUDGET_INSUFFICIENT",
              "WEAK_SUPPORT", "AMBIGUOUS_DEMONSTRATIONS")
SUGGESTS = {"REPRESENTATION_INADEQUATE": ("REVISE_REPRESENTATION", "REVISE_OBJECT_PARTS"),
            "OPERATIONS_INSUFFICIENT": ("REVISE_OBJECT_PARTS", "ADD_RULE"),
            "NOT_GENERATED": ("REVISE_SELECTOR", "REVISE_ACTION", "REVISE_BINDINGS"),
            "BUDGET_INSUFFICIENT": ("ALLOCATE_MORE_SEARCH",),
            "WEAK_SUPPORT": ("KEEP_ALTERNATIVES", "ABSTAIN"),
            "AMBIGUOUS_DEMONSTRATIONS": ("KEEP_ALTERNATIVES",)}


@dataclass
class Diagnosis:
    hypothesis: str
    score: float                     # evidence in [0, 1]; not a probability
    evidence: str


def score(fb, budget_exhausted=False, edits_exhausted=False, loo_unstable=False, thin_tables=False):
    """[Diagnosis] for one feedback record (feedback.Feedback), highest evidence first."""
    out = []
    if fb.status == "FITS":
        out.append(Diagnosis("AMBIGUOUS_DEMONSTRATIONS", 1.0 if fb.n_behaviours > 1 else 0.0,
                             f"{fb.n_behaviours} distinct test predictions among {fb.n_fits} fits"))
        out.append(Diagnosis("WEAK_SUPPORT", 1.0 if (loo_unstable or thin_tables) else 0.0,
                             "leave-one-out unstable" if loo_unstable else ("thin table support" if thin_tables
                                                                            else "no thin-evidence signal")))
    else:
        local = fb.share_part + fb.share_added
        out.append(Diagnosis("REPRESENTATION_INADEQUATE", local,
                             f"{fb.share_part:.2f} of still-wrong cells on parts of objects, {fb.share_added:.2f} on "
                             f"background"))
        out.append(Diagnosis("OPERATIONS_INSUFFICIENT", (1.0 if edits_exhausted else 0.3) * fb.share_whole,
                             f"{fb.share_whole:.2f} on whole objects; edit space "
                             f"{'exhausted' if edits_exhausted else 'not exhausted'}"))
        near = 1.0 if (fb.status == "INCOMPLETE" and fb.broken == 0 and fb.fixed > fb.remaining) else 0.2
        out.append(Diagnosis("NOT_GENERATED", near * (0.0 if edits_exhausted else 1.0),
                             f"fixed {fb.fixed}, still wrong {fb.remaining}, broken {fb.broken}"))
        out.append(Diagnosis("BUDGET_INSUFFICIENT", 1.0 if budget_exhausted else 0.0,
                             "search budget exhausted" if budget_exhausted else "budget left"))
    out.sort(key=lambda d: -d.score)
    return out


def actions(diagnoses):
    """Revision actions ordered by the evidence for the hypotheses that suggest them (ties keep table order)."""
    order, seen = [], set()
    for d in diagnoses:
        if d.score <= 0:
            continue
        for a in SUGGESTS[d.hypothesis]:
            if a not in seen:
                seen.add(a)
                order.append(a)
    return order
