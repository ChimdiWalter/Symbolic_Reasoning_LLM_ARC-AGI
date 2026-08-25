"""Gates that must pass BEFORE the Step-B runner sees the 62 clusters.

Everything here is SYNTHETIC: corpora manufactured in this file, turned
into Step-A-format frontier records and clusters by the FROZEN Step-A
runner (so the Step-B runner is exercised on inputs of exactly the real
shape), then run through the Step-B runner with explicit path overrides.
No pinned cluster, record or corpus file is read.

  1 protocol      a shape-changing task the baseline cannot express but
                  the substrate can (K2) is proposed AND resolved on >= 2
                  sources, labelled NEW_SEMANTIC_PRODUCTION, kept;
                  a repaint task whose only defect is a key witnessed
                  once yields a SLOT_LEARNER_REPAIR proposal that fails
                  leave-one-out, so it is NOT kept;
                  a task nothing in the substrate fits yields no proposal
  2 LOO fidelity  the runner's stats-recording LOO loop returns the frozen
                  function's verdict on every fixture
  3 neutrality    installing the substrate (no candidate) changes nothing
                  for the frozen search on a baseline-solvable task, and
                  the runtime is restored afterwards
  4 determinism   two runs of the runner are byte-identical on every
                  hashed output (timing is not hashed), or, where a search
                  hit the frozen deadline, identical after masking every
                  record downstream of that search in both runs; masked
                  work is counted and reported, never hidden
  5 checkpoint    a run stopped mid-phase (gate-only --stop-after-units)
                  leaves its journal and NO outputs; rerunning resumes
                  from the journal, completes, removes the journal, and
                  the outputs equal the uninterrupted reference run's
                  under the same deadline-hit masking as gate 4

This script is a GATE. Its record is an input to the run manifest, never
to the runner.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V          # noqa: E402
from level4_blind_runtime import search as SEARCH      # noqa: E402
from level4_stepB import install as N                  # noqa: E402
from level4_stepB import k2_inventory as I             # noqa: E402

OUT = ROOT / "outputs" / "cora_breakthrough"
INPUTS = OUT / "level4_mechanism_inputs"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load("stepB_run", ROOT / "scripts" / "cora_level4_stepB_run.py")


def token(label: str) -> str:
    return hashlib.sha256(f"synthetic-stepB-{label}".encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

def extent_demonstrations(seed: int) -> list:
    """One L-shaped object; the output is its tight extent on background.
    Shape changes, so no admitted term can produce it; the substrate's
    embed-with-frame can."""
    demos = []
    for index in range(3):
        grid_in = np.zeros((7, 7), dtype=int)
        r = (index + seed) % 4
        c = (2 * index + seed) % 4
        colour = 2 + (seed + index) % 5
        cells = [(r, c), (r + 1, c), (r + 2, c), (r + 2, c + 1), (r + 2, c + 2)]
        for cell in cells:
            grid_in[cell] = colour
        grid_out = np.zeros((3, 3), dtype=int)
        for rr, cc in cells:
            grid_out[rr - r, cc - c] = colour
        demos.append({"input": grid_in.tolist(), "output": grid_out.tolist()})
    return demos


def single_witness_demonstrations(seed: int) -> list:
    """Repaint by area (1 -> 8, 2 -> 9); the third demonstration also
    carries an area-3 shape (-> 7) seen nowhere else."""
    demos = []
    for index in range(3):
        g = np.zeros((7, 7), dtype=int)
        s = (index + seed) % 3
        g[1, 1 + s] = 3                                   # area 1
        g[3, 1 + s] = 5
        g[3, 2 + s] = 5                                   # area 2
        o = g.copy()
        o[o == 3] = 8
        o[o == 5] = 9
        if index == 2:
            for cell in ((5, 1), (5, 2), (5, 3)):
                g[cell] = 4
                o[cell] = 7
        demos.append({"input": g.tolist(), "output": o.tolist()})
    return demos


def unrelated_demonstrations(seed: int) -> list:
    """The output is a constant 2x2 grid of one colour, unrelated to the
    input's single object: nothing in the substrate should fit."""
    demos = []
    for index in range(3):
        g = np.zeros((5, 5), dtype=int)
        g[(index + seed) % 4, (index * 2 + seed) % 4] = 4
        g[(index + seed) % 4 + 1, (index * 2 + seed) % 4] = 4
        o = np.full((2, 2), 9, dtype=int)
        demos.append({"input": g.tolist(), "output": o.tolist()})
    return demos


