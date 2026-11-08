# Protocol U5: a literature-derived bioimage operator grammar, admitted from the frozen CORA component's own failures, used under verify-or-abstain, and tested for transfer (PRE-REGISTERED before download)

Written and committed on 2 Nov 2026, before any dataset in section 3 was downloaded and before any outcome. Its sha256
is recorded in `MANIFEST_FREEZE.json`. The protocol is not changed after any result. Changes made before an evaluation
outcome go in dated, hashed amendments; deviations go in a dated section of the result record.

## 1. Question and hypotheses

**Question.** Does CORA's design (typed object programs, used only when they reproduce the demonstrations and survive
leave-one-out re-derivation, otherwise abstain) generalize to biological image segmentation when its language is
extended by operators that (a) come from the published bioimage literature and (b) are admitted only where the frozen
CORA component's own failure records on calibration images show that it cannot express the needed correction? And
does a grammar induced on one dataset transfer, frozen, to datasets of other modalities?

- **H1, usefulness.** On held-out parents of the induction dataset A, the failure-grounded grammar under CORA's
  verify-or-abstain rule raises object F1 above the strong native baseline and above matched static comparators.
- **H2, transfer.** The grammar and policy induced on A, frozen and applied unchanged to datasets B and C (using only
  their calibration images as demonstrations), raise object F1 on held-out parents of B and C above the same controls.
- **H3, failure evidence.** The gain depends on the failure evidence: it exceeds the failure-blind and the
  shuffled-record controls.

Four claims are kept apart throughout (section 14): portability (the procedure runs unchanged), cross-domain usefulness
(it improves strong baselines on held-out parents), learned transfer (what was induced on A helps B and C), and grammar
growth (gates a to e of section 14.4). Results are reported whichever way they fall.

## 2. What earlier studies showed, and what U5 changes

Read before writing: `records/NOV1_UNIVERSALITY_AUDIT_FOR_SUBMITTED_SYSTEM.md` (section 2),
`records/GRAMMAR_INDUCTION_DOMAIN{1,2,3}_*_20261026.md`, `records/NOV1_UNIVERSALITY_RESULT.md`, and U4's protocol,
amendment and scripts (`experiments/universality_fresh_image_20261103/`; its runs were not touched).

| earlier finding | cause, as recorded | what U5 does instead |
|---|---|---|
| Grammar induction accepted no production in any of three domains | productions were typed lambdas whose semantics is inlining of existing primitives, so they added no expressive power; in domain 1 the search reached the same fit without them ("the production is never needed") | candidate operators are new primitives with new effect classes (split, merge, boundary change, hole filling, re-detection), each taken from the literature, and an operator is a candidate only where probes of the frozen component show it cannot express that class (section 8); an alias check (section 9) rejects operators whose edits existing operators reproduce |
| The growth penalty (lambda = 0.02 per node) required 4 to 6% residual reduction; the best symbolic candidate gave 0.15 to 0.34% | a fixed MDL-style penalty far above the achievable effect sizes | specification requires a measured oracle gain of the error class on induction parents (at least 0.005 pooled F1), and admission is decided on separate validation parents by the sign of the paired change, calibrated to the effect sizes that exist |
| Language-model proposers wrote malformed productions (type names as parameters, signature notation in heads) | free-text generation of programs | no free-text proposer in this lane; candidates are typed operator instances enumerated exhaustively; the independent team's neural proposer must emit schema-checked typed JSON (section 15) |
| Diagnosis-guided probes returned INVALID; slot budgets were matched but actual compute was not (auditor BLOCKED) | probe generation through the adapter's checks; unmeasured compute | failure records come from the frozen packages' own module evidence on typed calibration probes; every arm's CPU is measured, and the matched-search comparator receives CORA's measured CPU |
| Domain 1 had no failure left to repair | the initial grammar already fitted | a calibration gate requires measured headroom before induction (section 6) |
| StarDist plus a sibling repair gained +0.014 F1, but blind and shuffled orders found the same edit | the winning edit (delete dim objects) was one of the adapter's own candidates; any order found it | the strong native baseline already contains the best single-feature deletion filter, so deletion is not counted as a gain of the grammar; failure-blind and shuffled controls repeat the whole admission with 5 seeds each |
| The submitted packages on S-BSST265 (U1): under B3 no edit; under O's rule 7 deletions, 4 wrong; a tuned filter did better | the frozen component can express only whole-object deletion and recolouring on these tasks | U5 asks what the frozen component cannot express, and supplies exactly that, under the same acceptance discipline |

## 3. Datasets (chosen and justified before any download)

### 3.1 Primary datasets, in a fixed order

