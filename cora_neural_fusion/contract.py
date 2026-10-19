"""The typed, auditable proposal contract between the neural solver and CORA.

Every candidate that could reach an attempt slot is a `Proposal`. Its fields record:
- where it came from;
- what observations it used;
- what it claims;
- whether it executes;
- how it was verified.

`UNKNOWN` and `ABSTAIN` are legal values, so no proposal is forced into a valid program.
"""
from dataclasses import asdict, dataclass, field
from typing import List, Optional

SOURCES = ("NVARC_BASE", "QWEN_GUIDED_CORA", "CORA_BASE", "FALLBACK")
VERIFICATION = ("UNVERIFIED", "DEMO_CONSISTENT", "EXPLORATORY", "FOLD_CERTIFIED", "NEURAL_ASSISTED_NOT_INDEPENDENT",
                "REJECTED", "ABSTAIN")
OBSERVATIONS = "training input/output pairs and test inputs only; no test output"


@dataclass
class Proposal:
    task: str
    output_index: int
    grid: Optional[list]                       # None means ABSTAIN
    source: str                                # one of SOURCES
    rank: Optional[int] = None                 # the neural solver's own rank (0 = its attempt 1), if known
    neural_score: Optional[float] = None       # only if the run recorded it
    explained_by: List[dict] = field(default_factory=list)   # CORA hypotheses (summaries) predicting exactly this grid
    executable: bool = False                   # produced by executing a CORA hypothesis
    verification: str = "UNVERIFIED"           # one of VERIFICATION
    observations: str = OBSERVATIONS
    neural_provenance: str = "UNKNOWN"         # e.g. "adapted on all demonstrations (NVARC TTT)"
    cpu_s: float = 0.0
    note: str = ""

    def __post_init__(self):
        assert self.source in SOURCES and self.verification in VERIFICATION
        if self.grid is not None:
            assert valid_grid(self.grid), "not an ARC grid"

    def to_dict(self):
        return asdict(self)


def valid_grid(g):
    """An ARC grid: a non-empty rectangular list of lists of ints 0..9, at most 30 × 30."""
    return (isinstance(g, list) and 0 < len(g) <= 30 and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) <= 30
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
