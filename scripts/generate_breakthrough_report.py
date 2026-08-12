"""Generate a comprehensive Breakthrough Gap Closure Report.

Aggregates all available output artifacts and answers 9 key questions
about the Reasoning Project's progress, evidence quality, and claims status.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = PROJECT_ROOT / "outputs"

REPORT_VERSION = "1.0"

ARTIFACT_PATHS = {
    "curriculum_summary": OUTPUTS / "memory_growth" / "curriculum_summary.json",
    "oracle_summary": OUTPUTS / "oracle_candidate_analysis" / "summary.json",
    "reasoning_events": OUTPUTS / "events" / "reasoning_events.jsonl",
    "operator_invention": OUTPUTS / "operator_invention",
    "active_falsifier": OUTPUTS / "active_falsifier",
    "cross_domain_v2": OUTPUTS / "cross_domain_v2",
    "certificates": OUTPUTS / "certificates",
    "reasoning_scaling": OUTPUTS / "reasoning_scaling",
    "integrated_eval": OUTPUTS / "integrated_eval" / "integrated_eval.json",
    "ablation_summary": OUTPUTS / "ablation_v6" / "ablation_summary.json",
    "portfolio_v10_full": OUTPUTS / "portfolio_v10_full",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load a JSON file, returning None if it does not exist."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[WARN] Could not load {path}: {exc}", flush=True)
        return None


def load_jsonl(path: Path) -> Optional[List[Dict[str, Any]]]:
    """Load a JSON-Lines file, returning None if it does not exist."""
    if not path.exists():
        return None
    records: List[Dict[str, Any]] = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[WARN] Could not load {path}: {exc}", flush=True)
        return None


def scan_dir_jsons(directory: Path) -> List[Dict[str, Any]]:
    """Load all .json files in *directory*, returning a list of dicts."""
    results: List[Dict[str, Any]] = []
    if not directory.is_dir():
        return results
    for fpath in sorted(directory.glob("*.json")):
        data = load_json(fpath)
        if data is not None:
            results.append(data)
    return results


def safe_get(d: Optional[Dict], *keys: str, default: Any = None) -> Any:
    """Nested dict access with a fallback default."""
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


# ---------------------------------------------------------------------------
# Artifact loader
# ---------------------------------------------------------------------------


class ArtifactStore:
    """Loads and caches every artifact referenced by the report."""

    def __init__(self) -> None:
        self.curriculum: Optional[Dict] = None
        self.oracle: Optional[Dict] = None
        self.events: Optional[List[Dict]] = None
        self.operators: List[Dict] = []
        self.falsifier: List[Dict] = []
        self.cross_domain: List[Dict] = []
        self.certificates: List[Dict] = []
        self.scaling: List[Dict] = []
        self.integrated: Optional[Dict] = None
        self.ablation: Optional[Dict] = None
        self.portfolio: Optional[Dict] = None

    def load_all(self) -> None:
        print("[INFO] Loading artifacts ...", flush=True)
        self.curriculum = load_json(ARTIFACT_PATHS["curriculum_summary"])
        self.oracle = load_json(ARTIFACT_PATHS["oracle_summary"])
        self.events = load_jsonl(ARTIFACT_PATHS["reasoning_events"])
        self.operators = scan_dir_jsons(ARTIFACT_PATHS["operator_invention"])
        self.falsifier = scan_dir_jsons(ARTIFACT_PATHS["active_falsifier"])
        self.cross_domain = scan_dir_jsons(ARTIFACT_PATHS["cross_domain_v2"])
        self.certificates = scan_dir_jsons(ARTIFACT_PATHS["certificates"])
        self.scaling = scan_dir_jsons(ARTIFACT_PATHS["reasoning_scaling"])
        self.integrated = load_json(ARTIFACT_PATHS["integrated_eval"])
        self.ablation = load_json(ARTIFACT_PATHS["ablation_summary"])

        portfolio_summary = ARTIFACT_PATHS["portfolio_v10_full"] / "summary.json"
        self.portfolio = load_json(portfolio_summary)

        found = sum([
            self.curriculum is not None,
            self.oracle is not None,
            self.events is not None,
            len(self.operators) > 0,
            len(self.falsifier) > 0,
            len(self.cross_domain) > 0,
            len(self.certificates) > 0,
            len(self.scaling) > 0,
            self.integrated is not None,
            self.ablation is not None,
            self.portfolio is not None,
        ])
        print(f"[INFO] Loaded {found}/11 artifact sources.", flush=True)


# ---------------------------------------------------------------------------
# Question answerers
# ---------------------------------------------------------------------------


def q1_initially_failed(store: ArtifactStore) -> Tuple[str, str]:
    """Q1: How many tasks initially failed?"""
    lines: List[str] = []
    total = safe_get(store.portfolio, "total_tasks", default=None)
    solved = safe_get(store.portfolio, "solved", default=None)
    if total is not None and solved is not None:
        failed = total - solved
        lines.append(f"- Portfolio v10 full: **{solved}** solved out of **{total}** total tasks.")
        lines.append(f"- Initially failed: **{failed}** tasks ({100 * failed / total:.1f}%).")
    else:
        lines.append("- Portfolio v10 full summary not available.")

    int_total = safe_get(store.integrated, "total_tasks", default=None)
    int_solved_sym = safe_get(store.integrated, "configurations", "symbolic_only", "solved", default=None)
    if int_total is not None and int_solved_sym is not None:
        int_failed = int_total - int_solved_sym
        lines.append(f"- Integrated eval (symbolic-only): **{int_solved_sym}** solved, **{int_failed}** failed out of {int_total}.")

    if not lines:
        lines.append("- No task-level data available to answer this question.")

    return "Q1: How many tasks initially failed?", "\n".join(lines)


def q2_near_solved(store: ArtifactStore) -> Tuple[str, str]:
    """Q2: How many tasks were near-solved?"""
    lines: List[str] = []
    if store.curriculum is not None:
        near = safe_get(store.curriculum, "near_solved_count", default=None)
        if near is not None:
            lines.append(f"- Near-solved count (curriculum): **{near}**.")
        else:
            lines.append(f"- Curriculum summary exists but `near_solved_count` key not found.")
            lines.append(f"  Available keys: {list(store.curriculum.keys())}")
    if store.oracle is not None:
        oracle_near = safe_get(store.oracle, "near_solved", default=None)
        if oracle_near is not None:
            lines.append(f"- Near-solved count (oracle analysis): **{oracle_near}**.")
    if not lines:
        lines.append("- No near-solved data available (curriculum_summary.json and oracle summary missing).")
    return "Q2: How many tasks were near-solved?", "\n".join(lines)


def q3_promoted(store: ArtifactStore) -> Tuple[str, str]:
    """Q3: How many were later promoted (failed -> solved)?"""
    lines: List[str] = []
    if store.curriculum is not None:
        promoted = safe_get(store.curriculum, "promoted_count", default=None)
        if promoted is not None:
            lines.append(f"- Promoted (curriculum): **{promoted}** tasks moved from near-solved to solved.")
        else:
            lines.append("- Curriculum summary exists but `promoted_count` key not found.")
    # Compare portfolio v10 with integrated eval for promotion delta
    v10_solved = safe_get(store.portfolio, "solved", default=None)
    int_full = safe_get(store.integrated, "configurations", "full_pipeline", "solved", default=None)
    if v10_solved is not None and int_full is not None:
        delta = int_full - v10_solved
        lines.append(
            f"- Portfolio v10: {v10_solved} solved; Integrated full pipeline: {int_full} solved "
            f"(delta: {'+' if delta >= 0 else ''}{delta})."
        )
    if not lines:
        lines.append("- No promotion data available.")
    return "Q3: How many were later promoted?", "\n".join(lines)


def q4_concepts_invented(store: ArtifactStore) -> Tuple[str, str]:
    """Q4: What concepts/operators were invented?"""
    lines: List[str] = []
    if store.operators:
        lines.append(f"- Operator invention artifacts found: **{len(store.operators)}** file(s).")
        for i, op in enumerate(store.operators[:10]):
            name = safe_get(op, "name", default=safe_get(op, "operator", default=f"operator_{i}"))
            desc = safe_get(op, "description", default="(no description)")
            lines.append(f"  - `{name}`: {desc}")
        if len(store.operators) > 10:
            lines.append(f"  - ... and {len(store.operators) - 10} more.")
    else:
        lines.append("- No operator_invention artifacts found.")

    # Check portfolio solver contributions
    contributions = safe_get(store.portfolio, "solver_contributions", default=None)
    if contributions is not None:
        lines.append("- Solver contributions (portfolio v10):")
        for solver, count in sorted(contributions.items(), key=lambda x: -x[1]):
            lines.append(f"  - `{solver}`: {count} tasks")
    return "Q4: What concepts/operators were invented?", "\n".join(lines)


def q5_falsification(store: ArtifactStore) -> Tuple[str, str]:
    """Q5: Did active falsification reduce false positives?"""
    lines: List[str] = []
    h2 = safe_get(store.integrated, "hypotheses", "H2_falsification", default=None)
    if h2 is not None:
        fp_without = safe_get(h2, "false_positives_without_reranker", default="?")
        fp_with = safe_get(h2, "false_positives_with_reranker", default="?")
        reduction = safe_get(h2, "reduction", default="?")
        verdict = safe_get(h2, "verdict", default="unknown")
        lines.append(f"- False positives without reranker: **{fp_without}**")
        lines.append(f"- False positives with reranker: **{fp_with}**")
        lines.append(f"- Reduction: **{reduction}**")
        lines.append(f"- Verdict: **{verdict}**")
    if store.falsifier:
        lines.append(f"- Active falsifier artifacts: {len(store.falsifier)} file(s) found.")
    if not lines:
        lines.append("- No falsification data available.")
    return "Q5: Did active falsification reduce false positives?", "\n".join(lines)


def q6_cross_domain(store: ArtifactStore) -> Tuple[str, str]:
    """Q6: Did cross-domain transfer happen?"""
    lines: List[str] = []
    h1 = safe_get(store.integrated, "hypotheses", "H1_structural_transfer", default=None)
    if h1 is not None:
        sym_only = safe_get(h1, "symbolic_only", default="?")
        with_wm = safe_get(h1, "with_world_model", default="?")
        unique = safe_get(h1, "wm_unique_tasks", default=[])
        lines.append(f"- Symbolic only: **{sym_only}** solved")
        lines.append(f"- With world model: **{with_wm}** solved")
        lines.append(f"- World-model-unique tasks: {len(unique)} ({', '.join(unique[:5])})")
    if store.cross_domain:
        lines.append(f"- Cross-domain v2 artifacts: {len(store.cross_domain)} file(s) found.")
        for cd in store.cross_domain[:5]:
            src = safe_get(cd, "source_domain", default="?")
            tgt = safe_get(cd, "target_domain", default="?")
            success = safe_get(cd, "transfer_success", default="?")
            lines.append(f"  - {src} -> {tgt}: success={success}")
    if not lines:
        lines.append("- No cross-domain transfer data available.")
    return "Q6: Did cross-domain transfer happen?", "\n".join(lines)


def q7_memory_improvement(store: ArtifactStore) -> Tuple[str, str]:
    """Q7: Did memory improve future solving?"""
    lines: List[str] = []
    if store.curriculum is not None:
        lines.append(f"- Curriculum summary available. Keys: {list(store.curriculum.keys())}")
        baseline = safe_get(store.curriculum, "baseline_solved", default=None)
        after_mem = safe_get(store.curriculum, "after_memory_solved", default=None)
        if baseline is not None and after_mem is not None:
            lines.append(f"- Baseline solved: {baseline}, After memory: {after_mem} (gain: {after_mem - baseline})")
    if store.events:
        mem_events = [e for e in store.events if safe_get(e, "type", default="") == "memory_recall"]
        lines.append(f"- Memory recall events in event log: {len(mem_events)}")
    if not lines:
        lines.append("- No memory growth or event data available.")
    return "Q7: Did memory improve future solving?", "\n".join(lines)


def q8_regression(store: ArtifactStore) -> Tuple[str, str]:
    """Q8: Did any module regress performance?"""
    lines: List[str] = []
    if store.ablation is not None:
        full_solved = safe_get(store.ablation, "full", "n_solved", default=None)
        if full_solved is None:
            full_solved = safe_get(store.ablation, "full", "solved", default=None)
        lines.append(f"- Ablation v6 full portfolio: **{full_solved}** solved.")
        for key, val in store.ablation.items():
            if key == "full":
                continue
            ablated_solved = safe_get(val, "n_solved", default=safe_get(val, "solved", default=None))
            if ablated_solved is not None and full_solved is not None:
                delta = full_solved - ablated_solved
                direction = "REGRESSION" if delta < 0 else ("no change" if delta == 0 else f"drop of {delta}")
                lines.append(f"  - Without `{key}`: {ablated_solved} solved ({direction})")
    else:
        lines.append("- Ablation summary not available.")

    # Check integrated eval for regression signals
    configs = safe_get(store.integrated, "configurations", default=None)
    if configs is not None:
        sym = safe_get(configs, "symbolic_only", "solved", default=0)
        full = safe_get(configs, "full_pipeline", "solved", default=0)
        if full < sym:
            lines.append(f"- **REGRESSION DETECTED**: full_pipeline ({full}) < symbolic_only ({sym}).")
        else:
            lines.append(f"- No regression in integrated eval: full_pipeline ({full}) >= symbolic_only ({sym}).")
    return "Q8: Did any module regress performance?", "\n".join(lines)


def q9_claims_status(store: ArtifactStore) -> Tuple[str, str]:
    """Q9: Are claims supported or still speculative?"""
    # Build claims table
    claims: List[Tuple[str, str, str]] = []

    # H1
    h1_verdict = safe_get(store.integrated, "hypotheses", "H1_structural_transfer", "verdict", default=None)
    claims.append((
        "H1: Structural transfer via world model",
        _verdict_to_status(h1_verdict),
        f"Integrated eval verdict: {h1_verdict}" if h1_verdict else "No integrated eval data",
    ))

    # H2
    h2_verdict = safe_get(store.integrated, "hypotheses", "H2_falsification", "verdict", default=None)
    claims.append((
        "H2: World-model falsification reduces FPs",
        _verdict_to_status(h2_verdict),
        f"Integrated eval verdict: {h2_verdict}" if h2_verdict else "No integrated eval data",
    ))

    # H3
    h3_verdict = safe_get(store.integrated, "hypotheses", "H3_path_repair", "verdict", default=None)
    claims.append((
        "H3: Path repair after corruption",
        _verdict_to_status(h3_verdict),
        f"Integrated eval verdict: {h3_verdict}" if h3_verdict else "No integrated eval data",
    ))

    # H4
    h4_verdict = safe_get(store.integrated, "hypotheses", "H4_compression_selection", "verdict", default=None)
    claims.append((
        "H4: Compression selection via WM agreement",
        _verdict_to_status(h4_verdict),
        f"Integrated eval verdict: {h4_verdict}" if h4_verdict else "No integrated eval data",
    ))

    # H5
    h5_verdict = safe_get(store.integrated, "hypotheses", "H5_integrated_scientist", "verdict", default=None)
    claims.append((
        "H5: Integrated scientist outperforms parts",
        _verdict_to_status(h5_verdict),
        f"Integrated eval verdict: {h5_verdict}" if h5_verdict else "No integrated eval data",
    ))

    # Memory growth
    mem_status = "[NOT_YET_TESTED]" if store.curriculum is None else "[PARTIALLY_SUPPORTED]"
    claims.append((
        "Memory growth promotes near-solved tasks",
        mem_status,
        "Curriculum summary " + ("found" if store.curriculum else "missing"),
    ))

    # Operator invention
    op_status = "[NOT_YET_TESTED]" if not store.operators else "[PARTIALLY_SUPPORTED]"
    claims.append((
        "Novel operator invention",
        op_status,
        f"{len(store.operators)} operator artifact(s) found",
    ))

    # Cross-domain transfer
    cd_status = "[NOT_YET_TESTED]" if not store.cross_domain else "[PARTIALLY_SUPPORTED]"
    claims.append((
        "Cross-domain transfer",
        cd_status,
        f"{len(store.cross_domain)} cross-domain artifact(s) found",
    ))

    # Scaling
    sc_status = "[NOT_YET_TESTED]" if not store.scaling else "[PARTIALLY_SUPPORTED]"
    claims.append((
        "Reasoning scaling laws",
        sc_status,
        f"{len(store.scaling)} scaling artifact(s) found",
    ))

    # Format as table
    header = "| Claim | Status | Evidence |"
    sep = "|-------|--------|----------|"
    rows = [f"| {c} | {s} | {e} |" for c, s, e in claims]
    table = "\n".join([header, sep] + rows)

    return "Q9: Are claims supported or still speculative?", table


def _verdict_to_status(verdict: Optional[str]) -> str:
    if verdict is None:
        return "[NOT_YET_TESTED]"
    v = verdict.lower()
    if v == "supported":
        return "[SUPPORTED]"
    elif v == "inconclusive":
        return "[INCONCLUSIVE]"
    elif v in ("partially_supported", "partial"):
        return "[PARTIALLY_SUPPORTED]"
    else:
        return f"[{verdict.upper()}]"


# ---------------------------------------------------------------------------
# Summary metrics table
# ---------------------------------------------------------------------------


def build_summary_table(store: ArtifactStore) -> str:
    """Build a markdown table of key metrics."""
    rows: List[Tuple[str, str]] = []

    total = safe_get(store.portfolio, "total_tasks", default=None)
    solved = safe_get(store.portfolio, "solved", default=None)
    rate = safe_get(store.portfolio, "solve_rate", default=None)
    rows.append(("Total ARC tasks evaluated", str(total) if total else "N/A"))
    rows.append(("Portfolio v10 solved", str(solved) if solved else "N/A"))
    rows.append(("Portfolio v10 solve rate", f"{rate:.1%}" if rate else "N/A"))

    int_sym = safe_get(store.integrated, "configurations", "symbolic_only", "solved", default=None)
    int_full = safe_get(store.integrated, "configurations", "full_pipeline", "solved", default=None)
    rows.append(("Integrated eval symbolic-only", str(int_sym) if int_sym is not None else "N/A"))
    rows.append(("Integrated eval full pipeline", str(int_full) if int_full is not None else "N/A"))

    fp_without = safe_get(store.integrated, "hypotheses", "H2_falsification", "false_positives_without_reranker", default=None)
    fp_with = safe_get(store.integrated, "hypotheses", "H2_falsification", "false_positives_with_reranker", default=None)
    rows.append(("FP without reranker", str(fp_without) if fp_without is not None else "N/A"))
    rows.append(("FP with reranker", str(fp_with) if fp_with is not None else "N/A"))

    h3_recovery = safe_get(store.integrated, "hypotheses", "H3_path_repair", "recovery_rate", default=None)
    rows.append(("H3 recovery rate", f"{h3_recovery:.0%}" if h3_recovery is not None else "N/A"))

    ablation_full = safe_get(store.ablation, "full", "n_solved", default=safe_get(store.ablation, "full", "solved", default=None))
    rows.append(("Ablation v6 full portfolio", str(ablation_full) if ablation_full is not None else "N/A"))

    rows.append(("Operator invention artifacts", str(len(store.operators))))
    rows.append(("Cross-domain transfer artifacts", str(len(store.cross_domain))))
    rows.append(("Certificates artifacts", str(len(store.certificates))))

    header = "| Metric | Value |"
    sep = "|--------|-------|"
    body = [f"| {m} | {v} |" for m, v in rows]
    return "\n".join([header, sep] + body)


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def generate_report(store: ArtifactStore) -> str:
    """Assemble the full markdown report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections: List[str] = []

    # Title
    sections.append("# Cumulative Reasoning: Breakthrough Gap Closure Report")
    sections.append("")
    sections.append(f"**Generated:** {now}  ")
    sections.append(f"**Version:** {REPORT_VERSION}  ")
    sections.append(f"**Project root:** `{PROJECT_ROOT}`  ")
    sections.append("")

    # Summary metrics
    sections.append("## Key Metrics Summary")
    sections.append("")
    sections.append(build_summary_table(store))
    sections.append("")

    # 9 Questions
    question_funcs = [
        q1_initially_failed,
        q2_near_solved,
        q3_promoted,
        q4_concepts_invented,
        q5_falsification,
        q6_cross_domain,
        q7_memory_improvement,
        q8_regression,
        q9_claims_status,
    ]

    sections.append("---")
    sections.append("")
    sections.append("## Detailed Answers")
    sections.append("")

    for func in question_funcs:
        title, body = func(store)
        sections.append(f"### {title}")
        sections.append("")
        sections.append(body)
        sections.append("")

    # Claims Status table (standalone section for quick reference)
    sections.append("---")
    sections.append("")
    sections.append("## Claims Status")
    sections.append("")
    _, claims_table = q9_claims_status(store)
    sections.append(claims_table)
    sections.append("")
    sections.append("**Legend:**")
    sections.append("- `[SUPPORTED]`: Empirical evidence confirms the claim.")
    sections.append("- `[PARTIALLY_SUPPORTED]`: Some evidence exists but is incomplete or marginal.")
    sections.append("- `[INCONCLUSIVE]`: Evidence is mixed or insufficient to decide.")
    sections.append("- `[NOT_YET_TESTED]`: No experiment has been run for this claim.")
    sections.append("")

    # What Not To Claim
    sections.append("---")
    sections.append("")
    sections.append("## What Not To Claim")
    sections.append("")
    sections.append(_what_not_to_claim(store))
    sections.append("")

    # Limitations
    sections.append("---")
    sections.append("")
    sections.append("## Limitations")
    sections.append("")
    sections.append(_limitations(store))
    sections.append("")

    return "\n".join(sections)