| order | dataset | modality | source | file and size | licence | baseline segmenter and its documented training data |
|---|---|---|---|---|---|---|
| D1 | LIVECell (Edlund et al. 2021, Nat Methods 18:1038) | phase contrast, 8 cell lines | `http://livecell-dataset.s3.eu-central-1.amazonaws.com/LIVECell_dataset_2021/`: `images.zip` (1,241,715,651 bytes) and `annotations/LIVECell/livecell_coco_test.json` | as listed | CC BY-NC 4.0 (images and annotations); allows non-commercial research use, including evaluation; nothing is redistributed | Cellpose 3.1.1.2 `cyto2` (Stringer et al. 2021; Pachitariu and Stringer 2022): trained on the Cellpose dataset plus user-submitted images; LIVECell is not in it (LIVECell has its own Cellpose model, not used) |
| D2 | NuInsSeg (Mahbod et al. 2024, Sci Data) | H&E nuclei, 31 human and mouse organs, 40x | Zenodo 10.5281/zenodo.10518968, `NuInsSeg.zip` | 1,627,427,342 bytes, MD5 `08f9a33e23e983d82ee93aa58e69d095` | CC BY 4.0 | StarDist 0.9.2 `2D_versatile_he` (Schmidt et al. 2018): trained on MoNuSeg 2018 training data and TNBC (Naylor et al.); NuInsSeg is not in it |
| D3 | FluoEcoli-Instance v1 (Huynh et al. 2025, IEEE JSTSP 19(8):1967) | fluorescence, E. coli cells | Zenodo 10.5281/zenodo.23389427, `FluoEcoli-Instance.zip` | 2,422,943,929 bytes, MD5 `7014ab9749f6d96ae8dcf22efca86db0` | CC BY 4.0 | Cellpose 4.2.1.1 `cpsam_v2` (Pachitariu, Rariden and Stringer 2025), local weights sha256 `0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667`; released June 2026; the deposit is of 15 Oct 2026 and is not among Cellpose-SAM's documented training sets |

**Backup, used only if a primary dataset fails eligibility (section 3.3) or its calibration gate (section 6):**
Fluorescent Neuronal Cells v2, green collection (Clissa et al. 2024, Sci Data; AMS Acta eprint 7347, CC BY 4.0),
fluorescence c-FOS in rodent brain slices, objects from the released COCO polygons, baseline StarDist 0.9.2
`2D_versatile_fluo` (trained on a subset of DSB 2018; FNC is not in it). It replaces the first failing primary
dataset. The decision uses calibration data only.

**Why these:** three modalities (label-free phase contrast, brightfield histology, fluorescence), three object
classes (whole cells, nuclei, bacteria), three standard pretrained segmenters, licences that allow evaluation,
manual or expert instance annotations, and no use in any of our studies (checked against `records/` and the
experiment manifests after download, as in U4).

