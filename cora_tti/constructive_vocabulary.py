"""Constructive vocabulary: the frozen Item-2 grammar as executable law.

Every rule here is READ FROM the frozen protocol manifest
(outputs/tti/constructive_protocol_manifest.json, sha pinned in
constructive_protocol_manifest_hash.txt) rather than re-transcribed, so the
code cannot silently drift from the freeze. The module owns:

    - the constructor inventory and terminal vocabulary;
    - the staged-pipeline grammar and its caps, as a token state machine
      (the decoder's masking source and the generator's validity law);
    - AST <-> token round trip, canonical serialization, digests;
    - structural-family calculation (tuple of per-block Select counts);
    - schema MDL (meta_ast.ast_nodes semantics with induced slots counted
      as empty tables, documented divergence: ast_nodes on a raw "?k" slot
      string would miscount it as len("?k") table entries);
    - deterministic typed enumeration (lazy; the uniform/MDL baselines'
      candidate stream).

No function takes a task id, family label, DEV outcome, or any hidden
value; the grammar cannot be altered by anything observed at solve time.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Sequence

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "outputs" / "tti" / "constructive_protocol_manifest.json"
MANIFEST_HASH_PATH = ROOT / "outputs" / "tti" / "constructive_protocol_manifest_hash.txt"

_OPS = ("Compose", "Partition", "Select", "Map", "Key", "Lookup", "Paint")


class GrammarViolation(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@lru_cache(maxsize=1)
def manifest() -> dict:
    text = MANIFEST_PATH.read_text()
    digest = hashlib.sha256(text.encode()).hexdigest()
    pinned = MANIFEST_HASH_PATH.read_text().split()[0]
    if digest != pinned:
        raise GrammarViolation("manifest_drift",
                               f"{digest[:12]} != pinned {pinned[:12]}")
    return json.loads(text)


@lru_cache(maxsize=1)
def vocab() -> dict:
    m = manifest()
    g = m["grammar"]
    return {
        "ops": tuple(m["ops"]),
        "partitions": tuple(m["partitions"]),
        "predicates": tuple(m["predicates"]),
        "key_features": tuple(m["key_features"]),
        "induced_slot_type": m["induced_slot_types"][0],
        "max_blocks": g["blocks"][1], "min_blocks": g["blocks"][0],
        "max_selects": g["selects_per_block"][1],
        "max_stages": g["max_stages"], "max_nodes": g["max_ast_nodes"],
        "max_slots": 3,
        "banned_target_families": tuple(g["banned_target_families"]),
        "holdout_families": tuple(m["splits"]["family_holdout"]),
    }


# --------------------------------------------------------------------------
# blocks <-> AST <-> tokens
# --------------------------------------------------------------------------
# a block spec is (partition, (predicate, ...), key_feature); the induced
# Lookup slot of block i is the canonical "?i".

def ast_from_blocks(blocks: Sequence[tuple]) -> tuple:
    stages = []
    for index, (partition, selects, feature) in enumerate(blocks):
        stages.append(("Partition", (partition,)))
        for predicate in selects:
            stages.append(("Select", (predicate,)))
        stages.append(("Map", (("Key", (feature,)),
                               ("Lookup", (f"?{index}",)))))
        stages.append(("Paint", ()))
    return ("Compose", tuple(stages))


def blocks_from_ast(ast) -> list:
    """Strict structural parse; raises GrammarViolation on any deviation."""
    if not (isinstance(ast, tuple) and len(ast) == 2):
        raise GrammarViolation("grammar_invalid", "not an (op, args) tuple")
    op, stages = ast
    if op != "Compose":
        raise GrammarViolation("grammar_invalid", f"root {op!r} != Compose")
    blocks, i, slot_index = [], 0, 0
    stages = list(stages)
    while i < len(stages):
        stage = stages[i]
        if not (isinstance(stage, tuple) and len(stage) == 2):
            raise GrammarViolation("grammar_invalid", "malformed stage")
        if stage[0] != "Partition":
            raise GrammarViolation("grammar_invalid",
                                   f"block must start with Partition, got {stage[0]}")
        partition = stage[1][0]
        i += 1
        selects = []
        while i < len(stages) and stages[i][0] == "Select":
            selects.append(stages[i][1][0])
            i += 1
        if i >= len(stages) or stages[i][0] != "Map":
            raise GrammarViolation("grammar_invalid", "block missing Map")
        key_node, lookup_node = stages[i][1]
        if key_node[0] != "Key" or lookup_node[0] != "Lookup":
            raise GrammarViolation("grammar_invalid", "Map children malformed")
        feature = key_node[1][0]
        slot = lookup_node[1][0]
        if slot != f"?{slot_index}":
            raise GrammarViolation("slot_invalid",
                                   f"expected ?{slot_index}, got {slot!r}")
        slot_index += 1
        i += 1
        if i >= len(stages) or stages[i][0] != "Paint":
            raise GrammarViolation("grammar_invalid", "block missing Paint")
        i += 1
        blocks.append((partition, tuple(selects), feature))
    if not blocks:
        raise GrammarViolation("grammar_invalid", "empty pipeline")
    return blocks


def tokens_from_ast(ast) -> list:
    out = []
    for partition, selects, feature in blocks_from_ast(ast):
        out.append(("P", partition))
        out.extend(("S", predicate) for predicate in selects)
        out.append(("M", feature))
        out.append(("PAINT",))
    out.append(("EOS",))
    return out


def ast_from_tokens(tokens: Sequence[tuple]) -> tuple:
    blocks, current = [], None
    for token in tokens:
        kind = token[0]
        if kind == "P":
            if current is not None:
                raise GrammarViolation("grammar_invalid", "P inside open block")
            current = [token[1], [], None]
        elif kind == "S":
            if current is None or current[2] is not None:
                raise GrammarViolation("grammar_invalid", "S outside block head")
            current[1].append(token[1])
        elif kind == "M":
            if current is None or current[2] is not None:
                raise GrammarViolation("grammar_invalid", "M misplaced")
            current[2] = token[1]
        elif kind == "PAINT":
            if current is None or current[2] is None:
                raise GrammarViolation("grammar_invalid", "PAINT before M")
            blocks.append((current[0], tuple(current[1]), current[2]))
            current = None
        elif kind == "EOS":
            if current is not None:
                raise GrammarViolation("grammar_invalid",
                                       "EOS in the middle of a block")
            break
        else:
            raise GrammarViolation("grammar_invalid", f"unknown token {kind}")
    if current is not None:
        raise GrammarViolation("grammar_invalid", "unterminated block")
    if not blocks:
        raise GrammarViolation("grammar_invalid", "no blocks")
    return ast_from_blocks(blocks)


# --------------------------------------------------------------------------
# structure, family, accounting
# --------------------------------------------------------------------------

def family(ast) -> tuple:
    return tuple(len(selects) for _, selects, _ in blocks_from_ast(ast))


def family_text(fam: tuple) -> str:
    return "(" + ",".join(str(n) for n in fam) + ("," if len(fam) == 1 else "") + ")"


def block_count(ast) -> int:
    return len(blocks_from_ast(ast))


def stage_count(ast) -> int:
    return len(ast[1])


def slot_count(ast) -> int:
    return block_count(ast)


def mdl(ast) -> int:
    """meta_ast.ast_nodes semantics; an uninstantiated slot = empty table."""
    def nodes(node):
        op, args = node
        if op == "Lookup":
            table = args[0]
            return 1 + (0 if isinstance(table, str) and table.startswith("?")
                        else len(table))
        total = 1
        for arg in args:
            if isinstance(arg, tuple) and len(arg) == 2 \
                    and isinstance(arg[0], str) and arg[0] in _OPS:
                total += nodes(arg)
        return total
    return nodes(ast)


def canonical(ast) -> str:
    def to_json(node):
        if isinstance(node, tuple) and len(node) == 2 \
                and isinstance(node[0], str) and node[0] in _OPS:
            return {"op": node[0], "args": [to_json(a) for a in node[1]]}
        return {"lit": json.dumps(node, default=list)}
    return json.dumps(to_json(ast), sort_keys=True)


def digest(ast) -> str:
    return hashlib.sha256(canonical(ast).encode()).hexdigest()


# --------------------------------------------------------------------------
# validation (the generator's and compiler's shared law)
# --------------------------------------------------------------------------

def validate(ast) -> tuple:
    """(True, "") or (False, rejection_code)."""
    v = vocab()
    try:
        blocks = blocks_from_ast(ast)
    except GrammarViolation as err:
        return False, err.code
    if not (v["min_blocks"] <= len(blocks) <= v["max_blocks"]):
        return False, "block_count_exceeded"
    for partition, selects, feature in blocks:
        if partition not in v["partitions"]:
            return False, "unknown_terminal"
        if feature not in v["key_features"]:
            return False, "unknown_terminal"
        if len(selects) > v["max_selects"]:
            return False, "select_count_exceeded"
        for predicate in selects:
            if predicate not in v["predicates"]:
                return False, "unknown_terminal"
    if stage_count(ast) > v["max_stages"]:
        return False, "stage_count_exceeded"
    if mdl(ast) > v["max_nodes"]:
        return False, "node_count_exceeded"
    if slot_count(ast) > v["max_slots"]:
        return False, "slot_count_exceeded"
    return True, ""


def is_banned_target_family(fam: tuple) -> bool:
    return family_text(fam) in vocab()["banned_target_families"]


def is_holdout_family(fam: tuple) -> bool:
    return family_text(fam) in vocab()["holdout_families"]


# --------------------------------------------------------------------------
# grammar state machine (single source of decoder masks)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class GrammarState:
    blocks_done: int = 0
    in_block: bool = False
    selects_in_block: int = 0
    awaiting_paint: bool = False
    stages_used: int = 0
    finished: bool = False

    def legal_tokens(self) -> list:
        v = vocab()
        if self.finished:
            return []
        out = []
        if self.awaiting_paint:
            return [("PAINT",)]
        if self.in_block:
            if self.selects_in_block < v["max_selects"] \
                    and self.stages_used + 3 <= v["max_stages"]:
                out.extend(("S", p) for p in v["predicates"])
            out.extend(("M", f) for f in v["key_features"])
            return out
        #  between blocks
        if self.blocks_done >= v["min_blocks"]:
            out.append(("EOS",))
        if self.blocks_done < v["max_blocks"] \
                and self.stages_used + 3 <= v["max_stages"]:
            out.extend(("P", p) for p in v["partitions"])
        return out

    def advance(self, token: tuple) -> "GrammarState":
        if token not in self.legal_tokens():
            raise GrammarViolation("grammar_invalid",
                                   f"illegal token {token} in state {self}")
        kind = token[0]
        if kind == "P":
            return replace(self, in_block=True, selects_in_block=0,
                           stages_used=self.stages_used + 1)
        if kind == "S":
            return replace(self, selects_in_block=self.selects_in_block + 1,
                           stages_used=self.stages_used + 1)
        if kind == "M":
            return replace(self, in_block=False, awaiting_paint=True,
                           stages_used=self.stages_used + 1)
        if kind == "PAINT":
            return replace(self, awaiting_paint=False,
                           blocks_done=self.blocks_done + 1,
                           stages_used=self.stages_used + 1)
        return replace(self, finished=True)


def tokens_are_valid(tokens: Sequence[tuple]) -> bool:
    state = GrammarState()
    try:
        for token in tokens:
            state = state.advance(token)
    except GrammarViolation:
        return False
    return state.finished


# --------------------------------------------------------------------------
# deterministic typed enumeration (lazy)
# --------------------------------------------------------------------------

def _select_sequences() -> list:
    v = vocab()
    seqs = [()]
    for length in range(1, v["max_selects"] + 1):
        def extend(prefix):
            if len(prefix) == length:
                seqs.append(tuple(prefix))
                return
            for p in v["predicates"]:
                extend(prefix + [p])
        extend([])
    return seqs


def enumerate_asts(max_blocks: int | None = None) -> Iterator[tuple]:
    """All grammar-valid schemas in canonical order: by block count, then
    lexicographic block specs. Deterministic; lazy."""
    v = vocab()
    limit = min(max_blocks or v["max_blocks"], v["max_blocks"])
    seqs = _select_sequences()
    block_specs = [(p, s, f) for p in v["partitions"]
                   for s in seqs for f in v["key_features"]]

    def combos(n, prefix):
        if n == 0:
            ast = ast_from_blocks(prefix)
            ok, _ = validate(ast)
            if ok:
                yield ast
            return
        for spec in block_specs:
            yield from combos(n - 1, prefix + [spec])

    for blocks_n in range(v["min_blocks"], limit + 1):
        yield from combos(blocks_n, [])
