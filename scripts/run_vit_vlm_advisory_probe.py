#!/usr/bin/env python3
"""
ViT/VLM Advisory Probe Experiment
==================================

Evaluates whether a frozen vision model (DINOv2-small via timm) can improve
perception, routing, and operator-family prediction for the ARC reasoning
pipeline.  The VLM/ViT is advisory only: it proposes candidate explanations
that the symbolic pipeline must still validate through train consistency,
LOO, proof obligations, falsification, and certificates.

Outputs:
  summary.md
  results.csv
  operator_family_predictions.csv
  object_change_predictions.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Lazy imports for heavy libs (torch, timm, sklearn) -- imported at use-site
# ---------------------------------------------------------------------------

logger = logging.getLogger("vit_advisory_probe")

# ----------------------------- ARC colour map ------------------------------
ARC_COLORS = {
    0: (0, 0, 0),        # black
    1: (0, 116, 217),    # blue
    2: (255, 65, 54),    # red
    3: (46, 204, 64),    # green
    4: (255, 220, 0),    # yellow
    5: (170, 170, 170),  # gray
    6: (240, 18, 190),   # magenta
    7: (255, 133, 27),   # orange
    8: (127, 219, 255),  # cyan
    9: (135, 12, 37),    # maroon
}

# Promoted tasks (the 4 validated promotions)
PROMOTED_TASKS = ["d89b689b", "e9ac8c9e", "a48eeaf7", "2a5f8217"]

# Operator family label set
OPERATOR_FAMILIES = [
    "copy_to_position",
    "quadrant_fill",
    "project_to_halo",
    "color_transfer",
    "variable_destination",
    "shape_completion",
    "many_to_few",
    "fill",
    "recolor_in_place",
    "other",
    "unknown",
]

# Object change type label set
CHANGE_TYPES = [
    "removed",
    "recolored",
    "moved",
    "copied",
    "shape_changed",
    "filled",
    "no_change",
]

# ----------------------------- Grid rendering ------------------------------

def render_grid_image(
    grid: List[List[int]],
    cell_size: int = 10,
    border: int = 1,
) -> Image.Image:
    """Render an ARC grid as a PIL Image with coloured blocks."""
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    w = cols * cell_size + (cols + 1) * border
    h = rows * cell_size + (rows + 1) * border
    img = Image.new("RGB", (w, h), (40, 40, 40))  # dark gray border bg
    pixels = img.load()
    for r in range(rows):
        for c in range(cols):
            color = ARC_COLORS.get(grid[r][c], (128, 128, 128))
            y0 = border + r * (cell_size + border)
            x0 = border + c * (cell_size + border)
            for dy in range(cell_size):
                for dx in range(cell_size):
                    pixels[x0 + dx, y0 + dy] = color
    return img


def render_pair_image(
    input_grid: List[List[int]],
    output_grid: List[List[int]],
    cell_size: int = 10,
    gap: int = 10,
) -> Image.Image:
    """Render input and output side-by-side with a gap."""
    img_in = render_grid_image(input_grid, cell_size)
    img_out = render_grid_image(output_grid, cell_size)
    w = img_in.width + gap + img_out.width
    h = max(img_in.height, img_out.height)
    canvas = Image.new("RGB", (w, h), (20, 20, 20))
    canvas.paste(img_in, (0, 0))
    canvas.paste(img_out, (img_in.width + gap, 0))
    return canvas


# ------------------- Image pre-processing for ViT -------------------------

def preprocess_for_vit(img: Image.Image, target_size: int = 224):
    """Resize, normalize, convert to tensor (C, H, W)."""
    import torch
    img_resized = img.resize((target_size, target_size), Image.BILINEAR)
    arr = np.array(img_resized, dtype=np.float32) / 255.0
    # ImageNet normalization
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    tensor = torch.from_numpy(arr).permute(2, 0, 1)  # (3, H, W)
    return tensor


# --------------------- Feature extractor wrapper ---------------------------

class ViTFeatureExtractor:
    """Frozen DINOv2-small feature extractor via timm."""

    def __init__(self, device: str = "cpu", model_name: str | None = None):
        import timm
        import torch

        self.device = torch.device(device)
        # Try DINOv2-small from timm; fall back to generic small ViT
        candidates = [
            model_name,
            "vit_small_patch14_dinov2.lvd142m",
            "vit_small_patch14_dinov2",
            "vit_small_patch16_224.dino",
            "vit_small_patch16_224",
        ]
        self.model = None
        self.model_name_used = None
        for cand in candidates:
            if cand is None:
                continue
            try:
                self.model = timm.create_model(cand, pretrained=True, num_classes=0)
                self.model_name_used = cand
                logger.info("Loaded ViT model: %s", cand)
                break
            except Exception:
                logger.debug("Model %s not available, trying next", cand)
        if self.model is None:
            raise RuntimeError(
                "No suitable ViT model found in timm. "
                "Available DINOv2 models: " + str(timm.list_models("*dinov2*"))
            )
        self.model.eval()
        self.model.to(self.device)

        # Determine input size from model config
        data_cfg = timm.data.resolve_model_data_config(self.model)
        self.input_size = data_cfg.get("input_size", (3, 224, 224))[-1]
        logger.info(
            "ViT ready: %s  input_size=%d  device=%s",
            self.model_name_used, self.input_size, self.device,
        )

    @property
    def embed_dim(self) -> int:
        return self.model.num_features

    def extract(self, img: Image.Image) -> np.ndarray:
        """Extract a 1-D feature vector from a PIL Image."""
        import torch
        tensor = preprocess_for_vit(img, self.input_size).unsqueeze(0).to(self.device)
        with torch.no_grad():
            feat = self.model(tensor)
        return feat.cpu().numpy().flatten()

    def extract_pair(
        self,
        input_grid: List[List[int]],
        output_grid: List[List[int]],
    ) -> np.ndarray:
        """Extract concatenated (input_feat || output_feat) vector."""
        f_in = self.extract(render_grid_image(input_grid))
        f_out = self.extract(render_grid_image(output_grid))
        return np.concatenate([f_in, f_out])

    def extract_single(self, grid: List[List[int]]) -> np.ndarray:
        return self.extract(render_grid_image(grid))


# --------------------- Data loading helpers --------------------------------

def load_arc_tasks(data_dir: str) -> Dict[str, Any]:
    """Load ARC training challenges + solutions, return merged dict."""
    challenges_path = os.path.join(data_dir, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(data_dir, "arc-agi_training_solutions.json")
    with open(challenges_path) as f:
        challenges = json.load(f)
    solutions = {}
    if os.path.exists(solutions_path):
        with open(solutions_path) as f:
            solutions = json.load(f)
    return challenges, solutions


def load_object_traces(path: str) -> Dict[str, Dict]:
    """Load object_traces.jsonl -> dict keyed by task_id."""
    traces = {}
    if not os.path.exists(path):
        logger.warning("object_traces.jsonl not found at %s", path)
        return traces
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            traces[rec["task_id"]] = rec
    return traces


def load_operator_gap_trace_csv(path: str) -> Dict[str, Dict]:
    """Load operator_gap_trace.csv -> dict keyed by task_id."""
    records = {}
    if not os.path.exists(path):
        logger.warning("operator_gap_trace.csv not found at %s", path)
        return records
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records[row["task_id"]] = row
    return records


def load_operator_gap_traces_jsonl(path: str) -> Dict[str, Dict]:
    """Load operator_gap_traces.jsonl -> dict keyed by task_id."""
    records = {}
    if not os.path.exists(path):
        logger.warning("operator_gap_traces.jsonl not found at %s", path)
        return records
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            records[rec["task_id"]] = rec
    return records


def load_near_solved_states(path: str) -> Dict[str, Dict]:
    """Load near_solved_states.jsonl -> dict keyed by task_id."""
    records = {}
    if not os.path.exists(path):
        logger.warning("near_solved_states.jsonl not found at %s", path)
        return records
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            records[rec["task_id"]] = rec
    return records


def load_promotion_audit(path: str) -> Dict[str, Dict]:
    """Load final_promotion_chain_audit.csv -> dict keyed by task_id."""
    records = {}
    if not os.path.exists(path):
        logger.warning("promotion audit not found at %s", path)
        return records
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records[row["task_id"]] = row
    return records


# --------------------- Label derivation ------------------------------------

def derive_change_type(obj_trace: Dict) -> str:
    """Derive dominant change type from an object_traces record."""
    ft = obj_trace.get("failure_type", "")
    op_family = obj_trace.get("operator_gap_family", "unknown")

    # Check for rich change types in near-solved traces
    if "rich_change_types" in str(obj_trace):
        pass  # handled below

    if ft == "size_change":
        return "shape_changed"
    if ft == "no_classification":
        return "no_change"

    # Heuristic from reconstruction similarity
    recon_sim = obj_trace.get("reconstruction_similarity", 0.0)
    if recon_sim > 0.95:
        return "removed"
    if recon_sim > 0.8:
        return "recolored"
    if op_family == "copy_to_position":
        return "copied"

    # Default
    if recon_sim > 0.5:
        return "moved"
    return "shape_changed"


def derive_operator_family(
    obj_trace: Dict,
    gap_trace: Optional[Dict] = None,
    promotion: Optional[Dict] = None,
) -> str:
    """Derive operator family label from available traces."""
    # Promotion records have explicit family
    if promotion and "operator_family" in promotion:
        fam = promotion["operator_family"]
        if fam in OPERATOR_FAMILIES:
            return fam
        # Map compound names
        if "copy_to_position" in fam:
            return "copy_to_position"
        if "color_transfer" in fam or "recolor" in fam:
            return "color_transfer"
        return "other"

    # Operator gap trace (CSV or JSONL) has needed_operator_family or operator_family
    if gap_trace:
        fam = gap_trace.get("needed_operator_family", gap_trace.get("operator_family", "unknown"))
        if fam in OPERATOR_FAMILIES:
            return fam
        if "copy" in str(fam):
            return "copy_to_position"
        if "recolor" in str(fam):
            return "color_transfer"
        if "fill" in str(fam).lower():
            return "fill"
        if "shape" in str(fam):
            return "shape_completion"
        return "other"

    # Object trace has operator_gap_family
    fam = obj_trace.get("operator_gap_family", "unknown")
    if fam in OPERATOR_FAMILIES:
        return fam
    return "unknown"


# ---------------------- Probe classifiers ----------------------------------

def train_probe(X_train, y_train, n_classes: int, probe_type: str = "mlp"):
    """Train a lightweight probe. Returns (model, label_encoder)."""
    from sklearn.preprocessing import LabelEncoder
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    le = LabelEncoder()
    y_enc = le.fit_transform(y_train)

    unique_classes = len(set(y_enc))
    if unique_classes < 2:
        logger.warning("Only %d class(es) -- probe will be trivial", unique_classes)

    if probe_type == "mlp":
        clf = Pipeline([
            ("scaler", StandardScaler()),
            ("mlp", MLPClassifier(
                hidden_layer_sizes=(128, 64),
                max_iter=500,
                early_stopping=True,
                validation_fraction=0.15,
                random_state=42,
                learning_rate_init=0.001,
            )),
        ])
    else:
        clf = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(
                max_iter=1000,
                solver="lbfgs",
                random_state=42,
                C=1.0,
            )),
        ])

    try:
        clf.fit(X_train, y_enc)
    except Exception as e:
        logger.warning("Probe training failed: %s  -- falling back to logistic", e)
        clf = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(
                max_iter=2000,
                solver="lbfgs",
                random_state=42,
            )),
        ])
        clf.fit(X_train, y_enc)

    return clf, le


def evaluate_probe(clf, le, X_test, y_test) -> Dict[str, Any]:
    """Evaluate a probe. Returns accuracy, per-class metrics."""
    from sklearn.metrics import classification_report, accuracy_score
    import numpy as np

    known_classes = set(le.classes_)
    mask = np.array([y in known_classes for y in y_test])
    if mask.sum() == 0:
        return {
            "accuracy": 0.0,
            "report": {},
            "predictions": ["unknown"] * len(y_test),
            "ground_truth": list(y_test),
            "skipped_unseen": int((~mask).sum()),
        }
    X_eval = X_test[mask]
    y_eval = [y for y, m in zip(y_test, mask) if m]
    y_enc = le.transform(y_eval)
    y_pred = clf.predict(X_eval)
    acc = accuracy_score(y_enc, y_pred)
    report = classification_report(
        y_enc, y_pred,
        target_names=le.classes_,
        output_dict=True,
        zero_division=0,
    )
    all_preds = []
    j = 0
    for m in mask:
        if m:
            all_preds.append(le.inverse_transform([y_pred[j]])[0])
            j += 1
        else:
            all_preds.append("unseen_class")
    return {
        "accuracy": acc,
        "report": report,
        "predictions": all_preds,
        "ground_truth": list(y_test),
        "skipped_unseen": int((~mask).sum()),
    }


def nearest_neighbor_classify(
    X_train: np.ndarray,
    y_train: List[str],
    X_test: np.ndarray,
    k: int = 3,
) -> List[str]:
    """Simple kNN classification when too few samples for a proper probe."""
    from sklearn.metrics.pairwise import cosine_similarity
    preds = []
    sims = cosine_similarity(X_test, X_train)
    for i in range(len(X_test)):
        top_k_idx = np.argsort(sims[i])[-k:]
        votes = [y_train[j] for j in top_k_idx]
        counter = Counter(votes)
        preds.append(counter.most_common(1)[0][0])
    return preds


# ---------------------- Source/target proposal quality ---------------------

def compute_source_target_features(
    extractor: "ViTFeatureExtractor",
    input_grid: List[List[int]],
) -> np.ndarray:
    """Extract features for source/target proposal from input grid only."""
    return extractor.extract_single(input_grid)


# ======================= Main experiment ===================================

def run_experiment(args):
    import torch

    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "arc"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ----- Determine device -----
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Device: %s", device)

    # ----- Load data -----
    logger.info("Loading ARC tasks...")
    challenges, solutions = load_arc_tasks(str(data_dir))
    all_task_ids = sorted(challenges.keys())
    logger.info("Total ARC training tasks: %d", len(all_task_ids))

    # ----- Load existing traces -----
    cache_fast_dir = base_dir / "outputs" / "cache_fast"
    obj_traces = load_object_traces(str(cache_fast_dir / "object_traces.jsonl"))
    near_solved = load_near_solved_states(str(cache_fast_dir / "near_solved_states.jsonl"))
    gap_traces_jsonl = load_operator_gap_traces_jsonl(
        str(cache_fast_dir / "operator_gap_traces.jsonl")
    )
    gap_traces_csv = load_operator_gap_trace_csv(
        str(base_dir / "outputs" / "operator_gap_analysis_v3" / "operator_gap_trace.csv")
    )
    promotions = load_promotion_audit(
        str(base_dir / "outputs" / "operator_reasoning_phase"
            / "final_promotion_chain_audit.csv")
    )

    logger.info(
        "Traces loaded: obj=%d  near_solved=%d  gap_jsonl=%d  gap_csv=%d  promotions=%d",
        len(obj_traces), len(near_solved), len(gap_traces_jsonl),
        len(gap_traces_csv), len(promotions),
    )

    # ----- Build evaluation subset -----
    eval_task_ids = set(PROMOTED_TASKS)

    # Add tasks from operator gap trace CSV (rejected = not promoted)
    rejected_from_gap = set(gap_traces_csv.keys()) - set(PROMOTED_TASKS)
    eval_task_ids |= rejected_from_gap

    # Add random tasks
    remaining = [t for t in all_task_ids if t not in eval_task_ids]
    random.seed(42)
    n_random = min(args.max_tasks, len(remaining))
    random_tasks = set(random.sample(remaining, n_random))
    eval_task_ids |= random_tasks

    # Intersect with what we actually have in challenges
    eval_task_ids = sorted([t for t in eval_task_ids if t in challenges])
    logger.info("Evaluation subset: %d tasks (%d promoted, %d gap-rejected, %d random)",
                len(eval_task_ids), len(PROMOTED_TASKS),
                len(rejected_from_gap), len(random_tasks))

    # ----- Load feature extractor -----
    logger.info("Loading ViT feature extractor...")
    extractor = ViTFeatureExtractor(device=device, model_name=args.model_name)
    feat_dim = extractor.embed_dim
    logger.info("Feature dim: %d (per grid), pair dim: %d", feat_dim, feat_dim * 2)

    # ----- Extract features and labels -----
    logger.info("Extracting features for %d tasks...", len(eval_task_ids))
    task_features = {}      # task_id -> list of pair features (one per train pair)
    task_change_labels = {} # task_id -> change type
    task_opfam_labels = {}  # task_id -> operator family
    task_input_features = {} # task_id -> list of input-only features

    for i, tid in enumerate(eval_task_ids):
        if (i + 1) % 20 == 0 or i == 0:
            logger.info("  Extracting features: %d/%d (task %s)", i + 1, len(eval_task_ids), tid)

        task_data = challenges[tid]
        train_pairs = task_data.get("train", [])
        if not train_pairs:
            continue

        pair_feats = []
        input_feats = []
        for pair in train_pairs:
            inp = pair["input"]
            out = pair["output"]
            pf = extractor.extract_pair(inp, out)
            pair_feats.append(pf)
            inf = extractor.extract_single(inp)
            input_feats.append(inf)

        # Average across train pairs for a single task-level representation
        task_features[tid] = np.mean(pair_feats, axis=0)
        task_input_features[tid] = np.mean(input_feats, axis=0)

        # Derive labels
        obj_tr = obj_traces.get(tid, {})
        gap_tr = gap_traces_jsonl.get(tid) or gap_traces_csv.get(tid)
        promo = promotions.get(tid)

        task_change_labels[tid] = derive_change_type(obj_tr) if obj_tr else "no_change"
        task_opfam_labels[tid] = derive_operator_family(obj_tr, gap_tr, promo)

    labeled_tids = [t for t in eval_task_ids if t in task_features]
    logger.info("Tasks with features: %d", len(labeled_tids))

    # ----- Prepare training/test splits -----
    # Use 80/20 split (or LOO for very small sets)
    random.seed(42)
    shuffled = list(labeled_tids)
    random.shuffle(shuffled)
    split_idx = max(1, int(0.8 * len(shuffled)))
    train_tids = shuffled[:split_idx]
    test_tids = shuffled[split_idx:]

    # Ensure promoted tasks are in test set for evaluation
    for pt in PROMOTED_TASKS:
        if pt in train_tids and pt in labeled_tids:
            train_tids.remove(pt)
            if pt not in test_tids:
                test_tids.append(pt)

    logger.info("Train: %d tasks, Test: %d tasks", len(train_tids), len(test_tids))

    # Build arrays
    X_train = np.array([task_features[t] for t in train_tids])
    X_test = np.array([task_features[t] for t in test_tids])

    # ===== Probe 1: Object-change classifier =====
    logger.info("--- Probe 1: Object-change classifier ---")
    y_train_change = [task_change_labels[t] for t in train_tids]
    y_test_change = [task_change_labels[t] for t in test_tids]

    change_class_counts = Counter(y_train_change)
    logger.info("  Train class distribution: %s", dict(change_class_counts))

    if len(set(y_train_change)) >= 2 and len(train_tids) >= 10:
        probe_type = "mlp" if len(train_tids) >= 30 else "logistic"
        change_clf, change_le = train_probe(
            X_train, y_train_change, len(CHANGE_TYPES), probe_type=probe_type
        )
        change_results = evaluate_probe(change_clf, change_le, X_test, y_test_change)
    else:
        logger.info("  Too few classes/samples for probe -- using kNN")
        preds = nearest_neighbor_classify(X_train, y_train_change, X_test, k=3)
        correct = sum(1 for p, g in zip(preds, y_test_change) if p == g)
        change_results = {
            "accuracy": correct / max(len(preds), 1),
            "predictions": preds,
            "ground_truth": y_test_change,
            "report": {},
        }

    logger.info("  Object-change accuracy: %.4f", change_results["accuracy"])

    # ===== Probe 2: Operator-family prediction =====
    logger.info("--- Probe 2: Operator-family prediction ---")
    y_train_opfam = [task_opfam_labels[t] for t in train_tids]
    y_test_opfam = [task_opfam_labels[t] for t in test_tids]

    opfam_class_counts = Counter(y_train_opfam)
    logger.info("  Train class distribution: %s", dict(opfam_class_counts))

    if len(set(y_train_opfam)) >= 2 and len(train_tids) >= 10:
        probe_type = "mlp" if len(train_tids) >= 30 else "logistic"
        opfam_clf, opfam_le = train_probe(
            X_train, y_train_opfam, len(OPERATOR_FAMILIES), probe_type=probe_type
        )
        opfam_results = evaluate_probe(opfam_clf, opfam_le, X_test, y_test_opfam)
    else:
        logger.info("  Too few classes/samples for probe -- using kNN")
        preds = nearest_neighbor_classify(X_train, y_train_opfam, X_test, k=3)
        correct = sum(1 for p, g in zip(preds, y_test_opfam) if p == g)
        opfam_results = {
            "accuracy": correct / max(len(preds), 1),
            "predictions": preds,
            "ground_truth": y_test_opfam,
            "report": {},
        }

    logger.info("  Operator-family accuracy: %.4f", opfam_results["accuracy"])

    # ===== Probe 3: Source/target proposal quality =====
    logger.info("--- Probe 3: Source/target proposal quality ---")
    # Use near-solved states to see if ViT features can predict which
    # tasks have good selector decisions (classification found vs not)
    X_input_train = np.array([task_input_features[t] for t in train_tids])
    X_input_test = np.array([task_input_features[t] for t in test_tids])

    # Binary: does the task have a discriminative property (selector works)?
    def has_selector(tid):
        ns = near_solved.get(tid, {})
        # Check best_hypothesis
        bh = ns.get("best_hypothesis")
        if bh and isinstance(bh, dict) and bh.get("property"):
            return "selector_works"
        ot = obj_traces.get(tid, {})
        if ot.get("discriminative_property"):
            return "selector_works"
        has_cls = ot.get("has_classification", [])
        if any(has_cls):
            return "selector_works"
        return "no_selector"

    y_train_sel = [has_selector(t) for t in train_tids]
    y_test_sel = [has_selector(t) for t in test_tids]

    sel_class_counts = Counter(y_train_sel)
    logger.info("  Selector train distribution: %s", dict(sel_class_counts))

    if len(set(y_train_sel)) >= 2 and len(train_tids) >= 10:
        probe_type = "logistic"  # binary task, keep simple
        sel_clf, sel_le = train_probe(
            X_input_train, y_train_sel, 2, probe_type=probe_type
        )
        sel_results = evaluate_probe(sel_clf, sel_le, X_input_test, y_test_sel)
    else:
        logger.info("  Too few classes/samples for selector probe -- using kNN")
        preds = nearest_neighbor_classify(X_input_train, y_train_sel, X_input_test, k=3)
        correct = sum(1 for p, g in zip(preds, y_test_sel) if p == g)
        sel_results = {
            "accuracy": correct / max(len(preds), 1),
            "predictions": preds,
            "ground_truth": y_test_sel,
            "report": {},
        }

    logger.info("  Selector-quality accuracy: %.4f", sel_results["accuracy"])

    # ===== Per-task breakdown for promoted tasks =====
    promoted_breakdown = {}
    for pt in PROMOTED_TASKS:
        if pt not in task_features:
            promoted_breakdown[pt] = {"status": "no_features"}
            continue
        idx_in_test = test_tids.index(pt) if pt in test_tids else None
        entry = {
            "in_test_set": idx_in_test is not None,
            "gt_change_type": task_change_labels.get(pt, "?"),
            "gt_operator_family": task_opfam_labels.get(pt, "?"),
            "gt_selector": has_selector(pt),
        }
        if idx_in_test is not None:
            entry["pred_change_type"] = change_results["predictions"][idx_in_test]
            entry["pred_operator_family"] = opfam_results["predictions"][idx_in_test]
            entry["pred_selector"] = sel_results["predictions"][idx_in_test]
            entry["change_correct"] = entry["pred_change_type"] == entry["gt_change_type"]
            entry["opfam_correct"] = entry["pred_operator_family"] == entry["gt_operator_family"]
            entry["selector_correct"] = entry["pred_selector"] == entry["gt_selector"]
        promoted_breakdown[pt] = entry

    # ===== Identify helpful vs hallucination cases =====
    helpful_cases = []
    hallucination_cases = []

    for i, tid in enumerate(test_tids):
        pred_opfam = opfam_results["predictions"][i]
        gt_opfam = opfam_results["ground_truth"][i]
        pred_change = change_results["predictions"][i]
        gt_change = change_results["ground_truth"][i]

        # Check near-solved status
        ns = near_solved.get(tid, {})
        existing_status = ns.get("status", "unknown")
        existing_score = ns.get("hypothesis_score", 0.0)

        # Helpful: ViT correct, existing system failed or was slow
        if pred_opfam == gt_opfam and existing_status in ("partial",) and gt_opfam != "unknown":
            helpful_cases.append({
                "task_id": tid,
                "pred_opfam": pred_opfam,
                "gt_opfam": gt_opfam,
                "existing_status": existing_status,
                "reason": "correct_family_prediction_for_partial_task",
            })

        # Hallucination: ViT confidently wrong
        if pred_opfam != gt_opfam and gt_opfam != "unknown" and pred_opfam != "unknown":
            hallucination_cases.append({
                "task_id": tid,
                "pred_opfam": pred_opfam,
                "gt_opfam": gt_opfam,
                "reason": "wrong_family_prediction",
            })

    # ===== Write results CSVs =====
    logger.info("Writing output files...")

    # results.csv -- per-task summary
    with open(output_dir / "results.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "task_id", "split", "gt_change_type", "pred_change_type", "change_correct",
            "gt_operator_family", "pred_operator_family", "opfam_correct",
            "gt_selector", "pred_selector", "selector_correct",
            "is_promoted", "existing_status",
        ])
        for i, tid in enumerate(test_tids):
            ns = near_solved.get(tid, {})
            writer.writerow([
                tid, "test",
                change_results["ground_truth"][i],
                change_results["predictions"][i],
                change_results["predictions"][i] == change_results["ground_truth"][i],
                opfam_results["ground_truth"][i],
                opfam_results["predictions"][i],
                opfam_results["predictions"][i] == opfam_results["ground_truth"][i],
                sel_results["ground_truth"][i],
                sel_results["predictions"][i],
                sel_results["predictions"][i] == sel_results["ground_truth"][i],
                tid in PROMOTED_TASKS,
                ns.get("status", "unknown"),
            ])

    # operator_family_predictions.csv
    with open(output_dir / "operator_family_predictions.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["task_id", "ground_truth", "prediction", "correct"])
        for i, tid in enumerate(test_tids):
            gt = opfam_results["ground_truth"][i]
            pred = opfam_results["predictions"][i]
            writer.writerow([tid, gt, pred, gt == pred])

    # object_change_predictions.csv
    with open(output_dir / "object_change_predictions.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["task_id", "ground_truth", "prediction", "correct"])
        for i, tid in enumerate(test_tids):
            gt = change_results["ground_truth"][i]
            pred = change_results["predictions"][i]
            writer.writerow([tid, gt, pred, gt == pred])

    # ===== Write summary.md =====
    with open(output_dir / "summary.md", "w") as f:
        f.write("# ViT/VLM Advisory Probe -- Experiment Summary\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Model: {extractor.model_name_used}\n")
        f.write(f"Device: {device}\n")
        f.write(f"Feature dim: {feat_dim} (per grid), {feat_dim*2} (pair)\n")
        f.write(f"Total eval tasks: {len(eval_task_ids)}\n")
        f.write(f"Train/test split: {len(train_tids)}/{len(test_tids)}\n\n")

        f.write("## Overall Probe Accuracy\n\n")
        f.write(f"| Probe | Accuracy |\n")
        f.write(f"|-------|----------|\n")
        f.write(f"| Object-change classifier | {change_results['accuracy']:.4f} |\n")
        f.write(f"| Operator-family prediction | {opfam_results['accuracy']:.4f} |\n")
        f.write(f"| Source/target proposal (selector) | {sel_results['accuracy']:.4f} |\n\n")

        f.write("## Class Distributions (training set)\n\n")
        f.write("### Object-change types\n")
        for k, v in sorted(change_class_counts.items(), key=lambda x: -x[1]):
            f.write(f"- {k}: {v}\n")
        f.write("\n### Operator families\n")
        for k, v in sorted(opfam_class_counts.items(), key=lambda x: -x[1]):
            f.write(f"- {k}: {v}\n")
        f.write("\n### Selector quality\n")
        for k, v in sorted(sel_class_counts.items(), key=lambda x: -x[1]):
            f.write(f"- {k}: {v}\n")

        f.write("\n## Per-task Breakdown: Promoted Tasks\n\n")
        for pt in PROMOTED_TASKS:
            entry = promoted_breakdown.get(pt, {})
            f.write(f"### {pt}\n")
            if entry.get("status") == "no_features":
                f.write("  (no features extracted)\n\n")
                continue
            for k, v in entry.items():
                f.write(f"- {k}: {v}\n")
            f.write("\n")

        f.write("## Helpful Cases\n\n")
        f.write(f"Found {len(helpful_cases)} case(s) where ViT prediction could help routing:\n\n")
        for hc in helpful_cases[:20]:
            f.write(f"- **{hc['task_id']}**: predicted `{hc['pred_opfam']}` "
                    f"(correct), existing status=`{hc['existing_status']}`\n")

        f.write("\n## Hallucination / Failure Cases\n\n")
        f.write(f"Found {len(hallucination_cases)} case(s) of confidently wrong predictions:\n\n")
        for hc in hallucination_cases[:20]:
            f.write(f"- **{hc['task_id']}**: predicted `{hc['pred_opfam']}`, "
                    f"ground truth=`{hc['gt_opfam']}`\n")

        f.write("\n## Routing Assessment\n\n")
        n_helpful = len(helpful_cases)
        n_halluc = len(hallucination_cases)
        n_test = len(test_tids)
        f.write(f"- Potentially helpful routing: {n_helpful}/{n_test} "
                f"({100*n_helpful/max(n_test,1):.1f}%)\n")
        f.write(f"- Hallucinated/wrong predictions: {n_halluc}/{n_test} "
                f"({100*n_halluc/max(n_test,1):.1f}%)\n")
        f.write(f"- Net advisory value: {'POSITIVE' if n_helpful > n_halluc else 'NEGATIVE or NEUTRAL'}\n\n")

        f.write("## Unsupported Claims Check\n\n")
        f.write("The ViT advisory probe does NOT generate final answers. "
                "All predictions are operator-family or change-type labels that the "
                "symbolic pipeline must still validate through:\n")
        f.write("- Train consistency checks\n")
        f.write("- Leave-one-out validation\n")
        f.write("- Proof obligations\n")
        f.write("- Falsification probes\n")
        f.write("- Certificate emission\n\n")
        f.write("No unsupported claims are introduced by this advisory probe, "
                "as it only proposes candidates for downstream validation.\n")

    logger.info("Experiment complete. Outputs in %s", output_dir)
    logger.info("  summary.md")
    logger.info("  results.csv")
    logger.info("  operator_family_predictions.csv")
    logger.info("  object_change_predictions.csv")

    return {
        "change_accuracy": change_results["accuracy"],
        "opfam_accuracy": opfam_results["accuracy"],
        "selector_accuracy": sel_results["accuracy"],
        "n_helpful": len(helpful_cases),
        "n_hallucination": len(hallucination_cases),
    }


# ============================= CLI =========================================

def parse_args():
    p = argparse.ArgumentParser(
        description="ViT/VLM Advisory Probe for ARC reasoning pipeline"
    )
    p.add_argument(
        "--output-dir", type=str,
        default="outputs/vit_vlm_advisory_probe",
        help="Directory for output files",
    )
    p.add_argument(
        "--max-tasks", type=int, default=50,
        help="Maximum number of random tasks to include (beyond promoted + gap tasks)",
    )
    p.add_argument(
        "--model-name", type=str, default=None,
        help="Specific timm model name (default: auto-select DINOv2-small)",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Enable debug logging",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    results = run_experiment(args)
    print("\n=== Final Results ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
