"""Versioned capability registry (REGISTRY_SCHEMA.json). One registry per arm; each invention episode starts from G0
and may create version G1.<episode>. Entries are appended; a status change appends to status_history.
Never holds evaluator-only knowledge (removed names, references, agreement with a reference).
"""
import hashlib
import json
import os
import time

from cgrow import paths as P

SCHEMA = "cgrow-capability-registry/1"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Registry:
    def __init__(self, registry_id, lineage, g0_sha):
        self.doc = {"schema": SCHEMA, "registry_id": registry_id, "lineage": lineage, "entries": [],
                    "versions": [{"version": "G0", "parent": None, "entries": [], "sha256": g0_sha,
                                  "created_utc": now(), "regression_check": None, "rollback_of": None,
                                  "frozen": True}]}

    def entry(self, ident, prop, chk, tests, provenance, kind, kind_evidence, status, reason, evidence=None,
              scope="task-local"):
        src = prop["code"]
        params = [{"name": p["name"], "type": "Integer", "domain": f"{p['lo']}..{p['hi']}"} for p in prop["params"]]
        e = {"id": ident, "revision": 1, "level": "operation", "summary": prop["fields"].get("SEMANTICS", "")[:300],
             "types": {"type_system": "arcdsl", "inputs": [{"name": "grid", "type": "Grid"}] +
                       [{"name": p["name"], "type": "Integer"} for p in prop["params"]], "output": "Grid"},
             "parameters": params,
             "preconditions": [{"id": "p0", "statement": prop["fields"].get("PRECONDITIONS", "none")[:300],
                                "check": None}],
             "contract": {"semantics": prop["fields"].get("SEMANTICS", "")[:500], "postconditions": ["returns a grid"],
                          "termination": "gridfn step limit 4,000,000 and 0.5 s CPU per call in the isolated worker",
                          "differs_from": [], "checker": "cgrow.sandbox_check+self_tests",
                          "checked": {"nodes": chk.get("nodes"), "self_tests": tests}},
             "implementation": {"substrate": "gridfn2_sandbox", "source": src,
                                "sha256": hashlib.sha256(src.encode()).hexdigest(), "entry_point": "new_op",
                                "resource_limits": {"max_seconds": 0.5, "max_steps": 4000000, "max_memory_mb": 512,
                                                    "max_grid_side": 30}},
             "tests": [{"id": t["id"], "by": "proposer", "passed": t["passed"], "detail": t["detail"]} for t in tests],
             "provenance": provenance | {"producer": "capability_growth_20261027", "created_utc": now()},
             "origin": "INVENTED", "kind": kind, "kind_evidence": kind_evidence, "scope": scope, "status": status,
             "status_history": [{"status": status, "utc": now(), "reason": reason, "grammar_version": None,
                                 "evidence": evidence}],
             "validation": None}
        self.doc["entries"].append(e)
        return e

    def set_status(self, e, status, reason, version=None, evidence=None, scope=None):
        e["status"] = status
        if scope:
            e["scope"] = scope
        e["status_history"].append({"status": status, "utc": now(), "reason": reason, "grammar_version": version,
                                    "evidence": evidence})

    def version(self, name, entry_ids, regression, rollback_of=None, removed=()):
        v = {"version": name, "parent": "G0", "entries": [f"{i}@1" for i in entry_ids], "removed": list(removed),
             "sha256": hashlib.sha256(json.dumps(sorted(entry_ids)).encode()).hexdigest(), "created_utc": now(),
             "regression_check": regression, "rollback_of": rollback_of, "frozen": False}
        self.doc["versions"].append(v)
        return v

    def save(self, path):
        with P.open_write(path) as f:
            json.dump(self.doc, f, indent=1, default=str)


def validate(doc, schema_path=None):
    """Light structural check against REGISTRY_SCHEMA.json (required fields and enums), no external library."""
    schema_path = schema_path or os.path.join(P.HERE, "REGISTRY_SCHEMA.json")
    with open(schema_path, encoding="utf-8") as f:
        sc = json.load(f)
    errs = []
    for k in sc["required"]:
        if k not in doc:
            errs.append(f"missing {k}")
    ent = sc["$defs"]["entry"]
    for e in doc.get("entries", []):
        for k in ent["required"]:
            if k not in e:
                errs.append(f"{e.get('id')}: missing {k}")
        for k in ("origin", "kind", "scope", "status"):
            if e.get(k) not in ent["properties"][k]["enum"]:
                errs.append(f"{e.get('id')}: bad {k} {e.get(k)}")
        extra = set(e) - set(ent["properties"])
        if extra:
            errs.append(f"{e.get('id')}: unknown fields {sorted(extra)}")
    ver = sc["$defs"]["grammar_version"]
    for v in doc.get("versions", []):
        for k in ver["required"]:
            if k not in v:
                errs.append(f"{v.get('version')}: missing {k}")
    return errs
