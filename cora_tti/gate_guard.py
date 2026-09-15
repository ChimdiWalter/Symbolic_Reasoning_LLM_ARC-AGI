"""Mechanical enforcement of the Capability-Growth Gate's access order and provenance.

ACCESS ORDER. Eight sealed classes. Each unlocks at a stage, and five also need
a committed, one-shot, hash-bound, chained EVENT, so the order inside a stage
and across stages is enforced too:

    class                   what                                        unlocks
    STEP_B_SOURCE           runner, level4_stepB/, level4_blind_runtime/     stage 3
    PRE_RUN_RECORDS         Step-A, admissibility, v21 and other records     stage 3
    STEP_B_OUTPUTS          Step-B run outputs and mechanism inputs          stage 3 + event g3b_open
    PROMOTION_DATA          the Promotion-task extract                       stage 7 + event g7b_open
    E_TRANSFER_PROVENANCE   the provenance firewall                          stage 7 + event g7b_open
    E_TRANSFER              the E_transfer extract and artifacts             stage 8 + event g8_open,
                                                                             closed by event g8_closed
    LOCKBOX                 Lockbox200, holdout splits, the Lockbox          stage 11 + event g11_complete,
                                                                             which follows g8_closed and needs a
                                                                             committed LOCKBOX-ELIGIBLE closure record
                            manifest, and every raw ARC data file
    NEVER                   the checkpoint journal, the withheld seal        never

EVENTS. An event is a small JSON file in the gate directory, written once by
write_event() at the step that owns it and then committed. It counts only when
it is committed exactly once, has one distinct blob across all refs and the
reflog, and is byte-identical to HEAD; when the artifact it attests is committed
and still hashes to the attested value; when the stage records it requires were
committed no later than the event; and when its predecessor event is valid and
was committed strictly earlier in history. write_event() also refuses to open
E_transfer provenance, or E_transfer, for an admitted set that is empty after
withdrawals. An absent or uncommitted event keeps its classes sealed. A rewritten, drifted or
broken event is a provenance failure and stops the gate.

CLASSIFICATION. Names that identify sealed material are matched anywhere in a
path, including outside both checkouts, and the strictest matching class wins,
so a copy cannot escape by being moved. Root-anchored rules then apply, then the
fail-closed defaults: an unrecognized file under outputs/ or logs/ is
STEP_B_OUTPUTS, and anything under data/ is LOCKBOX. A renamed copy whose new
name carries no sealed stem cannot be recognized by name; the access ledger and
the transcript scans are the controls for that case. Worktree copies of Step-B
artifacts are never read.

FILTERED EXTRACTION. No stage reads raw ARC data or the Lockbox manifest for
content. The one exception is extract(): at stage 7 after g7b_open for Promotion
tasks, and at stage 8 after g8_open and before g8_closed for E_transfer tasks,
it returns only licensed members through cora_tti.split_extract. Unlicensed
members are never decoded, retained, printed or returned; only their count is
recorded.

PROVENANCE. Every stage after stage 2 verifies the commit-bound freeze pin and
module pin at construction and on every read. Any failure raises
PinProvenanceError and the gate stops. That is never a scientific result.

PROTOCOL ARTIFACTS. The run manifest, its hash, the design hash, the final
output hash and the run log are not sealed. At stages 1 and 2 the guard refuses
their content; the pin tool hashes and counts them. Their content opens at stage 3.

HASH-ONLY PATH. At stages 2 and 11 a stage may obtain a digest and size of a
sealed file, for any class except NEVER, without reading it for content.
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
from cora_tti import split_extract as SX


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
    """Ordered from least to most strict; when several classes match, the highest wins."""
    STEP_B_SOURCE = 1
    PRE_RUN_RECORDS = 2
    STEP_B_OUTPUTS = 3
    PROMOTION_DATA = 4
    E_TRANSFER_PROVENANCE = 5
    E_TRANSFER = 6
    LOCKBOX = 7
    NEVER = 8


@dataclass(frozen=True)
class EventSpec:
    file: str
    predecessor: str | None
    attests: str | None
    requires: tuple = ()


EVENTS = {
    "g3b_open": EventSpec("event_g3b_open.json", None, "gate_tool_manifest.json",
                          ("g3a_record.json",)),
    "g7b_open": EventSpec("event_g7b_open.json", "g3b_open", "etransfer_admitted_set.json",
                          ("g6_record.json", "g7a_record.json")),
    "g8_open": EventSpec("event_g8_open.json", "g7b_open", "etransfer_withdrawals.json",
                         ("g7b_record.json",)),
    "g8_closed": EventSpec("event_g8_closed.json", "g8_open", "etransfer_ledger.jsonl"),
    "g11_complete": EventSpec("event_g11_complete.json", "g8_closed", "gate_completion_record.json",
                              ("lockbox_closure.json",)),
}

UNLOCKS = {
    SealedClass.STEP_B_SOURCE: (Stage.INSPECT_RETAINED_PRODUCTIONS, None),
    SealedClass.PRE_RUN_RECORDS: (Stage.INSPECT_RETAINED_PRODUCTIONS, None),
    SealedClass.STEP_B_OUTPUTS: (Stage.INSPECT_RETAINED_PRODUCTIONS, "g3b_open"),
    SealedClass.PROMOTION_DATA: (Stage.E_TRANSFER_EVALUATION, "g7b_open"),
    SealedClass.E_TRANSFER_PROVENANCE: (Stage.E_TRANSFER_EVALUATION, "g7b_open"),
    SealedClass.E_TRANSFER: (Stage.E_TRANSFER_MEASUREMENT, "g8_open"),
    SealedClass.LOCKBOX: (Stage.GATE_COMPLETE, "g11_complete"),
    SealedClass.NEVER: (None, None),
}

EXTRACT_PURPOSES = {
    "promotion": (Stage.E_TRANSFER_EVALUATION, "g7b_open"),
    "etransfer": (Stage.E_TRANSFER_MEASUREMENT, "g8_open"),
}

HASH_ONLY_STAGES = (Stage.PIN_PROTOCOL_HASHES, Stage.GATE_COMPLETE)

EVENT_ABSENT = "EVENT_ABSENT"
EVENT_VALID = "EVENT_VALID"
EVENT_WRITTEN = "EVENT_WRITTEN"
EVENT_EXISTS_REFUSING_OVERWRITE = "EVENT_EXISTS_REFUSING_OVERWRITE"
EVENT_ARTIFACT_NOT_COMMITTED = "EVENT_ARTIFACT_NOT_COMMITTED"
EVENT_PREDECESSOR_NOT_VALID = "EVENT_PREDECESSOR_NOT_VALID"
EVENT_REWRITTEN = "EVENT_REWRITTEN"
EVENT_ARTIFACT_DRIFT = "EVENT_ARTIFACT_DRIFT"
EVENT_CHAIN_BROKEN = "EVENT_CHAIN_BROKEN"
EVENT_MALFORMED = "EVENT_MALFORMED"
EVENT_REQUIREMENT_NOT_COMMITTED = "EVENT_REQUIREMENT_NOT_COMMITTED"
EVENT_ADMITTED_SET_EMPTY = "EVENT_ADMITTED_SET_EMPTY"
EVENT_LOCKBOX_NOT_ELIGIBLE = "EVENT_LOCKBOX_NOT_ELIGIBLE"

#  Keys look like "main:<relpath>", "tti:<relpath>" or "abs:<path>", lowercased.
#  1. Sealed names matched ANYWHERE in the key, so moved copies keep their class.
ANYWHERE_PATTERNS = (
    (SealedClass.NEVER, ("*level4_stepb_journal*", "*withheld_expectation_seal*")),
    (SealedClass.LOCKBOX, ("*arc-agi*", "*lockbox/*", "*lockbox_manifest*", "*lockbox200*",
                           "*eval_split*", "*holdout*")),
    (SealedClass.E_TRANSFER, ("*e_transfer*", "*etransfer_tasks*", "*transfer_witnesses*")),
    (SealedClass.E_TRANSFER_PROVENANCE, ("*provenance_firewall*",)),
    (SealedClass.PROMOTION_DATA, ("*promotion_tasks*",)),
    (SealedClass.STEP_B_OUTPUTS, ("*level4_stepb_inventory*", "*level4_stepb_witnesses*",
                                  "*level4_stepb_k1_lattice*", "*level4_stepb_gate_outputs*",
                                  "*level4_mechanism_inputs*", "*invention_corpus*")),
)

#  2. Not sealed, unless rule 1 matched. Protocol artifacts open for content at stage 3;
#     the gate directory is open at every stage.
PROTOCOL_ARTIFACTS = (
    "main:outputs/cora_breakthrough/level4_stepb_run_manifest.json",
    "main:outputs/cora_breakthrough/level4_stepb_run_manifest_hash.txt",
    "main:outputs/cora_breakthrough/level4_stepb_design_hash.txt",
    "main:outputs/cora_breakthrough/level4_stepb_output_hash.txt",
    "main:logs/level4_stepb_run.log",
)
GATE_DIRECTORY = ("tti:outputs/tti/stepb_gate/*",)
ALWAYS_PERMITTED = PROTOCOL_ARTIFACTS + GATE_DIRECTORY

#  3. Root-anchored rules.
ANCHORED_PATTERNS = (
    (SealedClass.LOCKBOX, ("*:data/*",)),
    (SealedClass.STEP_B_SOURCE, ("*:scripts/cora_level4_stepb_run.py", "*:level4_stepb/*",
                                 "*:level4_blind_runtime/*")),
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
    (SealedClass.STEP_B_OUTPUTS, ("*:outputs/cora_breakthrough/level4_stepb_*",)),
)

#  Every file among the extracts is sealed whatever its name; one without a known stem fails closed.
EXTRACTS_FAIL_CLOSED = ("tti:outputs/tti/stepb_gate/extracts/*",)

NON_AUTHORITATIVE = ("tti:outputs/cora_breakthrough/*",)
WATCHED_ROOTS = ("outputs", "logs")


class SealedAccessError(RuntimeError):
    """A stage tried to read something its stage, or its committed events, do not unlock."""


class PinProvenanceError(RuntimeError):
    """A pinned artifact set, or a committed event, is not what was committed.

    Deliberately NOT a subclass of SealedAccessError. It stops the gate, and it
    is never a scientific negative or positive result.
    """

    def __init__(self, status: str, verification=None, path: str | None = None):
        self.status, self.verification, self.path = status, verification, path
        where = f" at {path}" if path else ""
        super().__init__(
            f"{status}{where}. The gate stops. This is a provenance failure, not a "
            "scientific result. Do not repin, rewrite an event, or overwrite any pin.")


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


def _strictest(matched):
    return max(matched) if matched else None


def classify(path) -> SealedClass | None:
    checkout, key = keyed(path)
    anywhere = [cls for cls, patterns in ANYWHERE_PATTERNS if _matches(key, patterns)]
    if anywhere:
        return _strictest(anywhere)
    if _matches(key, EXTRACTS_FAIL_CLOSED):
        return SealedClass.E_TRANSFER
    if _matches(key, ALWAYS_PERMITTED):
        return None
    anchored = [cls for cls, patterns in ANCHORED_PATTERNS if _matches(key, patterns)]
    if anchored:
        return _strictest(anchored)
    if checkout in ("main", "tti"):
        head = key.split(":", 1)[1].split("/", 1)[0]
        if head == "data":
            return SealedClass.LOCKBOX
        if head in WATCHED_ROOTS:
            return SealedClass.STEP_B_OUTPUTS
    return None


def is_non_authoritative(path) -> bool:
    return _matches(keyed(path)[1], NON_AUTHORITATIVE)


#  ------------------------------------------------------------------ events

def _event_path(name: str) -> Path:
    return FP.gate_dir() / EVENTS[name].file


def _committed_identical(path: Path) -> bool:
    try:
        relative = FP._relative_to_tti(path)
    except ValueError:
        return False
    blob = FP._git("cat-file", "blob", f"HEAD:{relative}", binary=True)
    return blob is not None and path.is_file() and blob == path.read_bytes()


def _introducing_commit(path: Path) -> tuple:
    out = FP._git("log", "--format=%H", "--", FP._relative_to_tti(path))
    commits = out.splitlines() if out else []
    return (commits[-1] if commits else None), len(commits)


def event_status(name: str) -> tuple:
    """(status, introducing commit). EVENT_VALID, EVENT_ABSENT, or a provenance status."""
    spec, path = EVENTS[name], _event_path(name)
    if not path.is_file():
        return EVENT_ABSENT, None
    relative = FP._relative_to_tti(path)
    if FP._git("cat-file", "blob", f"HEAD:{relative}", binary=True) is None:
        return EVENT_ABSENT, None
    commit, count = _introducing_commit(path)
    if count != 1 or len(FP.distinct_blobs(relative)) != 1 or not _committed_identical(path):
        return EVENT_REWRITTEN, commit
    try:
        record = json.loads(path.read_bytes())
        if record.get("event") != name:
            return EVENT_MALFORMED, commit
    except ValueError:
        return EVENT_MALFORMED, commit
    if spec.attests:
        artifact = FP.gate_dir() / spec.attests
        if (not artifact.is_file() or not _committed_identical(artifact)
                or FP.file_digest(artifact) != record.get("attests_sha256")):
            return EVENT_ARTIFACT_DRIFT, commit
    for required in spec.requires:
        requirement = FP.gate_dir() / required
        if not requirement.is_file() or not _committed_identical(requirement):
            return EVENT_CHAIN_BROKEN, commit
        required_commit, _ = _introducing_commit(requirement)
        if (required_commit is None
                or FP._git("merge-base", "--is-ancestor", required_commit, commit) is None):
            return EVENT_CHAIN_BROKEN, commit
    if name == "g11_complete" and not lockbox_eligible():
        return EVENT_CHAIN_BROKEN, commit
    if spec.predecessor:
        predecessor_status, predecessor_commit = event_status(spec.predecessor)
        if (predecessor_status != EVENT_VALID
                or record.get("predecessor_commit") != predecessor_commit
                or predecessor_commit == commit
                or FP._git("merge-base", "--is-ancestor", predecessor_commit, commit) is None):
            return EVENT_CHAIN_BROKEN, commit
    return EVENT_VALID, commit


def _ids(file: str, key: str) -> set:
    path = FP.gate_dir() / file
    if not path.is_file():
        return set()
    try:
        return set(json.loads(path.read_bytes()).get(key) or ())
    except (ValueError, AttributeError, TypeError):
        return set()


def remaining_admitted() -> set:
    """Admitted extension ids minus withdrawn ones, from the committed gate records."""
    return _ids("etransfer_admitted_set.json", "admitted") - _ids("etransfer_withdrawals.json", "withdrawn")


def lockbox_eligible() -> bool:
    """True only when the committed G11 closure record says LOCKBOX-ELIGIBLE."""
    path = FP.gate_dir() / "lockbox_closure.json"
    try:
        return path.is_file() and json.loads(path.read_bytes()).get("outcome") == "LOCKBOX-ELIGIBLE"
    except (ValueError, AttributeError):
        return False


def write_event(name: str) -> dict:
    """Write an event once, at the step that owns it. The caller commits it."""
    spec, path = EVENTS[name], _event_path(name)
    if path.exists():
        return {"outcome": EVENT_EXISTS_REFUSING_OVERWRITE, "event": name}
    record = {"event": name, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "attests": spec.attests, "attests_sha256": None,
              "predecessor_event": spec.predecessor, "predecessor_commit": None}
    for required in spec.requires:
        if not _committed_identical(FP.gate_dir() / required):
            return {"outcome": EVENT_REQUIREMENT_NOT_COMMITTED, "event": name, "requirement": required}
    if spec.attests:
        artifact = FP.gate_dir() / spec.attests
        if not _committed_identical(artifact):
            return {"outcome": EVENT_ARTIFACT_NOT_COMMITTED, "event": name, "artifact": spec.attests}
        record["attests_sha256"] = FP.file_digest(artifact)
    if name in ("g7b_open", "g8_open") and not remaining_admitted():
        return {"outcome": EVENT_ADMITTED_SET_EMPTY, "event": name}
    if name == "g11_complete" and not lockbox_eligible():
        return {"outcome": EVENT_LOCKBOX_NOT_ELIGIBLE, "event": name}
    if spec.predecessor:
        predecessor_status, predecessor_commit = event_status(spec.predecessor)
        if predecessor_status != EVENT_VALID:
            return {"outcome": EVENT_PREDECESSOR_NOT_VALID, "event": name,
                    "predecessor": spec.predecessor, "predecessor_status": predecessor_status}
        record["predecessor_commit"] = predecessor_commit
    FP.gate_dir().mkdir(parents=True, exist_ok=True)
    with open(path, "x") as handle:
        handle.write(json.dumps(record, indent=1, sort_keys=True) + "\n")
    return {"outcome": EVENT_WRITTEN, "event": name, "file": str(path)}


#  ------------------------------------------------------------------- guard

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
    """Enforces read order, events and provenance, and records every decision."""

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

    #  ------------------------------------------------------------ helpers

    def _record(self, path, sealed, permitted, reason, mode="CONTENT") -> AccessRecord:
        record = AccessRecord(str(path), sealed.name if sealed else None, self.stage.name,
                              permitted, reason, _now(), mode)
        self.ledger.append(record)
        return record

    def _provenance(self, path, status: str, mode: str = "CONTENT") -> None:
        self._record(path, classify(path), False, status, mode)
        raise PinProvenanceError(status, path=str(path))

    def _event_open(self, path, event: str, mode: str = "CONTENT") -> tuple:
        status, _ = event_status(event)
        if status == EVENT_VALID:
            return True, ""
        if status == EVENT_ABSENT:
            return False, f"event '{event}' ({EVENTS[event].file}) is not committed"
        self._provenance(path, status, mode)

    def _assert_matches_pin(self, path, mode: str = "CONTENT") -> None:
        resolved = str(Path(path).resolve())
        for mapping, missing_code, drift_code in (
                (self._pinned, FP.PIN_ARTIFACT_MISSING, FP.PIN_ARTIFACT_DRIFT),
                (self._module_pinned, FP.MODULE_ARTIFACT_MISSING, FP.MODULE_ARTIFACT_DRIFT)):
            if resolved in mapping:
                candidate = Path(resolved)
                if not candidate.is_file():
                    self._provenance(path, missing_code, mode)
                if FP.file_digest(candidate) != mapping[resolved]:
                    self._provenance(path, drift_code, mode)
        if resolved not in self._pinned and FP.in_pinned_scope(resolved):
            self._provenance(path, FP.PIN_SCOPE_GREW_AFTER_FREEZE, mode)

    #  ---------------------------------------------------------- decisions

    def decide(self, path) -> AccessRecord:
        sealed = classify(path)
        if is_non_authoritative(path):
            return self._record(path, sealed, False, "non-authoritative copy in the dev worktree; "
                                "gate stages read only the pinned main-checkout artifact")
        if sealed is None:
            if (self.stage < Stage.INSPECT_RETAINED_PRODUCTIONS
                    and _matches(keyed(path)[1], PROTOCOL_ARTIFACTS)):
                return self._record(path, sealed, False, "protocol artifacts are only hashed and "
                                    "counted at stages 1 and 2; their content opens at stage 3")
            return self._record(path, sealed, True, "not sealed")
        if sealed is SealedClass.NEVER:
            return self._record(path, sealed, False, "NEVER: the checkpoint journal and the "
                                "withheld expectation seal are not read by any gate stage")
        needed, event = UNLOCKS[sealed]
        if self.stage < needed:
            return self._record(path, sealed, False,
                                f"{sealed.name} unlocks at stage {int(needed)} {needed.name}; "
                                f"current stage is {int(self.stage)} {self.stage.name}")
        if event:
            opened, why = self._event_open(path, event)
            if not opened:
                return self._record(path, sealed, False, f"{sealed.name} also requires {why}")
        if sealed is SealedClass.E_TRANSFER:
            closed, why = self._event_open(path, "g8_closed")
            if closed:
                return self._record(path, sealed, False, "the single E_transfer pass is closed")
        return self._record(path, sealed, True, f"{sealed.name} unlocked at stage {int(self.stage)}")

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
            reason = "hash-only access is licensed only at stages 2 and 11"
        elif sealed is SealedClass.NEVER or is_non_authoritative(path):
            reason = "hash-only access refused for this class"
        else:
            reason = None
        self._record(path, sealed, reason is None, reason or "hash-only", "HASH_ONLY")
        if reason:
            raise SealedAccessError(f"REFUSED hash-only: {path}\n  {reason}")
        if self.stage > Stage.PIN_PROTOCOL_HASHES:
            self._assert_matches_pin(path, "HASH_ONLY")
        digest, _ = FP.digest_and_lines(path)
        return {"path": str(path), "sha256": digest, "bytes": Path(path).stat().st_size}

    def extract(self, path, purpose: str, keys=None, key_path=None) -> dict:
        """Licensed members only, from a raw ARC data file or the Lockbox manifest."""
        if purpose not in EXTRACT_PURPOSES:
            raise ValueError(f"unknown extraction purpose: {purpose}")
        if (keys is None) == (key_path is None):
            raise ValueError("give exactly one of keys or key_path")
        needed, event = EXTRACT_PURPOSES[purpose]
        sealed = classify(path)

        def refuse(reason):
            self._record(path, sealed, False, reason, "FILTERED_EXTRACT")
            raise SealedAccessError(f"REFUSED filtered extraction: {path}\n  {reason}")

        if self.stage != needed:
            refuse(f"{purpose} extraction is licensed only at stage {int(needed)} {needed.name}")
        if sealed is not SealedClass.LOCKBOX or is_non_authoritative(path):
            refuse("filtered extraction applies only to raw ARC data files and the Lockbox manifest")
        opened, why = self._event_open(path, event, "FILTERED_EXTRACT")
        if not opened:
            refuse(why)
        if purpose == "etransfer":
            closed, _ = self._event_open(path, "g8_closed", "FILTERED_EXTRACT")
            if closed:
                refuse("the single E_transfer pass is closed")
        self._assert_matches_pin(path, "FILTERED_EXTRACT")
        if keys is not None:
            members, skipped, missing = SX.extract_members(path, keys)
            self._record(path, sealed, True, f"filtered extraction for {purpose}: "
                         f"licensed {len(members)}, missing {len(missing)}, skipped {skipped}",
                         "FILTERED_EXTRACT")
            return {"members": members, "missing": missing, "skipped": skipped}
        value, skipped = SX.extract_path(path, key_path)
        self._record(path, sealed, True, f"filtered extraction for {purpose}: declared path of "
                     f"depth {len(key_path)}, skipped {skipped}", "FILTERED_EXTRACT")
        return {"value": value, "skipped": skipped}

    #  -------------------------------------------------------------- ledger

    def write_ledger(self, name: str | None = None) -> Path:
        FP.gate_dir().mkdir(parents=True, exist_ok=True)
        target = FP.gate_dir() / (name or f"access_ledger_stage{int(self.stage):02d}.jsonl")
        with target.open("a") as handle:
            for record in self.ledger:
                handle.write(json.dumps(record.__dict__, sort_keys=True) + "\n")
        self.ledger.clear()
        return target