**Excluded** (scored before, reserved, or in a baseline's training data): BBBC039; S-BSST265 and its re-deposit
S-BIAD634; Aitslab_bioimaging1 and the EGFP-Galectin-3 set of the same fields (Zenodo 12193890); HeLaCytoNuc;
BBBC038/DSB 2018 (reserved for another of the author's studies by a decision record, and in StarDist's training data); MoNuSeg and
TNBC (StarDist H&E training data). Single-cell, spatial and perturbation data are out of scope here (the independent
team's lane).

**Download rules:** each archive goes into its own new folder under
`/path/to/bio_data/raw/`, is checked against the published size and MD5 where one is
published, and its sha256 is recorded in `DATA_MANIFEST.json` with provenance and licence text. Archives are read with
`python3 -I` only. Model weights go to `/path/to/bio_data/models/` with their sha256.
Licence gate: if a licence page states a term that forbids evaluation use, stop for that dataset and report.

### 3.2 Pools, inputs, objects and ignore regions

- **D1 LIVECell:** the pool is the official test split (`livecell_test_images`, `livecell_coco_test.json`). Input:
  the grey phase image. Objects: each annotation's polygon, rasterized in decreasing area order so that a smaller
  object drawn later keeps its pixels. Intensity image for features: the grey image normalized at (1, 99.8)
  percentiles and clipped to [0, 1].
- **D2 NuInsSeg:** the pool is all patches. Input: RGB, normalized at (1, 99.8) jointly over channels (StarDist's H&E
  usage). Objects: the released labelled (instance) masks. Intensity image: haematoxylin optical density from colour
  deconvolution (`skimage.color.rgb2hed`, channel 0; Ruifrok and Johnston 2001), normalized at (1, 99.8). Ignore
  regions: the released ambiguous-area masks; any reference or predicted object with at least half of its pixels in
  an ambiguous area is removed from both sides before matching, identically for every arm.
- **D3 FluoEcoli-Instance:** the pool is the official test split. Input: the fluorescence image (the first channel if
  several), normalized at (1, 99.8). Objects: COCO polygons, rasterized as for D1. Intensity image: the same
  normalized channel.
- **Caps (compute):** at most 720 images for D1 and 1,500 patches for D3, taken per parent in sha256 order of the
  file name, with an equal per-parent quota of max(1, floor(cap / number of parents)); D2 uses all patches.

### 3.3 Eligibility (mechanical; recorded before any mask beyond one format check is decoded)

A dataset is eligible if: its archive matches the published size (and MD5 where published); per-object instance
annotations decode for a first image; parent identifiers can be derived by the rule of section 4; and the split gives
at least 10 calibration and 15 evaluation parents (the induction dataset also needs at least 5 induction and 5
validation parents). The grouping is written to `DATA_MANIFEST.json` before any further mask is decoded.

### 3.4 The author's private data (folded in on 2 Nov, before this freeze)

The coordinator relayed the author's permission to use all datasets here, with these safeguards:
candidates are identified from project records only; each candidate's status records are read before any data;
a written third-party restriction stops that dataset; private results are aggregate only and labelled
"private data; not publicly reproducible"; no private image, mask, crop or per-image identifier enters a committed file
or a public path; derived files stay in a mode-0700 folder outside git; evaluation parents are never tuned on. Status
records read, and the decisions they imply:

| candidate | status records read | decision |
|---|---|---|
| a private image cohort of the author's | its project's protocol and annotation plan (unprocessed camera originals; annotation not done) and the record of the author's permission | **Not opened.** No reference annotation exists in the records, so no edit on it could be scored (object F1, AP, edit precision and harmful edits all need references). It stays untouched; no read time exists to log |
| protected third-party image data | its decision and permission records | **Stopped, not opened.** Its written third-party terms do not confirm this use, and an unconfirmed use is treated as prohibited. In addition its cell outlines are a vendor model's outputs, with no expert labels, so no human reference exists |
| the author's private annotated images | the project's decision records and the columns of its reference table | **Excluded as unclear.** The unexposed images are another study's evaluation set ("never for development"), and that study is running; the rest were used in training or fail a geometry check; no standard pretrained segmenter for them exists outside that program, which is out of bounds. Under the rule "unclear means excluded" none is read |
| the author's candidate selections for future annotation | file names only | Not usable: selections for future annotation, no masks |

If a private candidate's status changes before evaluation (for example, references are created), it can enter only by a
dated pre-outcome amendment, as an extra target domain under this protocol.

## 4. Parents, split and mask access

- **Parent:** the smallest acquisition unit above the single image such that no two parents image the same cells,
  derived from file names and archive structure only:
  - D1: (cell line, well, location), i.e. one field of view with all its time points and crops;
  - D2: the finest slide or patient unit the archive encodes, otherwise the organ folder (for example "human liver");
  - D3: the source full-size image of each patch, or a coarser acquisition unit (position, experiment) if the names
    encode one.
  The rule is applied mechanically and the grouping is recorded in `DATA_MANIFEST.json` before any further mask is
  decoded.
- **Split by parent:** parents in sha256 order of `"<dataset>:<parent id>"`; the first round(0.4 n) are CALIBRATION,
  the rest EVALUATION. On the induction dataset, calibration parents in sha256 order of `"induct:<parent id>"` are
  divided into INDUCTION (first floor(n_cal / 2)) and VALIDATION (the rest). The same division is made on B and C for
  the secondary in-domain arm.
- **Mask access:** calibration masks may be read for decisions. Evaluation masks are decoded only by the evaluator,
  after every arm's decisions are hashed in `DECISIONS_FROZEN.json` (the same guard as U4). Evaluation images are
  segmented only after the evaluation hold of section 17 is released.

## 5. Baselines and the start of every grammar arm

Per dataset, with the segmenters of section 3.1:
- **NATIVE:** the pretrained model at its default settings (StarDist: the model's own thresholds; Cellpose 3 cyto2:
  diameter from its size model, flow threshold 0.4, cell-probability threshold 0; Cellpose-SAM: diameter none, flow
  threshold 0.4, cell-probability threshold 0).
- **TUNED:** detection thresholds tuned on calibration images by pooled object F1: StarDist by its own
  `optimize_thresholds` (`save_to_json=False`); Cellpose by a grid of flow threshold {0.2, 0.4, 0.6, 0.8, 1.0} x
  cell-probability threshold {-3, -2, -1, 0, 1, 2}, masks recomputed from stored network outputs; ties go to the
  defaults, then to the lower thresholds.
- **STRONG_NATIVE:** TUNED minus the best single-feature deletion rule chosen on calibration, using U4's frozen C3
  grammar (`c3_rules` and `rule_deletes` of `experiments/universality_submitted_pkg_20261101/scripts/adapter.py`,
  sha256 `6e6f307c...`, unchanged; features from `bbbc039.Features` on the intensity image of section 3.2).
- **S, the start of every grammar arm, is STRONG_NATIVE.** ABSTAIN_ALL therefore equals STRONG_NATIVE by construction:
  every contrast "X minus ABSTAIN_ALL" is the value an arm adds on top of the strong native post-processing, and an
  arm that abstains everywhere scores exactly 0.

Network passes run on CPU, or on GPU 0 only under
`flock /path/to/repository/outputs/locks/gpu0.lock`; never GPU 1.

## 6. Calibration gate (per dataset; calibration split only; recorded before any evaluation)

Each object of S on calibration images is classified against the reference (definitions in section 8.1). Measured:
the error share (objects of S that are not matched at IoU > 0.5) and the oracle gain (pooled F1 after every
post-processing-correctable error is corrected from the reference: delete, split, merge and boundary classes, section
8.1, minus the pooled F1 of S). **Proceed only if the error share is at least 5% and the oracle gain at least 0.01.**
Otherwise the dataset is reported as unsuitable, no evaluation is run for it, and the backup of section 3.1 replaces
the first such primary dataset; if more datasets fail, the study continues with fewer, and says so. This ensures that
abstaining everywhere cannot pass as success.

**The induction dataset A** is the first dataset, in the order D1, D2, D3 (backup last), that is eligible and passes
its gate; the next two are B and C.

## 7. The literature grammar (typed; every operator cited)

**Types.** `Img`: the intensity image of section 3.2. `Lab`: an instance label image. `Unit`: what one edit acts on
(an object, a mutual-best pair of touching objects, or a candidate new object). `Guard`: a predicate on a unit's
features (true, one threshold predicate, or a conjunction of two predicates on different features). An operator has
type `(Lab, Img, Guard, theta) -> Lab`, acts on each selected unit locally, never overwrites another object's pixels,
and is given in a fixed canonical order (the order below).

**Unit features** (computed on the current segmentation, scale-free where possible): `area_rel` (area over the median
object area of the image), `intensity_rel` (mean intensity over the median object mean of the image), `contrast`
(mean inside minus mean in a 2-pixel outer ring free of other objects, over the image's intensity standard deviation),
`solidity`, `ecc` (as `bbbc039.Features`), `border` (touches the image edge), `n_neigh` (number of touching objects),
`hole_frac` (enclosed background over area), `n_cores` (number of h-maxima of the distance transform at the
operator's theta); pairs: `u_solidity`, `u_area_rel`, `b_contrast` (mean intensity on the shared boundary over the
mean of the two interiors), `area_ratio`; candidates: `area_rel`, `intensity_rel`, `contrast`, `solidity`.

| # | operator | effect class | theta grid | guard features | source |
|---|---|---|---|---|---|
| 1 | `add_lowthresh`: add objects of the native segmenter re-decoded at a lower detection threshold that overlap existing objects by less than 10% of their area | ADD | relative to TUNED: StarDist prob threshold x 0.5; Cellpose cell-probability threshold minus 2 | candidate features | hysteresis (two-threshold) detection, Canny 1986; probability thresholds of StarDist (Schmidt et al. 2018) and Cellpose (Stringer et al. 2021) |
| 2 | `fill_holes`: fill enclosed background of the object | FILL | maximum hole size relative to area {0.1, 1.0} | hole_frac, area_rel, solidity | Soille 2003 (hole filling by reconstruction); CellProfiler IdentifyPrimaryObjects "fill holes" (Carpenter et al. 2006; McQuin et al. 2018); Cellpose `fill_holes_and_remove_small_masks` |
| 3 | `split_dt`: marker-controlled watershed on the object's distance transform, markers = h-maxima | SPLIT | h = {0.15, 0.3, 0.45} x equivalent radius | area_rel, solidity, ecc, n_cores, contrast | Beucher and Lantuejoul 1979; Vincent and Soille 1991; Malpica et al. 1997; CellProfiler "declump by shape" |
| 4 | `split_int`: marker-controlled watershed on the smoothed intensity (sigma 1 px), markers = intensity h-maxima | SPLIT | h = {0.05, 0.1, 0.2} (normalized intensity) | area_rel, solidity, ecc, n_cores, contrast | Wahlby et al. 2004; CellProfiler "declump by intensity" |
| 5 | `merge_pairs`: merge mutual-best touching pairs (lowest b_contrast) into one object, filling the 1-pixel gap | MERGE | none | u_solidity, u_area_rel, b_contrast, area_ratio | merging over-segmented fragments by boundary strength and shape (Wahlby et al. 2004; Lin et al. 2005) |
| 6 | `close`: per-object morphological closing into free background | GROW | disk radius {1, 2, 3} | solidity, area_rel, contrast | Serra 1982; Soille 2003 |
| 7 | `open`: per-object morphological opening, keeping the largest component | SHRINK | disk radius {1, 2, 3} | solidity, area_rel, ecc | Serra 1982; Soille 2003 |
| 8 | `dilate`: expand the object into free background | GROW | radius {1, 2, 3} px | area_rel, contrast, intensity_rel | CellProfiler ExpandOrShrinkObjects; `skimage.segmentation.expand_labels` (van der Walt et al. 2014) |
| 9 | `erode`: shrink the object | SHRINK | radius {1, 2} px | area_rel, contrast, intensity_rel | CellProfiler ExpandOrShrinkObjects |
| 10 | `delete`: remove the object (area, intensity and shape filters) | DELETE | none | area_rel, intensity_rel, contrast, solidity, ecc, n_neigh | CellProfiler size and FilterObjects filters; ImageJ Analyze Particles (Schneider et al. 2012); `skimage.morphology.remove_small_objects`; Cellpose `min_size` |
| 11 | `clear_border`: remove objects touching the image edge | DELETE | none | area_rel, border-contact fraction | CellProfiler "discard objects touching the border"; `skimage.segmentation.clear_border`; ImageJ "exclude on edges" |

Implementations use numpy, scipy and scikit-image only, and are frozen by hash with the code (section 16).

## 8. Failure records from the frozen CORA component (calibration only)

### 8.1 Needed corrections

Every object of S on a calibration parent, and every reference object left unmatched, is assigned at most one needed
correction from the reference (IoU as `bbbc039.match`; "covers" means overlap of at least half of the other object's
area); the taxonomy follows the merge, split, missed and extra classes of Caicedo et al. 2019 and Project A's
correspondence groups. An unmatched object (no reference at IoU > 0.5) takes the first class that applies, in this
order of precedence:
- **SPLIT:** it covers at least two reference objects;
- **MERGE:** it lies at least half inside a reference object that is covered by at least two predicted objects;
- **FILL:** it has enclosed background, and filling it raises its IoU with its dominant reference above 0.5;
- **GROW / SHRINK:** it has a single dominant reference object at 0.2 < IoU <= 0.5 and is smaller / larger than it;
- **DELETE:** any other unmatched object;
- **ADD** (a reference object, not a predicted one): no predicted object covers at least half of it, and it is not
  covered by a SPLIT object.

The oracle gain of a class is the pooled F1 on induction parents after every error of that class is corrected from
the reference, minus that of S.

### 8.2 Probe tasks for the frozen packages

For each class with at least 12 instances on induction parents, the instances (classes in the order SPLIT, MERGE,
FILL, GROW, SHRINK, DELETE, ADD; instances in sha256 order of parent and object id) are permuted with
`default_rng(3000000 + 1000 * class index)` and cut into consecutive groups of 6, at most 40 groups; each group is one
ARC-format task with 4 demonstrations and 2 query windows, so no instance is used twice. A window is U1's 21 x 21
encoding (the functions `window_ids`, `colours` and `scale_of` of U1's frozen adapter, unchanged); ADD windows, which
have no centre object in S, use the same sampling centred on the missed reference object, without the centre-object
rule. The input is the window of S;
the target is the window of S with that one correction applied from the reference (the corrected label image passed
to the same functions, colours from the corrected objects' mean intensities). This poses exactly the needed
correction to the frozen component, one class at a time.

Each task runs through `cast_selective_v2.evaluate(task, cpu_s=15, wall_s=30)` from U2's byte-extracted systems
(`experiments/universality_similar_problems_20261102/systems/h`), in a forked child with a 40 s hard CPU limit, with
every system file and package manifest hashed before and after against U2's `SYSTEMS_MANIFEST.json` (logged in U5's
own folder). Its evidence gives, per module (M4, M2, L0), the number of programs that reproduce every demonstration
(`n_fits`) and the B1 and B3 acceptances; B1 is the cast_v1 rule (the nine core modules are byte-identical in the
two packages, and U1 found B1 and O identical).

### 8.3 Records, expressibility and specification

- **A failure record** is a probe task on which no module has a fitting program (NO_FIT), or whose fitting programs
  were not accepted under B3, or whose accepted answer differs from the query target. Each record stores the class,
  the task, per-module `n_fits` and status, the B1 and B3 acceptances and the query outcomes. TIMEOUT tasks are
  unresolved and are reported, not counted.
- **Expressibility:** a class is NOT EXPRESSIBLE by the frozen programs if at least half of its resolved probe tasks
  (at least 6 resolved) are NO_FIT.
- **Specification:** an operator is SPECIFIED by the failure records if its effect class is not expressible and the
  class's oracle gain on induction parents is at least 0.005 pooled F1. Specified operators are ordered by their class's
  oracle gain, then by grammar order. Classes the frozen programs can express (DELETE is expected to be one) specify
  nothing, whatever their headroom.

## 9. Admission: validation on separate calibration parents, and the alias check

For each specified operator w, in order, the CORA policy of section 10 is run with demonstrations = induction parents,
grammar = (operators admitted so far) + w, queries = validation parents, and compared with the same run without w.
**w is admitted only if all four hold:**
1. **it changes held outputs:** at least one accepted edit of w on validation parents;
2. the pooled F1 over validation parents rises;
3. more validation parents improve than worsen (per-parent F1);
4. **it is not an alias:** fewer than half of w's accepted validation edits are reproduced (every resulting object at
   IoU >= 0.9) by one edit, or a sequence of two edits, of already-admitted operators at any theta of their grids, or
   by deletion (the action already inside S and expressible by the frozen programs).

Admitted operators join at once (greedy, in order). k* is the number admitted. The INDUCED GRAMMAR G_A is the ordered
list of admitted operators; it is frozen in `POLICY_FREEZE.json` with every calibration-derived decision.

## 10. CORA's verify-or-abstain rule over the grammar

The frozen package cannot execute new operators, so U5 re-implements its acceptance rule over object programs; the
mapping to B3's conditions is given for each step. Given demonstrations D (calibration parents with S, Img and the
reference), an ordered grammar G and queries Q, each operator w in G is processed in canonical order on the current
segmentation (the previous operators' accepted edits applied, on demonstrations and queries alike):

1. **Units and effects.** Units of w on every parent; for each theta, each unit's edited result and, on
   demonstrations, its effect on the parent's matching (change in matched objects and in object count; edits of
   different units are local and additive under one-to-one matching at IoU > 0.5).
2. **Programs.** pi = (theta, guard); predicates are `f < q` or `f > q` with q at the deciles (10 to 90) of f over
   the demonstration units; guards are true, one predicate, or two predicates on different features.
3. **Fitting programs (reproduce every demonstration).** FIT = programs that lower no demonstration parent's object
   F1, raise the pooled demonstration F1, and reach at least 0.9 of the best such gain (the near-optimal set:
   Semenova, Rudin and Parr 2022). An empty FIT means w abstains everywhere (B3: no complete fitting program).
4. **Leave-one-out re-derivation.** For each demonstration parent p, FIT and the top program (largest gain, then fewer
   demonstration edits, then fewer predicates, then enumeration order) are rebuilt from D without p. Every rebuilt
   top program must exist and must lower no held-out parent's F1; otherwise w abstains everywhere (B3: genuine top-1
   leave-one-out).
5. **Agreement.** An edit of unit u is accepted only if every program in FIT selects u with results equal (every
   resulting object at IoU >= 0.9) (B3: no disagreement among fitting programs), and every rebuilt top program selects
   u with the same result (B3: the folds agree on the test output). Units where any of these disagree are abstained
   on (left unchanged). This is a consistent selective strategy in the sense of El-Yaniv and Wiener 2010.
6. **Restart.** Steps 2 to 5 are repeated with the predicate and theta enumeration reversed; if the accepted edit set
   differs, w abstains everywhere (B3: restart in reversed order).
7. **Conflicts.** Accepted edits of w that touch the same object are all abstained on.

At least two demonstration parents with units are required (as CAST requires two demonstrations). The output is the
edited segmentation and an edit log. The constants (0.9, deciles, two predicates, IoU 0.9) are fixed here.

## 11. Transfer

- **A, held-out:** demonstrations = all calibration parents of A (induction and validation); grammar G_A; queries =
  A's evaluation parents.
- **B and C, frozen transfer:** the grammar G_A, its order and the policy of section 10 unchanged; no specification,
  probe or admission is run for this arm on B or C; the demonstrations are B's (or C's) calibration parents, used
  exactly as a CAST task uses its demonstrations; queries = their evaluation parents.