def solvable_demonstrations() -> list:
    """Repaint each colour component by its area. In the language."""
    demos = []
    layouts = [((0, 0), ((2, 2), (2, 3))), ((3, 4), ((0, 1), (1, 1))),
               ((4, 0), ((0, 3), (0, 4)))]
    for single, pair in layouts:
        grid_in = np.zeros((5, 5), dtype=int)
        grid_in[single] = 3
        for cell in pair:
            grid_in[cell] = 3
        grid_out = grid_in.copy()
        grid_out[single] = 6
        for cell in pair:
            grid_out[cell] = 7
        demos.append({"input": grid_in.tolist(), "output": grid_out.tolist()})
    return demos


def corpus() -> list:
    rows = []
    for i in range(3):
        rows.append({"source_token": token(f"extent-{i}"),
                     "demonstrations": extent_demonstrations(i)})
    for i in range(3):
        rows.append({"source_token": token(f"once-{i}"),
                     "demonstrations": single_witness_demonstrations(i)})
    for i in range(3):
        rows.append({"source_token": token(f"none-{i}"),
                     "demonstrations": unrelated_demonstrations(i)})
    return rows


def write_corpus(path: Path, rows: list) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


# --------------------------------------------------------------------------
# running the two frozen runners on the fixtures
# --------------------------------------------------------------------------

def run_step_a(corpus_path: Path, workdir: Path, tag: str, workers: int) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cora_level4_stepA_extract.py"),
         "--corpus", str(corpus_path), "--outdir", str(workdir), "--tag", tag,
         "--workers", str(workers)],
        capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit(f"Step-A runner failed:\n{result.stdout}\n{result.stderr}")


def run_step_b(corpus_path: Path, workdir: Path, a_tag: str, tag: str,
               workers: int, extra: tuple = (), expect: tuple = (0,),
               load: bool = True) -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cora_level4_stepB_run.py"),
         "--corpus", str(corpus_path), "--outdir", str(workdir), "--tag", tag,
         "--records", str(workdir / f"{a_tag}_frontier_records.jsonl"),
         "--clusters", str(workdir / f"{a_tag}_clusters.json"),
         "--workers", str(workers), *extra],
        capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode not in expect:
        raise SystemExit(f"Step-B runner failed:\n{result.stdout}\n{result.stderr}")
    out = {"stdout": result.stdout, "returncode": result.returncode}
    if not load:
        return out
    for name in ("candidates", "selection", "summary"):
        out[name] = json.loads((workdir / f"{tag}_{name}.json").read_text())
    for name in ("proposals", "resolution", "k1_searches"):
        out[name] = [json.loads(l) for l in
                     (workdir / f"{tag}_{name}.jsonl").read_text().splitlines()
                     if l.strip()]
    return out


def output_digest(workdir: Path, tag: str) -> str:
    lines = (workdir / f"{tag}_output_hash.txt").read_text().split("\n")
    return lines[0].strip()


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------

def gate_protocol(result: dict, rows: list) -> dict:
    extent = {r["source_token"] for r in rows if "extent" in json.dumps(r)[:0] or
            r["source_token"] in {token(f"extent-{i}") for i in range(3)}}
    once = {token(f"once-{i}") for i in range(3)}
    none = {token(f"none-{i}") for i in range(3)}
    by_id = {c["candidate_id"]: c for c in result["candidates"]["candidates"]}
    sel = result["selection"]["selection"]
    props = result["proposals"]
    checks = {}
    k2_extent = [p for p in props if p["lane"] == "K2" and p["source_token"] in extent]
    checks["extent_proposed_by_K2"] = len({p["source_token"] for p in k2_extent}) >= 2
    checks["extent_K2_labelled_new_semantic_production"] = all(
        by_id[p["candidate_id"]]["label"] == "NEW_SEMANTIC_PRODUCTION"
        for p in k2_extent) and bool(k2_extent)
    kept_extent = [s for s in sel if s["kept"] and s["lane"] == "K2"
                 and set(s["certified_sources"]) & extent]
    checks["extent_candidate_kept_with_2plus_certified_sources"] = any(
        len(set(s["certified_sources"]) & extent) >= 2 for s in kept_extent)
    checks["kept_requires_2_certified"] = all(
        s["kept"] == (len(s["certified_sources"]) >= 2) for s in sel)
    checks["certified_subset_of_proposing"] = all(
        set(s["certified_sources"]) <= set(s["proposing_sources"]) for s in sel)
    k1_once = [p for p in props if p["lane"] == "K1" and p["source_token"] in once]
    checks["single_witness_proposed_by_K1"] = bool(k1_once)
    checks["K1_labelled_repair"] = all(
        by_id[p["candidate_id"]]["label"] == "SLOT_LEARNER_REPAIR" for p in k1_once)
    checks["K1_single_witness_not_certified"] = not any(
        r["certified"] for r in result["resolution"]
        if r["lane"] == "K1" and r["source_token"] in once)
    checks["K1_proposals_only_from_learners_that_drop_a_guard"] = all(
        by_id[p["candidate_id"]]["learner"] for p in k1_once)
    checks["unrelated_task_never_proposed"] = not any(
        p["source_token"] in none for p in props)
    checks["labels_fixed_by_lane"] = all(
        (c["lane"] == "K2") == (c["label"] == "NEW_SEMANTIC_PRODUCTION")
        for c in result["candidates"]["candidates"])
    checks["every_cluster_processed"] = (
        result["summary"]["counts"]["eligible_clusters"] >= 1
        and result["summary"]["counts"]["k2_proposal_units"] >= 1)
    checks["resolution_uses_candidate_when_certified"] = all(
        r["uses_candidate"] for r in result["resolution"] if r["certified"])
    return {"gate": "the runner obeys the frozen protocol",
            "passed": all(checks.values()), "checks": checks,
            "proposals": len(props), "kept_pairs": sum(s["kept"] for s in sel),
            "deadline_hits": result["summary"]["counts"]["searches_hitting_deadline"]}


