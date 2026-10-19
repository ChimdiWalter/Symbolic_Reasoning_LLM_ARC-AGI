"""The typed reasoning state S_t = (D, R_t, H_t, K_t, F_t, U_t, B_t) of Neural-CORA v1, and its observable diagnoses.

The state is updated after every candidate execution by `search.search_typed`. It records only what is observable at
inference time: the demonstrations, the test input, and the solver's own executions. The test output is never part
of the state.
- D: the task's demonstrations and test input (referenced, not copied).
- R_t: the segmentation views (object decompositions) of the consistent hypotheses so far.
- H_t: the version set, i.e. the demonstration-consistent hypotheses so far, with provenance (order position, score)
  and their test predictions.
- K_t: the typed vocabulary in force (grammar version and the pruned domain sizes).
- F_t: execution feedback. For each rejected candidate: the demonstration that first failed, and how (wrong cells,
  or no output / size change).
- U_t: the observable diagnoses below.
- B_t: the candidate budget, the candidates spent and the CPU time.

Observable diagnoses (facts about this run, not claims about the language):
- NO_FIT_OBSERVED: no candidate fits every demonstration within this language and budget. This does not show that
  the language is inadequate.
- AMBIGUOUS_PREDICTIONS: two or more consistent hypotheses disagree on the test input.
- UNVERIFIED_QUERY: every consistent hypothesis agrees on the test input. That is still unverified: agreement is not
  correctness.
- PROGRAM_REJECTED: a consistent hypothesis produced no output on the test input (native rejected it).
- TIMEOUT_OR_ERROR: a software or resource failure, not a reasoning diagnosis.
- FOLD_FRAGILITY: not computed by the v1 search. It needs leave-one-out reconstruction (implemented in CORA-v2,
  not here).

v1 does not yet *act* on these diagnoses: no revision action is chosen or executed. The action policy pi_phi is a
later, separately gated stage (records/NEURAL_CORA_V1_PILOT_PROTOCOL.md).
"""
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class ReasoningState:
    grammar: str
    budget: int
    domain_sizes: dict
    n_candidates: int = 0
    n_consistent: int = 0
    fail_demo: Counter = field(default_factory=Counter)        # F_t: first failing demonstration index
    fail_kind: Counter = field(default_factory=Counter)        # F_t: "wrong_cells" | "no_output_or_size"
    views: Counter = field(default_factory=Counter)            # R_t: views of consistent hypotheses
    n_test_rejected: int = 0                                   # PROGRAM_REJECTED evidence
    errors: int = 0                                            # TIMEOUT_OR_ERROR evidence
    distinct: int = 0                                          # distinct test predictions among H_t

    def observe(self, h, wrong, test_pred):
        """One execution's feedback. `wrong` is interp.fit's per-demonstration list; test_pred is None when no output."""
        self.n_candidates += 1
        if wrong and all(w == 0 for w in wrong):
            self.n_consistent += 1
            self.views[h.variant] += 1
            if test_pred is None:
                self.n_test_rejected += 1
        else:
            self.fail_demo[len(wrong) - 1] += 1
            self.fail_kind["no_output_or_size" if wrong[-1] is None else "wrong_cells"] += 1

    def diagnoses(self):
        d = []
        if self.n_consistent == 0:
            d.append("NO_FIT_OBSERVED")
        if self.distinct >= 2:
            d.append("AMBIGUOUS_PREDICTIONS")
        if self.distinct == 1:
            d.append("UNVERIFIED_QUERY")
        if self.n_test_rejected:
            d.append("PROGRAM_REJECTED")
        if self.errors:
            d.append("TIMEOUT_OR_ERROR")
        return d

    def summary(self):
        return {"grammar": self.grammar, "budget": self.budget, "domain_sizes": self.domain_sizes,
                "n_candidates": self.n_candidates, "n_consistent": self.n_consistent,
                "fail_demo": {str(k): v for k, v in sorted(self.fail_demo.items())}, "fail_kind": dict(self.fail_kind),
                "views_of_consistent": dict(self.views), "n_test_rejected": self.n_test_rejected,
                "errors": self.errors, "distinct_predictions": self.distinct, "diagnoses": self.diagnoses(),
                "fold_fragility": "not computed in v1 search"}
