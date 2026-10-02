"""Item-2 v1.6: write the frozen manifest and its hash file.

Reads the development report (for the chosen P1 representation, the P0 keys
after the one permitted development action, and the population facts), the
power record (for the caps), and the protocol document; pins every
implementation file, dependency tree, external file, runtime version, the
exclusion set, the training resource and its responses. Run once at the
freeze and again only through a recorded erratum.

    freeze_v16.py <caps.json>
caps.json: {"target_ambiguous_groups", "floor_ambiguous_groups",
            "target_groups", "slot_cap", "wall_clock_s",
            "min_unseen_groups", "alpha_above_chance_unseen"}
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v15_sel as S                             # noqa: E402
from cora_arc2026 import v16_cfr as C                             # noqa: E402

PROTOCOL = "docs/CORA_TTI_CANDIDATE_FAILURE_RESPONSE_v1.6.md"
MANIFEST = os.path.join(HERE, "outputs", "tti", "candidate_failure_response_v16_manifest.json")
DEV_REPORT = os.path.join(HERE, "outputs", "tti", "v16_dev_report.json")
POWER = os.path.join(HERE, "outputs", "tti", "v16_power.json")
IMPLEMENTATION = (
    "cora_arc2026/v16_cfr.py", "cora_arc2026/v15_sel.py", "cora_arc2026/v14_loc.py",
    "cora_arc2026/v13_gen.py", "cora_arc2026/scorer_fit.py", "cora_arc2026/engine_trace.py",
    "cora_arc2026/vendor/tfg_extractor.py", "geocat_arc/object_reasoning/_trace_hook.py",
    "scripts/generate_v16_pairs.py", "scripts/v16_responses.py", "scripts/evaluate_v16_cfr.py",
    "scripts/v16_supp_dependence.py", "scripts/v16_power.py", "scripts/v16_dev_evaluate.py",
    "scripts/v16_build_exclusion.py", "scripts/run_v16_generation.sh",
    "scripts/run_v16_post_generation.sh", "tests/test_v16_cfr.py",
    "tests/test_v16_prospective.py",
    "outputs/tti/v16_exclusion_digests.json", "outputs/tti/v16_dev_report.json",
    "outputs/tti/v16_power.json", "outputs/tti/v15_test_corpus_sha256.txt",
    "outputs/tti/constructive_protocol_v1.3_manifest.json",
    "outputs/tti/v13_calibration/calibration.json",
    "records/ITEM2_V16_DEVELOPMENT_PLAN.md",
)
EXTERNAL = (
    "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti/outputs/tti/constructive_protocol_manifest.json",
    "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti/outputs/tti/constructive_protocol_manifest_hash.txt",
)


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    with open(sys.argv[1]) as handle:
        caps = json.load(handle)
    with open(DEV_REPORT) as handle:
        dev = json.load(handle)
    with open(POWER) as handle:
        power = json.load(handle)
    dropped = dev["P0_development"]["constant_keys_dropped"]
    p0_keys = [k for k in C.P0_KEYS if k not in dropped]
    chosen = dev["P1_selection"]["chosen"]
    training_groups = dev["groups"] - dev["heldout_pairs_rule"]["heldout_groups"]
    man = {
        "protocol": "CORA-TTI Item-2 v1.6 candidate-conditioned failure response (bounded repair)",
        "version": "1.6", "status": "FROZEN_ERRATUM_1_NOT_RUN",
        "protocol_doc": PROTOCOL, "protocol_doc_sha256": sha256(os.path.join(HERE, PROTOCOL)),
        "parent": {"v15_result_commit": "eb5efa5",
                   "v15_classification": "FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION",
                   "v15_protocol_sha256": "e3209c1f0ce3ab9d7c925f546dd9a25111b0b22cb0b8300dfbe53b5fb2e1e42a",
                   "v15_manifest_sha256": "0cc4b900d22c11cce444051e7374af33d4e2261bb75547df9c9f6fe77054a89c"},
        "question": ("on verification-ambiguous candidate pairs, does a candidate-conditioned "
                     "measurement of how each proposed extension changes the reasoner's failure "
                     "state identify the true extension better than the demonstration summary, "
                     "prospectively, on independent-input pairs disjoint from every earlier corpus"),
        "reasoner": "constructive-domain frozen base search K: baseline single-block schemas with the occurrence-scoped fitter",
        "probe": "K + {e}: leave-one-out re-derivation of e on N-1 demonstrations rendered on the held-out demonstration; nothing installed; state hash equal before and after",
        "probe_identity": C.probe_identity(), "fitter_identity": C._sf().fitter_identity(),
        "response_fields": list(C.RESPONSE_FIELDS),
        "P0_rule": "lexicographic over P0_keys in order with signs P0_signs; first differing key decides; no choice otherwise",
        "P0_keys": p0_keys, "P0_signs": [s for k, s in zip(C.P0_KEYS, C.P0_SIGNS) if k in p0_keys],
        "P0_constant_keys_dropped_in_development": dropped,
        "P1_representation": chosen,
        "P1_model": "v1.5 conditional logit (per-token rows over [1, standardized D_RICH, grammar state]) plus shared weights on the scaled response Delta; L2 0.01; Newton to 1e-12",
        "P2": "D + F_S7 through the v1.5 scorer, fitted on the same training resource",
        "arms": ["D", "P0", "P0_SHUFFLED", "P0_SWAPPED", "P0_then_D", "P0_then_D_SHUFFLED",
                 "P0_then_D_SWAPPED", "P1", "P1_SHUFFLED", "P1_SWAPPED", "R", "P2", "F_S7"],
        "gated_arms_in_order": ["P0", "P0_then_D", "P1"],
        "population": "verification-ambiguous test queries: both candidates fit all N demonstrations; decided queries are chosen by verification and never credited to failure conditioning",
        "primary_arm": "P0", "second_gated_arm": "P0_then_D (hybrid headline)", "third_gated_arm": "P1",
        "multiplicity": "three gated arms, first pass wins, each at alpha 0.01; the family-wise alpha for a pass of some arm is at most 0.03 (the arms are strongly dependent, so it is well below that); P0 alone keeps 0.01 exactly; recorded, not corrected (erratum 1)",
        "gates": {"A": "arm above 1/2 on ambiguous queries, exact group sign-flip p < alpha",
                  "B": "arm beats D on ambiguous queries, p < alpha",
                  "C": "arm beats its matched donor-response control, p < alpha",
                  "D": "mean per-query increment over D >= delta_min",
                  "E": "zero leakage", "F": "order-invariant choice", "G": "digest disjointness",
                  "H": "nonnegative observed increment over D on ambiguous queries",
                  "T": "on structurally unseen pairs: >= min_unseen_groups ambiguous groups, positive increment over D, above chance at alpha_above_chance"},
        "classification_ladder": [
            "0 freeze, integrity, leakage, order, overlap or gated-arm convergence failure: MIXED_OR_INCONCLUSIVE (AUDIT_BLOCKED)",
            "1 ambiguous groups < floor: MIXED_OR_INCONCLUSIVE, no statistic computed",
            "2 P0 passes A, B, C, D, H, T: PURE_CFR_SELECTION_GENERALIZES",
            "3 P0_then_D passes A, B, C, D, H, T: PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES (hybrid headline)",
            "4 P1 passes A, B, C, D, H, T: HYBRID_CFR_SELECTION_GENERALIZES",
            "5 the first gated arm passing A, B, C, D, H but not T: that arm's FAMILIAR_PAIRS_ONLY class (does not license the compiler)",
            "6 the first gated arm passing A, B, C at alpha but not D: CFR_INCREMENT_SIGNIFICANT_BELOW_FLOOR (does not license the compiler; the floor is not lowered)",
            "7 ambiguous groups < target: MIXED_OR_INCONCLUSIVE (underpowered negative)",
            "8 every gated arm fails C decisively: CANDIDATE_RESPONSE_NOT_EPISODE_SPECIFIC",
            "9 every gated arm fails B decisively: CANDIDATE_INTERVENTION_NO_INCREMENT_OVER_DEMONSTRATIONS",
            "10 otherwise: MIXED_OR_INCONCLUSIVE"],
        "decisive_failure": "not significant at alpha AND one-sided 95 percent upper bound below delta_min",
        "licenses_on_pass_only": "PURE_CFR_SELECTION_GENERALIZES, PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES or HYBRID_CFR_SELECTION_GENERALIZES license the generic ConstructiveExtensionCompiler block; the headline follows the arm (pure; pure rule with learned fallback, hybrid; hybrid); nothing else is licensed",
        "statistics": {"alpha": 0.01, "delta_min": 0.05,
                       "inference": "exact one-sided sign-flip over integer group sums on ambiguous queries; group-clustered intervals reported",
                       "unit": "half-credit units; a P0 tie is 1"},
        "caps": {"target_ambiguous_groups": caps["target_ambiguous_groups"],
                 "floor_ambiguous_groups": caps["floor_ambiguous_groups"],
                 "test_groups": caps["target_groups"], "slot_cap": caps["slot_cap"],
                 "wall_clock_s": caps["wall_clock_s"]},
        "transfer_gate": {"min_unseen_groups": caps["min_unseen_groups"],
                          "alpha_above_chance": caps["alpha_above_chance_unseen"],
                          "unseen": "token pair held out by the frozen hash rule or absent from the training resource"},
        "heldout_rule": {"prefix": C.HELDOUT_PREFIX, "first_hex": C.HELDOUT_FIRST_HEX},
        "test_law": {"seed_base": 500_000_000, "slot_stride": S.SLOT_STRIDE,
                     "attempt_stride": S.ATTEMPT_STRIDE, "attempts_per_slot": S.ATTEMPTS_PER_SLOT,
                     "replicates_per_target": S.REPLICATES, "families": list(S.FAMILIES),
                     "admission": "v1.5 law unchanged",
                     "novelty": "skip before any engine run if the group or either target digest is excluded or already in the test"},
        "exclusion": {"path": "outputs/tti/v16_exclusion_digests.json",
                      "sha256": sha256(os.path.join(HERE, "outputs/tti/v16_exclusion_digests.json"))},
        "development_resource": {"source": "v1.5 test corpus, 288 groups, development data only",
                                 "groups": dev["groups"], "report": "outputs/tti/v16_dev_report.json"},
        "training_resource": {"groups": training_groups,
                              "rule": "development groups whose token pair is not held out",
                              "hash_list": "outputs/tti/v15_test_corpus_sha256.txt",
                              "hash_list_sha256": sha256(os.path.join(HERE, "outputs/tti/v15_test_corpus_sha256.txt")),
                              "responses": "outputs/tti/v16_dev_responses.json",
                              "responses_sha256": sha256(os.path.join(HERE, "outputs/tti/v16_dev_responses.json"))},
        "power": {"record": "outputs/tti/v16_power.json", "seed": power["seed"], "sims": power["sims"],
                  "discordance": power["discordance"], "table": power["table"],
                  "note": "the rho 0 rows assume independent queries within a group and are an upper bound; rho 0.5 and 1 rows share the disagreement direction within a group (erratum 1)"},
        "stop_rule_note": "the generator stops at test_groups unique groups; ambiguous groups are about 0.646 of groups in development, so test_groups was set so that P(ambiguous < target) is small (erratum 1)",
        "erratum_1": {"record": "records/ITEM2_V16_ERRATUM_01.md",
                      "cause": "pre-run adversarial review: 0 blocking, 5 major, minor findings",
                      "supersedes": {"commit": "4f9c77b",
                                     "manifest_sha256": "724630194b2709e69c00ba213cff83be3bb738a9555c354d388f0c213ea5d148",
                                     "protocol_doc_sha256": "be1b1e54c4cff2dfe0f158979c74096963fa9e887086b8215608ae260a59d25d"},
                      "thresholds_changed": False},
        "environment": {"required_snapshot": {"ARC_META_BUDGET_S": "8", "PYTHONHASHSEED": "0"},
                        "rule": "every ARC_* refused except ARC_META_BUDGET_S=8; PYTHONHASHSEED=0; single-threaded BLAS"},
        "runtime_versions": L.runtime_versions(),
        "implementation_sha256": {rel: sha256(os.path.join(HERE, rel)) for rel in IMPLEMENTATION},
        "dependency_tree_sha256": {n: L.tree_digest(r) for n, r in sorted(L.dependency_roots(HERE).items())},
        "external_file_sha256": {p: sha256(p) for p in EXTERNAL},
        "order_after_freeze": ["one adversarial review", "errata before any prospective data",
                               "run_v16_generation.sh", "run_v16_post_generation.sh",
                               "record the official verdict and the supplementary checks separately"],
    }
    with open(MANIFEST, "w") as handle:
        handle.write(json.dumps(man, indent=1, sort_keys=True) + "\n")
    digest = sha256(MANIFEST)
    with open(MANIFEST + ".sha256", "w") as handle:
        handle.write(f"{digest}  {os.path.basename(MANIFEST)}\n")
    print(json.dumps({"manifest_sha256": digest, "protocol_sha256": man["protocol_doc_sha256"],
                      "P0_keys": p0_keys, "P1_representation": chosen,
                      "training_groups": training_groups}))


if __name__ == "__main__":
    main()