def gate_loo_fidelity(manifest) -> dict:
    RUNNER._init_worker(manifest, {}, [])
    env = RUNNER._STATE["base"]
    rows = []
    for label, demos in (("solvable", solvable_demonstrations()),
                         ("extent", extent_demonstrations(0)),
                         ("once", single_witness_demonstrations(0))):
        pairs = [(np.array(d["input"]), np.array(d["output"])) for d in demos]
        frozen = SEARCH.loo_by_rediscovery(pairs, env=env)
        passed, total, folds = RUNNER.loo_with_stats(pairs, env)
        rows.append({"fixture": label, "frozen": list(frozen),
                     "runner": [passed, total],
                     "identical": tuple(frozen) == (passed, total),
                     "deadline_hits": sum(f["deadline_hit"] for f in folds)})
    return {"gate": "the runner's LOO loop equals the frozen function",
            "passed": all(r["identical"] for r in rows), "rows": rows}


def gate_neutrality() -> dict:
    pairs = [(np.array(d["input"]), np.array(d["output"]))
             for d in solvable_demonstrations()]
    before = (dict(V.REGISTRY), dict(V.TERMINAL_VALUES), list(V.INDUCED_TYPES),
              dict(SEARCH.SLOT_LEARNERS), V._eval)
    frozen_results, frozen_stats = SEARCH.search(pairs)
    types, instances = I.build()
    with N.installed(instances):
        env = RUNNER.E.LanguageEnv(base=RUNNER.FROZEN_BASE, label="K")
        installed_results, installed_stats = SEARCH.search(pairs, env=env)
    after = (dict(V.REGISTRY), dict(V.TERMINAL_VALUES), list(V.INDUCED_TYPES),
             dict(SEARCH.SLOT_LEARNERS), V._eval)

    def winner(results):
        return json.dumps(V.to_json(results[0][0]), sort_keys=True) if results else None
    checks = {
        "winner_identical": winner(frozen_results) == winner(installed_results),
        "generated_identical": frozen_stats.generated == installed_stats.generated,
        "typed_identical": frozen_stats.typed == installed_stats.typed,
        "runtime_restored": before == after,
    }
    return {"gate": "installing the substrate changes nothing for the frozen search",
            "passed": all(checks.values()), "checks": checks}


def _rows(workdir: Path, tag: str, name: str) -> list:
    return [json.loads(l) for l in (workdir / f"{tag}_{name}.jsonl").read_text()
            .splitlines() if l.strip()]


