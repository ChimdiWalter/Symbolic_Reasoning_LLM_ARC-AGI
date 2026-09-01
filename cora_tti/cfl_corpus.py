"""Cognitive Failure Localization corpus generator (parent architecture idea 1).

Self-supervised (F, z) pairs by deliberately crippling KNOWN components, so a
localizer can learn q(z | TFG) with zero human labels:

    SEMANTICS          remove a semantic production the task requires
                       (delegated to the Stage-A operator-dropout generator)
    RESOURCE_LIMIT     the FULL language solves the task comfortably, but the
                       search is given a starvation budget and dies on time
    PARAMETER_LEARNING the language and budget are intact, but the slot
                       learner is disabled (returns None), so every candidate
                       that needs an induced value dies at slot fitting

Each episode records the TFG of the crippled failure plus the ground-truth
cause. The scientific question the corpus exists to answer is whether these
causes are DISTINGUISHABLE from mechanistic failure evidence alone — a
localizer at chance level on held-out cripples is a real (publishable)
negative about this failure representation, not a bug.

Discipline: synthetic tasks only (D2); tasks are generated from sampled
programs of the PUBLIC registry; no task identity exists to leak. The slot
learner is disabled via the documented registry dict and ALWAYS restored in a
finally block; nothing frozen is touched.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V              # noqa: E402
from level4_blind_runtime import env as E                  # noqa: E402
from level4_blind_runtime import stepA_trace_search as TS  # noqa: E402

from cora_tti import dropout_generator as DG               # noqa: E402
from cora_tti import tfg_extractor as TX                   # noqa: E402

CAUSES = ("SEMANTICS", "RESOURCE_LIMIT", "PARAMETER_LEARNING")


@dataclass
class CFLConfig:
    #: generous budget under which the healthy solver must succeed
    healthy_budget_s: float = 4.0
    #: starvation budget for RESOURCE_LIMIT episodes
    starved_budget_s: float = 0.05
    #: budget for the crippled searches
    crippled_budget_s: float = 1.5


def _solvable_task(rng: np.random.Generator, config: CFLConfig,
                   max_tries: int = 40):
    """A synthetic task the FULL healthy system solves within budget."""
    env = E.LanguageEnv(base=dict(V.REGISTRY), label="full")
    for _ in range(max_tries):
        program = DG.sample_ast(rng, DG.GOAL, V.REGISTRY)
        if program is None:
            continue
        pairs = DG.render_demos(program, rng, env)
        if pairs is None:
            continue
        report = TX.extract(pairs, env=env, budget_s=config.healthy_budget_s)
        if report["solved"]:
            return pairs
    return None


class _learner_disabled:
    """Replace every slot learner with a refusal for the duration."""

    def __enter__(self):
        self.saved = dict(TS.SLOT_LEARNERS)
        for key in TS.SLOT_LEARNERS:
            TS.SLOT_LEARNERS[key] = lambda ast, pairs, slot: None
        return self

    def __exit__(self, *exc):
        TS.SLOT_LEARNERS.clear()
        TS.SLOT_LEARNERS.update(self.saved)
        return False


def resource_episode(rng: np.random.Generator, config: CFLConfig):
    pairs = _solvable_task(rng, config)
    if pairs is None:
        return None
    report = TX.extract(pairs, budget_s=config.starved_budget_s)
    if report["solved"]:
        return None                     # solved even starved: not an episode
    return {"tfg": report["tfg"].to_json(),
            "tfg_digest": report["tfg"].digest(),
            "flags": {"cause": "RESOURCE_LIMIT",
                      "healthy_budget_s": config.healthy_budget_s,
                      "starved_budget_s": config.starved_budget_s},
            "demonstrations": [{"input": a.tolist(), "output": b.tolist()}
                               for a, b in pairs]}


def parameter_episode(rng: np.random.Generator, config: CFLConfig):
    pairs = _solvable_task(rng, config)
    if pairs is None:
        return None
    with _learner_disabled():
        report = TX.extract(pairs, budget_s=config.crippled_budget_s)
    if report["solved"]:
        return None                     # solvable without any induced slot
    return {"tfg": report["tfg"].to_json(),
            "tfg_digest": report["tfg"].digest(),
            "flags": {"cause": "PARAMETER_LEARNING",
                      "crippled_budget_s": config.crippled_budget_s},
            "demonstrations": [{"input": a.tolist(), "output": b.tolist()}
                               for a, b in pairs]}


def semantics_episode(rng: np.random.Generator, withheld: str,
                      config: CFLConfig):
    """Delegates to Stage A; re-labels nothing (cause is already SEMANTICS)."""
    return DG.episode(rng, withheld,
                      DG.EpisodeConfig(search_budget_s=config.crippled_budget_s,
                                       verify_full=False))


def generate(out_path: Path, per_cause: int, seed: int,
             config: CFLConfig = CFLConfig(),
             semantic_productions: Sequence[str] = ("PaintEach", "Map_V1",
                                                    "Partition")) -> dict:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows, shortfall = [], {}

    def rng_for(tag: str) -> np.random.Generator:
        return np.random.default_rng(int.from_bytes(
            hashlib.sha256(f"{seed}:{tag}".encode()).digest()[:8], "big"))

    #  SEMANTICS: round-robin over the given productions
    made, attempts = 0, 0
    rng = rng_for("semantics")
    while made < per_cause and attempts < per_cause * 30:
        attempts += 1
        name = semantic_productions[attempts % len(semantic_productions)]
        row = semantics_episode(rng, name, config)
        if row is not None:
            rows.append({"tfg": row["tfg"], "tfg_digest": row["tfg_digest"],
                         "flags": row["flags"],
                         "demonstrations": row["demonstrations"]})
            made += 1
    if made < per_cause:
        shortfall["SEMANTICS"] = made

    for cause, fn in (("RESOURCE_LIMIT", resource_episode),
                      ("PARAMETER_LEARNING", parameter_episode)):
        made, attempts = 0, 0
        rng = rng_for(cause)
        while made < per_cause and attempts < per_cause * 30:
            attempts += 1
            row = fn(rng, config)
            if row is not None:
                rows.append(row)
                made += 1
        if made < per_cause:
            shortfall[cause] = made

    text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    out_path.write_text(text)
    manifest = {
        "stage": "CFL cripple corpus v1",
        "seed": seed, "per_cause": per_cause,
        "causes": list(CAUSES),
        "semantic_productions": list(semantic_productions),
        "config": {"healthy_budget_s": config.healthy_budget_s,
                   "starved_budget_s": config.starved_budget_s,
                   "crippled_budget_s": config.crippled_budget_s},
        "counts": {c: sum(1 for r in rows if r["flags"]["cause"] == c)
                   for c in CAUSES},
        "shortfall": shortfall,
        "file_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
    out_path.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True))
    return manifest
