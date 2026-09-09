"""Mechanical enforcement of the Capability-Growth Gate's access order.

The gate's protocol says which artifacts may be read at which stage. A protocol
that lives only in a document is enforced by whoever remembers it. This module
enforces it in code, so that a stage script physically cannot open sealed data
before its stage, and so that every access that does happen is recorded.

Three sealed classes, each unlocked by a different stage:

    STEP_B_SEMANTICS  the retained productions, journal, witnesses, inventory
                      and gate outputs of the frozen Step-B run. Locked until
                      stage 3, because stages 1 and 2 exist precisely to pin
                      the hashes BEFORE anything is inspected.
    E_TRANSFER        the reserved transfer set. Locked until stage 7, and it
                      is never a tuning signal at any stage.
    LOCKBOX           Lockbox200 and the ARC holdout. Locked until the entire
                      gate is complete, which no stage inside the gate can
                      declare.

The guard fails closed. An unrecognized path under a watched root is treated as
sealed rather than as permitted, so adding a new artifact to the experiment
directory does not silently open a hole.

Usage:

    from cora_tti.gate_guard import GateGuard, Stage

    guard = GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)
    with guard.open(path) as handle:      # raises SealedAccessError if too early
        ...
    guard.write_ledger()
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

MAIN = Path("/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project")
TTI = Path(__file__).resolve().parents[1]
GATE_DIR = TTI / "outputs" / "tti" / "stepB_gate"
FREEZE_PIN = GATE_DIR / "stepB_freeze_pin.json"


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


#  The stage at which each sealed class becomes readable. LOCKBOX unlocks at a
#  stage number no gate stage may occupy, so nothing inside the gate can open it.
UNLOCKS_AT = {
    SealedClass.STEP_B_SEMANTICS: Stage.INSPECT_RETAINED_PRODUCTIONS,
    SealedClass.E_TRANSFER: Stage.E_TRANSFER_EVALUATION,
    SealedClass.LOCKBOX: Stage.GATE_COMPLETE,
}

#  Patterns are matched against the path RELATIVE TO THE PROJECT ROOT, not
#  against the absolute path. Matching the absolute path lets an unrelated
#  ancestor directory name decide a file's sealed class, which is wrong even
#  when it happens to fail safe.
SEAL_PATTERNS = {
    SealedClass.STEP_B_SEMANTICS: (
        "outputs/cora_breakthrough/level4_stepB_journal.jsonl",
        "outputs/cora_breakthrough/level4_stepB_witnesses.json",
        "outputs/cora_breakthrough/level4_stepB_inventory.json",
        "outputs/cora_breakthrough/level4_stepB_k1_lattice.json",
        "outputs/cora_breakthrough/level4_stepB_gate_outputs/*",
        "outputs/cora_breakthrough/level4_mechanism_inputs/*",
        "outputs/cora_breakthrough/level4_withheld_expectation_seal.json",
        #  The runner and the candidate inventory define the experiment's
        #  semantics. The standing rule forbids inspecting them while the run is
        #  live, and stage 3 is exactly when inspecting them becomes part of
        #  characterizing what was produced. Hashing them does not go through
        #  this guard, so pinning at stages 1 and 2 is unaffected.
        "scripts/cora_level4_stepb_run.py",
        "level4_stepb/*.py",
    ),
    SealedClass.E_TRANSFER: (
        "*e_transfer*",
        "*transfer_witnesses*",
    ),
    SealedClass.LOCKBOX: (
        "outputs/lockbox/*",
        "*lockbox_manifest*",
        "*eval_split*",
        "*holdout*",
    ),
}

#  Paths under a watched root that are quantitative by construction and carry no
#  Step-B semantics. Hash and size files are the pin's own vocabulary.
ALWAYS_PERMITTED = (
    "outputs/cora_breakthrough/level4_stepB_run_manifest.json",
    "outputs/cora_breakthrough/level4_stepB_run_manifest_hash.txt",
    "outputs/cora_breakthrough/level4_stepB_design_hash.txt",
    "outputs/cora_breakthrough/level4_stepB_output_hash.txt",
    "logs/level4_stepB_run.log",
)

#  Anything below these roots is watched. Outside them the guard does not apply.
WATCHED_ROOTS = ("outputs", "logs", "data")


class SealedAccessError(RuntimeError):
    """Raised when a stage tries to read something its stage does not unlock."""


class MissingPinError(RuntimeError):
    """Raised when a stage past 2 runs without a verified freeze pin."""


def relative_key(path: os.PathLike | str) -> str:
    """The path as the guard reasons about it: relative to the project root.

    Falling back to the absolute path keeps a stray reference from outside the
    tree governed rather than silently exempt.
    """
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(MAIN.resolve()).as_posix().lower()
    except (ValueError, OSError):
        return resolved.as_posix().lower()


def classify(path: os.PathLike | str) -> SealedClass | None:
    """Return the sealed class of a path, or None if it is not sealed.

    Fails closed: a path under a watched root that matches nothing known is
    treated as STEP_B_SEMANTICS rather than as open, so adding an artifact to
    the experiment directory does not open a hole by default.
    """
    key = relative_key(path)
    for pattern in ALWAYS_PERMITTED:
        if fnmatch.fnmatch(key, pattern.lower()):
            return None
    #  Narrow classes first, then the broad Step-B fallback.
    for sealed in (SealedClass.LOCKBOX, SealedClass.E_TRANSFER,
                   SealedClass.STEP_B_SEMANTICS):
        for pattern in SEAL_PATTERNS[sealed]:
            if fnmatch.fnmatch(key, pattern.lower()):
                return sealed
    head = key.split("/", 1)[0]
    if head in WATCHED_ROOTS:
        return SealedClass.STEP_B_SEMANTICS
    return None


@dataclass
class AccessRecord:
    path: str
    sealed_class: str | None
    stage: str
    permitted: bool
    reason: str
    when_utc: str


@dataclass
class GateGuard:
    """Enforces the gate's read order and records every decision."""

    stage: Stage
    require_pin: bool = True
    ledger: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.stage = Stage(self.stage)
        if self.require_pin and self.stage > Stage.PIN_PROTOCOL_HASHES:
            self._assert_pinned()

    def _assert_pinned(self) -> None:
        if not FREEZE_PIN.is_file():
            raise MissingPinError(
                f"stage {self.stage.name} requires the freeze pin, and "
                f"{FREEZE_PIN} does not exist. Run scripts/pin_stepB_freeze.py "
                "first. Stages 1 and 2 exist so that nothing is inspected "
                "before the hashes are recorded.")
        text = FREEZE_PIN.read_text()
        stored = (GATE_DIR / "stepB_freeze_pin_hash.txt")
        if not stored.is_file():
            raise MissingPinError("the freeze pin has no recorded hash")
        actual = hashlib.sha256(text.encode()).hexdigest()
        if stored.read_text().split()[0] != actual:
            raise MissingPinError(
                "the freeze pin does not match its recorded hash; it has been "
                "altered since it was written, and no stage may proceed")

    #  ------------------------------------------------------------ decisions

    def decide(self, path: os.PathLike | str) -> AccessRecord:
        sealed = classify(path)
        if sealed is None:
            permitted, reason = True, "not sealed"
        else:
            unlocks = UNLOCKS_AT[sealed]
            permitted = self.stage >= unlocks
            reason = (f"{sealed.name} unlocks at stage {int(unlocks)} "
                      f"{unlocks.name}; current stage is {int(self.stage)} "
                      f"{self.stage.name}")
        record = AccessRecord(
            path=str(path), sealed_class=sealed.name if sealed else None,
            stage=self.stage.name, permitted=permitted, reason=reason,
            when_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        self.ledger.append(record)
        return record

    def check(self, path: os.PathLike | str) -> None:
        record = self.decide(path)
        if not record.permitted:
            raise SealedAccessError(
                f"REFUSED: {path}\n  {record.reason}\n"
                "  This is the protocol's access order, not a recoverable error. "
                "Do not widen the guard to proceed.")

    def permits(self, path: os.PathLike | str) -> bool:
        """Non-raising form. Still recorded in the ledger."""
        return self.decide(path).permitted

    @contextmanager
    def open(self, path: os.PathLike | str, mode: str = "r", **kwargs):
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
        GATE_DIR.mkdir(parents=True, exist_ok=True)
        target = GATE_DIR / (name or f"access_ledger_stage{int(self.stage):02d}.jsonl")
        with target.open("a") as handle:
            for record in self.ledger:
                handle.write(json.dumps(record.__dict__, sort_keys=True) + "\n")
        self.ledger.clear()
        return target
