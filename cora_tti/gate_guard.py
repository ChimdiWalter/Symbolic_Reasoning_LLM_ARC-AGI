"""Mechanical enforcement of the Capability-Growth Gate's access order and provenance.

ACCESS ORDER. Eight sealed classes. Each unlocks at a stage, and three also need
a committed event, so that the order INSIDE a stage is enforced too:

    class                   what                                      unlocks
    STEP_B_SOURCE           runner, level4_stepB/, level4_blind_runtime/   stage 3
    PRE_RUN_RECORDS         Step-A, admissibility, v21 and other           stage 3
                            records that existed before the run
    STEP_B_OUTPUTS          Step-B run outputs and mechanism inputs        stage 3, once the tool
                                                                           manifest is committed
    E_TRANSFER_PROVENANCE   the provenance firewall                        stage 7, once the admitted
                                                                           set is committed
    PROMOTION_DATA          the Promotion-task extract                     stage 7, once the admitted
                                                                           set is committed
    E_TRANSFER              the E_transfer extract and artifacts           stage 8, once the
                                                                           withdrawals are committed
    LOCKBOX                 Lockbox200, holdout splits, and EVERY raw      stage 11, in code only
                            ARC data file: the training file contains
                            Lockbox200 and E_transfer, so it is mixed
    NEVER                   the checkpoint journal, the withheld           never
                            expectation seal

Raw ARC data is read by no gate stage. Promotion and E_transfer tasks reach a
stage only through per-split extracts written by a candidate-independent step,
under outputs/tti/stepB_gate/extracts/.

Classification is relative to whichever checkout holds the file, so a sealed
artifact cannot escape by being copied into the dev worktree, and an ancestor
directory name cannot decide a class. It fails closed: an unrecognized file
under outputs/ or logs/ is STEP_B_OUTPUTS, and anything under data/ is LOCKBOX.
Worktree copies of Step-B artifacts are never read at any stage.

PROVENANCE. Every stage after stage 2 verifies, at construction and on every
read, the commit-bound freeze pin and the commit-bound G2 module pin: digests,
presence, no growth inside a pinned scope. Any failure raises
PinProvenanceError and the gate stops. That is never a scientific result.

HASH-ONLY PATH. At stages 2 and 11 a stage may obtain a digest and size of a
sealed file without reading it for content, for any class except NEVER. The
ledger records these as HASH_ONLY.
"""
from __future__ import annotations

import fnmatch
import json
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
    STEP_B_SOURCE = 1
    PRE_RUN_RECORDS = 2
    STEP_B_OUTPUTS = 3
    E_TRANSFER_PROVENANCE = 4
    PROMOTION_DATA = 5
    E_TRANSFER = 6
    LOCKBOX = 7
    NEVER = 8


UNLOCKS = {
    SealedClass.STEP_B_SOURCE: (Stage.INSPECT_RETAINED_PRODUCTIONS, None),
    SealedClass.PRE_RUN_RECORDS: (Stage.INSPECT_RETAINED_PRODUCTIONS, None),
    SealedClass.STEP_B_OUTPUTS: (Stage.INSPECT_RETAINED_PRODUCTIONS, "tool_manifest"),
    SealedClass.E_TRANSFER_PROVENANCE: (Stage.E_TRANSFER_EVALUATION, "admitted_set"),
    SealedClass.PROMOTION_DATA: (Stage.E_TRANSFER_EVALUATION, "admitted_set"),
    SealedClass.E_TRANSFER: (Stage.E_TRANSFER_MEASUREMENT, "withdrawals"),
    SealedClass.LOCKBOX: (Stage.GATE_COMPLETE, None),
    SealedClass.NEVER: (None, None),
}

EVENT_FILES = {
    "tool_manifest": "gate_tool_manifest.json",
    "admitted_set": "etransfer_admitted_set.json",
    "withdrawals": "etransfer_withdrawals.json",
}

HASH_ONLY_STAGES = (Stage.PIN_PROTOCOL_HASHES, Stage.GATE_COMPLETE)

#  Keys look like "main:<relpath>", "tti:<relpath>" or "abs:<path>", lowercased.
NEVER_PATTERNS = (
    "*:outputs/cora_breakthrough/level4_stepb_journal.jsonl",
    "*:outputs/cora_breakthrough/level4_withheld_expectation_seal.json",
)

EXTRACT_PATTERNS = (
    (SealedClass.PROMOTION_DATA, ("tti:outputs/tti/stepb_gate/extracts/promotion_*",)),
    (SealedClass.E_TRANSFER, ("tti:outputs/tti/stepb_gate/extracts/etransfer_*",)),
)

#  Quantitative or protocol artifacts, readable at every stage.
ALWAYS_PERMITTED = (
    "main:outputs/cora_breakthrough/level4_stepb_run_manifest.json",
    "main:outputs/cora_breakthrough/level4_stepb_run_manifest_hash.txt",
    "main:outputs/cora_breakthrough/level4_stepb_design_hash.txt",
    "main:outputs/cora_breakthrough/level4_stepb_output_hash.txt",
    "main:logs/level4_stepb_run.log",
    "tti:outputs/tti/stepb_gate/*",
)

