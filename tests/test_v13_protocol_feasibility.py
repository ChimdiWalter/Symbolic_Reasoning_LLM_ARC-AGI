"""Static feasibility tests for the frozen v1.3 contrastive protocol.

No generation, no fitting, no audit. These check that the frozen law is
mechanically constructible and that the artifacts match what it says.
"""
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
for _p in (TTI, HERE):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from cora_arc2026 import leak_scan_v12 as LEAK                    # noqa: E402
from cora_tti import constructive_dataset as CD                   # noqa: E402
from cora_tti import constructive_vocabulary as CV                # noqa: E402
from cora_tti import scoped_slot_fitting as SF                    # noqa: E402

MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "constructive_protocol_v1.3_manifest.json")
DOC = os.path.join(HERE, "docs",
                   "CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL_v1.3.md")


def manifest():
    with open(MANIFEST) as handle:
        return json.load(handle)


def contrast_targets(seed=31000, family=(0, 0)):
    """The three contrast types, built from the frozen grammar only."""
    v = CV.vocab()
    base = CD.sample_target(seed, family)
    blocks = CV.blocks_from_ast(base)
    out = {}
    alt_p = [p for p in v["partitions"] if p != blocks[0][0]][0]
    out["PARTITION"] = CV.ast_from_blocks(
        [(alt_p, blocks[0][1], blocks[0][2])] + blocks[1:])
    alt_f = [f for f in v["key_features"] if f != blocks[0][2]][0]
    out["FEATURE"] = CV.ast_from_blocks(
        [(blocks[0][0], blocks[0][1], alt_f)] + blocks[1:])
    out["SELECT"] = CV.ast_from_blocks(
        [(blocks[0][0], (v["predicates"][0],), blocks[0][2])] + blocks[1:])
    return base, out


def test_artifacts_match_their_recorded_hashes():
    m = manifest()
    assert m["protocol_doc_sha256"] == hashlib.sha256(
        open(DOC, "rb").read()).hexdigest()
    assert open(MANIFEST + ".sha256").read().split()[0] == hashlib.sha256(
        open(MANIFEST, "rb").read()).hexdigest()


def test_all_three_contrast_types_are_constructible_and_legal():
    base, made = contrast_targets()
    assert set(made) == set(manifest()["group_law"]["contrast_types"])
    for name, ast in made.items():
        ok, code = CV.validate(ast)
        assert ok, f"{name}: {code}"
        assert CV.digest(ast) != CV.digest(base), name
        assert not CV.is_banned_target_family(CV.family(ast)), name


def test_contrast_targets_differ_in_exactly_one_grammar_position():
    base, made = contrast_targets()
    b0 = CV.blocks_from_ast(base)
    for name, ast in made.items():
        b1 = CV.blocks_from_ast(ast)
        assert len(b0) == len(b1), name
        differences = 0
        for x, y in zip(b0, b1):
            differences += sum(1 for a, b in zip(x, y) if a != b)
        assert differences == 1, (name, differences)


def test_the_select_contrast_confound_is_recorded():
    base, made = contrast_targets()
    assert CV.family(made["SELECT"]) != CV.family(base)
    assert CV.family(made["PARTITION"]) == CV.family(base)
    assert CV.family(made["FEATURE"]) == CV.family(base)
    note = manifest()["group_law"]["recorded_confound"]
    assert "SELECT" in note and "family" in note
    assert "SELECT" in manifest()["gates"]["G2_contrast_type_robustness"]


def test_replicates_are_possible_because_the_renderer_takes_a_seed_list():
    import inspect
    params = inspect.signature(CD.render_demonstrations).parameters
    assert "seeds" in params
    assert manifest()["group_law"]["replicates_per_target"] == 4
    assert manifest()["group_law"]["episodes_per_group"] == 8


def test_demo_distance_features_come_from_demonstrations_not_the_target():
    feats = manifest()["d_demo"]["features"]
    assert len(feats) == 6
    forbidden = {"target_digest", "structural_family", "seed", "group_id"}
    assert not (set(feats) & forbidden)
    assert manifest()["d_demo"]["epsilon_demo"] == 0.5


def test_frontier_descriptor_is_target_independent_and_42_wide():
    d = manifest()["d_frontier"]
    assert d["width"] == 42
    for banned in ("target AST", "target family", "task id", "hidden answer"):
        assert banned in d["forbidden_inputs"]


