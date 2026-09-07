"""Candidate-associated failure records: observer v1, additive and versioned.

The identified baseline already retains, for every one of its 200 attempted
hypotheses, the candidate triple, the fit status, the failure code and a detail
string that localizes the failure. `meta_baseline.tfg_from_trace` reduces that
to marginal counts by code and by partition, which discards the association

    which candidate  <->  which failure

and, when the baseline fails on every hypothesis, the partition marginal is
constant (50 of 200 per partition) and therefore carries no information at all.

This module recovers the association from the SAME trace. It does not change the
baseline, does not re-run it, does not relax fitting, and cannot turn a rejected
candidate into an accepted one. Every field it cannot establish from the
retained record is UNKNOWN; nothing is inferred from the generating target,
which this module never receives.

Non-interference: `observe()` is a pure function of a BaselineTrace that has
already completed. It performs no fitting, no evaluation and no I/O, holds no
state, and returns a new object. tests/test_candidate_trace.py checks that
running it leaves candidate order, per-candidate verdicts, accepted programs and
the trace object itself byte-identical, and measures its runtime cost.

DETAIL PARSING. The detail strings are prose emitted by the fitter. Parsing them
is reading evidence that was already recorded, not creating new evidence. The
grammar of recognized forms is declared in DETAIL_PATTERNS and versioned with
OBSERVER_VERSION; an unrecognized detail yields UNKNOWN fields rather than a
guess, and the count of unparsed details is reported so the representation's
coverage is never overstated.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

OBSERVER_VERSION = "candidate_trace:v1"

#: The marker for information the retained record does not contain. It is a
#: distinct value, never 0 and never a default, so a consumer cannot mistake
#: absence for a measurement.
UNKNOWN = None

#: Declared grammar of fitter detail strings. Each entry maps a compiled pattern
#: to the structured fields it establishes. Order matters only in that the first
#: match wins; the patterns are mutually exclusive by construction.
DETAIL_PATTERNS = (
    ("coverage_shortfall",
     re.compile(r"^covered (?P<covered>\d+) != changed (?P<changed>\d+)$")),
    ("partition_empty",
     re.compile(r"^partition (?P<partition>\S+) produced no sets$")),
    ("feature_undefined",
     re.compile(r"^feature (?P<feature>\S+) undefined on a region$")),
    ("region_partially_changed",
     re.compile(r"^block (?P<block>\d+) region partially changed$")),
    ("region_multicoloured",
     re.compile(r"^block (?P<block>\d+) region demands (?P<colours>\[.*\])$")),
    ("key_under_witnessed",
     re.compile(r"^block (?P<block>\d+) key (?P<key>.+) witnessed by "
                r"(?P<witnesses>\d+) < (?P<required>\d+) demonstrations$")),
    ("no_visible_constraint",
     re.compile(r"^block (?P<block>\d+) has no visible constraint$")),
    ("no_owned_change",
     re.compile(r"^block (?P<block>\d+) changes no owned cell$")),
    ("keys_never_visible",
     re.compile(r"^block (?P<block>\d+) keys never visible: (?P<keys>\[.*\])$")),
    ("nonfunctional_key",
     re.compile(r"^block (?P<block>\d+) key (?P<key>.+) demands "
                r"(?P<first>\d+) and (?P<second>\d+)$")),
    ("prefix_undefined",
     re.compile(r"^prefix undefined for (?P<partition>\S+)$")),
    ("unknown_partition",
     re.compile(r"^unknown partition (?P<partition>\S+)$")),
    ("demonstration_static", re.compile(r"^demonstration changes nothing$")),
    ("shape_change", re.compile(r"^shape change is outside this grammar$")),
    ("no_occurrences",
     re.compile(r"^no induced occurrences / unparsable structure$")),
)


@dataclass(frozen=True)
class CandidateFailureRecord:
    """One attempted baseline hypothesis and what was recorded about its failure.

    Everything here is derived from the baseline's own attempt on the
    demonstrations. No field is derived from the generating target.
    """
    index: int
    partition: str
    predicate: str
    feature: str
    status: str                      # EXACT_DEMONSTRATION_FIT / FIT_FAILURE / ...
    code: Optional[str]              # the fitter's failure code, or None
    detail_class: Optional[str]      # a key of DETAIL_PATTERNS, or None = UNKNOWN
    #  graded evidence, where the record contains it; UNKNOWN otherwise
    cells_covered: Optional[int] = UNKNOWN
    cells_changed: Optional[int] = UNKNOWN
    coverage_fraction: Optional[float] = UNKNOWN
    conflict_block: Optional[int] = UNKNOWN
    witnesses_seen: Optional[int] = UNKNOWN
    witnesses_required: Optional[int] = UNKNOWN
    #  what this record does NOT contain, named explicitly
    missing: tuple = field(default_factory=tuple)

    def to_json(self) -> dict:
        return asdict(self)


def _parse_detail(detail: str) -> tuple:
    if not detail:
        return None, {}
    for name, pattern in DETAIL_PATTERNS:
        match = pattern.match(detail)
        if match:
            return name, match.groupdict()
    return None, {}


#: fields a consumer might expect; any not established becomes an explicit
#: "missing" entry on the record rather than a silent absence
EXPECTED_FIELDS = ("cells_covered", "cells_changed", "coverage_fraction",
                   "conflict_block", "witnesses_seen", "witnesses_required")


def _record_from(row: dict) -> CandidateFailureRecord:
    partition, predicate, feature = row["triple"]
    detail_class, groups = _parse_detail(row.get("detail") or "")
    covered = changed = fraction = None
    block = seen = required = None
    if detail_class == "coverage_shortfall":
        covered, changed = int(groups["covered"]), int(groups["changed"])
        fraction = (covered / changed) if changed else None
    if "block" in groups:
        block = int(groups["block"])
    if detail_class == "key_under_witnessed":
        seen, required = int(groups["witnesses"]), int(groups["required"])
    values = {"cells_covered": covered, "cells_changed": changed,
              "coverage_fraction": fraction, "conflict_block": block,
              "witnesses_seen": seen, "witnesses_required": required}
    missing = tuple(name for name in EXPECTED_FIELDS if values[name] is UNKNOWN)
    return CandidateFailureRecord(
        index=int(row["index"]), partition=partition, predicate=predicate,
        feature=feature, status=row["status"], code=row.get("code"),
        detail_class=detail_class, missing=missing, **values)


@dataclass
class CandidateTrace:
    """The candidate-associated view of one completed baseline trace."""
    observer_version: str
    baseline_config_digest: str
    records: list
    unparsed_details: int
    observation_seconds: float

    def to_json(self) -> dict:
        return {"observer_version": self.observer_version,
                "baseline_config_digest": self.baseline_config_digest,
                "records": [r.to_json() for r in self.records],
                "unparsed_details": self.unparsed_details,
                "observation_seconds": round(self.observation_seconds, 4)}

    def identity(self) -> dict:
        """The representation itself, WITHOUT the measured runtime. Cost is
        accounted separately; a timing value must never enter an identity."""
        return {k: v for k, v in self.to_json().items() if k != "observation_seconds"}

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.identity(), sort_keys=True).encode()).hexdigest()

    def coverage_report(self) -> dict:
        """How much of the representation is actually populated. Reported so the
        signal is never overstated as richer than the records support."""
        total = len(self.records)
        populated = {name: sum(1 for r in self.records
                               if getattr(r, name) is not UNKNOWN)
                     for name in EXPECTED_FIELDS}
        return {"records": total, "populated_fields": populated,
                "unparsed_details": self.unparsed_details,
                "fully_unknown_records": sum(
                    1 for r in self.records if len(r.missing) == len(EXPECTED_FIELDS))}


def observe(trace) -> CandidateTrace:
    """Build the candidate-associated view from a COMPLETED baseline trace.

    Pure: reads `trace.records` and `trace.config_digest` and returns a new
    object. It mutates nothing, fits nothing, and evaluates nothing.
    """
    started = time.perf_counter()
    records = [_record_from(row) for row in trace.records]
    unparsed = sum(1 for row, rec in zip(trace.records, records)
                   if (row.get("detail") or "") and rec.detail_class is None)
    return CandidateTrace(observer_version=OBSERVER_VERSION,
                          baseline_config_digest=trace.config_digest,
                          records=records, unparsed_details=unparsed,
                          observation_seconds=time.perf_counter() - started)


# --------------------------------------------------------------------------
# the aggregate view, for the condition that must NOT see the association
# --------------------------------------------------------------------------

def aggregate_view(trace) -> dict:
    """Exactly what the current TFG exposes: marginal counts by failure code and
    by partition, plus the execution census. No candidate association."""
    by_code: dict = {}
    by_partition: dict = {}
    for row in trace.records:
        if row["status"] == "FIT_FAILURE":
            by_code[row["code"]] = by_code.get(row["code"], 0) + 1
            by_partition[row["triple"][0]] = by_partition.get(row["triple"][0], 0) + 1
    return {"failures_by_code": dict(sorted(by_code.items(), key=lambda kv: str(kv[0]))),
            "failures_by_partition": dict(sorted(by_partition.items())),
            "outcome_census": dict(sorted(trace.census.items())),
            "work_done": trace.work_done, "enumerated_total": trace.enumerated_total}