- **Secondary, in-domain induction on B and C:** the full procedure of sections 8 and 9 on B's (C's) own induction and
  validation parents, giving G_B (G_C); it separates portability (the procedure runs and induces there) from learned
  transfer (A's grammar helps there).
- **Secondary, program transfer:** A's final fitted top programs, with A's thresholds, applied to B and C without
  their demonstrations. Descriptive only.

## 12. Arms (all frozen before any evaluation outcome; one evaluator)

| arm | definition |
|---|---|
| NATIVE | section 5 |
| TUNED | section 5 (descriptive) |
| STRONG_NATIVE = ABSTAIN_ALL | S, section 5 |
| ALL_ON | S, then every operator of the grammar in canonical order, each on the units passing its literature-default rule with calibration-tuned values: add (area_rel >= t, t in {1.0, 0.75, 0.5, 0.25}), fill (hole size <= t of area, t in {0.02, 0.1, 1.0}), each split (solidity < t, t in {0.70, 0.75, 0.80, 0.85, 0.90}, and n_cores >= 2, theta in its grid), merge (u_solidity > t, t in {0.95, 0.90, 0.85, 0.80}), close, open, dilate and erode (radius in their grids, all objects), delete (area_rel < t, t in {0.1, 0.2, 0.3, 0.5}), clear_border (area_rel < t, t in {0.25, 0.5, 1.0, infinity}). Every grid's mildest value changes few objects, but none is the identity. Coordinate descent in canonical order on all calibration parents, exact application, until no change (at most 5 sweeps) |
| CORA (primary) | S, then G_A under section 10, demonstrations = the dataset's calibration parents |
| FAILURE_BLIND | five seeds r = 1..5: k* operators drawn uniformly without replacement from the 11 (`default_rng(7000 + r)`), ignoring every failure record, then the same validation (section 9) and the same policy; the control's score is the mean over seeds, each seed also reported |
| SHUFFLED | five seeds r = 1..5: the class labels of the failure records and of the per-class oracle gains relabelled by a seeded derangement of the seven classes (`default_rng(8000 + r)`), then specification, validation and policy as for CORA; mean over seeds, each reported |
| MATCHED_SEARCH | S, then the best program found by a search over sequences of 1 to 3 steps (operator, theta, guard), every operator of the grammar available, guards from section 10's space on calibration units, beam width 3, scored by pooled calibration F1 without any verification: within a step, candidates are scored by the same additive unit effects as section 10; each kept step is applied exactly before the next. Anytime schedule: depth 3 and beam 3 first; while CPU remains, the search is repeated with beam 10, then beam 30, then depth 5 at beam 30, keeping the best program found; it stops when its CPU time reaches CORA's measured CPU on that dataset (section 13) or the schedule is exhausted; ties go to fewer edits, then to the order |
| CORA_FULL (secondary) | the section 10 policy over all 11 operators, without admission |
| CORA_INDOMAIN (secondary, B and C) | G_B or G_C under section 10 |
| NEURAL_PROPOSER (secondary, only if received) | section 15 |

Every calibration-tuned or calibration-fitted arm uses only the calibration parents of the dataset it is evaluated on
(on B and C, B's or C's), except that the grammars of CORA, FAILURE_BLIND and SHUFFLED are those admitted on A.

## 13. Matched compute

- **CORA's measured CPU** on A is the process CPU (user plus system, all threads, child processes included) of its
  probes, failure-record processing, specification, validation, final fitting and application. On B and C it is the
  fitting and application there plus A's induction CPU. Shared steps (segmentation, features, unit effects) are
  counted for no arm.
- **MATCHED_SEARCH** receives exactly that CPU. If it stops early because nothing improves, the result says so and
  reports both costs; it is not then called equal consumed computation.
- Every arm's CPU and wall time are reported.

## 14. Outcomes, analysis and labels

### 14.1 Outcomes

Per evaluation parent and arm, pooled over the parent's images:
- **primary:** object F1 at IoU > 0.5 (`bbbc039.match` and `pooled`);
- **AP over IoU thresholds:** the mean over t in {0.50, 0.55, ..., 0.95} of TP_t / (TP_t + FP_t + FN_t);
- **edits:** accepted edits; beneficial (more matched objects, or an unmatched object removed), harmful (fewer matched
  objects, or an unmatched object added) and neutral, each judged alone against the reference; edit precision
  (beneficial / accepted); harmful-edit rate (harmful / accepted); coverage (edited objects of S / objects of S); for
  CORA arms also the abstention share (units selected by some fitting program but not accepted / units);
- the evaluation split's opportunity (error share and oracle gain), computed after the decisions are frozen; the
  cohort is not replaced whatever it shows.

### 14.2 Uncertainty

Contrasts are means over parents of per-parent differences, with a 95% percentile bootstrap over parents (10,000
resamples, `default_rng(0)`). Ratios (edit precision, harmful rate, coverage) are sum over parents of numerators over
sum of denominators, with the same parent-clustered bootstrap; empty denominators are undefined, never 0 (U4's
Amendment 1 rules). Pooled B and C estimates use a bootstrap stratified by dataset (descriptive).

### 14.3 Labels for CORA on each dataset (applied in this order)

1. **INSUFFICIENT_PARENTS** or **UNSUITABLE** (sections 3.3 and 6).
2. **NON_DEGRADATION_ONLY:** CORA accepts no edit on evaluation parents.
3. **HARMFUL:** the upper bound of CORA minus ABSTAIN_ALL is below 0.
4. **INCOMPLETE_CONTROLS:** any of ALL_ON, MATCHED_SEARCH, FAILURE_BLIND, SHUFFLED is missing.
5. **CROSS_DOMAIN_USEFUL:** lower bounds above 0 for CORA minus each of ABSTAIN_ALL, ALL_ON, MATCHED_SEARCH,
   FAILURE_BLIND and SHUFFLED.
6. **GAIN_OVER_STRONG_NATIVE_ONLY:** the lower bound of CORA minus ABSTAIN_ALL is above 0, but not label 5.
7. **NO_MEASURED_GAIN:** anything else.

### 14.4 Grammar growth (all five gates; a wider vocabulary alone is not growth)

GROWTH_SUPPORTED on a dataset only if: (a) the static and unadmitted comparators (ALL_ON, MATCHED_SEARCH, CORA_FULL)
had explicit access to every candidate operator, MATCHED_SEARCH had CORA's measured CPU (or exhausted its schedule,
reported), and FAILURE_BLIND and SHUFFLED ran the same procedure as CORA at the same work;
(b) admission (which operators were admitted, section 9) is reported separately from useful construction (which
admitted operators made accepted edits that were beneficial on evaluation parents); (c) every admitted operator passed
the alias check; (d) the admitted operators changed held-out outputs (at least one accepted edit on evaluation
parents); (e) CORA beats the matched strong static comparators (lower bounds above 0 against MATCHED_SEARCH and
ALL_ON).

