"""Level 4, Step B: the invention run over every eligible Step-A cluster.

This is the proposal mechanism of docs/CORA_LEVEL4_STEPB_DESIGN.md (pin
28cc8734330345bf...), driven by the frozen item-1 substrate (level4_stepB/, pin
ca695dfa47aff5cf...). It reads ONLY: the pinned Step-A output, the pinned A.1
artifact (verified, not used), the four sanitized mechanism inputs, the
item-1 artifacts, and the blind runtime. It executes ONLY the blind
runtime and the frozen substrate. It never learns a task identity, never
opens E_transfer, and never selects a cluster.

PROTOCOL, uniform for every cluster, no early stop:

  1 ORDER      eligible clusters in the frozen order
               (-N_distinct_sources, -N_records, canonical(cluster_key)).
  2 INTERFACE  (frontier type, goal type) is the ONLY thing a cluster
               contributes to candidate generation. The same enumerator
               (level4_stepB.candidates) runs for every interface.
  3 PROPOSAL   a cluster PROPOSES a candidate through a source when an
               exact program for ALL of that source's sanitized
               demonstrations exists in the blind environment extended by
               the candidate alone:
                 K2  the source's own failed frontier terms (deduplicated
                     by the VALUES they take on the demonstrations) are
                     plugged into the candidate's port; terminal parameters
                     are enumerated in vocabulary order; induced parameters
                     are fitted by the ordinary slot learners; the first
                     exact fit, in canonical order, is the proposal record.
                 K1  the ordinary unchanged search runs with the relaxed
                     learner installed in place of the frozen one (the body
                     is already in the language, so nothing is plugged).
  4 RESOLUTION for every (class representative, proposing source), the
               class being the dedup class of step 6 (a proposal by any
               member is resolved through the least-MDL member): the ordinary
               unchanged search on the full demonstrations, then
               leave-one-out by complete rediscovery, inside the blind
               environment with the candidate installed. A source is
               certified iff a program is found, it uses the candidate
               (K2), and every fold passes.
  5 SELECTION  a candidate is KEPT for a cluster iff >= 2 distinct source
               tokens of that cluster are certified. Ties by frozen MDL of
               the candidate's definition, then lexicographically.
  6 DEDUP      candidates with equal (lane, signature, behaviour
               fingerprint over the frozen witness set, learner) form one
               WITNESS-EQUIVALENCE class; every proposing cluster is kept
               as provenance. Equality on a finite probe set is not a proof
               of global denotational equivalence; the class is exactly
               what the frozen fingerprint says and nothing more.

Labels are fixed at generation (lane K2 -> NEW_SEMANTIC_PRODUCTION, lane
K1 -> SLOT_LEARNER_REPAIR) and never changed here. The K2 label names the
GENERATION LANE only: it does not establish semantic novelty (item 1 showed
generic constructors can reproduce baseline behaviour). Novelty is decided
later by the separation certificate, which is NOT computed here.

OUTPUT DISCIPLINE: counts only to stdout; every record to files; SHA-256
of every file pinned by this runner at completion, before inspection.
Byte-determinism is claimable only for searches that finish inside the
frozen budget; every search records a deadline flag (timing itself is
kept out of every hashed file).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V          # noqa: E402
from level4_blind_runtime import env as E              # noqa: E402
from level4_blind_runtime import search as SEARCH      # noqa: E402
from level4_stepB import candidates as CA              # noqa: E402
from level4_stepB import install as N                  # noqa: E402
from level4_stepB import k1_lattice as L               # noqa: E402
from level4_stepB import k2_inventory as I             # noqa: E402
from level4_stepB import kinds as K                    # noqa: E402
from level4_stepB import witnesses as W                # noqa: E402

OUT = ROOT / "outputs" / "cora_breakthrough"
INPUTS = OUT / "level4_mechanism_inputs"
STEP_A_FILES = ("level4_stepA_frontier_records.jsonl",
                "level4_stepA_fold_summary.json",
                "level4_stepA_clusters.json")
ITEM1_FILES = ("level4_stepB_inventory.json", "level4_stepB_k1_lattice.json",
               "level4_stepB_witnesses.json")

_spec = importlib.util.spec_from_file_location(
    "stepA_runner", ROOT / "scripts" / "cora_level4_stepA_extract.py")
STEP_A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(STEP_A)

#: The frozen registry, captured before anything is installed.
FROZEN_BASE = dict(V.REGISTRY)



def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


# --------------------------------------------------------------------------
# pins
# --------------------------------------------------------------------------

def verify_pins(frozen_inputs: bool) -> dict:
    """Every pinned input must match before a byte of it is used."""
    checks = {}
    drift = []

    def pin(name, path, pinned):
        got = sha(path)
        checks[name] = got[:len(pinned)] == pinned
        if not checks[name]:
            drift.append(name)

    if frozen_inputs:
        lines = (OUT / "level4_stepA_output_hash.txt").read_text().split("\n")
        for line in lines[1:]:
            if line.strip():
                name, digest = line.split()
                pin(name, OUT / name, digest)
        digest = hashlib.sha256()
        for name in STEP_A_FILES:
            digest.update((OUT / name).read_bytes())
        checks["stepA_output_hash"] = digest.hexdigest() == lines[0].strip()
        if not checks["stepA_output_hash"]:
            drift.append("stepA_output_hash")
        pin("level4_stepA1_analysis.json", OUT / "level4_stepA1_analysis.json",
            (OUT / "level4_stepA1_hash.txt").read_text().split()[0])
    pin("design", ROOT / "docs" / "CORA_LEVEL4_STEPB_DESIGN.md",
        (OUT / "level4_stepB_design_hash.txt").read_text().split()[0])
    pin("item1_freeze", OUT / "level4_stepB_item1_freeze.json",
        (OUT / "level4_stepB_item1_hash.txt").read_text().split()[0])
    freeze = json.loads((OUT / "level4_stepB_item1_freeze.json").read_text())
    for name in ITEM1_FILES:
        pin(name, OUT / name, freeze["artifacts"][name])
    for name, digest in freeze["executables"].items():
        candidates = [ROOT / "level4_stepB" / name, ROOT / "scripts" / name,
                      ROOT / "tests" / name]
        path = next(p for p in candidates if p.exists())
        pin(f"item1:{name}", path, digest)
    manifest = json.loads((INPUTS / "machine_manifest.json").read_text())
    bundle = STEP_A.verify_inputs(manifest, INPUTS / "invention_corpus.jsonl")
    checks.update({f"bundle:{k}": v for k, v in bundle["checks"].items()})
    drift.extend(f"bundle:{d}" for d in bundle["drift"])
    return {"checks": checks, "drift": drift, "manifest": manifest}


def substrate_is_frozen() -> dict:
    """The substrate that will RUN must regenerate the pinned artifacts."""
    inventory = json.dumps(I.inventory_record(), indent=1, sort_keys=True,
                           default=str)
    lattice = json.dumps(L.lattice_record(), indent=1, sort_keys=True)
    witness = json.dumps(W.witness_set(I.closure(), I.resolver()),
                         indent=1, sort_keys=True, default=str)
    out = {}
    for name, text in zip(ITEM1_FILES, (inventory, lattice, witness)):
        out[name] = hashlib.sha256(text.encode()).hexdigest() == sha(OUT / name)
    return out


# --------------------------------------------------------------------------
# clusters
# --------------------------------------------------------------------------

def cluster_key(row: dict) -> str:
    return canonical({"frontier_type": row["frontier_type"],
                      "goal_type": row["goal_type"],
                      "goal_delta_signature": row["goal_delta_signature"],
                      "failure_class": row["failure_class"]})


def ordered_clusters(clusters: dict) -> list:
    eligible = [c for c in clusters["clusters"] if c["eligible"]]
    eligible.sort(key=lambda c: (-c["distinct_source_tokens"], -c["records"],
                                 cluster_key(c)))
    out = []
    for index, c in enumerate(eligible, start=1):
        out.append({"cluster_id": f"C{index:03d}", "key": cluster_key(c),
                    "interface": [c["frontier_type"], c["goal_type"]],
                    "distinct_source_tokens": c["distinct_source_tokens"],
                    "records": c["records"]})
    return out


def group_records(records_path: Path, clusters: list) -> dict:
    """cluster_id -> source_token -> sorted distinct frontier ASTs (json)."""
    by_key = {c["key"]: c["cluster_id"] for c in clusters}
    out = {c["cluster_id"]: {} for c in clusters}
    with records_path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            cid = by_key.get(cluster_key(row))
            if cid is None:
                continue
            out[cid].setdefault(row["source_token"], set()).add(
                canonical(row["frontier_ast"]))
    return {cid: {tok: sorted(asts) for tok, asts in sorted(src.items())}
            for cid, src in out.items()}


# --------------------------------------------------------------------------
# workers
# --------------------------------------------------------------------------

_STATE: dict = {}


def _budget() -> float:
    return SEARCH.budget_s()


def _deadline_hit(seconds: float) -> bool:
    return seconds >= _budget() - 0.01


def _init_worker(manifest, corpus, interfaces):
    base = STEP_A.build_env(manifest)        # BEFORE anything is installed
    types, instances = I.build()
    context = N.installed(instances)
    context.__enter__()                       # never exited in a worker
    _STATE["installed"] = context             # keep it alive: a collected
    #                                           context manager would run its
    #                                           finally-block and RESTORE
    _STATE["base"] = E.LanguageEnv(base=FROZEN_BASE, concepts=dict(base.concepts),
                                   label=base.label)
    _STATE["corpus"] = corpus
    _STATE["candidates"] = {}
    for a, b in interfaces:
        cands, _ = CA.candidates_for(V.T(*CA._split(a)), V.T(*CA._split(b)),
                                     instances)
        for c in cands:
            _STATE["candidates"][c.candidate_id] = c
    _STATE["learners"] = {lid: learner for lid, _, learner in L.lattice()}
    _STATE["frozen_learner_key"] = CA._learner_type()


def _pairs(token: str) -> list:
    return [(np.array(d["input"]), np.array(d["output"]))
            for d in _STATE["corpus"][token]]


def _env_with(candidate: CA.Candidate) -> E.LanguageEnv:
    base = _STATE["base"]
    if candidate.lane == "K2":
        return E.LanguageEnv(base=base.base,
                             concepts={**base.concepts,
                                       candidate.candidate_id: candidate.concept()},
                             label=f"{base.label}+{candidate.candidate_id}")
    return base


class _learner_installed:
    """K1: the relaxed learner replaces the frozen one for the duration."""

    def __init__(self, learner_id):
        self.learner_id = learner_id

    def __enter__(self):
        key = _STATE["frozen_learner_key"]
        self.saved = SEARCH.SLOT_LEARNERS[key]
        if self.learner_id:
            SEARCH.SLOT_LEARNERS[key] = _STATE["learners"][self.learner_id]
        return self

    def __exit__(self, *exc):
        SEARCH.SLOT_LEARNERS[_STATE["frozen_learner_key"]] = self.saved
        return False


def _value_classes(asts: list, pairs: list, env) -> list:
    """Distinct values the failed frontier terms take on the demonstration
    inputs; one representative term per class, canonical order."""
    classes = {}
    for text in asts:
        ast = V.from_json(json.loads(text))
        core = E.expand(ast, env)
        if core is None:
            continue
        values = []
        for grid_in, _ in pairs:
            value = V._eval(core, V.Ctx(grid_in))
            if value is None:
                break
            values.append(K.as_canonical(value))
        else:
            key = canonical(values)
            if key not in classes or text < classes[key][0]:
                classes[key] = (text, ast)
    return [classes[k] for k in sorted(classes)]


def _param_options(candidate: CA.Candidate) -> list:
    options = []
    for slot in CA.C.introduced_slots(candidate.schema):
        if slot == candidate.port_slot:
            options.append(None)
            continue
        t = candidate.slot_types[slot]
        if str(t) in V.TERMINAL_VALUES:
            options.append(list(V.TERMINAL_VALUES[str(t)]))
        else:
            options.append([f"?{t}"])
    return options


def propose_k2(unit: dict) -> dict:
    """One (cluster, source): plug every value class into every candidate."""
    cid, token, asts, cand_ids = (unit["cluster_id"], unit["source_token"],
                                  unit["asts"], unit["candidate_ids"])
    pairs = _pairs(token)
    base = _STATE["base"]
    classes = _value_classes(asts, pairs, base)
    hits, attempts = [], 0
    for cand_id in cand_ids:
        candidate = _STATE["candidates"][cand_id]
        env = _env_with(candidate)
        options = _param_options(candidate)
        memo: dict = {}
        found = None
        for class_index, (text, ast) in enumerate(classes):
            for combo in CA._product([[ast] if o is None else o for o in options]):
                attempts += 1
                surface = (cand_id, tuple(combo))
                fitted, evidence = SEARCH.fit_slots(surface, pairs, memo, env)
                if fitted is None:
                    continue
                if SEARCH.observational_signature(fitted, pairs, env) is None:
                    continue
                found = {"candidate_id": cand_id, "cluster_id": cid,
                         "source_token": token, "lane": "K2",
                         "value_class": class_index,
                         "plugged_term": json.loads(text),
                         "program": E.to_json(fitted, env),
                         "slot_evidence": evidence}
                break
            if found:
                break
        if found:
            hits.append(found)
    return {"cluster_id": cid, "source_token": token, "lane": "K2",
            "value_classes": len(classes), "terms": len(asts),
            "attempts": attempts, "hits": hits}


def _search_record(pairs, env, learner_id=""):
    with _learner_installed(learner_id):
        results, stats = SEARCH.search(pairs, env=env)
    return results, {"found": bool(results),
                     "program": E.to_json(results[0][0], env) if results else None,
                     "deadline_hit": _deadline_hit(stats.seconds),
                     "typed_candidates": stats.typed}


def loo_with_stats(pairs, env, learner_id="") -> tuple:
    """The frozen LOO-by-rediscovery loop, with per-fold timing recorded
    (the gate script checks its verdicts equal the frozen function's)."""
    if len(pairs) < 2:
        return 0, 0, []
    passed, folds = 0, []
    for held in range(len(pairs)):
        subset = [p for i, p in enumerate(pairs) if i != held]
        with _learner_installed(learner_id):
            results, stats = SEARCH.search(subset, env=env)
        ok = False
        if results:
            grid_in, grid_out = pairs[held]
            predicted = E.evaluate(results[0][0], grid_in, env)
            ok = predicted is not None and np.array_equal(predicted, grid_out)
        passed += ok
        folds.append({"passed": ok, "deadline_hit": _deadline_hit(stats.seconds)})
    return passed, len(pairs), folds


def propose_k1(unit: dict) -> dict:
    """One (learner, source): the ordinary search with the relaxed learner."""
    token, learner_id = unit["source_token"], unit["learner_id"]
    pairs = _pairs(token)
    _, row = _search_record(pairs, _STATE["base"], learner_id)
    row.update({"source_token": token, "learner_id": learner_id, "lane": "K1"})
    return row


def resolve(unit: dict) -> dict:
    """One (candidate, source): search + LOO with the candidate installed."""
    cand_id, token = unit["candidate_id"], unit["source_token"]
    candidate = _STATE["candidates"][cand_id]
    pairs = _pairs(token)
    env = _env_with(candidate)
    results, row = _search_record(pairs, env, candidate.learner_id)
    uses = (bool(results) and (candidate.lane == "K1"
                               or E.uses_concept(results[0][0], env, cand_id)))
    passed, total, folds = loo_with_stats(pairs, env, candidate.learner_id)
    row.update({"candidate_id": cand_id, "source_token": token,
                "lane": candidate.lane, "uses_candidate": uses,
                "loo_passed": passed, "loo_folds": total, "folds": folds,
                "certified": bool(results) and uses and passed == total,
                "any_deadline_hit": row["deadline_hit"]
                or any(f["deadline_hit"] for f in folds)})
    return row


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------

def _run(pool, fn, units, label, started):
    out = []
    if pool is None:
        for done, unit in enumerate(units, start=1):
            out.append(fn(unit))
            _progress(label, done, len(units), started)
    else:
        for done, result in enumerate(
                pool.imap_unordered(fn, units, chunksize=1), start=1):
            out.append(result)
            _progress(label, done, len(units), started)
    return out


def _progress(label, done, total, started):
    if done % 25 and done != total:
        return
    print(f"  {label:12} {done}/{total}  {round(time.monotonic() - started)}s")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", default=str(OUT / STEP_A_FILES[0]))
    parser.add_argument("--clusters", default=str(OUT / STEP_A_FILES[2]))
    parser.add_argument("--corpus", default=str(INPUTS / "invention_corpus.jsonl"))
    parser.add_argument("--outdir", default=str(OUT))
    parser.add_argument("--tag", default="level4_stepB")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--require-manifest", action="store_true")
    args = parser.parse_args()

    frozen_inputs = (Path(args.records).resolve() == (OUT / STEP_A_FILES[0]).resolve()
                     and Path(args.clusters).resolve() == (OUT / STEP_A_FILES[2]).resolve()
                     and Path(args.corpus).resolve() == (INPUTS / "invention_corpus.jsonl").resolve())
    pins = verify_pins(frozen_inputs)
    if pins["drift"]:
        print(f"ABORT: pinned input drift in {pins['drift']}")
        return 1
    substrate = substrate_is_frozen()
    if not all(substrate.values()):
        print(f"ABORT: the substrate does not regenerate its pinned artifacts {substrate}")
        return 1
    manifest_hash = None
    if args.require_manifest:
        manifest_path = OUT / "level4_stepB_run_manifest.json"
        pinned = (OUT / "level4_stepB_run_manifest_hash.txt").read_text().split()[0]
        manifest_hash = sha(manifest_path)
        if manifest_hash != pinned:
            print("ABORT: run manifest drift")
            return 1
        cited = json.loads(manifest_path.read_text())["stepB_executables"]
        own = sha(Path(__file__).resolve())
        if cited.get("scripts/cora_level4_stepB_run.py") != own:
            print("ABORT: this runner is not the one the manifest pins")
            return 1
    manifest = pins["manifest"]

    clusters = ordered_clusters(json.loads(Path(args.clusters).read_text()))
    grouped = group_records(Path(args.records), clusters)
    corpus = {}
    for line in Path(args.corpus).read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            corpus[row["source_token"]] = row["demonstrations"]
    interfaces = sorted({tuple(c["interface"]) for c in clusters})

    print(f"eligible clusters         {len(clusters)}")
    print(f"interfaces                {len(interfaces)}")
    print(f"inputs are the frozen ones {frozen_inputs}")
    print(f"workers                   {args.workers}")
    sys.stdout.flush()
    started = time.monotonic()

    # -- candidates per interface, fingerprinted over the frozen witnesses --
    types, instances = I.build()
    resolve_types = I.resolver()
    witnesses = W.witness_values(types, resolve_types)
    by_interface, records, reports = {}, [], {}
    with N.installed(instances):
        for a, b in interfaces:
            cands, report = CA.candidates_for(V.T(*CA._split(a)),
                                              V.T(*CA._split(b)), instances)
            reports[f"{a} -> {b}"] = report
            by_interface[(a, b)] = [c.candidate_id for c in cands]
            for c in cands:
                records.append(CA.record(c, CA.fingerprint(c, witnesses)))
    by_id = {r["candidate_id"]: r for r in records}

    # -- witness-equivalence classes (design: dedup BEFORE certification) --
    #    the representative is the least-MDL member, then lexicographic
    classes = {}
    for r in records:
        key = (r["lane"], r["signature"], r["behaviour_fingerprint"],
               r["learner"] or "")
        classes.setdefault(key, []).append(r["candidate_id"])
    rep_of, class_of = {}, {}
    for key, members in classes.items():
        members.sort(key=lambda i: (by_id[i]["mdl"], i))
        class_id = "E-" + hashlib.sha256(canonical(key).encode()).hexdigest()[:16]
        for m in members:
            rep_of[m] = members[0]
            class_of[m] = class_id
    print(f"candidates                {len(records)}  "
          f"K2 {sum(r['lane'] == 'K2' for r in records)}  "
          f"K1 {sum(r['lane'] == 'K1' for r in records)}")
    sys.stdout.flush()

    # -- units ---------------------------------------------------------------
    k2_units, k1_units = [], {}
    for c in clusters:
        cand_ids = by_interface[tuple(c["interface"])]
        k2_ids = [i for i in cand_ids if by_id[i]["lane"] == "K2"]
        k1_learners = sorted({by_id[i]["learner"] for i in cand_ids
                              if by_id[i]["lane"] == "K1"})
        for token, asts in grouped[c["cluster_id"]].items():
            if k2_ids:
                k2_units.append({"cluster_id": c["cluster_id"],
                                 "source_token": token, "asts": asts,
                                 "candidate_ids": k2_ids})
            for lid in k1_learners:
                k1_units[(lid, token)] = {"learner_id": lid, "source_token": token}
    k1_units = [k1_units[k] for k in sorted(k1_units)]

    pool = None
    if args.workers > 1:
        pool = mp.get_context("fork").Pool(
            args.workers, initializer=_init_worker,
            initargs=(manifest, corpus, interfaces))
    else:
        _init_worker(manifest, corpus, interfaces)

    # -- proposal ------------------------------------------------------------
    k2_results = _run(pool, propose_k2, k2_units, "propose K2", started)
    k2_results.sort(key=lambda r: (r["cluster_id"], r["source_token"]))
    k1_results = _run(pool, propose_k1, k1_units, "propose K1", started)
    k1_results.sort(key=lambda r: (r["learner_id"], r["source_token"]))

    proposals = []
    for r in k2_results:
        proposals.extend(r["hits"])
    k1_found = {(r["learner_id"], r["source_token"]) for r in k1_results if r["found"]}
    for c in clusters:
        cand_ids = by_interface[tuple(c["interface"])]
        for cand_id in cand_ids:
            rec = by_id[cand_id]
            if rec["lane"] != "K1":
                continue
            for token in grouped[c["cluster_id"]]:
                if (rec["learner"], token) in k1_found:
                    proposals.append({"candidate_id": cand_id,
                                      "cluster_id": c["cluster_id"],
                                      "source_token": token, "lane": "K1"})
    proposals.sort(key=lambda p: (p["cluster_id"], p["candidate_id"],
                                  p["source_token"]))
    print(f"proposals                 {len(proposals)}  "
          f"K2 {sum(p['lane'] == 'K2' for p in proposals)}  "
          f"K1 {sum(p['lane'] == 'K1' for p in proposals)}")
    sys.stdout.flush()

    # -- resolution, per (class representative, source) ---------------------
    #    a proposal by any member of a class is resolved through the class's
    #    representative (equal fingerprint on the frozen witness set). EVERY
    #    representative of EVERY proposing source is resolved: no cap, no
    #    early stop; the work is only parallelised
    by_source = {}
    for p in proposals:
        by_source.setdefault(p["source_token"], set()).add(rep_of[p["candidate_id"]])
    res_units = []
    for token in sorted(by_source):
        for rep in sorted(by_source[token], key=lambda i: (by_id[i]["mdl"], i)):
            res_units.append({"candidate_id": rep, "source_token": token})
    resolutions = _run(pool, resolve, res_units, "resolve", started)
    resolutions.sort(key=lambda r: (r["candidate_id"], r["source_token"]))
    if pool is not None:
        pool.close()
        pool.join()
    for r in resolutions:
        r["class_id"] = class_of[r["candidate_id"]]
    certified = {(r["candidate_id"], r["source_token"])
                 for r in resolutions if r["certified"]}

    # -- selection per (candidate, cluster) ----------------------------------
    per_pair = {}
    for p in proposals:
        entry = per_pair.setdefault((p["candidate_id"], p["cluster_id"]),
                                    {"proposing_sources": set(),
                                     "certified_sources": set()})
        entry["proposing_sources"].add(p["source_token"])
        rep = rep_of[p["candidate_id"]]
        if (rep, p["source_token"]) in certified:
            entry["certified_sources"].add(p["source_token"])
    selection = []
    for (cand_id, cid), entry in sorted(per_pair.items()):
        selection.append({"candidate_id": cand_id, "cluster_id": cid,
                          "class_id": class_of[cand_id],
                          "resolved_through": rep_of[cand_id],
                          "lane": by_id[cand_id]["lane"],
                          "label": by_id[cand_id]["label"],
                          "proposing_sources": sorted(entry["proposing_sources"]),
                          "certified_sources": sorted(entry["certified_sources"]),
                          "kept": len(entry["certified_sources"]) >= 2})

    # -- witness-equivalence class records ----------------------------------
    merged = []
    for key, members in sorted(classes.items()):
        proposed_from = sorted({s["cluster_id"] for s in selection
                                if s["candidate_id"] in members})
        kept_for = sorted({s["cluster_id"] for s in selection
                           if s["candidate_id"] in members and s["kept"]})
        tokens = set()
        for s in selection:
            if s["candidate_id"] in members:
                tokens |= set(s["proposing_sources"])
        merged.append({"class_id": "E-" + hashlib.sha256(
                           canonical(key).encode()).hexdigest()[:16],
                       "representative": members[0], "members": members,
                       "lane": key[0], "label": by_id[members[0]]["label"],
                       "signature": key[1], "behaviour_fingerprint": key[2],
                       "proposed_from": proposed_from, "kept_for": kept_for,
                       "independent_source_tokens": len(tokens)})
    merged.sort(key=lambda m: (-len(m["kept_for"]), -len(m["proposed_from"]),
                               by_id[m["representative"]]["mdl"], m["class_id"]))

    # -- summary -------------------------------------------------------------
    proposing_clusters = {s["cluster_id"] for s in selection}
    kept_clusters = {s["cluster_id"] for s in selection if s["kept"]}
    #  K2-lane kept candidates: "NEW_SEMANTIC_PRODUCTION" is the generation
    #  lane's label; semantic novelty is decided later by the separation
    #  certificate, never here
    kept_new = {s["cluster_id"] for s in selection if s["kept"] and s["lane"] == "K2"}
    summary = {
        "stage": "Level 4 Step B: invention run",
        "inputs_are_frozen": frozen_inputs,
        "run_manifest_sha256": manifest_hash,
        "pins_verified": pins["checks"],
        "substrate_regenerates_pinned_artifacts": substrate,
        "cluster_order": clusters,
        "interfaces": [f"{a} -> {b}" for a, b in interfaces],
        "candidate_generation": reports,
        "counts": {
            "eligible_clusters": len(clusters),
            "candidates": len(records),
            "candidates_K2": sum(r["lane"] == "K2" for r in records),
            "candidates_K1": sum(r["lane"] == "K1" for r in records),
            "witness_equivalence_classes": len(merged),
            "k2_proposal_units": len(k2_units),
            "k2_attempts": sum(r["attempts"] for r in k2_results),
            "k1_search_units": len(k1_units),
            "proposals": len(proposals),
            "resolution_units": len(res_units),
            "certified_pairs": len(certified),
            "clusters_proposing": len(proposing_clusters),
            "clusters_with_kept_candidate": len(kept_clusters),
            "clusters_with_kept_K2_lane_candidate": len(kept_new),
            "kept_candidate_cluster_pairs": sum(s["kept"] for s in selection),
            "searches_hitting_deadline": sum(
                r["any_deadline_hit"] for r in resolutions)
            + sum(r["deadline_hit"] for r in k1_results),
        },
        "rates": {
            "proposal_rate": len(proposing_clusters) / max(1, len(clusters)),
            "repair_share_of_proposals": (
                sum(p["lane"] == "K1" for p in proposals) / max(1, len(proposals))),
            "semantic_production_share_of_proposals": (
                sum(p["lane"] == "K2" for p in proposals) / max(1, len(proposals))),
            "certification_rate": len(kept_clusters) / max(1, len(clusters)),
            "convergence": [{"class_id": m["class_id"], "clusters": len(m["kept_for"])}
                            for m in merged if len(m["kept_for"]) >= 2],
            "divergence_distinct_kept_classes": len(
                {m["class_id"] for m in merged if m["kept_for"]}),
        },
    }
    timing = {"seconds": round(time.monotonic() - started, 1),
              "workers": args.workers,
              "note": ("timing is kept out of every hashed output so that "
                       "byte-determinism can be tested; this file is not "
                       "part of the output hash")}

    outdir = Path(args.outdir)
    files = {
        f"{args.tag}_candidates.json": canonical(
            {"candidates": records, "classes": merged}),
        f"{args.tag}_k2_proposal_units.jsonl": "".join(
            canonical({k: v for k, v in r.items() if k != "hits"}) + "\n"
            for r in k2_results),
        f"{args.tag}_k1_searches.jsonl": "".join(
            canonical(r) + "\n" for r in k1_results),
        f"{args.tag}_proposals.jsonl": "".join(
            canonical(p) + "\n" for p in proposals),
        f"{args.tag}_resolution.jsonl": "".join(
            canonical(r) + "\n" for r in resolutions),
        f"{args.tag}_selection.json": canonical({"selection": selection}),
        f"{args.tag}_summary.json": canonical(summary),
    }
    for name, text in files.items():
        (outdir / name).write_text(text)
    (outdir / f"{args.tag}_timing.json").write_text(canonical(timing))
    digest = hashlib.sha256()
    lines = []
    for name in files:
        digest.update((outdir / name).read_bytes())
        lines.append(f"{name} {sha(outdir / name)}")
    output_hash = digest.hexdigest()
    (outdir / f"{args.tag}_output_hash.txt").write_text(
        output_hash + "\n" + "\n".join(lines) + "\n")

    print()
    print("STEP B COMPLETE")
    for key, value in summary["counts"].items():
        print(f"  {key:44} {value}")
    print(f"  {'seconds':44} {timing['seconds']}")
    print()
    print("STEP B FROZEN")
    print(f"output hash = {output_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
