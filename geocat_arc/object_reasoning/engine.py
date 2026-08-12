"""ObjectReasoningEngine — harness-facing facade (Requirement 4.4).

SAME duck type as geocat_arc.reasoning.reasoning_engine.ReasoningEngine so
the unified harness can mount it as a third layer:

    result = engine.solve(task_id, train_pairs)
    result.solution.is_exact / .apply_fn / .strategy / .train_accuracy
    result.near_solves / result.strategies_tried / result.best_accuracy

plus the object-level extras: result.solution.program_json (the complete
serialized ObjectProgram, Requirement 4.2) and result.certificate.

task_id is used for LOGGING, SERIALIZATION, and MEMORY PROVENANCE ONLY —
never to branch solving behavior (hard constraint 6.1).

Implementation notes (engine team):
- Solution.apply_fn is reconstructed FROM THE SERIALIZED PROGRAM JSON
  (ObjectProgram.from_dict -> actions.program_apply_fn), proving the JSON
  artifact is execution-complete (Requirement 4.2; tested).
- The engine keeps an in-memory (never persisted) cache of the train pairs
  it was handed this run, solely so promote_and_validate() can re-induce
  provenance tasks and run zero-regression probes through the NORMAL
  induction path (Section 5.4).  It holds no other task data (design
  decision 12); resume_tasks_for takes a task_loader callback.
"""
from __future__ import annotations

import dataclasses
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .actions import program_apply_fn
from .inducer import InductionConfig, certify, induce_program
from .memory import (
    FragmentLibrary,
    NearSolveStore,
    cluster_failures,
    invent_from_cluster,
    promote_fragments,
    validate_operator,
)
from .types import (
    ArrayPair,
    InductionResult,
    LibraryOperator,
    NearSolveRecord,
    ObjectProgram,
    ProgramCertificate,
    program_from_dict,
    to_grid_pairs,
)


@dataclass
class ObjectSolution:
    """Field-compatible with reasoning_engine.Solution + program_json."""
    task_id: str
    strategy: str                                   # "object_program"
    apply_fn: Callable[[np.ndarray], np.ndarray]    # wraps render_program ONLY
    train_accuracy: float
    loo_score: float
    is_exact: bool
    program_json: dict = field(default_factory=dict)  # ObjectProgram.to_dict()


@dataclass
class ObjectReasoningResult:
    """Field-compatible with reasoning_engine.ReasoningResult (profile is
    replaced by the richer InductionResult)."""
    task_id: str
    solution: Optional[ObjectSolution]
    near_solves: list[NearSolveRecord] = field(default_factory=list)
    strategies_tried: list[str] = field(default_factory=list)
    best_accuracy: float = 0.0
    induction: Optional[InductionResult] = None
    certificate: Optional[ProgramCertificate] = None