def masked_compare(workdir: Path, a: str, b: str) -> dict:
    """Byte identity, and identity MODULO deadline-affected work.

    A search that hits the frozen deadline explores a timing-dependent
    amount, so every record downstream of one (the search row itself, a K1
    proposal it produced, a resolution row, and that source's entry in a
    selection row) is masked in BOTH runs before comparison. Everything
    else must be byte-identical. The masked keys are reported, never hidden.
    """
    full = output_digest(workdir, a) == output_digest(workdir, b)
    affected_k1, affected_res = set(), set()
    for tag in (a, b):
        for r in _rows(workdir, tag, "k1_searches"):
            if r["deadline_hit"]:
                affected_k1.add((r["learner_id"], r["source_token"]))
        for r in _rows(workdir, tag, "resolution"):
            if r["any_deadline_hit"]:
                affected_res.add((r["candidate_id"], r["source_token"]))
    affected_sources = {t for _, t in affected_k1} | {t for _, t in affected_res}
    by_id = {c["candidate_id"]: c for c in json.loads(
        (workdir / f"{a}_candidates.json").read_text())["candidates"]}

    def view(tag):
        out = {}
        out["candidates"] = (workdir / f"{tag}_candidates.json").read_text()
        out["k2_units"] = (workdir / f"{tag}_k2_proposal_units.jsonl").read_text()
        out["k1_searches"] = [r for r in _rows(workdir, tag, "k1_searches")
                              if (r["learner_id"], r["source_token"]) not in affected_k1]
        out["proposals"] = [r for r in _rows(workdir, tag, "proposals")
                            if not (r["lane"] == "K1" and
                                    (by_id[r["candidate_id"]]["learner"],
                                     r["source_token"]) in affected_k1)]
        out["resolution"] = [r for r in _rows(workdir, tag, "resolution")
                             if (r["candidate_id"], r["source_token"]) not in affected_res]
        sel = json.loads((workdir / f"{tag}_selection.json").read_text())["selection"]
        masked = []
        for row in sel:
            row = dict(row)
            row["proposing_sources"] = [t for t in row["proposing_sources"]
                                        if t not in affected_sources]
            row["certified_sources"] = [t for t in row["certified_sources"]
                                        if t not in affected_sources]
            row["kept"] = "MASKED"
            masked.append(row)
        out["selection"] = masked
        return out

    va, vb = view(a), view(b)
    differing = [k for k in va if json.dumps(va[k], sort_keys=True)
                 != json.dumps(vb[k], sort_keys=True)]
    return {"identical_full": full, "identical_masked": not differing,
            "files_differing_after_mask": differing,
            "masked_k1_searches": len(affected_k1),
            "masked_resolution_pairs": len(affected_res),
            "masked_sources": len(affected_sources)}


def gate_determinism(workdir: Path, corpus_path: Path, a_tag: str,
                     workers: int, first: dict) -> dict:
    second = run_step_b(corpus_path, workdir, a_tag, "detb", workers)
    digests = [output_digest(workdir, "deta"), output_digest(workdir, "detb")]
    deadline = (first["summary"]["counts"]["searches_hitting_deadline"]
                + second["summary"]["counts"]["searches_hitting_deadline"])
    compare = masked_compare(workdir, "deta", "detb")
    keep = OUT / "level4_stepB_gate_outputs"
    keep.mkdir(exist_ok=True)
    for path in sorted(workdir.glob("det*")):
        (keep / path.name).write_bytes(path.read_bytes())
    return {"gate": "byte-identical output on repeated runs, modulo deadline-hit work",
            "passed": compare["identical_masked"],
            "identical": compare["identical_full"],
            "identical_after_masking_deadline_affected_records":
                compare["identical_masked"],
            "comparison": compare,
            "deadline_hits_in_both_runs": deadline,
            "note": ("timing is not hashed; a search that hits the frozen "
                     "deadline explores a timing-dependent amount, so "
                     "byte-determinism is required of everything EXCEPT the "
                     "records downstream of such a search, which are masked "
                     "in both runs and counted here; this fixture recorded "
                     f"{deadline} deadline hit(s); synthetic outputs kept in "
                     "level4_stepB_gate_outputs/ for inspection"),
            "digests": digests}


def gate_checkpoint_resume(workdir: Path, corpus_path: Path, a_tag: str,
                           workers: int) -> dict:
    """A run stopped mid-phase must resume from its journal to the same
    outputs as an uninterrupted run (masked by the same deadline-hit
    boundary the determinism gate accepts), and the journal must persist
    at the stop and be removed at completion."""
    stopped = run_step_b(corpus_path, workdir, a_tag, "ckpt", workers,
                         extra=("--stop-after-units", "5"), expect=(3,),
                         load=False)
    journal = workdir / "ckpt_journal.jsonl"
    checks = {}
    checks["stop_flag_exits_with_code_3"] = stopped["returncode"] == 3
    checks["stop_message_printed"] = "CHECKPOINT STOP" in stopped["stdout"]
    checks["journal_persists_at_stop"] = journal.exists()
    checks["journal_holds_header_plus_5_units"] = (
        journal.exists() and len(journal.read_text().splitlines()) == 6)
    checks["no_outputs_written_at_stop"] = not any(
        (workdir / f"ckpt_{n}").exists() for n in
        ("output_hash.txt", "summary.json", "selection.json"))
    resumed = run_step_b(corpus_path, workdir, a_tag, "ckpt", workers)
    checks["resume_replays_journaled_units"] = (
        "replayed from journal" in resumed["stdout"])
    checks["resume_completes"] = "STEP B FROZEN" in resumed["stdout"]
    checks["journal_removed_at_completion"] = not journal.exists()
    compare = masked_compare(workdir, "deta", "ckpt")
    checks["resumed_outputs_identical_masked"] = compare["identical_masked"]
    keep = OUT / "level4_stepB_gate_outputs"
    keep.mkdir(exist_ok=True)
    for path in sorted(workdir.glob("ckpt*")):
        (keep / path.name).write_bytes(path.read_bytes())
    return {"gate": "a stopped run resumes from its journal to the same outputs",
            "passed": all(checks.values()), "checks": checks,
            "identical_full": compare["identical_full"],
            "comparison": compare,
            "note": ("run 1 stops after 5 journaled units (exit 3); run 2 "
                     "resumes and completes; outputs are compared against "
                     "the uninterrupted reference run under the same "
                     "deadline-hit masking as the determinism gate")}