### 14.5 Claims

- **Portability:** the code, frozen by hash before evaluation, ran end to end on each dataset (segmentation, probes,
  specification, admission, policy) without change. Reported regardless of gains.
- **Cross-domain usefulness:** per dataset, label 5 (6 is reported as a gain over strong native post-processing
  only).
- **Learned transfer:** on both B and C, CORA with G_A has label 5 (so it beats FAILURE_BLIND and SHUFFLED, which
  carry A's blind and shuffled grammars). The contrast with CORA_INDOMAIN is reported as the transfer gap.
- **Grammar growth:** section 14.4, per dataset.
- Nothing is tuned on evaluation outcomes. Every number is reported, including for UNSUITABLE datasets.

## 15. Neural synthesis interface (the independent team builds the proposer)

`INTERFACE.md` defines a typed interface through which a neural proposer reads calibration observations and failure
records and emits typed program proposals in the grammar, which CORA verifies:
- **Input packet (calibration only):** the grammar card (types, operators, theta grids, guard features), per-unit
  feature and effect tables for calibration parents only, the needed-correction classes, the failure records and
  probe outcomes, and a calibration-only verifier. No evaluation parent, image, mask, identifier or outcome is in it.
- **Output:** JSON proposals `{operator, theta, guard}` sequences, checked against a schema before any execution.
- **Verification and scoring stay in this lane.** Proposals are frozen by sha256; the CORA policy of section 10 is run
  with the proposed programs as the candidate set (FIT is the subset that fits; agreement is over it); held-out
  parents are scored once by U5's evaluator. The independent team never reads evaluation parents of any imaging split.
- **NEURAL_PROPOSER** is scored only if proposals frozen by hash arrive before 2026-11-05T18:00Z; otherwise NOT_RUN.
- The packet and `INTERFACE.md` are frozen together (`PACKET_FREEZE.json`), and their hashes are reported.

## 16. Compute and process

- Heavy CPU steps through `scripts/with_cpu_slot.sh` (nice 19, idle I/O), one at a time, in a detached chain with
  `run.status` files; network passes on CPU or GPU 0 under the lock; never GPU 1.
- Soft budget 30 CPU-h: no new arm starts beyond it (its contrasts become unavailable; labels then INCOMPLETE_CONTROLS).
  About 12 CPU-h is expected.
- Code and tests are frozen by hash in `CODE_FREEZE.json` before the evaluation run; the chain checks the hashes.
- Commits at checkpoints, without trailers; `PROGRESS.md` is kept current.

## 17. Timeline and the hold for independent blind review

- After this freeze: downloads, eligibility, calibration segmentation and tuning, the calibration gate, probes,
  induction, the policy freeze and the calibration-only packet may run.
- **Evaluation is held** (no evaluation image is segmented, no arm applied to evaluation parents) until
  `/path/to/bio_data/work/GO_EVALUATION` exists, or 2026-11-04T12:00:00Z passes
  without `work/HOLD_FOR_AMENDMENT`. A review that requires changes is answered by a dated amendment before release.
- Results are due 2026-11-06T12:00Z.

## 18. Reporting

`results/RESULTS.json` and `results/SUMMARY.md`; the record `records/NOV5_BIO_GRAMMAR_TRANSFER_RESULT.md`, with a "Claim
for the paper" section that keeps portability, cross-domain usefulness, learned transfer and grammar growth separate.
If CORA abstains everywhere, the run is reported as non-degradation only, which is not evidence of zero risk.

## 19. Boundaries

Never touched: `Reasoning_Project` (Step B), anything named VDCG, other projects' job folders, other projects' sealed outcomes,
other private projects, collaborator data, `<companion study folder>`, the frozen packages, manifests and
earlier results (U4's runs included). No Kaggle action, no push. Private data only as in section 3.4.

## References

Beucher S, Lantuejoul C (1979) Use of watersheds in contour detection. Int. Workshop on Image Processing, Rennes.
Caicedo JC et al. (2019) Evaluation of deep learning strategies for nucleus segmentation in fluorescence images.
Cytometry A 95:952-965. Canny J (1986) A computational approach to edge detection. IEEE TPAMI 8:679-698. Carpenter AE
et al. (2006) CellProfiler. Genome Biol 7:R100. Clissa L et al. (2024) Fluorescent Neuronal Cells v2. Sci Data, doi:10.1038/s41597-024-03005-9.
Edlund C et al. (2021) LIVECell. Nat Methods 18:1038-1045. El-Yaniv R, Wiener Y (2010) On the foundations of noise-free
selective classification. JMLR 11:1605-1641. Huynh ST et al. (2025) FluoEcoli-Instance. IEEE JSTSP 19(8):1967-1982. Lin G
et al. (2005) Hierarchical, model-based merging of multiple fragments for improved three-dimensional segmentation of
nuclei. Cytometry A 63:20-33. Mahbod A et al. (2024) NuInsSeg. Sci Data, doi:10.1038/s41597-024-03117-2. Malpica N et al. (1997) Applying
watershed algorithms to the segmentation of clustered nuclei. Cytometry 28:289-297. McQuin C et al. (2018) CellProfiler
3.0. PLoS Biol 16:e2005970. Pachitariu M, Stringer C (2022) Cellpose 2.0. Nat Methods 19:1634-1641. Pachitariu M,
Rariden M, Stringer C (2025) Cellpose-SAM. bioRxiv 2025.04.28.651001. Ruifrok AC, Johnston DA (2001) Quantification of
histochemical staining by color deconvolution. Anal Quant Cytol Histol 23:291-299. Schmidt U et al. (2018) Cell
detection with star-convex polygons. MICCAI. Schneider CA et al. (2012) NIH Image to ImageJ. Nat Methods 9:671-675.
Semenova L, Rudin C, Parr R (2022) On the existence of simpler machine learning models. FAccT. Serra J (1982) Image
Analysis and Mathematical Morphology. Academic Press. Soille P (2003) Morphological Image Analysis, 2nd ed. Springer.
Stringer C et al. (2021) Cellpose. Nat Methods 18:100-106. van der Walt S et al. (2014) scikit-image. PeerJ 2:e453.
Vincent L, Soille P (1991) Watersheds in digital spaces. IEEE TPAMI 13:583-598. Wahlby C et al. (2004) Combining
intensity, edge and shape information for 2D and 3D segmentation of cell nuclei in tissue sections. J Microsc
215:67-76.