def _what_not_to_claim(store: ArtifactStore) -> str:
    """Generate a 'What Not To Claim' section based on evidence gaps."""
    warnings: List[str] = []

    # Check for overstated gains
    int_sym = safe_get(store.integrated, "configurations", "symbolic_only", "solved", default=None)
    int_full = safe_get(store.integrated, "configurations", "full_pipeline", "solved", default=None)
    if int_sym is not None and int_full is not None:
        delta = int_full - int_sym
        if delta <= 5:
            warnings.append(
                f"- **Do not overstate neural gains.** The full pipeline solves only "
                f"{delta} more task(s) than symbolic-only ({int_full} vs {int_sym}). "
                f"This is a modest improvement, not a paradigm shift."
            )

    h4_verdict = safe_get(store.integrated, "hypotheses", "H4_compression_selection", "verdict", default=None)
    if h4_verdict and h4_verdict.lower() == "inconclusive":
        warnings.append(
            "- **Do not claim validated compression selection (H4).** "
            "The correlation is inconclusive; more data points are needed."
        )

    fp_reduction = safe_get(store.integrated, "hypotheses", "H2_falsification", "reduction", default=None)
    if fp_reduction is not None and fp_reduction < 10:
        warnings.append(
            f"- **Do not overstate falsification power.** "
            f"The reranker reduced false positives by only {fp_reduction}, "
            f"which may not be statistically significant."
        )

    if store.curriculum is None:
        warnings.append(
            "- **Do not claim demonstrated memory-driven promotion.** "
            "The curriculum summary is missing; no empirical evidence of memory growth."
        )

    if not store.operators:
        warnings.append(
            "- **Do not claim novel operator invention.** "
            "No operator_invention artifacts were found."
        )

    if not store.cross_domain:
        warnings.append(
            "- **Do not claim cross-domain transfer.** "
            "No cross_domain_v2 artifacts were found."
        )

    if not store.scaling:
        warnings.append(
            "- **Do not claim reasoning scaling laws.** "
            "No reasoning_scaling artifacts were found."
        )

    if not warnings:
        warnings.append("- All claims appear to have at least partial supporting evidence.")

    return "\n".join(warnings)


