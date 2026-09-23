"""Static feasibility tests for the frozen Item-2 v1.2 protocol.

No corpus generation, no fitting, no scoring. These tests check that the
frozen law is not logically impossible in the way v1.1 was, and that the
frozen artifacts match what the protocol says.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
for _p in (TTI, HERE):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from cora_tti import constructive_dataset as CD                   # noqa: E402
from cora_tti import constructive_vocabulary as CV                # noqa: E402
from cora_tti import scoped_slot_fitting as SF                    # noqa: E402

MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "constructive_protocol_v1.2_manifest.json")
DOC = os.path.join(HERE, "docs",
                   "CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL_v1.2.md")


def manifest():
    with open(MANIFEST) as handle:
        return json.load(handle)


def test_frozen_artifacts_match_their_recorded_hashes():
    m = manifest()
    doc_sha = hashlib.sha256(open(DOC, "rb").read()).hexdigest()
    assert m["protocol_doc_sha256"] == doc_sha
    sidecar = open(MANIFEST + ".sha256").read().split()[0]
    body = hashlib.sha256(open(MANIFEST, "rb").read()).hexdigest()
    assert sidecar == body


def test_the_registered_fitter_identity_is_the_frozen_one():
    assert manifest()["constructive_fitter_law"]["fitter_identity_16"] \
        == SF.fitter_identity()[:16]


def test_baseline_enumerates_only_single_block_family_one():
    schemas = SF.baseline_single_block_schemas()
    fams = {CV.family_text(CV.family(s)) for s in schemas}
    m = manifest()["baseline_law"]
    assert len(schemas) == m["enumerated_count"] == 200
    assert fams == set(m["enumerated_families"]) == {"(1,)"}


def test_r4_and_r5_no_longer_enumerate_the_same_hypothesis_set():
    """The v1.1 contradiction is structurally gone.

    Every v1.2 train family is multi-block, so no train target lies inside
    the baseline's single-block enumeration. That removes the logical
    coupling; R4 stays behavioural, so it can still reject.
    """
    baseline_families = {CV.family_text(CV.family(s))
                         for s in SF.baseline_single_block_schemas()}
    train = set(manifest()["train_families"])
    assert train.isdisjoint(baseline_families)
    for text in train:
        counts = [int(c) for c in text.strip("()").rstrip(",").split(",")
                  if c.strip()]
        assert len(counts) >= 2, text


def test_no_v12_family_is_mechanically_dead_under_the_scoped_fitter():
    recorded = manifest()["family_feasibility_static_check"]
    for text, expected in recorded.items():
        if text == "note":
            continue
        fam = tuple(int(c) for c in text.strip("()").rstrip(",").split(",")
                    if c.strip())
        schema = CD.sample_target(manifest()["seeds"]["root"], fam)
        assert len(SF.occurrences(schema)) == expected, text
        assert expected >= 1, text


def test_select_free_train_families_are_retained_with_a_recorded_reason():
    m = manifest()
    assert "(0,0)" in m["train_families"]
    assert "(0,0,0)" in m["train_families"]
    assert m["select_free_retained"]["retained"] is True
    assert m["select_free_retained"]["departure_from_instruction"] is True
    assert m["select_free_retained"]["reason"]


def test_banned_and_holdout_families_are_unchanged_from_v1_1():
    m = manifest()
    v = CV.vocab()
    assert tuple(m["banned_target_families"]) == tuple(v["banned_target_families"])
    assert tuple(m["structural_holdout_families"]) == tuple(v["holdout_families"])


def test_train_and_holdout_families_are_disjoint():
    m = manifest()
    assert set(m["train_families"]).isdisjoint(m["structural_holdout_families"])


def test_seeds_cannot_collide_with_v1_1():
    s = manifest()["seeds"]
    for old in s["disjoint_from_v1_1"]:
        for new in (s["train_from"], s["val_from"], s["holdout_from"]):
            assert abs(new - old) >= 1000


def test_slot_allocation_is_deterministic_and_sums_correctly():
    m = manifest()["slots"]
    assert m["train_per_family"] * 5 == m["train"] == 300
    assert m["val_per_family"] * 5 == m["val"] == 60
    assert m["holdout_per_family"] * 2 == m["structural_holdout"] == 90


def test_the_baseline_was_not_weakened():
    m = manifest()["baseline_law"]
    assert m["weakened"] is False
    assert m["budget_s"] == 8.0
    assert m["timeout_distinct_from_exhaustion"] is True
    assert "fitter_identity" in m["records"]


def test_feature_allowlist_is_frozen_with_counts_and_means_only():
    allow = manifest()["model_view_feature_allowlist"]
    assert len(allow) == 18
    assert set(allow.values()) <= {"count", "mean", "bool"}
    assert "min" not in set(allow.values())
    assert "max" not in set(allow.values())


def test_prohibited_inputs_cover_every_label_channel():
    banned = set(manifest()["prohibited_model_inputs"])
    for key in ("task id", "ARC family label", "target AST",
                "target AST digest", "target structural-family label",
                "hidden output", "test output",
                "admission or rejection outcome", "Step-B information"):
        assert key in banned


def test_informative_gate_never_consults_the_hidden_target():
    gate = manifest()["informative_tfg_gate"]
    assert gate["uses_hidden_target"] is False
    assert gate["require"] == "frontier_term_count >= 2"
    assert len(gate["and_any_of"]) == 3
    assert gate["empty_or_constant_never_admitted"] is True


def test_interface_holdout_limitation_is_carried_forward_not_pretended():
    assert "INFEASIBLE" in manifest()["interface_holdout"]


def test_corpus_quality_criteria_are_frozen_before_generation():
    q = manifest()["corpus_quality_criteria"]
    assert q["admitted_train_min"] >= 120
    assert q["structural_families_min"] >= 3
    assert q["no_rank_one_collapse"] is True
    assert q["failure_means_v1_3_amendment_not_relaxation"] is True


def test_the_fit_must_beat_the_frozen_controls():
    m = manifest()
    assert set(m["fit_must_beat_controls"]) == {
        "real associated", "shuffled", "irrelevant", "aggregate only", "none"}
    assert "exact@5" in m["fit_metric"]


def test_claim_ceiling_is_protocol_frozen_only():
    m = manifest()
    assert m["claim_ceiling"] == "V1.2 PROTOCOL FROZEN AND FEASIBLE"
    for forbidden in ("generate the corpus", "train the scorer",
                      "build ConstructiveExtensionCompiler"):
        assert forbidden in m["not_authorized_in_the_freezing_block"]