def test_frontier_descriptor_is_computable_from_a_stored_v1_2_graph():
    """The same descriptor already ran in the v1.2 diagnosis."""
    corpus = os.path.join(HERE, "outputs", "tti", "v12_corpus")
    names = [n for n in sorted(os.listdir(corpus)) if n.startswith("slot")]
    for name in names[:40]:
        with open(os.path.join(corpus, name)) as handle:
            d = json.load(handle)
        if d["admitted"] and d.get("episode"):
            assert "full_engine_tfg" in d["episode"]
            assert d["episode"]["full_engine_tfg"].get("nodes")
            return
    raise AssertionError("no stored full-engine graph found")


def test_r4_and_r5_machinery_is_unchanged_and_present():
    m = manifest()
    assert m["fitter_identity_16"] == SF.fitter_identity()[:16]
    assert len(SF.baseline_single_block_schemas()) == 200
    assert m["admission"]["law"] == "unchanged from v1.2"
    assert m["admission"]["no_frontier_based_filter"] is True


def test_the_exact_chance_level_is_arithmetically_correct():
    m = manifest()["audit"]
    replicates = manifest()["group_law"]["replicates_per_target"]
    same = replicates - 1
    other = replicates
    assert abs(m["exact_chance"] - same / (same + other)) < 1e-6


def test_leak_scanner_covers_every_new_contrastive_metadata_field():
    view = {"features": {k: 0 for k in LEAK.FEATURES},
            "input_type": "Grid", "output_type": "Grid"}
    for field, value in (("group_id", "g0007"), ("contrast_type", "PARTITION"),
                         ("replicate_index", 424242),
                         ("differing_position", "block0_feature"),
                         ("pair_digest", "abcdef0123456789")):
        leaked = json.loads(json.dumps(view))
        leaked["output_type"] = str(value)
        found = LEAK.scan(leaked, {field: value})
        assert any(f"leaked:{field}" == f for f in found), (field, found)


def test_sample_size_is_derived_not_inherited_from_v1_2():
    s = manifest()["sample_size"]
    assert s["v1_2_criterion_reused"] is False
    assert s["descriptor_width"] * s["observations_per_feature"] == s["implied_episodes"]
    target = s["schedule_target"]
    assert target["train_groups"] * manifest()["group_law"]["episodes_per_group"] == 480
    assert target["total_groups"] == 84
    assert target["total_episodes"] == 672


def test_sizing_rule_is_a_formula_with_a_cap():
    r = manifest()["sizing_rule"]
    assert r["pilot_group_slots"] == 40
    assert r["cap"] == 1200
    assert r["cap_raised_afterwards"] is False
    assert r["q_re_estimated"] is False
    assert math.ceil(84 / 0.2) <= r["cap"]


def test_seeds_cannot_collide_with_earlier_protocols():
    s = manifest()["seeds"]
    assert s["root"] == 20260924
    assert s["root"] not in s["disjoint_from"].values()
    for base in (s["phase_A_from"], s["groups_from"], s["val_from"],
                 s["holdout_from"]):
        for old in (11000, 12000, 13000, 21000, 22000, 23000):
            assert abs(base - old) >= 1000


def test_calibration_precedes_selection_and_is_not_audit_evidence():
    a = manifest()["calibration_phase_A"]
    assert a["episodes"] == 200
    assert a["published_before_phase_B"] is True
    assert a["recomputed_later"] is False
    assert a["used_as_audit_evidence"] is False


def test_every_gate_is_present_and_not_adjustable():
    g = manifest()["gates"]
    for key in ("G1_primary_identifiability", "G2_contrast_type_robustness",
                "G3_separation", "G4_separation_magnitude", "G5_scale",
                "G6_coverage", "G7_distinct_targets", "G8_splits",
                "G9_leakage", "G10_evidence"):
        assert key in g and g[key]
    assert g["all_required"] is True
    assert g["adjustable_after_result"] is False


def test_claim_ceiling_and_prohibitions():
    m = manifest()
    assert m["claim_ceiling"] == \
        "V1.3 CONTRASTIVE CORPUS PROTOCOL FROZEN AND STATICALLY FEASIBLE"
    for banned in ("generate v1.3", "fit any scorer",
                   "build ConstructiveExtensionCompiler", "touch Step B"):
        assert banned in m["not_authorized_in_the_freezing_block"]
    for cannot in ("constructive reach", "transfer",
                   "structural-family generalization", "any ARC score"):
        assert cannot in m["cannot_establish"]


def test_the_audit_is_nonlearned():
    assert manifest()["audit"]["learned"] is False


def test_v1_2_is_preserved_and_the_earlier_draft_is_not_authoritative():
    s = manifest()["supersedes"]
    assert s["v1_2"]["preserved"] is True
    assert s["earlier_v1_3_draft"]["authoritative"] is False
