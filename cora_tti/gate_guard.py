"""Mechanical enforcement of the Capability-Growth Gate's access order and provenance.

Two properties are enforced in code rather than by recollection.

ACCESS ORDER. Three sealed classes unlock at different stages:

    STEP_B_SEMANTICS  the run's journal, witnesses, inventory, gate outputs,
                      mechanism inputs, expectation seal, runner source and
                      Step-B source. Unlocks at stage 3, because stages 1 and 2
                      exist to pin the hashes before anything is inspected.
    E_TRANSFER        the reserved transfer set, the provenance firewall that
                      holds its identifiers and the forbidden-name map, and raw
                      ARC training data from which blinded tokens could be
                      re-identified. Unlocks at stage 7. Never a tuning signal.
    LOCKBOX           Lockbox200, the holdout split, and raw ARC evaluation
                      data. Unlocks only once the whole gate is complete.

Classification is relative to the project root of whichever checkout holds the
file, main or dev worktree, so a sealed artifact cannot escape by being copied
into the worktree, and an unrelated ancestor directory name cannot decide a
class. It fails closed: an unrecognized file under a watched root is sealed.
Copies of Step-B artifacts inside the dev worktree are never read by any gate
stage at all, because the pinned main-checkout artifact is the only
authoritative one.

PROVENANCE. Every stage after pinning verifies, at construction and again on
every read, that the pin file matches its recorded digest, that every pinned
artifact exists with its pinned digest, and that nothing new has appeared in a
pinned scope. Any failure raises PinProvenanceError and the gate stops. That is
a provenance failure, never a scientific negative result, and it is never
repaired by repinning.
"""
from __future__ import annotations

import fnmatch
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

from cora_tti import freeze_pin as FP


class Stage(IntEnum):
    """The eleven gate stages, in the order the protocol fixes them."""
    PIN_OUTPUT_HASH = 1
    PIN_PROTOCOL_HASHES = 2
    INSPECT_RETAINED_PRODUCTIONS = 3
    CHARACTERIZE_CANDIDATES = 4
    CLASSIFY_CLAIM_LEVEL = 5
    CAPABILITY_GROWTH_WITNESS = 6
    E_TRANSFER_EVALUATION = 7
    E_TRANSFER_MEASUREMENT = 8
    PROMOTION = 9
    POST_PROMOTION_ANALYSIS = 10
    GATE_COMPLETE = 11


class SealedClass(IntEnum):
    STEP_B_SEMANTICS = 1
    E_TRANSFER = 2
    LOCKBOX = 3


UNLOCKS_AT = {
    SealedClass.STEP_B_SEMANTICS: Stage.INSPECT_RETAINED_PRODUCTIONS,
    SealedClass.E_TRANSFER: Stage.E_TRANSFER_EVALUATION,
    SealedClass.LOCKBOX: Stage.GATE_COMPLETE,
}

#  Keys look like "main:outputs/..." or "tti:outputs/...", lowercased. A leading
#  "*:" applies a pattern to both checkouts.
SEAL_PATTERNS = {
    SealedClass.STEP_B_SEMANTICS: (
        "*:outputs/cora_breakthrough/level4_stepb_journal.jsonl",
        "*:outputs/cora_breakthrough/level4_stepb_witnesses.json",
        "*:outputs/cora_breakthrough/level4_stepb_inventory.json",
        "*:outputs/cora_breakthrough/level4_stepb_k1_lattice.json",
        "*:outputs/cora_breakthrough/level4_stepb_gate_outputs/*",
        "*:outputs/cora_breakthrough/level4_mechanism_inputs/*",
        "*:outputs/cora_breakthrough/level4_withheld_expectation_seal.json",
        "*:scripts/cora_level4_stepb_run.py",
        "*:level4_stepb/*",
    ),
    SealedClass.E_TRANSFER: (
        "*e_transfer*",
        "*transfer_witnesses*",
        "*:outputs/cora_breakthrough/level4_provenance_firewall.json",
        "*:data/arc/*training*",
    ),
    SealedClass.LOCKBOX: (
        "*:outputs/lockbox/*",
        "*lockbox_manifest*",
        "*eval_split*",
        "*holdout*",
        "*:data/arc/*evaluation*",
    ),
}

#  Quantitative or protocol artifacts, readable at every stage, main checkout only.
ALWAYS_PERMITTED = (
    "main:outputs/cora_breakthrough/level4_stepb_run_manifest.json",
    "main:outputs/cora_breakthrough/level4_stepb_run_manifest_hash.txt",
    "main:outputs/cora_breakthrough/level4_stepb_design_hash.txt",
    "main:outputs/cora_breakthrough/level4_stepb_output_hash.txt",
    "main:logs/level4_stepb_run.log",
    "tti:outputs/tti/stepb_gate/*",
)

NON_AUTHORITATIVE = ("tti:outputs/cora_breakthrough/*",)
WATCHED_ROOTS = ("outputs", "logs", "data")


class SealedAccessError(RuntimeError):
    """A stage tried to read something its stage does not unlock."""


class PinProvenanceError(RuntimeError):
    """The pinned artifact set is not exactly what was pinned.

    Deliberately NOT a subclass of SealedAccessError. It stops the gate, and it
    is never a scientific negative result.
    """

    def __init__(self, status: str, verification=None, path: str | None = None):
        self.status, self.verification, self.path = status, verification, path
        where = f" at {path}" if path else ""
        super().__init__(
            f"{status}{where}. The gate stops. This is a provenance failure, not a "
            "scientific result. Do not repin and do not overwrite the pin.")


