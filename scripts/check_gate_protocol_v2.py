"""Mechanical checklist for the Capability-Growth Gate protocol v2.

Checks presence of required mechanics and absence of the v1 positions that the
2026-09-13 directive rejected. It is a floor, not a review: passing it does not
make the document correct, but failing it means a correction is missing.
"""
import re
import sys
from pathlib import Path

doc = Path(sys.argv[1]).read_text()
low = doc.lower()
results = []


def need(label, ok, detail=""):
    results.append((label, bool(ok), detail))


# ---- style
need("S1 no em dashes", "—" not in doc, f"{doc.count(chr(0x2014))} found")
need("S2 no attribution", not re.search(r"claude|anthropic|co-authored|generated with", low))

# ---- C1 supersession
need("C1 protocol id v2", "CORA_CAPABILITY_GROWTH_GATE:v2" in doc)
need("C1 names v1 commit", "da6c916" in doc)
need("C1 changes-from-v1 section", re.search(r"^#+\s*\d*\.?\s*changes from v1", doc, re.I | re.M))

# ---- C2 content invariant
need("C2 precise invariant", "transient" in low and "hash" in low and "never parsed" in low)
need("C2 old false claim gone", not re.search(r"reads no content|never reads (artifact )?content", low))

# ---- C3 readiness
for code in ("FREEZE_MARKER_ABSENT", "FREEZE_OUTPUT_NOT_READY", "FREEZE_RUNNER_STILL_ACTIVE",
             "PIN_SOURCE_UNSTABLE", "PIN_EXISTS_REFUSING_OVERWRITE", "PIN_CREATED"):
    need(f"C3 {code}", code in doc)
need("C3 output hash filename", "level4_stepB_output_hash.txt" in doc)

# ---- C4 verification
for code in ("PIN_VERIFIED", "PIN_MISSING", "PIN_HASH_RECORD_MISSING", "PIN_JSON_ALTERED",
             "PIN_ARTIFACT_MISSING", "PIN_ARTIFACT_DRIFT", "PIN_SCOPE_GREW_AFTER_FREEZE"):
    need(f"C4 {code}", code in doc)
need("C4 PinProvenanceError", "PinProvenanceError" in doc)
need("C4 provenance not scientific", re.search(r"not a scientific|never a scientific", low))

# ---- C5
need("C5 DRY_RUN_REFUSED_ON_LIVE_TREE", "DRY_RUN_REFUSED_ON_LIVE_TREE" in doc)

# ---- C6 quarantine
need("C6 deviation doc referenced", "CORA_STEPB_PREFREEZE_DEVIATIONS.md" in doc)
need("C6 SCHEMA_ASSUMPTION_FAILED", "SCHEMA_ASSUMPTION_FAILED" in doc)
need("C6 Q1..Q6 referenced", all(f"Q{i}" in doc for i in range(1, 7)))
need("C6a no corpus-writer premise", not re.search(r"write_corpus writes demonstrations only", low))
need("C6d no raw lane-digest halt", "PIN-NONDETERMINISTIC-LANES" not in doc or re.search(r"mask", low))

# ---- C7 real engine
need("C7 meta_induction lines", all(s in doc for s in ("550", "378", "455")) and "meta_induction" in doc)
need("C7 infrastructure evidence only", "infrastructure evidence" in low)
need("C7 meta_v21 additivity not verified", re.search(r"meta_v21[^.]{0,200}not verified|not verified[^.]{0,200}meta_v21", low))

# ---- C8 additive
need("C8 K_PLUS_E", "K_PLUS_E" in doc)
need("C8 ADDITIVE_INSTALL_PATH_UNAVAILABLE", "ADDITIVE_INSTALL_PATH_UNAVAILABLE" in doc)
need("C8 additivity preflight", "additivity preflight" in low)
need("C8 never suppress", re.search(r"never suppress", low))

# ---- C9 legs and statuses
for leg in ("baseline_K_fails", "production_proposed", "winner_uses_production",
            "full_adaptive_LOO_passes", "final_output_correct", "ablation_without_e_fails"):
    need(f"C9 leg {leg}", leg in doc)
for status in ("PASS", "FAIL", "INCONCLUSIVE", "CHECKER_ERROR", "RESOURCE_EXHAUSTED", "NOT_MEASURED"):
    need(f"C9 status {status}", status in doc)
need("C9 new instrumentation acknowledged", "record_tti_ablation" in doc and "test_output_correct" in doc)
need("C9 verdict codes", all(v in doc for v in ("CAPABILITY-GROWTH-WITNESS", "WITNESS-REFUTED", "WITNESS-INCONCLUSIVE")))

# ---- C10 adaptive LOO
need("C10 FULL_ADAPTIVE_LOO_UNAVAILABLE", "FULL_ADAPTIVE_LOO_UNAVAILABLE" in doc)
need("C10 target-dependent rule", "target-dependent" in low)
need("C10 v1 fixed-extension caveat not the definition",
     "Re-invention of the extension inside folds was not tested" not in doc)

# ---- C11, C12
need("C11 admission section", re.search(r"^#+\s*\d*\.?\s*admission to e_transfer", doc, re.I | re.M))
need("C12 WITNESS_SUBSTRATE_INCOMPLETE", "WITNESS_SUBSTRATE_INCOMPLETE" in doc)
need("C12 substrate section", re.search(r"^#+\s*\d*\.?\s*the substrate decision tree", doc, re.I | re.M))

# ---- C13 guard facts
need("C13 firewall at stage 7", re.search(r"firewall[^.]{0,250}(stage 7|g7)", low))
need("C13 worktree copies non-authoritative", re.search(r"worktree cop", low))

# ---- C14 seven fields
licensed = len(re.findall(r"claim licensed", low))
not_licensed = len(re.findall(r"claim not licensed|claims not licensed|does not license", low))
need("C14 'claim licensed' per stage (>= 11)", licensed >= 11, f"{licensed} found")
need("C14 'claim NOT licensed' per stage (>= 11)", not_licensed >= 11, f"{not_licensed} found")

# ---- C15, C16
need("C15 sealed number", "185/1000" in doc)
need("C15 rejected defects section", re.search(r"^#+\s*\d*\.?\s*rejected defects", doc, re.I | re.M))
need("C15 forbidden phrasings kept", "forbidden phrasing" in low)
need("C16 implementation status section", re.search(r"^#+\s*\d*\.?\s*implementation status", doc, re.I | re.M))
need("C16 61 tests", re.search(r"\b61 tests\b", low))

# ---- structure
headings = re.findall(r"^## (\d+)\.", doc, re.M)
need("structure 22 numbered sections", len(headings) >= 22, f"{len(headings)} numbered level-2 sections")

failed = [r for r in results if not r[1]]
for label, ok, detail in results:
    if not ok:
        print(f"  MISSING  {label}  {detail}")
print(f"\n{len(results) - len(failed)}/{len(results)} checks pass")
sys.exit(1 if failed else 0)
