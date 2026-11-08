# U5 neural synthesis interface: typed program proposals over the bioimage grammar, verified by CORA (v1)

This defines how a neural proposer, built by the independent research team, proposes programs in U5's grammar
(`PROTOCOL.md` section 7) and how CORA verifies them (section 10). U5 does not build the proposer. This file is frozen
together with the calibration-only packet; both hashes are in `PACKET_FREEZE.json`.

## 1. Data ownership and the boundary

- U5 owns every imaging evaluation split: the public datasets, the author's private images and the
  protected third-party data. Only CALIBRATION parents are exported. No evaluation image, mask, segmentation, identifier or outcome
  is in the packet, and the proposer must not read any file outside the packet folder.
- The scorer for held-out data stays in U5. Proposals are scored once, by U5's evaluator, after they are frozen by
  sha256. The independent team receives aggregate results only.
- Single-cell, spatial and perturbation data are not part of U5 (they are the independent team's lane).

## 2. The packet (calibration only)

Folder: `/path/to/bio_data/packet_v1/` (read-only; `PACKET_MANIFEST.json` lists every
file with its sha256).

| file | content |
|---|---|
| `grammar_card.json` | types, the 11 operators (name, effect class, theta grid, guard features, literature source), the predicate rule and the program schema |
| `proposal_schema.json` | JSON schema of a proposal file (section 3) |
| `policy.py`, `verifier_calibration.py` | the section 10 rule (numpy only) and a calibration-only checker of proposals |
| `<dataset>/base.json` | per calibration parent: reference objects, counted predictions and matched objects of the starting segmentation S |
| `<dataset>/units_<operator>.npz` | per unit of that operator on S, calibration parents only: parent index, features per theta, validity, result class, the effect on matching (`dTP`, `dN`), and the conflicting unit pairs per theta (`conflicts_t*`) |
| `<dataset>/failure_records.json` | the frozen component's probe outcomes per correction class (resolved, unresolved, no fit within budget, fit not accepted, accepted, correct, incorrect), the observations behind admission |
| `<dataset>/gate.json` | needed-correction counts and oracle gains per class (calibration) |
| `<dataset>/calibration_images/<id>.npz` | S, the intensity image, the reference and the ignore mask of every calibration image (public datasets only) |

Feature names and order per operator are in `grammar_card.json` (`features`). Theta values are indexed as in
`theta_grid`.

## 3. Proposals (the output of the proposer)

One JSON file per dataset, `proposals_<dataset>.json`:

```json
{"dataset": "nuinsseg", "proposer": "<name and version>", "programs": [
  {"id": "p1", "operator": "dilate", "theta_index": 1,
   "guard": [["area_rel", "<", 0.85], ["contrast", ">", 0.4]]}]}
```

- `operator`: one of the 11; `theta_index`: an index into its grid; `guard`: zero to two predicates, each
  `[feature name of that operator, "<" or ">", number]`, on different features.
- At most 2,000 programs per operator and dataset. Anything that fails the schema is discarded before execution and
  counted.
- Programs are candidates, not decisions: CORA accepts an edit only where it verifies them (section 4).

## 4. Verification (U5, unchanged rule)

For each operator in canonical order, the proposed programs replace the enumerated guard space of section 10. A
proposed program whose selection contains two units that apply would abstain on together (intersecting write sets or a
shared object; `conflicts_t*` in the packet) is invalid (Amendment 3). FIT is the remaining proposed programs that harm
no demonstration parent, raise the pooled F1 and reach 0.9 of the best proposed gain: a B3-inspired selective
verification with metric-consistent fits, not exact reproduction of the demonstrations.
Leave-one-parent-out re-derivation picks the top proposed program without each parent; it must exist and harm no
held-out parent. An edit is accepted only where every fitting proposal and every fold's top proposal agree; a reversed
order must give the same accepted set. Otherwise CORA abstains. Demonstrations are the dataset's calibration parents.
Multi-operator effects are recomputed exactly by U5 (the packet's tables describe single steps on S).

`verifier_calibration.py proposals_<dataset>.json <dataset>` runs this check on the packet's tables and reports, per
operator, the status (NO_FIT, LOO_FAIL, RESTART_UNSTABLE, EVIDENCE) and the number of calibration units accepted. It
cannot score held-out data.

## 5. Delivery and scoring

- Send the proposal files and their sha256 through the coordinator before 2026-11-05T18:00Z.
- U5 checks the schema, runs the section 10 rule with the proposals on each target's calibration parents, applies it
  once to the evaluation parents, and reports the NEURAL_PROPOSER arm with the protocol's metrics and contrasts
  (against CORA's enumerated candidates, ABSTAIN_ALL, ALL_ON and MATCHED_SEARCH).
- If nothing arrives in time, the arm is NOT_RUN.
