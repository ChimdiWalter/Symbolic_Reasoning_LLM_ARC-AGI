"""Guide hook: search-ordering signal from the trained guide network.

Env-gated by ARC_GUIDE (on iff set to "1").  When on, provides
``kind_priority(train_pairs)`` returning DeltaType value names mapped
to descending guide probability.  The hook NEVER raises into induction
-- any exception returns ``{}``.

Lazy-loads ``GuidePredictor`` ONCE per process (module-level cache,
device="cpu" so it never competes with GPU training jobs); caches
``rank()`` results keyed by a SHA-256 hash of the fold's train pairs
so repeated folds don't re-run inference.
"""

import hashlib
import json
import os
from typing import Optional

# Module-level caches (lazy-loaded; cleared only by _reset_for_test)
_predictor: Optional[object] = None
_rank_cache: dict[str, dict[str, float]] = {}


def _guide_on() -> bool:
    """True iff ``ARC_GUIDE`` is set to ``"1"``."""
    return os.environ.get("ARC_GUIDE", "") == "1"


def _pairs_hash(train_pairs) -> str:
    """Deterministic hash of ``list[(Grid, Grid)]`` for cache key."""
    h = hashlib.sha256()
    for gi, go in train_pairs:
        h.update(json.dumps(gi.to_list(), separators=(",", ":")).encode())
        h.update(b"|")
        h.update(json.dumps(go.to_list(), separators=(",", ":")).encode())
        h.update(b"\n")
    return h.hexdigest()


def kind_priority(train_pairs) -> dict[str, float]:
    """Return ``{kind_name: probability}`` from the guide network.

    Returns ``{}`` when:
    - ``ARC_GUIDE`` is not ``"1"`` (zero cost: no torch import)
    - the predictor fails to load (missing checkpoint, etc.)
    - ``rank()`` raises for any reason

    Parameters
    ----------
    train_pairs : list[tuple[Grid, Grid]]
        The *fold's own* train pairs (never the full N-pair set when
        called inside an LOO fold).
    """
    if not _guide_on():
        return {}
    try:
        key = _pairs_hash(train_pairs)
        if key in _rank_cache:
            return _rank_cache[key]

        global _predictor
        if _predictor is None:
            # Import torch + guide only when the gate is on -- the
            # import is deferred so that torch is never loaded when
            # ARC_GUIDE is off or unset.
            from guide.predict import GuidePredictor
            _predictor = GuidePredictor(device="cpu")

        task_dict = {
            "train": [{"input": gi.to_list(), "output": go.to_list()}
                      for gi, go in train_pairs],
        }
        ranked = _predictor.rank(task_dict)
        result = {name: prob for name, prob in ranked["kinds"]}
        _rank_cache[key] = result
        return result
    except Exception:
        return {}


def _reset_for_test() -> None:
    """Clear module-level caches (test-only)."""
    global _predictor
    _predictor = None
    _rank_cache.clear()
