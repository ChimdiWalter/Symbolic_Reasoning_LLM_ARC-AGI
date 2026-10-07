"""Task selection and the reasoner bundle (protocol sections 3 and 4).

Selection reads the ARC-AGI-2 training CHALLENGES file only (demonstrations
and unlabelled test inputs); it never opens a solutions file. Every rule here
is a function of the demonstrations and the task identifier string alone.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets

#: canonical authorized data (records/REAL_ARC_PILOT_V1_DATA_AUDIT.md)
DATA_DIR = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti/data/arc"
CHALLENGES = os.path.join(DATA_DIR, "arc-agi_training_challenges.json")
SOLUTIONS = os.path.join(DATA_DIR, "arc-agi_training_solutions.json")
CHALLENGES_SHA256 = "779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5"
SOLUTIONS_SHA256 = "9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9"

ORDER_PREFIX = "cora-real-arc-pilot-v1|"
DEV_SIZE = 60
STRATA = ("n3", "n4", "n5p")
#: pilot quota per stratum as a share of N (N a multiple of 6): 1/2, 1/3, 1/6
QUOTA_SIXTHS = {"n3": 3, "n4": 2, "n5p": 1}
ALLOWED_N = (48, 72, 96, 120)

BUNDLE_FORMAT = "cora-real-arc-pilot-bundle/1"
KEYMAP_FORMAT = "cora-real-arc-pilot-keymap/1"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def load_challenges(path=CHALLENGES, expected=CHALLENGES_SHA256) -> dict:
    digest = sha256_file(path)
    if digest != expected:
        raise ValueError(f"challenges sha256 {digest} != pinned {expected}")
    with open(path) as handle:
        return json.load(handle)


def _shape(grid):
    return (len(grid), len(grid[0]) if grid else 0)


def in_scope(task) -> bool:
    """The closed loop's static scope, from the demonstrations alone: at
    least three demonstrations, every demonstration keeps its grid shape, and
    every demonstration changes at least one cell (the expression phase's
    trigger, and the v1.8 proposer's same-shape grammar)."""
    train = task.get("train") or []
    if len(train) < 3:
        return False
    for pair in train:
        a, b = pair["input"], pair["output"]
        if _shape(a) != _shape(b) or a == b:
            return False
    return True


def stratum(task) -> str:
    n = len(task["train"])
    return "n3" if n == 3 else ("n4" if n == 4 else "n5p")


def order_key(task_id: str) -> str:
    return hashlib.sha256((ORDER_PREFIX + task_id).encode()).hexdigest()


def selection(challenges) -> dict:
    """The frozen order of the in-scope tasks, the development set (the first
    DEV_SIZE in the order) and, per stratum, the pilot candidates in order."""
    scoped = sorted((tid for tid, t in challenges.items() if in_scope(t)), key=order_key)
    dev = scoped[:DEV_SIZE]
    devset = set(dev)
    candidates = {s: [t for t in scoped if t not in devset and stratum(challenges[t]) == s]
                  for s in STRATA}
    counts = {s: sum(1 for t in scoped if stratum(challenges[t]) == s) for s in STRATA}
    return {"rule": {"scope": in_scope.__doc__.split("\n\n")[0].replace("\n", " "),
                     "order": f"ascending sha256('{ORDER_PREFIX}' + task_id)",
                     "dev": f"the first {DEV_SIZE} in-scope tasks in the order",
                     "pilot": "per stratum, the first quota tasks in the order outside the development set; "
                              "quota = N x (3, 2, 1) / 6 for (n3, n4, n5p)",
                     "allowed_n": list(ALLOWED_N)},
            "tasks_total": len(challenges), "in_scope": len(scoped), "strata_counts": counts,
            "order": [[t, stratum(challenges[t])] for t in scoped],
            "dev": dev, "pilot_candidates": candidates}


def pilot_ids(sel, n: int) -> list:
    if n not in ALLOWED_N:
        raise ValueError(f"N must be one of {ALLOWED_N}")
    out = []
    for s in STRATA:
        q = n * QUOTA_SIXTHS[s] // 6
        if len(sel["pilot_candidates"][s]) < q:
            raise ValueError(f"stratum {s} has {len(sel['pilot_candidates'][s])} < quota {q}")
        out.extend(sel["pilot_candidates"][s][:q])
    return out


def opaque_key(salt_hex: str, task_id: str) -> str:
    return "k" + hmac.new(bytes.fromhex(salt_hex), task_id.encode(), hashlib.sha256).hexdigest()[:12]


def make_bundle(challenges, task_ids, salt_hex=None):
    """(bundle, keymap). The bundle holds, per opaque key, the demonstrations
    and the test INPUTS only; the keymap (evaluator side) holds the salt and
    the key -> task id map."""
    salt_hex = salt_hex or secrets.token_hex(32)
    tasks, keys = {}, {}
    for tid in task_ids:
        t = challenges[tid]
        k = opaque_key(salt_hex, tid)
        if k in tasks:
            raise ValueError("opaque key collision")
        tasks[k] = {"train": [{"input": p["input"], "output": p["output"]} for p in t["train"]],
                    "test": [{"input": p["input"]} for p in t["test"]]}
        keys[k] = {"task_id": tid, "stratum": stratum(t), "n_test": len(t["test"])}
    bundle = {"format": BUNDLE_FORMAT, "tasks": {k: tasks[k] for k in sorted(tasks)}}
    check_bundle(bundle)
    keymap = {"format": KEYMAP_FORMAT, "salt": salt_hex, "keys": {k: keys[k] for k in sorted(keys)},
              "bundle_sha256": hashlib.sha256(canonical_json(bundle)).hexdigest(),
              "challenges_sha256": CHALLENGES_SHA256, "solutions_sha256": SOLUTIONS_SHA256}
    return bundle, keymap


BUNDLE_TASK_KEYS = frozenset({"train", "test"})


def _grid_ok(g) -> bool:
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


def check_bundle(bundle) -> None:
    """Refuse a bundle that carries anything but opaque keys, demonstration
    pairs and unlabelled test inputs."""
    if not isinstance(bundle, dict) or set(bundle) != {"format", "tasks"} or bundle["format"] != BUNDLE_FORMAT:
        raise ValueError("bundle top level")
    for k, t in bundle["tasks"].items():
        if not (isinstance(k, str) and len(k) == 13 and k[0] == "k" and all(c in "0123456789abcdef" for c in k[1:])):
            raise ValueError(f"key {k!r} is not opaque")
        if set(t) != BUNDLE_TASK_KEYS:
            raise ValueError(f"task {k}: keys {sorted(t)}")
        for p in t["train"]:
            if set(p) != {"input", "output"} or not (_grid_ok(p["input"]) and _grid_ok(p["output"])):
                raise ValueError(f"task {k}: demonstration")
        for p in t["test"]:
            if set(p) != {"input"} or not _grid_ok(p["input"]):
                raise ValueError(f"task {k}: a test entry carries more than its input")


def write_json(path, obj) -> str:
    data = canonical_json(obj)
    tmp = path + ".tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.replace(tmp, path)
    return hashlib.sha256(data).hexdigest()
