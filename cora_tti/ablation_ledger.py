"""Append-only, hash-chained evidence ledger (phase P2; plan §XII and §XIX).

Every claim the competition track will ever make — a development score, a
holdout gate, a TTI-dependent solve — must trace to a ledger entry that cannot
be silently edited or reordered. Entries form a hash chain: each entry stores
the sha256 of its predecessor, so truncation, insertion, or in-place edits are
mechanically detectable by `verify()`.

Entry kinds:

    evaluation      one scored run: config fingerprint + the causal stack
                    {base, global, gpn, tti, final} (any subset present)
    tti_ablation    one per-output causal test of a claimed TTI solve; the
                    §XII conjunction is computed here, never by the caller
    holdout_gate    a holdout scoring event (mirrors the emulator's ledger)
    note            free-form context (never evidence)

`causal_decomposition()` reduces evaluation entries to the paper's stack
(score_base -> +global -> +gpn -> +tti -> +final) and refuses to fabricate
missing stages. `tti_dependent()` is the single implementation of the
conjunction: baseline failure AND production proposed AND used by the winner
AND LOO pass AND test-correct AND ablation-fails — a solve that survives
ablation is credited to search, not invention.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

GENESIS = "0" * 64
KINDS = ("evaluation", "tti_ablation", "holdout_gate", "note")

#: the §XII conjunction, in the exact order reported
CONJUNCTION = ("baseline_fails", "production_proposed", "winner_uses_production",
               "loo_all_folds_pass", "test_output_correct", "ablation_fails")


def tti_dependent(evidence: Mapping[str, bool]) -> bool:
    """True iff EVERY conjunct holds. Missing keys count as False."""
    return all(bool(evidence.get(key)) for key in CONJUNCTION)


class AblationLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- internals -----------------------------------------------------------
    def _entries_raw(self) -> list:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in
                self.path.read_text().splitlines() if line.strip()]

    def _tip(self) -> str:
        entries = self._entries_raw()
        return entries[-1]["entry_sha256"] if entries else GENESIS

    @staticmethod
    def _digest(entry: Mapping[str, Any]) -> str:
        body = {k: v for k, v in entry.items() if k != "entry_sha256"}
        return hashlib.sha256(
            json.dumps(body, sort_keys=True).encode()).hexdigest()

    def _append(self, kind: str, payload: Mapping[str, Any]) -> dict:
        if kind not in KINDS:
            raise ValueError(f"unknown ledger kind {kind!r}")
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind,
                 "payload": payload, "prev_sha256": self._tip()}
        entry["entry_sha256"] = self._digest(entry)
        with self.path.open("a") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    # -- public appends ------------------------------------------------------
    def record_evaluation(self, config_fingerprint: str, split: str,
                          scores: Mapping[str, float],
                          detail: Mapping[str, Any] | None = None) -> dict:
        unknown = set(scores) - {"base", "global", "gpn", "tti", "final"}
        if unknown:
            raise ValueError(f"unknown score stages {sorted(unknown)}")
        return self._append("evaluation", {
            "config_fingerprint": config_fingerprint, "split": split,
            "scores": dict(scores), "detail": detail or {}})

    def record_tti_ablation(self, output_id: str, production_signature: str,
                            evidence: Mapping[str, bool]) -> dict:
        row = {key: bool(evidence.get(key, False)) for key in CONJUNCTION}
        return self._append("tti_ablation", {
            "output_id": output_id,
            "production_signature": production_signature,
            "evidence": row, "tti_dependent": tti_dependent(row)})

    def record_holdout_gate(self, gate: str, pass_at_2: float,
                            predictions_sha256: str) -> dict:
        if gate not in ("C3", "C4", "C5"):
            raise ValueError("holdout gates are C3/C4/C5 only")
        return self._append("holdout_gate", {
            "gate": gate, "pass_at_2": pass_at_2,
            "predictions_sha256": predictions_sha256})

    def record_note(self, text: str) -> dict:
        return self._append("note", {"text": text})

    # -- reading and verification -------------------------------------------
    def entries(self, kind: str | None = None) -> list:
        rows = self._entries_raw()
        return [r for r in rows if kind is None or r["kind"] == kind]

    def verify(self) -> dict:
        """Walk the chain; report the first break. An edited, reordered,
        truncated-in-the-middle, or inserted entry breaks the chain."""
        prev = GENESIS
        for index, entry in enumerate(self._entries_raw()):
            if entry.get("prev_sha256") != prev:
                return {"ok": False, "break_at": index, "reason": "chain"}
            if self._digest(entry) != entry.get("entry_sha256"):
                return {"ok": False, "break_at": index, "reason": "content"}
            prev = entry["entry_sha256"]
        return {"ok": True, "entries": len(self._entries_raw()), "tip": prev}


def causal_decomposition(entries: Sequence[Mapping[str, Any]]) -> dict:
    """The paper's stack from the LATEST evaluation entry per split.

    Missing stages stay missing — nothing is interpolated. Deltas are reported
    stage over stage in the fixed order base -> global -> gpn -> tti -> final.
    """
    order = ("base", "global", "gpn", "tti", "final")
    latest: dict = {}
    for entry in entries:
        if entry["kind"] == "evaluation":
            latest[entry["payload"]["split"]] = entry["payload"]
    out = {}
    for split, payload in sorted(latest.items()):
        scores = payload["scores"]
        stack, deltas, previous = {}, {}, None
        for stage in order:
            if stage not in scores:
                continue
            stack[stage] = scores[stage]
            if previous is not None:
                deltas[f"{previous}->{stage}"] = round(
                    scores[stage] - scores[previous], 6)
            previous = stage
        out[split] = {"scores": stack, "deltas": deltas,
                      "config_fingerprint": payload["config_fingerprint"]}
    return out
