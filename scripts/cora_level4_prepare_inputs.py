"""Level-4 Step A prerequisites, all of them behind the provenance firewall.

Four things must exist before the extractor may run, and none of them may be
produced by the extractor itself, because each one would otherwise be a place
where an outcome could influence the design:

    the within-stage holdout      Experience splits E_invent / E_transfer
    the frozen token secret       source_token = HMAC(secret, task_id)
    the sanitized corpus          demonstrations with no task identity
    the machine manifest          the frozen parameters, in machine form

This script also RE-REDACTS the contract. The first redaction hid only the
contract-inactive productions. That is no longer sufficient: the A0 gate
excluded eleven further productions from the baseline, and a mechanism that
could see "these exist but you may not use them" would be reading a hint
about where the baseline is weak. Inactive and inadmissible names are
therefore merged into ONE opaque pool, ordered by a keyed hash so the
ordering carries no information either, and the mechanism learns only how
many names are forbidden.

Nothing here reads a hidden test output. Task identity enters only the
firewall file, which no mechanism input mirrors.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
BLIND = OUT / "level4_mechanism_inputs"
FIREWALL = OUT / "level4_provenance_firewall.json"

#: Frozen before extraction and never re-drawn. The split must be a function
#: of task identity alone, so that no outcome can move a task across it.
HOLDOUT_SALT = "cora-level4-within-stage-holdout-2026-08-22"
E_INVENT_FRACTION = 0.75

#: How many terms per failed fold may be tested for execution. Declared here,
#: before any record exists, so that a truncation cannot be chosen after
#: seeing which folds are expensive. Recorded on every truncated fold.
EXECUTION_TEST_CAP = 3000


def keyed_rank(task_id: str) -> str:
    return hashlib.sha256((HOLDOUT_SALT + task_id).encode()).hexdigest()


def load_secret(firewall: dict) -> str:
    """Stable across re-runs, secret from every mechanism input."""
    secret = firewall.get("source_token_secret")
    if not secret:
        secret = os.urandom(32).hex()
    return secret


def source_token(secret: str, task_id: str) -> str:
    return hmac.new(bytes.fromhex(secret), task_id.encode(),
                    hashlib.sha256).hexdigest()[:16]


def split_experience(task_ids: list) -> tuple:
    """Deterministic, outcome-blind, exact-sized holdout."""
    ordered = sorted(task_ids, key=keyed_rank)
    cut = round(len(ordered) * E_INVENT_FRACTION)
    return sorted(ordered[:cut]), sorted(ordered[cut:])


def type_names(t) -> set:
    """Every type name inside a type term, head and arguments alike."""
    out = {t.name}
    for arg in t.args:
        out |= type_names(arg)
    return out


def grounded_signature(production) -> str:
    """One EXACT grounded signature, as the runtime actually instantiates it."""
    left = " x ".join(str(t) for t in production.arg_types)
    return f"{left} -> {production.result_type}"


def redacted_contract(contract: dict, admitted: list, secret: str) -> tuple:
    """Signature_blind = Signature(K_L4*), exactly.

    The earlier version mapped each admitted production back to its generic
    base rule and published the contract's polymorphic form. That would tell
    the mechanism the baseline has ``ArgMax : Set[A] x FeatureExpr -> A``,
    when it operationally has ``ArgMax@Entity`` and NOT ``ArgMax@Region``:
    a capability claim the baseline does not support, handed to the very
    stage that is supposed to discover what the baseline lacks. So the blind
    contract is generated from the admitted runtime instantiations, and a
    base rule name never appears.

    The type metadata is restricted for the same reason. Publishing the
    contract's whole terminal table would name types belonging to excluded
    capabilities, which says "something you cannot see deals in Lattice".
    Only types E_L4* actually uses are exposed.
    """
    usable = []
    used_types: set = set()
    for name in sorted(admitted):
        production = V.LEVEL4_REGISTRY[name]
        usable.append({"production": name,
                       "signature": grounded_signature(production),
                       "arg_types": [str(t) for t in production.arg_types],
                       "result_type": str(production.result_type)})
        for t in tuple(production.arg_types) + (production.result_type,):
            used_types |= type_names(t)

    # every name the mechanism may not use, base rules included, in ONE
    # opaque pool: an excluded grounding whose base rule stayed visible would
    # be recoverable by subtraction
    admitted_bases = {V.LEVEL4_REGISTRY[n].contract_grades.get(
        "instantiated_from", n) for n in admitted}
    rules = contract["active_productions"] + \
        contract["layer_A_evidence_minimal"]["judgements"] + \
        contract["layer_B_frozen_design"]["rules"] + \
        contract["inactive_unresolved"]

    non_runtime = {"Concept", "Expr_formation"}
    hidden = {rule["rule"] for rule in rules
              if rule["rule"] not in non_runtime
              and rule["rule"] not in admitted_bases}
    hidden |= {n for n in V.LEVEL4_REGISTRY if n not in set(admitted)}

    # ordered by a keyed hash: neither alphabetical nor grouped by the reason
    # a name is hidden, so the pool cannot be partitioned by inspection
    ordered = sorted(hidden,
                     key=lambda n: hmac.new(bytes.fromhex(secret), n.encode(),
                                            hashlib.sha256).hexdigest())
    mapping = {f"forbidden_{i:02d}": n for i, n in enumerate(ordered)}

    terminals = {k: v for k, v in contract["terminals"]["types"].items()
                 if k in used_types}

    blind = {
        "note": ("Redacted view for the Level-4 mechanism. Productions appear "
                 "at the EXACT grounded instantiation the baseline runs, "
                 "never as a generic base rule, so no polymorphic generality "
                 "is implied that the baseline does not operationally "
                 "possess. Every production the mechanism may not use appears "
                 "as an opaque identifier, whether it is contract-inactive or "
                 "was found inadmissible; the mechanism knows how many names "
                 "are forbidden, never which, and cannot tell the two reasons "
                 "apart."),
        "usable_productions": usable,
        "usable_instantiations": sorted(admitted),
        "non_runtime_judgements": sorted(non_runtime),
        "forbidden_production_ids": sorted(mapping),
        "forbidden_count": len(mapping),
        "terminals": terminals,
        "terminal_values": {k: list(v) for k, v in V.TERMINAL_VALUES.items()
                            if k in used_types},
        "induced_types": sorted(t for t in V.INDUCED_TYPES if t in used_types),
        "goal_type": "Grid",
        "polymorphism_policy": {
            "rule": contract["polymorphism_policy"]["rule"]},
    }
    return blind, mapping


def assert_signature_blind(blind: dict, admitted: list) -> None:
    """Signature_blind == Signature(K_L4*), not merely name-set equality.

    Aborts on a missing production, an extra one, a differing argument or
    result type, or a surviving type variable. Name equality alone would let
    exactly the defect this function exists to prevent pass unnoticed.
    """
    published = {row["production"]: row for row in blind["usable_productions"]}
    missing = sorted(set(admitted) - set(published))
    extra = sorted(set(published) - set(admitted))
    if missing or extra:
        raise SystemExit(f"blind contract production mismatch: "
                         f"missing {missing}, extra {extra}")

    for name in sorted(admitted):
        production = V.LEVEL4_REGISTRY[name]
        row = published[name]
        want_args = [str(t) for t in production.arg_types]
        want_result = str(production.result_type)
        if row["arg_types"] != want_args:
            raise SystemExit(f"{name}: argument types {row['arg_types']} != "
                             f"frozen {want_args}")
        if row["result_type"] != want_result:
            raise SystemExit(f"{name}: result type {row['result_type']} != "
                             f"frozen {want_result}")
        for text in want_args + [want_result]:
            for part in re.findall(r"[A-Za-z_]+", text):
                if len(part) == 1 and part.isupper():
                    raise SystemExit(f"{name}: type variable {part} survives "
                                     f"in {text}")

    for row in blind["usable_productions"]:
        if "@" not in row["production"]:
            continue
        base = row["production"].split("@", 1)[0]
        if base in published:
            raise SystemExit(f"generic base rule {base} exposed alongside its "
                             f"grounding {row['production']}")


def write_corpus(challenges: dict, invent: list, secret: str) -> tuple:
    """Demonstrations only: no task id, no test pair, no solution."""
    lines, provenance = [], {}
    for task_id in invent:
        token = source_token(secret, task_id)
        provenance[token] = task_id
        lines.append(json.dumps({
            "source_token": token,
            "demonstrations": [{"input": pair["input"], "output": pair["output"]}
                               for pair in challenges[task_id]["train"]]}))
    # written in token order, so file position leaks no task ordering either
    lines.sort()
    path = BLIND / "invention_corpus.jsonl"
    path.write_text("\n".join(lines) + "\n")
    return path, provenance


def machine_manifest(admitted: list, corpus_path: Path, n_records: int,
                     forbidden_count: int) -> dict:
    """The frozen parameters, in the form the mechanism actually consumes.

    It names the productions the mechanism may use, because those are the
    substrate it runs on, and no others. Counts of what is withheld are safe;
    identities are not, and none appear.
    """
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    blind_pkg = ROOT / "level4_blind_runtime"
    concept_schema = json.loads(
        (OUT / "v21_concept_registry.json").read_text())["concept_0001"]

    return {
        "stage": "Level 4 Step A: failure-frontier extraction",
        "manifest_document_sha256": digest(
            ROOT / "docs" / "CORA_LEVEL4_MANIFEST.md"),
        # the whole bundle, data and executable alike: a manifest that pinned
        # only the JSON would leave the code the mechanism actually runs
        # unpinned, which is where the excluded capabilities would re-enter
        "bundle_sha256": {
            "a01_admissibility": digest(
                OUT / "level4_baseline_admissibility_v2.json"),
            "blind_contract": digest(BLIND / "contract_redacted.json"),
            "concepts_redacted": digest(BLIND / "concepts_redacted.json"),
            "invention_corpus": digest(corpus_path),
            **{f"blind_runtime/{p.name}": digest(p)
               for p in sorted(blind_pkg.glob("*.py"))},
        },
        "knowledge_state": {
            "label": "E_L4*",
            "productions": sorted(admitted),
            "production_count": len(admitted),
            "signatures": {
                n: (f"{' x '.join(str(t) for t in V.LEVEL4_REGISTRY[n].arg_types)}"
                    f" -> {V.LEVEL4_REGISTRY[n].result_type}")
                for n in sorted(admitted)},
            "abstractions": ["concept_0001"],
            "concept_schema_sha256": hashlib.sha256(json.dumps(
                concept_schema["schema"], sort_keys=True).encode()
            ).hexdigest()[:16],
            "forbidden_production_count": forbidden_count},
        "goal_type": "Grid",
        "search": {"max_depth": S.MAX_DEPTH, "per_type_cap": S.PER_TYPE_CAP,
                   "max_candidates": S.MAX_CANDIDATES,
                   "budget_seconds": S.budget_s()},
        "frontier": {
            "population": ("every failed leave-one-out fold of every corpus "
                           "record; a fold fails when induction on the other "
                           "demonstrations does not reproduce the held-out one"),
            "arose": ("terms generated by the goal-directed enumeration for "
                      "this fold, never free enumeration"),
            "executes": ("evaluates to a value on every demonstration input "
                         "of the fold's training subset"),
            "maximal": ("not a proper sub-term of another executing term"),
            "selected": ("among the maximal executing terms, those of greatest "
                         "surface depth; all incomparable maxima are kept and "
                         "ties are never broken by preference"),
            "execution_test_cap": EXECUTION_TEST_CAP},
        "failure_classes": ["budget", "type_connectivity", "routing",
                            "slot_learning", "semantic"],
        "failure_class_order": ("assigned in the order listed: an incomplete "
                                "search is reported as budget rather than as "
                                "an exhausted semantic failure"),
        "cluster_eligibility": {"distinct_source_tokens": 3},
        "corpus": {"file": corpus_path.name, "records": n_records,
                   "carries": ["source_token", "demonstrations"]},
        "prohibited": ("no task identity, no family name, no human summary of "
                       "a failure group, and no forbidden production name is "
                       "available to this stage"),
    }


def main():
    BLIND.mkdir(parents=True, exist_ok=True)
    firewall = json.loads(FIREWALL.read_text()) if FIREWALL.exists() else {}
    secret = load_secret(firewall)

    lockbox = json.loads((OUT.parent / "lockbox" / "manifest.json").read_text())
    experience = sorted(t["task_id"] for t in lockbox["tasks"]
                        if t["split"] == "experience")
    invent, transfer = split_experience(experience)

    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    corpus_path, provenance = write_corpus(challenges, invent, secret)

    contract = json.loads((OUT / "v2_1_semantic_contract_v2.json").read_text())

    # the FROZEN A0.1 artifact, pin-checked. The A0 artifact it supersedes
    # graded provenance against the current runtime's own hash, so admitting
    # from it would reinstate a check that could not fail.
    a01 = OUT / "level4_baseline_admissibility_v2.json"
    pinned = (OUT / "level4_a01_frozen_hash.txt").read_text().strip()
    actual = hashlib.sha256(a01.read_bytes()).hexdigest()
    if actual != pinned:
        raise SystemExit(f"A0.1 artifact {actual[:16]} does not match the "
                         f"frozen pin {pinned[:16]}")
    admissibility = json.loads(a01.read_text())
    admitted = admissibility["K_L4_star"]

    blind, mapping = redacted_contract(contract, admitted, secret)
    assert_signature_blind(blind, admitted)
    (BLIND / "contract_redacted.json").write_text(json.dumps(blind, indent=1))

    manifest = machine_manifest(admitted, corpus_path, len(invent),
                                len(mapping))
    (BLIND / "machine_manifest.json").write_text(json.dumps(manifest, indent=1))

    firewall.update({
        "warning": ("BEHIND THE PROVENANCE FIREWALL. The Level-4 invention "
                    "stage must never read this file. It is opened only by "
                    "the certification stage, after an extension has already "
                    "been proposed."),
        "source_token_secret": secret,
        "holdout_salt": HOLDOUT_SALT,
        "within_stage_holdout": {
            "E_invent": invent, "E_transfer": transfer,
            "sizes": {"E_invent": len(invent), "E_transfer": len(transfer)}},
        "source_token_to_task": provenance,
        "forbidden_name_map": mapping})
    FIREWALL.write_text(json.dumps(firewall, indent=1))

    print(f"Experience {len(experience)} -> E_invent {len(invent)} / "
          f"E_transfer {len(transfer)}")
    print(f"corpus records {len(provenance)} -> {corpus_path.name}")
    print(f"usable productions exposed {len(blind['usable_instantiations'])}, "
          f"forbidden opaque ids {len(mapping)}")
    for path in sorted(BLIND.iterdir()):
        print(f"  {path.name} sha256 "
              f"{hashlib.sha256(path.read_bytes()).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