SENSITIVE_PATTERNS = (
    (SealedClass.E_TRANSFER_PROVENANCE, (
        "*:outputs/cora_breakthrough/level4_provenance_firewall.json",)),
    (SealedClass.E_TRANSFER, ("*e_transfer*", "*transfer_witnesses*")),
    (SealedClass.LOCKBOX, (
        "*:outputs/lockbox/*", "*lockbox_manifest*", "*eval_split*", "*holdout*",
        "*arc-agi*training*", "*arc-agi*evaluation*", "*:data/*")),
    (SealedClass.STEP_B_SOURCE, (
        "*:scripts/cora_level4_stepb_run.py", "*:level4_stepb/*", "*:level4_blind_runtime/*")),
    (SealedClass.PRE_RUN_RECORDS, (
        "*:outputs/cora_breakthrough/level4_stepa_*",
        "*:outputs/cora_breakthrough/level4_baseline_admissibility*",
        "*:outputs/cora_breakthrough/v21_*",
        "*:outputs/cora_breakthrough/v2_*",
        "*:outputs/cora_breakthrough/concept_registry.json",
        "*:outputs/cora_breakthrough/level4_a01_*",
        "*:outputs/cora_breakthrough/level4_blind_*",
        "*:outputs/cora_breakthrough/level4_bundle_freeze.json",
        "*:outputs/cora_breakthrough/level4_leak_check.json",
        "*:outputs/cora_breakthrough/level4_manifest_hash.txt",
        "*:outputs/cora_breakthrough/level4_pre_level4_runtime_*",
        "*:outputs/cora_breakthrough/level4_runtime_hash_hunt.json")),
    (SealedClass.STEP_B_OUTPUTS, (
        "*:outputs/cora_breakthrough/level4_stepb_*",
        "*:outputs/cora_breakthrough/level4_mechanism_inputs/*")),
)

NON_AUTHORITATIVE = ("tti:outputs/cora_breakthrough/*",)
WATCHED_ROOTS = ("outputs", "logs")


class SealedAccessError(RuntimeError):
    """A stage tried to read something its stage, or its committed events, do not unlock."""


class PinProvenanceError(RuntimeError):
    """A pinned artifact set is not exactly what was pinned.

    Deliberately NOT a subclass of SealedAccessError. It stops the gate, and it
    is never a scientific negative or positive result.
    """

    def __init__(self, status: str, verification=None, path: str | None = None):
        self.status, self.verification, self.path = status, verification, path
        where = f" at {path}" if path else ""
        super().__init__(
            f"{status}{where}. The gate stops. This is a provenance failure, not a "
            "scientific result. Do not repin and do not overwrite any pin.")


def keyed(path) -> tuple:
    """(checkout, key), key being 'main:<relpath>', 'tti:<relpath>' or 'abs:<path>'."""
    resolved = Path(path).resolve()
    for name, root in (("main", FP.MAIN), ("tti", FP.TTI)):
        try:
            relative = resolved.relative_to(Path(root).resolve())
        except (ValueError, OSError):
            continue
        return name, f"{name}:{relative.as_posix()}".lower()
    return "abs", f"abs:{resolved.as_posix()}".lower()


def _matches(key: str, patterns) -> bool:
    return any(fnmatch.fnmatchcase(key, p) for p in patterns)


def classify(path) -> SealedClass | None:
    checkout, key = keyed(path)
    if _matches(key, NEVER_PATTERNS):
        return SealedClass.NEVER
    for sealed, patterns in EXTRACT_PATTERNS:
        if _matches(key, patterns):
            return sealed
    if _matches(key, ALWAYS_PERMITTED):
        return None
    for sealed, patterns in SENSITIVE_PATTERNS:
        if _matches(key, patterns):
            return sealed
    if checkout in ("main", "tti"):
        head = key.split(":", 1)[1].split("/", 1)[0]
        if head == "data":
            return SealedClass.LOCKBOX
        if head in WATCHED_ROOTS:
            return SealedClass.STEP_B_OUTPUTS
    return None


def is_non_authoritative(path) -> bool:
    return _matches(keyed(path)[1], NON_AUTHORITATIVE)


def event_committed(event: str) -> bool:
    """True when the event file exists and is byte-identical to its blob at HEAD."""
    path = FP.gate_dir() / EVENT_FILES[event]
    if not path.is_file():
        return False
    try:
        relative = FP._relative_to_tti(path)
    except ValueError:
        return False
    blob = FP._git("cat-file", "blob", f"HEAD:{relative}", binary=True)
    return blob is not None and blob == path.read_bytes()