def keyed(path) -> tuple:
    """(checkout, key) where key is 'main:<relpath>', 'tti:<relpath>' or 'abs:<path>'."""
    resolved = Path(path).resolve()
    for name, root in (("main", FP.MAIN), ("tti", FP.TTI)):
        try:
            relative = resolved.relative_to(Path(root).resolve())
        except (ValueError, OSError):
            continue
        return name, f"{name}:{relative.as_posix()}".lower()
    return "abs", f"abs:{resolved.as_posix()}".lower()


def classify(path) -> SealedClass | None:
    checkout, key = keyed(path)
    if any(fnmatch.fnmatchcase(key, p) for p in ALWAYS_PERMITTED):
        return None
    for sealed in (SealedClass.LOCKBOX, SealedClass.E_TRANSFER, SealedClass.STEP_B_SEMANTICS):
        if any(fnmatch.fnmatchcase(key, p) for p in SEAL_PATTERNS[sealed]):
            return sealed
    if checkout in ("main", "tti"):
        head = key.split(":", 1)[1].split("/", 1)[0]
        if head in WATCHED_ROOTS:
            return SealedClass.STEP_B_SEMANTICS
    return None


def is_non_authoritative(path) -> bool:
    _, key = keyed(path)
    return any(fnmatch.fnmatchcase(key, p) for p in NON_AUTHORITATIVE)


@dataclass
class AccessRecord:
    path: str
    sealed_class: str | None
    stage: str
    permitted: bool
    reason: str
    when_utc: str


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class GateGuard:
    """Enforces read order and provenance, and records every decision."""

    stage: Stage
    require_pin: bool = True
    ledger: list = field(default_factory=list)
    verification: object = field(default=None, init=False)
    _pinned: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.stage = Stage(self.stage)
        if self.stage > Stage.PIN_PROTOCOL_HASHES:
            if not self.require_pin:
                raise ValueError(
                    "stages after pinning cannot run without the freeze pin; "
                    "require_pin=False is meaningful only at stages 1 and 2")
            self.reverify()

    def reverify(self) -> None:
        result = FP.verify_pin()
        self.verification = result
        if not result.ok():
            raise PinProvenanceError(result.status, verification=result)
        self._pinned = FP.load_pinned_digests()

    #  ------------------------------------------------------------ decisions

    def decide(self, path) -> AccessRecord:
        sealed = classify(path)
        if is_non_authoritative(path):
            permitted, reason = False, ("non-authoritative copy in the dev worktree; gate "
                                        "stages read only the pinned main-checkout artifact")
        elif sealed is None:
            permitted, reason = True, "not sealed"
        else:
            unlocks = UNLOCKS_AT[sealed]
            permitted = self.stage >= unlocks
            reason = (f"{sealed.name} unlocks at stage {int(unlocks)} {unlocks.name}; "
                      f"current stage is {int(self.stage)} {self.stage.name}")
        record = AccessRecord(str(path), sealed.name if sealed else None,
                              self.stage.name, permitted, reason, _now())
        self.ledger.append(record)
        return record

    def _assert_matches_pin(self, path) -> None:
        resolved = str(Path(path).resolve())
        if resolved in self._pinned:
            candidate = Path(resolved)
            if not candidate.is_file():
                status = FP.PIN_ARTIFACT_MISSING
            elif FP.file_digest(candidate) != self._pinned[resolved]:
                status = FP.PIN_ARTIFACT_DRIFT
            else:
                return
        elif FP.in_pinned_scope(resolved):
            status = FP.PIN_SCOPE_GREW_AFTER_FREEZE
        else:
            return
        sealed = classify(path)
        self.ledger.append(AccessRecord(str(path), sealed.name if sealed else None,
                                        self.stage.name, False, status, _now()))
        raise PinProvenanceError(status, path=str(path))

    def check(self, path) -> None:
        record = self.decide(path)
        if not record.permitted:
            raise SealedAccessError(
                f"REFUSED: {path}\n  {record.reason}\n"
                "  This is the protocol's access order, not a recoverable error. "
                "Do not widen the guard to proceed.")
        if self.stage > Stage.PIN_PROTOCOL_HASHES:
            self._assert_matches_pin(path)

    def permits(self, path) -> bool:
        """Non-raising for access order only. Provenance failures still raise."""
        try:
            self.check(path)
        except SealedAccessError:
            return False
        return True

    @contextmanager
    def open(self, path, mode: str = "r", **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise SealedAccessError(
                f"REFUSED: the gate never writes into the experiment tree: {path}")
        self.check(path)
        handle = Path(path).open(mode, **kwargs)
        try:
            yield handle
        finally:
            handle.close()

    #  -------------------------------------------------------------- ledger

    def write_ledger(self, name: str | None = None) -> Path:
        FP.gate_dir().mkdir(parents=True, exist_ok=True)
        target = FP.gate_dir() / (name or f"access_ledger_stage{int(self.stage):02d}.jsonl")
        with target.open("a") as handle:
            for record in self.ledger:
                handle.write(json.dumps(record.__dict__, sort_keys=True) + "\n")
        self.ledger.clear()
        return target
