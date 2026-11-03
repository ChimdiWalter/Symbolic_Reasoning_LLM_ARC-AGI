"""Train-only executable grammar compression for CORA R25.

This module accepts retained demonstrations and already constructed, closed ASTs.
It cannot open a dataset or receive a query/answer.  A repeated, verified subtree
is admitted only when its typed template compresses at least two distinct tasks.
Every learned rule lowers to the unchanged constructor interpreter primitives.
Rules improve the available search representation, not the primitive semantics.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import time
from collections import Counter, defaultdict


SCHEMA = "CORA_R25_GROWTH_LIBRARY_V1"
DEFAULT_CAPS = {
    "max_records": 64,
    "max_programs_per_record": 2,
    "max_ast_nodes": 16,
    "max_subtrees": 2048,
    "max_rules": 8,
    "min_support_tasks": 2,
    "min_body_operators": 2,
    "min_MDL_gain": 1,
    "max_replays": 4096,
    "CPU_s": 8.0,
}
FORBIDDEN_AST_OPS = {"hole", "call", "eval", "literal", "var", "query"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class GrowthBudget(TimeoutError):
    pass


def _walk(ast, path=()):
    yield path, ast
    for index, child in enumerate(ast["args"]):
        yield from _walk(child, path + (index,))


def _operator_count(ast):
    return sum(node["op"] != "input" for _, node in _walk(ast))


def _replace(ast, path, replacement):
    if not path:
        return copy.deepcopy(replacement)
    result = copy.deepcopy(ast)
    parent = result
    for index in path[:-1]:
        parent = parent["args"][index]
    parent["args"][path[-1]] = copy.deepcopy(replacement)
    return result


def _value_kind(value):
    # bool must precede int: Python considers bool an int subclass.
    if type(value) is bool:
        return "Bool"
    if type(value) is int:
        return "Int"
    if type(value) is str:
        return "Enum"
    if type(value) is float and math.isfinite(value):
        return "Real"
    if value is None:
        return "Null"
    if type(value) is list:
        return ["List", [_value_kind(item) for item in value]]
    if type(value) is dict and all(type(k) is str for k in value):
        # Mapping keys such as palette colors are values, not language syntax.
        return ["Map", sorted(set(canonical(_value_kind(v)) for v in value.values()))]
    raise ValueError("PARAMETER_VALUE_OUTSIDE_FINITE_JSON")


def _valid_train(train):
    if (type(train) is not list or not 1 <= len(train) <= 10
            or any(type(pair) is not dict or set(pair) != {"input", "output"}
                   for pair in train)):
        raise ValueError("RETAINED_DEMONSTRATION_SCHEMA")
    for pair in train:
        for key in ("input", "output"):
            grid = pair[key]
            if (type(grid) is not list or not 1 <= len(grid) <= 30
                    or type(grid[0]) is not list or not 1 <= len(grid[0]) <= 30
                    or any(type(row) is not list or len(row) != len(grid[0])
                           or any(type(value) is not int or not 0 <= value <= 9 for value in row)
                           for row in grid)):
                raise ValueError("RETAINED_GRID_SCHEMA")
    return train


def _closed_ast(ast, max_nodes):
    if type(ast) is not dict or set(ast) != {"op", "type", "args", "params"}:
        raise ValueError("CLOSED_AST_SCHEMA")
    nodes = list(_walk(ast))
    if len(nodes) > max_nodes:
        raise ValueError("AST_NODE_CAP")
    for _, node in nodes:
        if (set(node) != {"op", "type", "args", "params"}
                or type(node["op"]) is not str
                or node["op"] in FORBIDDEN_AST_OPS
                or node["type"] != "Grid"
                or type(node["args"]) is not list
                or type(node["params"]) is not dict
                or any(type(key) is not str for key in node["params"])):
            raise ValueError("CLOSED_TYPED_AST_REQUIRED")
        if node["op"] == "input" and (node["args"] or node["params"]):
            raise ValueError("INPUT_LEAF_REQUIRED")
        for value in node["params"].values():
            _value_kind(value)
    if sum(node["op"] == "input" for _, node in nodes) != 1:
        # R25 constructor uses closed, unary Grid transformations.  Restricting
        # to one Grid hole avoids inventing unsupported multi-input semantics.
        raise ValueError("SINGLE_GRID_INPUT_REQUIRED")
    return ast


def _shape(ast):
    return {"op": ast["op"], "type": ast["type"],
            "params": {key: _value_kind(value)
                       for key, value in sorted(ast["params"].items())},
            "args": [_shape(child) for child in ast["args"]]}


def _parameter_locations(ast):
    for path, node in _walk(ast):
        for key in sorted(node["params"]):
            yield path, key, node["params"][key]


def _at(ast, path):
    for index in path:
        ast = ast["args"][index]
    return ast


def _template(members):
    """Least general structural anti-unifier, generalizing typed params only.

    Operators, Grid edges and parameter names are never generalized.  A slot is
    introduced only where its observed values differ, and equal value vectors
    share a slot.  Thus repeated parameter equality is preserved by construction.
    """
    first = members[0]["subtree"]
    body = copy.deepcopy(first)
    specifications = []
    shared_slots = {}
    for path, key, original in _parameter_locations(first):
        values = [_at(member["subtree"], path)["params"][key] for member in members]
        if all(value == original for value in values):
            continue
        kinds = [_value_kind(value) for value in values]
        if any(kind != kinds[0] for kind in kinds):
            raise ValueError("ANTI_UNIFICATION_TYPE_CHANGE")
        signature = canonical({"kind": kinds[0], "values": values})
        if signature not in shared_slots:
            name = "p" + str(len(specifications))
            shared_slots[signature] = name
            unique = {canonical(value): value for value in values}
            specifications.append({"name": name, "kind": kinds[0],
                                   "observed_values": [unique[k] for k in sorted(unique)],
                                   "locations": []})
        name = shared_slots[signature]
        specification = next(p for p in specifications if p["name"] == name)
        specification["locations"].append({"path": list(path), "key": key})
        _at(body, path)["params"][key] = {"$param": name}
    bindings = []
    for member in members:
        binding = {}
        for specification in specifications:
            location = specification["locations"][0]
            binding[specification["name"]] = copy.deepcopy(
                _at(member["subtree"], location["path"])["params"][location["key"]])
        bindings.append(binding)
    return body, specifications, bindings


def _instantiate(body, specs, binding):
    if set(binding) != {spec["name"] for spec in specs}:
        raise ValueError("RULE_PARAMETER_BINDING_SCHEMA")
    result = copy.deepcopy(body)
    for spec in specs:
        value = binding[spec["name"]]
        if _value_kind(value) != spec["kind"]:
            raise ValueError("RULE_PARAMETER_TYPE_CHANGE")
        for location in spec["locations"]:
            target = _at(result, location["path"])["params"]
            if target[location["key"]] != {"$param": spec["name"]}:
                raise ValueError("RULE_PARAMETER_LOCATION_CHANGED")
            target[location["key"]] = copy.deepcopy(value)
    return result


def _library_payload(library):
    result = copy.deepcopy(library)
    result.pop("library_sha256", None)
    return result


def _overlaps(a, b):
    if a["retained_sha256"] != b["retained_sha256"]:
        return False
    # Distinct fitted aliases from one task do not constitute independent
    # compression evidence; charge at most one parent representation per task.
    if a["verified_parent_program_sha256"] != b["verified_parent_program_sha256"]:
        return True
    x, y = a["subtree_path"], b["subtree_path"]
    return x[:len(y)] == y or y[:len(x)] == x


def empty_library():
    result = {"schema": SCHEMA, "rules": {}, "primitive_semantics_learned": False,
              "query_values_received": False, "held_answers_received": False}
    result["library_sha256"] = digest(_library_payload(result))
    return result


def validate_library(library):
    if (type(library) is not dict or library.get("schema") != SCHEMA
            or type(library.get("rules")) is not dict
            or library.get("library_sha256") != digest(_library_payload(library))):
        raise ValueError("FROZEN_LIBRARY_CHANGED")
    for rid, rule in library["rules"].items():
        payload = copy.deepcopy(rule)
        rule_hash = payload.pop("rule_sha256", None)
        if digest(payload) != rule_hash or rid != "r_" + rule_hash[:20]:
            raise ValueError("FROZEN_RULE_CHANGED")
        if (rule["MDL"]["total_gain"] <= 0 or rule["support_tasks"] < 2
                or rule["body_operators"] < 2):
            raise ValueError("NON_GROWTH_RULE_ADMISSION")
    return library


def _diagnosis(counts, status):
    if counts["exact_verified_programs"] == 0:
        return {"bottleneck": "NO_EXECUTABLE_DISCOVERY_CORPUS",
                "next_train_only_action": "construct_and_exact_verify_demonstration_programs_before_induction"}
    if counts["subtrees_collected"] == 0:
        return {"bottleneck": "SOLVES_HAVE_NO_MULTI_OPERATOR_REUSABLE_STRUCTURE",
                "next_train_only_action": "use_retained_failure_residuals_to_construct_compositions"}
    if counts["admitted_rules"] == 0:
        return {"bottleneck": "NO_REPEATED_COMPRESSIVE_STRUCTURE",
                "next_train_only_action": "increase_diverse_solved_discovery_support_without_relaxing_exactness"}
    return {"bottleneck": "TRANSFER_UTILITY_UNMEASURED",
            "next_train_only_action": "freeze_library_and_compare_fresh_composition_transfer_under_matched_budgets",
            "induction_interrupted": status != "COMPLETE"}


def induce(discovery_records, constructor, caps=None, check=lambda: None):
    """Learn from solved retained demonstrations only; return immutable library.

    ``discovery_records`` has exactly train, program/programs, optional
    opaque_index.  Identical train contents count as one task even under distinct
    indices.  Parent-program replay establishes semantic support for subtrees.
    No query or target is accepted, copied into a library, or used for gating.
    """
    started = time.process_time()
    limits = dict(DEFAULT_CAPS)
    if caps:
        if not set(caps) <= set(limits):
            raise ValueError("UNKNOWN_GROWTH_CAP")
        limits.update(caps)
    for key, value in limits.items():
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("POSITIVE_FINITE_GROWTH_CAP")
        if key != "CPU_s" and type(value) is not int:
            raise ValueError("INTEGER_GROWTH_CAP")
    if type(discovery_records) is not list or len(discovery_records) > limits["max_records"]:
        raise ValueError("DISCOVERY_RECORD_CAP")
    counters = {"input_records": len(discovery_records), "duplicate_task_records": 0,
                "programs_examined": 0, "exact_verified_programs": 0,
                "rejected_programs": 0, "subtrees_collected": 0,
                "structural_groups": 0, "support_rejections": 0,
                "MDL_rejections": 0, "context_replay_failures": 0,
                "retained_replays": 0, "admitted_rules": 0}
    rejection_reasons = defaultdict(int)

    def checked():
        check()
        if time.process_time() - started >= limits["CPU_s"]:
            raise GrowthBudget("GROWTH_CPU_CAP_UNKNOWN")
        if counters["retained_replays"] >= limits["max_replays"]:
            raise GrowthBudget("GROWTH_REPLAY_CAP_UNKNOWN")

    def exact(program, train):
        for pair in train:
            checked()
            counters["retained_replays"] += 1
            value = constructor.execute(program, pair["input"], library={}, check=checked)
            if value != pair["output"]:
                return False
        return True

    groups = defaultdict(list)
    source_provenance = []
    seen_tasks = set()
    status = "COMPLETE"
    admitted = []
    try:
        for record in discovery_records:
            checked()
            if (type(record) is not dict
                    or not set(record) <= {"train", "program", "programs", "opaque_index"}
                    or "train" not in record
                    or ("program" in record) == ("programs" in record)):
                raise ValueError("TRAIN_ONLY_DISCOVERY_RECORD_REQUIRED")
            train = record["train"]
            _valid_train(train)
            task_hash = digest(train)
            if task_hash in seen_tasks:
                counters["duplicate_task_records"] += 1
                continue
            seen_tasks.add(task_hash)
            programs = record.get("programs", [record.get("program")])
            if type(programs) is not list or len(programs) > limits["max_programs_per_record"]:
                raise ValueError("PROGRAMS_PER_DISCOVERY_RECORD_CAP")
            task_verified_hashes = []
            for program in programs:
                checked()
                counters["programs_examined"] += 1
                try:
                    _closed_ast(program, limits["max_ast_nodes"])
                    constructor.validate_ast(program)
                    verified = exact(program, train)
                except GrowthBudget:
                    raise
                except (ValueError, TypeError, KeyError, IndexError) as error:
                    counters["rejected_programs"] += 1
                    rejection_reasons[type(error).__name__ + ":" + str(error)[:96]] += 1
                    continue
                if not verified:
                    counters["rejected_programs"] += 1
                    rejection_reasons["EXACT_RETAINED_REPLAY_FAILED"] += 1
                    continue
                counters["exact_verified_programs"] += 1
                program_hash = digest(program)
                task_verified_hashes.append(program_hash)
                local_seen = set()
                for path, subtree in _walk(program):
                    checked()
                    if _operator_count(subtree) < limits["min_body_operators"]:
                        continue
                    subtree_hash = digest(subtree)
                    if subtree_hash in local_seen:
                        continue
                    local_seen.add(subtree_hash)
                    if counters["subtrees_collected"] >= limits["max_subtrees"]:
                        raise GrowthBudget("GROWTH_SUBTREE_CAP_UNKNOWN")
                    groups[canonical(_shape(subtree))].append({
                        "task_hash": task_hash, "train": train,
                        "program": program, "program_hash": program_hash,
                        "path": path, "subtree": subtree})
                    counters["subtrees_collected"] += 1
            source_provenance.append({"retained_sha256": task_hash,
                                      "verified_program_sha256": sorted(task_verified_hashes)})
        counters["structural_groups"] = len(groups)
        for _, raw_members in sorted(groups.items()):
            checked()
            # A source task contributes once per structural template.  This
            # conservative choice prevents one search's aliases inflating gain.
            task_members = {}
            for member in sorted(raw_members, key=lambda m: (m["task_hash"], m["program_hash"], m["path"])):
                task_members.setdefault(member["task_hash"], member)
            members = list(task_members.values())
            if len(members) < limits["min_support_tasks"]:
                counters["support_rejections"] += 1
                continue
            body, specifications, bindings = _template(members)
            body_operators = _operator_count(body)
            # Declared token-level MDL model: one symbol per primitive, one per
            # macro call, one per parameter binding, plus a definition cost of
            # body primitive symbols and parameter declarations.  Shared input
            # and unchanged literal constants cancel on both sides.  This is
            # explicit grammar compression, not a probability/accuracy metric.
            without = body_operators * len(members)
            definition = body_operators + len(specifications)
            calls = len(members) * (1 + len(specifications))
            gain = without - definition - calls
            if gain < limits["min_MDL_gain"]:
                counters["MDL_rejections"] += 1
                continue
            fresh_context_verified = True
            lineage = []
            for member, binding in zip(members, bindings):
                checked()
                replacement = _instantiate(body, specifications, binding)
                if replacement != member["subtree"]:
                    raise ValueError("ANTI_UNIFICATION_ROUNDTRIP_FAILED")
                lowered = _replace(member["program"], member["path"], replacement)
                if not exact(lowered, member["train"]):
                    fresh_context_verified = False
                    counters["context_replay_failures"] += 1
                    break
                lineage.append({"retained_sha256": member["task_hash"],
                                "verified_parent_program_sha256": member["program_hash"],
                                "subtree_path": list(member["path"]),
                                "subtree_sha256": digest(member["subtree"]),
                                "binding_sha256": digest(binding),
                                "fresh_context_exact": True})
            if not fresh_context_verified:
                continue
            unique_bindings = {canonical(binding): binding for binding in bindings}
            rule = {"version": 1, "body": body, "parameters": specifications,
                    "observed_bindings": [unique_bindings[k] for k in sorted(unique_bindings)],
                    "support_tasks": len(members), "body_operators": body_operators,
                    "MDL": {"model": "primitive_call_parameter_symbol_v1",
                            "without_rule": without, "definition": definition,
                            "calls_and_bindings": calls, "total_gain": gain},
                    "lineage": lineage,
                    "semantic_origin": "train_only_exact_verified_discovery_subtree",
                    "new_primitive_semantics": False}
            rule["rule_sha256"] = digest(rule)
            admitted.append(rule)
    except GrowthBudget as error:
        status = str(error)
    # Partial induction can retain only fully replayed, individually sealed
    # rules.  A budget interruption can never admit the in-progress candidate.
    selected, charged = [], []
    for rule in sorted(admitted, key=lambda r: (-r["MDL"]["total_gain"],
                       -r["support_tasks"], r["rule_sha256"])):
        # Do not add gains from overlapping occurrences.  Conservative reject
        # rather than refit a different template after observing the selection.
        if any(_overlaps(lineage, earlier) for lineage in rule["lineage"] for earlier in charged):
            rejection_reasons["OVERLAPPING_COMPRESSION_EVIDENCE"] += 1
            continue
        selected.append(rule)
        charged.extend(rule["lineage"])
        if len(selected) >= limits["max_rules"]:
            break
    library = empty_library()
    library["rules"] = {"r_" + rule["rule_sha256"][:20]: rule for rule in selected}
    library["source_provenance_sha256"] = digest(sorted(source_provenance,
                                                     key=lambda p: p["retained_sha256"]))
    library["library_sha256"] = digest(_library_payload(library))
    counters["admitted_rules"] = len(selected)
    receipt = {"schema": "CORA_R25_GROWTH_RECEIPT_V1", "status": status,
               "UNKNOWN": status != "COMPLETE", "caps": limits,
               "counts": counters, "rejection_reasons": dict(rejection_reasons),
               "source_provenance": sorted(source_provenance, key=lambda p: p["retained_sha256"]),
               "library_sha256": library["library_sha256"],
               "actual_CPU_s": time.process_time() - started,
               "query_values_received": False, "held_answers_received": False,
               "description_length_is_declared_symbol_model": True,
               "selected_total_disjoint_MDL_gain": sum(rule["MDL"]["total_gain"] for rule in selected),
               "overlapping_occurrences_not_double_counted": True,
               "same_interpreter_replay_is_not_independent_semantic_oracle": True}
    receipt["diagnosis"] = _diagnosis(counters, status)
    receipt["receipt_sha256"] = digest(receipt)
    return {"library": library, "receipt": receipt}


def _external_domain(domains, op, key):
    if not isinstance(domains, dict):
        return []
    selected = domains.get(op, {})
    if not isinstance(selected, dict):
        return []
    values = selected.get(key, [])
    if isinstance(values, range):
        values = list(values)
    return list(values) if isinstance(values, (tuple, list)) else []


def materialize(library, train=None, constructor=None, check=lambda: None,
                max_variants=64, expand_parameter_domains=True):
    """Lower learned templates to closed AST seeds, without receiving a query.

    Observed complete parameter bindings come first.  Then one-parameter
    changes use the constructor's *same public static domains*.  The unchanged
    constructor must exact-verify every materialized seed on retained examples.
    No successful transfer or failed query is fed back to this library.
    """
    validate_library(library)
    if train is not None:
        _valid_train(train)
    if type(max_variants) is not int or max_variants < 0:
        raise ValueError("MATERIALIZATION_VARIANT_CAP")
    domains = getattr(constructor, "OP_PARAMETER_DOMAINS", {}) if constructor else {}
    output, traces, seen = [], [], set()
    invalid_variants = 0
    candidates = {}
    for rid, rule in sorted(library["rules"].items()):
        check()
        bindings = [copy.deepcopy(binding) for binding in rule["observed_bindings"]]
        if expand_parameter_domains and rule["parameters"]:
            for binding in rule["observed_bindings"]:
                for spec in rule["parameters"]:
                    check()
                    values = list(spec["observed_values"])
                    location = spec["locations"][0]
                    owner = _at(rule["body"], location["path"])
                    values += _external_domain(domains, owner["op"], location["key"])
                    for value in values:
                        if _value_kind(value) != spec["kind"]:
                            continue
                        proposed = copy.deepcopy(binding)
                        proposed[spec["name"]] = copy.deepcopy(value)
                        bindings.append(proposed)
        unique = {canonical(binding): binding for binding in bindings}
        observed_keys = [canonical(binding) for binding in rule["observed_bindings"]]
        ordered = observed_keys + [key for key in sorted(unique) if key not in observed_keys]
        candidates[rid] = [(unique[key], key in observed_keys) for key in ordered]
    # Round robin over rules prevents the first rule's parameter domain from
    # consuming the entire shared variant cap.
    depth = 0
    while len(output) < max_variants:
        progressed = False
        for rid, choices in sorted(candidates.items()):
            check()
            if depth >= len(choices) or len(output) >= max_variants:
                continue
            progressed = True
            binding, observed = choices[depth]
            rule = library["rules"][rid]
            ast = _instantiate(rule["body"], rule["parameters"], binding)
            _closed_ast(ast, 64)
            if constructor:
                try:
                    constructor.validate_ast(ast)
                except (ValueError, TypeError, KeyError):
                    # Equality-coupled slots can inhabit different enum domains.
                    # Their candidate values must satisfy the complete unchanged
                    # typed interpreter signature at every occurrence.
                    invalid_variants += 1
                    continue
            key = digest(ast)
            if key in seen:
                continue
            seen.add(key)
            output.append(ast)
            traces.append({"AST_sha256": key, "rule_id": rid,
                           "binding_sha256": digest(binding),
                           "observed_binding": observed,
                           "retained_verification_still_required": True})
        if not progressed:
            break
        depth += 1
    return {"expanded": output, "library_sha256": library["library_sha256"],
            "materialization_receipts": traces, "variant_cap": max_variants,
            "invalid_domain_variants_skipped": invalid_variants,
            "query_values_received": False,
            "retained_demos_sha256": digest(train) if train is not None else None}


def controls(library, discovery_records=None, check=lambda: None):
    """Return explicit no-growth and operation-order shuffle controls.

    Reverse each unary rule's operation stack, carrying its parameters with its
    operator.  This preserves typing and parameter domains and often changes
    semantics.  It can leave commuting operations semantically equivalent, so
    syntactic changes alone are never claimed as a proven semantic derangement.
    A strong static control is constructed separately by static_matched().
    """
    validate_library(library)
    changed = 0
    shuffled = empty_library()
    new_rules = {}
    for _, original in sorted(library["rules"].items()):
        check()
        rule = copy.deepcopy(original)
        stack, cursor = [], rule["body"]
        while cursor["op"] != "input":
            if len(cursor["args"]) != 1:
                raise ValueError("SHUFFLE_REQUIRES_UNARY_TYPED_RULE")
            item = copy.deepcopy(cursor)
            item["args"] = []
            stack.append(item)
            cursor = cursor["args"][0]
        reversed_body = copy.deepcopy(cursor)
        for item in stack:
            item["args"] = [reversed_body]
            reversed_body = item
        if reversed_body != rule["body"]:
            changed += 1
        rule["body"] = reversed_body
        for specification in rule["parameters"]:
            specification["locations"] = []
        by_name = {p["name"]: p for p in rule["parameters"]}
        for path, node in _walk(reversed_body):
            for key, value in node["params"].items():
                if type(value) is dict and set(value) == {"$param"}:
                    by_name[value["$param"]]["locations"].append({"path": list(path), "key": key})
        rule.pop("rule_sha256", None)
        # Controls never claim new admission proof: lineage belongs to the
        # authentic source rule, and the altered rule is only a search seed.
        rule["control"] = {"kind": "unary_operation_order_reverse",
                           "original_rule_sha256": original["rule_sha256"],
                           "independently_admitted": False}
        rule["rule_sha256"] = digest(rule)
        new_rules["r_" + rule["rule_sha256"][:20]] = rule
    shuffled["rules"] = new_rules
    shuffled["control"] = {"kind": "unary_operation_order_reverse",
                           "semantic_change_proven": False,
                           "rules_with_changed_operation_order": changed,
                           "unchanged_control_is_not_causal_evidence": changed == 0}
    shuffled["library_sha256"] = digest(_library_payload(shuffled))
    return {"unlearned": empty_library(), "blind": empty_library(),
            "shuffled": shuffled,
            "receipt": {"kind": "explicit_controls", "rules_changed": changed,
                        "blind_means_no_growth_not_blind_discovery": True,
                        "static_matched_requires_constructor_static_programs": True}}


def static_matched(constructor, train, learned_materialization, caps=None,
                   check=lambda: None):
    """Strong deterministic static seeds under matched slot and AST-cost caps.

    This path does not receive discovery records or library rule bodies.  Only
    the learned arm's number of seed slots and total expanded operator budget
    are public matching metadata.  static_programs must use retained demos and
    the unchanged shared primitive families, with all cost charged by runner.
    """
    _valid_train(train)
    target_costs = [_operator_count(ast) for ast in learned_materialization.get("expanded", [])]
    target_count, target_cost = len(target_costs), sum(target_costs)
    target_histogram = dict(sorted(Counter(target_costs).items()))
    if not hasattr(constructor, "static_programs"):
        return {"expanded": [], "control": "UNAVAILABLE_NO_STATIC_API",
                "target_slots": target_count, "target_operator_cost": target_cost,
                "matched": False}
    # Roots come exclusively from the constructor's public, output-independent
    # static grammar.  Build all needed cost layers, rather than matching a
    # multi-operation learned seed with a cheaper one-operation baseline.
    programs = constructor.static_programs(train, caps=caps, check=check, max_programs=32)
    root_by_family = defaultdict(list)
    root_seen = set()
    for program in programs:
        _closed_ast(program, 64)
        constructor.validate_ast(program)
        if _operator_count(program) != 1 or len(program["args"]) != 1:
            continue
        key = digest(program)
        if key not in root_seen:
            root_seen.add(key)
            root_by_family[program["op"]].append(copy.deepcopy(program))
    roots = []
    # Preserve the public family's original appearance order, with one parameter
    # setting from each family before taking its next parameter setting.
    for depth in range(max((len(group) for group in root_by_family.values()), default=0)):
        for group in root_by_family.values():
            if depth < len(group):
                roots.append(group[depth])
    roots = roots[:32]
    pool, pool_seen = defaultdict(list), set()
    candidates_examined = 0
    candidate_cap = 8192

    def add_sequence(indices):
        nonlocal candidates_examined
        check()
        candidates_examined += 1
        ast = {"op": "input", "type": "Grid", "args": [], "params": {}}
        for index in reversed(indices):
            root = copy.deepcopy(roots[index])
            root["args"] = [ast]
            ast = root
        key = digest(ast)
        if key in pool_seen:
            return
        pool_seen.add(key)
        constructor.validate_ast(ast)
        pool[len(indices)].append(ast)

    for amount, required in target_histogram.items():
        if amount == 0:
            pool[0] = [{"op": "input", "type": "Grid", "args": [], "params": {}}]
            continue
        if amount > 12 or not roots:
            continue
        n = len(roots)
        # Cyclic mixed-family chains are deliberately visited before a plain
        # Cartesian enumeration, which would spend its prefix repeating a single
        # outer family.  These chains are deterministic, with no discovered rule
        # body, retained-output comparison, score, query, or task ID involved.
        for stride in range(1, n + 1):
            for start in range(n):
                if len(pool[amount]) >= required or candidates_examined >= candidate_cap:
                    break
                add_sequence(tuple((start + stride * position) % n for position in range(amount)))
            if len(pool[amount]) >= required or candidates_examined >= candidate_cap:
                break
        if len(pool[amount]) < required and candidates_examined < candidate_cap:
            for indices in itertools.product(range(n), repeat=amount):
                if len(pool[amount]) >= required or candidates_examined >= candidate_cap:
                    break
                add_sequence(indices)
    result, offsets = [], Counter()
    for amount in target_costs:
        if offsets[amount] < len(pool[amount]):
            result.append(pool[amount][offsets[amount]])
            offsets[amount] += 1
    cost = sum(_operator_count(ast) for ast in result)
    actual_histogram = dict(sorted(Counter(_operator_count(ast) for ast in result).items()))
    def literal_bytes(asts):
        return sum(len(canonical(node["params"]).encode()) for ast in asts for _, node in _walk(ast))
    return {"expanded": result, "control": "strong_static_matched_seeds",
            "target_slots": target_count, "target_operator_cost": target_cost,
            "actual_slots": len(result), "actual_operator_cost": cost,
            "target_primitive_cost_histogram": target_histogram,
            "actual_primitive_cost_histogram": actual_histogram,
            "matched": len(result) == target_count and actual_histogram == target_histogram,
            "public_roots": len(roots), "static_candidates_examined": candidates_examined,
            "static_candidate_cap": candidate_cap,
            "learned_parameter_literal_bytes": literal_bytes(learned_materialization.get("expanded", [])),
            "static_parameter_literal_bytes": literal_bytes(result),
            "parameter_literal_costs_matched": False,
            "uses_discovery_programs_for_seed_construction": False,
            "uses_retained_outputs_for_seed_construction": False,
            "query_values_received": False,
            "causal_gain_claim_allowed_only_if_matched_and_scored": True}


def attribute_program(program, materialization):
    """Explain exact learned-subtree reuse without observing any answer.

    This is structural attribution only.  A separate, frozen-prediction scoring
    stage must establish new solves and a matched unlearned comparison must
    establish any increment attributable to growth.
    """
    _closed_ast(program, 64)
    by_hash = {row["AST_sha256"]: row for row in materialization.get("materialization_receipts", [])}
    matches = []
    for path, subtree in _walk(program):
        key = digest(subtree)
        if key in by_hash:
            matches.append({"path": list(path), "AST_sha256": key,
                            "rule_id": by_hash[key]["rule_id"],
                            "operators_outside_match": _operator_count(program) - _operator_count(subtree),
                            "binding_observed_in_discovery": by_hash[key]["observed_binding"]})
    return {"learned_expansion_used": bool(matches),
            "proper_composition_of_learned_expansion": any(row["operators_outside_match"] > 0 for row in matches),
            "matches": matches, "structural_attribution_is_not_accuracy_gain": True,
            "query_values_received": False}