@dataclass
class AccessRecord:
    path: str
    sealed_class: str | None
    stage: str
    permitted: bool
    reason: str
    when_utc: str
    access_mode: str = "CONTENT"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class GateGuard:
    """Enforces read order and provenance, and records every decision."""

    stage: Stage
    require_pin: bool = True
    ledger: list = field(default_factory=list)
    verification: object = field(default=None, init=False)
    module_verification: object = field(default=None, init=False)
    _pinned: dict = field(default_factory=dict, init=False, repr=False)
    _module_pinned: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.stage = Stage(self.stage)
        if self.stage > Stage.PIN_PROTOCOL_HASHES:
            if not self.require_pin:
                raise ValueError(
                    "stages after pinning cannot run without the freeze pin; "
                    "require_pin=False is meaningful only at stages 1 and 2")
            self.reverify()

    def reverify(self) -> None:
        result = FP.verify_pin(require_binding=True)
        self.verification = result
        if not result.ok():
            raise PinProvenanceError(result.status, verification=result)
        modules = FP.verify_module_pin()
        self.module_verification = modules
        if not modules.ok():
            raise PinProvenanceError(modules.status, verification=modules)
        self._pinned = FP.load_pinned_digests()
        self._module_pinned = FP.load_module_pinned_digests()

    #  ------------------------------------------------------------ decisions

    def decide(self, path, access_mode: str = "CONTENT") -> AccessRecord:
        sealed = classify(path)
        if is_non_authoritative(path):
            permitted, reason = False, ("non-authoritative copy in the dev worktree; gate "
                                        "stages read only the pinned main-checkout artifact")
        elif sealed is None:
            permitted, reason = True, "not sealed"
        elif sealed is SealedClass.NEVER:
            permitted, reason = False, ("NEVER: the checkpoint journal and the withheld "
                                        "expectation seal are not read by any gate stage")
        else:
            needed, event = UNLOCKS[sealed]
            if self.stage < needed:
                permitted, reason = False, (
                    f"{sealed.name} unlocks at stage {int(needed)} {needed.name}; "
                    f"current stage is {int(self.stage)} {self.stage.name}")
            elif event and not event_committed(event):
                permitted, reason = False, (
                    f"{sealed.name} also requires the committed event '{event}' "
                    f"({EVENT_FILES[event]}), which is absent or not identical to HEAD")
            else:
                permitted, reason = True, f"{sealed.name} unlocked at stage {int(self.stage)}"
        record = AccessRecord(str(path), sealed.name if sealed else None, self.stage.name,
                              permitted, reason, _now(), access_mode)
        self.ledger.append(record)
        return record

    def _refuse_provenance(self, path, status: str) -> None:
        sealed = classify(path)
        self.ledger.append(AccessRecord(str(path), sealed.name if sealed else None,
                                        self.stage.name, False, status, _now()))
        raise PinProvenanceError(status, path=str(path))

    def _assert_matches_pin(self, path) -> None:
        resolved = str(Path(path).resolve())
        for mapping, missing_code, drift_code in (
                (self._pinned, FP.PIN_ARTIFACT_MISSING, FP.PIN_ARTIFACT_DRIFT),
                (self._module_pinned, FP.MODULE_ARTIFACT_MISSING, FP.MODULE_ARTIFACT_DRIFT)):
            if resolved in mapping:
                candidate = Path(resolved)
                if not candidate.is_file():
                    self._refuse_provenance(path, missing_code)
                if FP.file_digest(candidate) != mapping[resolved]:
                    self._refuse_provenance(path, drift_code)
        if resolved not in self._pinned and FP.in_pinned_scope(resolved):
            self._refuse_provenance(path, FP.PIN_SCOPE_GREW_AFTER_FREEZE)

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

    def hash_only(self, path) -> dict:
        """Digest and size of a sealed file without reading it for content (stages 2 and 11)."""
        sealed = classify(path)
        if self.stage not in HASH_ONLY_STAGES:
            permitted, reason = False, f"hash-only access is licensed only at stages 2 and 11"
        elif sealed is SealedClass.NEVER or is_non_authoritative(path):
            permitted, reason = False, "hash-only access refused for this class"
        else:
            permitted, reason = True, "hash-only"
        self.ledger.append(AccessRecord(str(path), sealed.name if sealed else None,
                                        self.stage.name, permitted, reason, _now(), "HASH_ONLY"))
        if not permitted:
            raise SealedAccessError(f"REFUSED hash-only: {path}\n  {reason}")
        if self.stage > Stage.PIN_PROTOCOL_HASHES:
            self._assert_matches_pin(path)
        digest, _ = FP.digest_and_lines(path)
        return {"path": str(path), "sha256": digest, "bytes": Path(path).stat().st_size}

    #  -------------------------------------------------------------- ledger

    def write_ledger(self, name: str | None = None) -> Path:
        FP.gate_dir().mkdir(parents=True, exist_ok=True)
        target = FP.gate_dir() / (name or f"access_ledger_stage{int(self.stage):02d}.jsonl")
        with target.open("a") as handle:
            for record in self.ledger:
                handle.write(json.dumps(record.__dict__, sort_keys=True) + "\n")
        self.ledger.clear()
        return target