def _limitations(store: ArtifactStore) -> str:
    """Generate a Limitations section."""
    items: List[str] = []

    items.append(
        "1. **Single benchmark.** All results are on ARC / ConceptARC. "
        "Generalization to other reasoning benchmarks is untested."
    )
    items.append(
        "2. **Deterministic seeds.** Seed sweeps cover a limited range; "
        "variance estimates may underestimate true variability."
    )

    missing = []
    for name, path in ARTIFACT_PATHS.items():
        if not path.exists():
            missing.append(name)
    if missing:
        items.append(
            f"3. **Missing artifacts.** The following artifact sources were not found: "
            f"{', '.join(f'`{m}`' for m in missing)}. "
            f"Claims relying on these sources are marked [NOT_YET_TESTED]."
        )

    items.append(
        f"4. **No external baselines.** This report does not compare against "
        f"published ARC leaderboard results (SOTA ~43% on ARC-AGI-2)."
    )
    items.append(
        "5. **World model overhead.** The integrated eval took "
        + (
            f"{safe_get(store.integrated, 'elapsed_seconds', default=0):.0f}s"
            if store.integrated
            else "unknown time"
        )
        + ", which may not be practical for competition settings."
    )

    return "\n".join(items)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the Breakthrough Gap Closure Report.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/breakthrough_gap_closure_report.md",
        help="Path to write the report (relative to project root or absolute).",
    )
    args = parser.parse_args()

    # Resolve output path
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Generating Breakthrough Gap Closure Report ...", flush=True)
    t0 = time.time()

    store = ArtifactStore()
    store.load_all()

    report = generate_report(store)

    with open(out_path, "w") as f:
        f.write(report)

    elapsed = time.time() - t0
    print(f"[INFO] Report written to: {out_path}", flush=True)
    print(f"[INFO] Report length: {len(report)} chars, {report.count(chr(10))} lines.", flush=True)
    print(f"[INFO] Completed in {elapsed:.1f}s.", flush=True)


if __name__ == "__main__":
    main()
