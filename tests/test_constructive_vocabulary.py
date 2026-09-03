"""Vocabulary gates (directive block 3): the frozen grammar as tested law."""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_tti import constructive_vocabulary as CV   # noqa: E402

B1 = ("colour_components", ("rectangular", "touching_border"), "area")   # (2,)
B0 = ("background_components", (), "shape")                              # (0,)
BS = ("separator_panels", ("all",), "row_band")                          # (1,)


def test_manifest_consumed_and_hash_checked():
    v = CV.vocab()
    assert len(v["partitions"]) == 4 and len(v["predicates"]) == 5
    assert len(v["key_features"]) == 10
    assert v["induced_slot_type"] == "Map[FeatureValue,Colour]"


def test_roundtrip_ast_tokens_ast_exact():
    for blocks in ([B1], [B0, BS], [B0, B0, B0], [BS, B1]):
        ast = CV.ast_from_blocks(blocks)
        tokens = CV.tokens_from_ast(ast)
        assert CV.tokens_are_valid(tokens)
        assert CV.ast_from_tokens(tokens) == ast


def test_canonical_digest_stable():
    ast = CV.ast_from_blocks([B0, BS])
    assert CV.digest(ast) == CV.digest(CV.ast_from_blocks([B0, BS]))
    assert CV.digest(ast) != CV.digest(CV.ast_from_blocks([BS, B0]))


def test_family_and_counts():
    ast = CV.ast_from_blocks([B0, B1, BS])
    assert CV.family(ast) == (0, 2, 1)
    assert CV.block_count(ast) == 3 and CV.slot_count(ast) == 3
    assert CV.stage_count(ast) == 3 * 3 + 3            # P,M,Paint per block + selects
    assert CV.mdl(ast) >= 12                            # slots count as empty tables


def test_family_text_and_split_roles():
    assert CV.family_text((2,)) == "(2,)"
    assert CV.family_text((2, 1)) == "(2,1)"
    assert CV.is_banned_target_family((1,))            # fixed-search control family
    assert CV.is_banned_target_family((0,))            # excluded from targets
    assert CV.is_holdout_family((2,)) and CV.is_holdout_family((2, 1))
    assert not CV.is_holdout_family((1, 1))


def test_holdout_families_remain_decoder_legal():
    for blocks in ([B1], [B1, BS]):                    # (2,) and (2,1)
        ast = CV.ast_from_blocks(blocks)
        ok, _ = CV.validate(ast)
        assert ok
        assert CV.tokens_are_valid(CV.tokens_from_ast(ast))


def test_rejections():
    #  unknown constructor
    ok, code = CV.validate(("Compose", (("Crop", ("x",)),)))
    assert not ok and code == "grammar_invalid"
    #  unknown terminals
    ok, code = CV.validate(CV.ast_from_blocks([("nope", (), "area")]))
    assert not ok and code == "unknown_terminal"
    ok, code = CV.validate(CV.ast_from_blocks([("colour_components", ("nope",), "area")]))
    assert not ok and code == "unknown_terminal"
    #  excessive blocks
    ok, code = CV.validate(CV.ast_from_blocks([B0] * 4))
    assert not ok and code == "block_count_exceeded"
    #  excessive selects
    too_many = ("colour_components", ("all", "all", "all"), "area")
    ok, code = CV.validate(CV.ast_from_blocks([too_many]))
    assert not ok and code == "select_count_exceeded"
    #  non-Compose root and mid-block termination
    with pytest.raises(CV.GrammarViolation):
        CV.blocks_from_ast(("Partition", ("colour_components",)))
    assert not CV.tokens_are_valid([("P", "colour_components"), ("EOS",)])
    #  wrong slot naming
    bad = ("Compose", (("Partition", ("colour_components",)),
                       ("Map", (("Key", ("area",)), ("Lookup", ("?7",)))),
                       ("Paint", ())))
    ok, code = CV.validate(bad)
    assert not ok and code == "slot_invalid"


def test_undeclared_constructor_mutation_negative_control():
    ast = CV.ast_from_blocks([B0])
    stages = list(ast[1])
    stages.insert(1, ("Reindex", ("x",)))              # undeclared constructor
    mutated = ("Compose", tuple(stages))
    ok, code = CV.validate(mutated)
    assert not ok and code == "grammar_invalid"


def test_state_machine_masks_are_sound_and_complete():
    #  random walks under the mask always terminate in valid sequences
    import random
    rng = random.Random(7)
    for _ in range(200):
        state, tokens = CV.GrammarState(), []
        while not state.finished:
            legal = state.legal_tokens()
            assert legal, f"dead end in {state}"
            token = legal[rng.randrange(len(legal))]
            tokens.append(token)
            state = state.advance(token)
        assert CV.tokens_are_valid(tokens)
        ast = CV.ast_from_tokens(tokens)
        ok, code = CV.validate(ast)
        assert ok, code


def test_deterministic_enumeration():
    a = list(itertools.islice(CV.enumerate_asts(max_blocks=1), 50))
    b = list(itertools.islice(CV.enumerate_asts(max_blocks=1), 50))
    assert a == b
    assert sum(1 for _ in CV.enumerate_asts(max_blocks=1)) == 1240   # 4*31*10
    for ast in a:
        ok, code = CV.validate(ast)
        assert ok, code


def test_no_task_conditioned_branches():
    """No public function accepts a task identity; mechanical signature scan."""
    import inspect
    for name, fn in vars(CV).items():
        if callable(fn) and not name.startswith("_") and inspect.isfunction(fn):
            params = set(inspect.signature(fn).parameters)
            assert not params & {"task_id", "task", "family_label", "dev_outcome"}, name