def tested_executables() -> dict:
    """SHA-256 of exactly what this gate run exercised, recorded so the
    manifest can prove the gates apply to the executable about to run."""
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "tested_runner_sha256": sha(ROOT / "scripts" / "cora_level4_stepB_run.py"),
        "tested_candidates_sha256": sha(ROOT / "level4_stepB" / "candidates.py"),
        "tested_item1_freeze_sha256": sha(OUT / "level4_stepB_item1_freeze.json"),
        "tested_design_sha256": sha(ROOT / "docs" / "CORA_LEVEL4_STEPB_DESIGN.md"),
        "tested_blind_runtime": {q.name: sha(q) for q in
                                 sorted((ROOT / "level4_blind_runtime").glob("*.py"))},
    }


def main() -> int:
    workers = 12
    manifest = json.loads((INPUTS / "machine_manifest.json").read_text())
    rows = corpus()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        corpus_path = workdir / "synthetic.jsonl"
        write_corpus(corpus_path, rows)
        print("step A on the synthetic corpus")
        sys.stdout.flush()
        run_step_a(corpus_path, workdir, "syn", workers)
        clusters = json.loads((workdir / "syn_clusters.json").read_text())
        print(f"  clusters {len(clusters['clusters'])}  eligible "
              f"{sum(c['eligible'] for c in clusters['clusters'])}")

        print("gate 1: protocol (first Step-B run)")
        sys.stdout.flush()
        first = run_step_b(corpus_path, workdir, "syn", "deta", workers)
        protocol = gate_protocol(first, rows)
        for name, value in protocol["checks"].items():
            print(f"  {'PASS' if value else 'FAIL'}  {name}")

        print("gate 4: determinism (second Step-B run)")
        sys.stdout.flush()
        determinism = gate_determinism(workdir, corpus_path, "syn", workers, first)
        print(f"  identical {determinism['identical']}  masked-identical "
              f"{determinism['identical_after_masking_deadline_affected_records']}  "
              f"deadline hits {determinism['deadline_hits_in_both_runs']}  "
              f"differing {determinism['comparison']['files_differing_after_mask']}")

        print("gate 5: checkpoint resume (stopped Step-B run + resumed run)")
        sys.stdout.flush()
        checkpoint = gate_checkpoint_resume(workdir, corpus_path, "syn", workers)
        for name, value in checkpoint["checks"].items():
            print(f"  {'PASS' if value else 'FAIL'}  {name}")

    print("gate 2: LOO fidelity")
    sys.stdout.flush()
    loo = gate_loo_fidelity(manifest)
    for r in loo["rows"]:
        print(f"  {r['fixture']:10} frozen {r['frozen']} runner {r['runner']} "
              f"identical {r['identical']}")
    print("gate 3: neutrality")
    neutrality = gate_neutrality()
    for name, value in neutrality["checks"].items():
        print(f"  {'PASS' if value else 'FAIL'}  {name}")

    report = {"gate": "Step-B pre-run gates",
              "tested_executables": tested_executables(),
              "passed": all(g["passed"] for g in
                            (protocol, loo, neutrality, determinism,
                             checkpoint)),
              "protocol": protocol, "loo_fidelity": loo,
              "neutrality": neutrality, "determinism": determinism,
              "checkpoint_resume": checkpoint}
    (OUT / "level4_stepB_gates.json").write_text(json.dumps(report, indent=1))
    print()
    print("ALL GATES PASSED" if report["passed"] else "GATES FAILED")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