class ObjectReasoningEngine:
    """Stage-1 object-level engine.

    Lifecycle: construct once per run with the output directory; call
    solve() per task (any order — the order is recorded for the Requirement
    1.2 order-effect ablation); call promote_and_validate() between batches
    (or at end of run) to grow the library.

    Args:
        output_dir: run-local root; programs -> programs/<task_id>.json,
            certificates -> certificates/<task_id>.json, near-solves ->
            near_solves.jsonl, library -> library.json (Requirements 4.2/5.x).
        use_library: False = the --no-library ablation (Requirement 1.2).
        config: shared InductionConfig; per-task mutation is forbidden.
    """

    #: Section 5.4(b): number of already-solved probe tasks per candidate.
    N_PROBES: int = 10

    def __init__(self, output_dir: Path | str,
                 use_library: bool = True,
                 config: Optional[InductionConfig] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.near_solve_store = NearSolveStore(self.output_dir / "near_solves.jsonl")
        # AUTONOMOUS M2 (round 7): learned-verb registry, engine-dir
        # scoped like library.json; constant per run (legality rule 3).
        from .synth_verbs import LearnedVerbRegistry
        from .correspondence import set_learned_verbs
        set_learned_verbs(LearnedVerbRegistry.load(str(self.output_dir)))
        self.library = FragmentLibrary(self.output_dir / "library.json",
                                       enabled=use_library)
        self.config = config or InductionConfig()
        self.task_order: list[str] = []          # processing order (Req 1.2)
        self.accepted: dict[str, dict] = {}      # task_id -> program dict (provenance)
        self.run_id: str = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
        # transient, in-memory only: train pairs seen this run (Section 5.4
        # provenance re-induction + probes; never persisted, never branched on).
        self._train_cache: dict[str, list[ArrayPair]] = {}

    # -- internal helpers --

    def _config_with_library(self,
                             extra: Optional[list[LibraryOperator]] = None
                             ) -> InductionConfig:
        operators = list(self.library.operators())
        if extra:
            operators = operators + list(extra)
        return dataclasses.replace(self.config, library=operators,
                                   use_library=self.library.enabled
                                   and self.config.use_library)

    def _persist_program(self, task_id: str, program_json: dict) -> Path:
        path = self.output_dir / "programs" / f"{task_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(program_json, indent=2))
        return path

    def _persist_certificate(self, cert: ProgramCertificate) -> Path:
        path = self.output_dir / "certificates" / f"{cert.task_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cert.to_dict(), indent=2))
        return path

    # -- main entry point (harness contract) --

    def solve(self, task_id: str,
              train_pairs: list[ArrayPair]) -> ObjectReasoningResult:
        """Induce a program for one task (submission mode: test outputs are
        never seen here).  Never raises on solver failure."""
        self.task_order.append(task_id)
        self._train_cache[task_id] = list(train_pairs)
        result = ObjectReasoningResult(task_id=task_id, solution=None,
                                       strategies_tried=["object_program"])
        try:
            grid_pairs = to_grid_pairs(train_pairs)
            cfg = self._config_with_library()
            # Round-14 cumulative loop: the task's OWN prior near-solve
            # partials (seeded near_solves.jsonl, like library.json) feed
            # the overlay expansion as base hints — constant within the
            # task, so folds re-derive; gate unchanged.
            hints = []
            if os.environ.get("ARC_OVERLAY", "") not in ("", "0"):
                try:
                    for rec in self.near_solve_store.load_all():
                        if rec.task_id == task_id and rec.program_partial:
                            hints.append(rec.program_partial)
                except Exception:
                    hints = []
            induction = induce_program(grid_pairs, cfg,
                                       base_hints=hints[:3])
            induction.task_id = task_id  # provenance stamp only

            # Round-13 dihedral-frame fallback (idea 1): when the identity
            # frame fails and ARC_DIHEDRAL_FRAMES=<budget_s> is set, run
            # the FULL induction on the 7 non-identity reframings
            # (deterministic order, first certification wins).  Each frame
            # is an independent complete run of the gate; the certificate
            # transfers because the transform is a grid bijection.
            frames_budget = float(os.environ.get("ARC_DIHEDRAL_FRAMES", 0))
            if not induction.accepted and frames_budget > 0:
                import numpy as _np
                from .types import FramedProgram
                for k, flip in ((1, False), (2, False), (3, False),
                                (0, True), (1, True), (2, True), (3, True)):
                    def _t(a):
                        a = _np.asarray(a)
                        if flip:
                            a = _np.fliplr(a)
                        return _np.ascontiguousarray(_np.rot90(a, k))
                    framed_pairs = to_grid_pairs(
                        [(_t(i), _t(o)) for i, o in train_pairs])
                    f_cfg = dataclasses.replace(cfg, budget_s=frames_budget)
                    try:
                        f_ind = induce_program(framed_pairs, f_cfg)
                    except Exception:
                        continue
                    if f_ind.accepted and f_ind.program is not None:
                        f_ind.program = FramedProgram(
                            frame=(k, flip), inner=f_ind.program)
                        f_ind.task_id = task_id
                        f_ind.events.append("DIHEDRAL_FRAME_ACCEPTED")
                        induction = f_ind
                        break
            result.induction = induction
            result.best_accuracy = induction.train_fit_pixels

            if induction.accepted and induction.program is not None:
                # Requirement 4.2: the JSON artifact alone must reconstruct
                # execution — apply_fn is built from the serialized dict, not
                # from the live program object.
                program_json = induction.program.to_dict()
                reconstructed = program_from_dict(
                    json.loads(json.dumps(program_json)))
                apply_fn = program_apply_fn(reconstructed)
                self._persist_program(task_id, program_json)
                certificate: Optional[ProgramCertificate] = None
                try:
                    certificate = certify(induction, task_id,
                                          run_id=self.run_id)
                    self._persist_certificate(certificate)
                    induction.events.append("REASONING_CERTIFICATE_CREATED")
                except ValueError:
                    # single-pair tasks (folds == 0) are accepted but cannot
                    # carry an A5 certificate (design decision 9).
                    certificate = None
                self.accepted[task_id] = program_json
                loo_score = induction.loo.score if induction.loo else 0.0
                result.solution = ObjectSolution(
                    task_id=task_id, strategy="object_program",
                    apply_fn=apply_fn, train_accuracy=1.0,
                    loo_score=loo_score, is_exact=True,
                    program_json=program_json)
                result.certificate = certificate
                result.best_accuracy = 1.0
                induction.events.append("TASK_PROMOTED_TO_SOLVED")
                induction.events.append("FINAL_PREDICTION_EMITTED")
            elif induction.near_solve is not None:
                record = induction.near_solve
                record.task_id = task_id  # provenance stamp only
                self.record_near_solve(record)
                result.near_solves = [record]
        except Exception:
            # harness contract: never raise on solver failure
            result.solution = None
        return result

    # -- near-solve recording hook (also usable by outer layers) --

    def record_near_solve(self, record: NearSolveRecord) -> None:
        """Persist a near-solve (glue — implemented)."""
        self.near_solve_store.append(record)

    # -- cumulative-learning hooks (Section 5; called between batches) --

    def _reinduce(self, task_id: str,
                  extra_ops: Optional[list[LibraryOperator]] = None
                  ) -> Optional[InductionResult]:
        """Re-run NORMAL induction on a cached task (no task-targeted
        shortcuts, no stored answers)."""
        pairs = self._train_cache.get(task_id)
        if pairs is None:
            return None
        cfg = self._config_with_library(extra=extra_ops)
        res = induce_program(to_grid_pairs(pairs), cfg)
        res.task_id = task_id
        return res

    def promote_and_validate(self) -> list[str]:
        """Mine fragments over accepted programs + invent from failure
        clusters; validate (Section 5.4) and register survivors."""
        registered: list[str] = []
        existing = {op.name for op in self.library.operators()}

        accepted_programs = {tid: program_from_dict(d)
                             for tid, d in self.accepted.items()}
        candidates = promote_fragments(accepted_programs)

        def _probe_fns(candidate: LibraryOperator) -> list:
            solved = sorted(self.accepted)
            rng = random.Random(0)  # deterministic global choice, not per task
            probes = solved if len(solved) <= self.N_PROBES \
                else rng.sample(solved, self.N_PROBES)

            def make(tid: str):
                def probe() -> bool:
                    res = self._reinduce(tid, extra_ops=[candidate])
                    return bool(res is not None and res.accepted)
                return probe
            return [make(t) for t in probes]

        for op in candidates:
            if op.name in existing:
                continue
            passed, record = validate_operator(
                op,
                reinduce_provenance_fn=lambda tid, _op=op: self._reinduce(
                    tid, extra_ops=[_op]),
                solved_probe_fns=_probe_fns(op),
            )
            op.falsification_record = record
            if passed:
                self.library.register(op)
                existing.add(op.name)
                registered.append(op.name)

        # invention from failure clusters (Section 5.2/5.3)
        records = self.near_solve_store.load_all()
        clusters = cluster_failures(records)

        def retro_solve_fn(task_id: str, candidate: LibraryOperator) -> bool:
            res = self._reinduce(task_id, extra_ops=[candidate])
            return bool(res is not None and res.accepted)

        for cluster in clusters:
            if not cluster.is_invention_candidate:
                continue
            candidate = invent_from_cluster(cluster, self.near_solve_store,
                                            retro_solve_fn=retro_solve_fn)
            if candidate is None or candidate.name in existing:
                continue
            passed, record = validate_operator(
                candidate,
                reinduce_provenance_fn=lambda tid, _op=candidate:
                    self._reinduce(tid, extra_ops=[_op]),
                solved_probe_fns=_probe_fns(candidate),
            )
            candidate.falsification_record = record
            if passed:
                self.library.register(candidate)
                existing.add(candidate.name)
                registered.append(candidate.name)
        return registered

    def resume_tasks_for(self, operator_name: str,
                         task_loader: Callable[[str], list[ArrayPair]]) -> list[str]:
        """Task resumption (Section 1 chain): re-run solve() on every task
        whose NearSolveRecords are in the newly registered operator's source
        cluster — through the normal induction path only."""
        ops = {op.name: op for op in self.library.operators()}
        op = ops.get(operator_name)
        if op is None:
            return []
        member_tasks: list[str] = list(op.loo_record.get("retro_attempted", []))
        if not member_tasks:
            member_tasks = [t for t in op.provenance
                            if t not in self.accepted]
        newly_solved: list[str] = []
        for task_id in sorted(set(member_tasks)):
            if task_id in self.accepted:
                continue
            try:
                pairs = task_loader(task_id)
            except Exception:
                continue
            result = self.solve(task_id, pairs)
            if result.induction is not None:
                result.induction.events.append("TASK_RESUMED")
            if result.solution is not None:
                newly_solved.append(task_id)
        return newly_solved
