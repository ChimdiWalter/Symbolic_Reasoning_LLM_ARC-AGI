# Fresh Boolean model candidates for a held replication

Prepared 8 November 2026 (UTC). Metadata only: no rule body, model file, pickle, label, private file or answer file was read.

**Purpose.** The natural sparse result (433 of 595 exact rules at 40 observations) and the inferred-wiring result (101 of 595) use a reused cohort of 75 published models from 50 lineages. This record lists published Boolean models that could support a held replication outside that cohort.

## 1. Answer

| Set | Models | Independent lineage groups | Eligible targets |
|---|---:|---:|---:|
| **Meets all four criteria** (licence through a CC BY source article) | 13 | 13 | **102** |
| The same, without the one threshold-format model | 12 | 12 | 94 |
| Meets criteria 1 to 3; licence unknown for 7 of them | 20 | 19 | 153 |
| The same, one model per family | 19 | 19 | 145 |

- **A held replication meeting all four criteria is not feasible today:** 102 eligible targets from 13 lineages, below the target of about 150 from at least 10 lineages.
- The licence criterion is the binding one. Adding the seven models without a known licence gives 153 targets from 19 lineage groups, which is numerically enough. That would need an explicit author decision to use those files locally without redistribution. It does not satisfy criterion 4 as stated.
- **Totals by input count (1, 2, 3, 4 or more) cannot be given from metadata.** The public summary reports only each model's average in-degree. The target-weighted mean essential in-degree is 2.63 for the 13 licensed models and 2.34 for the other seven. For comparison, the 595-target cohort had 165 one-input, 156 two-input and 274 higher-input targets. The breakdown should be computed during blinded qualification, after the roster and target selection are frozen.

## 2. Inclusion rules applied

From `cage/biology_support_replication_20261105/PROTOCOL_OUTLINE.txt` and `METADATA_AUDIT.json` (cohort `M_new_contract_75`, lineage set SHA256 ad499d46bac8ec2559ee74a2c42ea06eb3d6a70ac5edac779d6c4fb697fe109c):

- Two-valued Boolean model with 2 to 60 variables.
- Lineage-disjoint from previously used models.
- At most eight regulated genes per model; the 595 total used this cap. Every planned target stays in the denominator.

**Freshness test.** I required independence from **all 191 consumed BBM lineages**, not only the cohort's 50. BBM is the 285-model collection used in development, and its source-pool models were also used, so they are not unseen. Lineage calls come from `records/NOV8_KADELKA_PARENT_EXPOSURE_LEDGER.md` (SHA256 54fe61013d7f8e6397f3dfbf5c057f41aad47ff3b3f0ceda7cc1e1c8da8fc5db).

**Counting.** Eligible targets per model are min(8, variables), where "variables" is the regulated-variable count in the public summary; inputs are listed separately. All 20 models have 5 to 41 nodes in total.

## 3. Sources

- Kadelka repository, pinned commit 932844cded53a0f9da9886710917803b42b3edb7.
  - `general_info_N122_models.xlsx`, Git blob 80d81144ca6ec50b5cdfe94bfbcecdb95dfd77aa, verified after download. It gives per-model variables, external inputs, average in-degree and regulation counts. It contains no rules.
  - `update_rules_122_models_Kadelka_SciAdv/all_txt_files.csv`, blob e478ea66bdc98a5bcf91ac3d6e1237d84e112786. File list only.
- Source-article licences from the Europe PMC licence field, collected for the ledger.
- The cohort-definition files above. The model-set and lineage-set identities were read from the metadata audit only.

## 4. Candidate models

Files are at `update_rules_122_models_Kadelka_SciAdv/<file>` at the pinned commit. The repository declares no licence. Where the source article is CC BY, that is the only known licence route.

### 4a. Meets all four criteria: 13 models, 102 targets

| PMID | File | Source DOI | Variables / inputs | Targets | Mean essential in-degree | Licence | Lineage note |
|---|---|---|---|---:|---:|---|---|
| 19622164 | 19622164_TGF_beta1.txt | 10.1186/1752-0509-3-77 | 17 / 0 | 8 | 4.00 | CC BY article | Data-driven matrix-regulation network; no consumed link |
| 20169167 | 20169167.txt | 10.1371/journal.pone.0009101 | 6 / 1 | 6 | 1.83 | CC BY article | Pseudomonas syringae regulon; no subject link |
| 24079299 | 24079299.txt | 10.1186/1757-4749-5-28 | 28 / 6 | 8 | 2.25 | CC BY article | Salmonella; same group as a mycobacterial lineage (different organism) |
| 24376455 | 24376455.txt | 10.3389/fgene.2013.00272 | 10 / 0 | 8 | 2.40 | CC BY article | Expression-inferred melanoma network; family shared with 23630177 |
| 24564942 | 24564942_threshold.txt | 10.1186/1475-925x-12-s1-s1 | 8 / 0 | 8 | 2.88 | CC BY article | C. elegans cell cycle; threshold format needs frozen semantics |
| 25967891 | 25967891.txt | 10.1186/s12918-015-0166-y | 12 / 1 | 8 | 3.42 | CC BY article | Floral GRN family outside BBM |
| 26346668 | 26346668.txt | 10.1155/2015/908757 | 28 / 2 | 8 | 1.43 | CC BY article | Endothelial cell fate; no link |
| 28187161 | 28187161.txt | 10.1371/journal.pone.0171927 | 24 / 6 | 8 | 2.00 | CC BY article | Cambium; no link |
| 29378814 | 29378814.txt | 10.15252/msb.20177952 | 29 / 7 | 8 | 5.00 | CC BY article | Mouse pluripotency; no link |
| 29596489 | 29596489.txt | 10.1371/journal.pone.0195126 | 21 / 2 | 8 | 2.52 | CC BY article | IGF and Wnt in satellite cells; same lab as cardiac lineages (other subject) |
| 30038409 | 30038409.txt | 10.1038/s41598-018-29480-w | 40 / 1 | 8 | 2.23 | CC BY article | Human pluripotency; no link |
| 31516637 | 31516637_model4.txt | 10.1186/s12263-019-0647-5 | 10 / 0 | 8 | 1.90 | CC BY article | Metabolic switch; one of four variants, use this one only |
| 31949240 | 31949240.txt | 10.1038/s41598-019-57386-8 | 19 / 5 | 8 | 2.16 | CC BY article | Renal microvascular; no link |

### 4b. Meets criteria 1 to 3, licence unknown: 7 models, 51 targets

| PMID | File | Source DOI | Variables / inputs | Targets | Mean essential in-degree | Lineage note |
|---|---|---|---|---:|---:|---|
| 1753781 | 1753781.txt | 10.1016/s0022-5193(05)80457-6 | 8 / 0 | 8 | 3.75 | Tumour-immunity automata; extends the authors' own earlier work |
| 21450717 | 21450717_model_5_2.txt | 10.1093/bioinformatics/btr158 | 18 / 2 | 8 | 1.56 | Auxin and brassinosteroid; one variant of several |
| 21639591 | 21639591.txt | 10.1049/iet-syb.2010.0019 | 23 / 2 | 8 | 2.39 | Phospholipase C calcium; shared author with other-subject lineages only |
| 23630177 | 23630177_metastatic_melanoma.txt | 10.1093/bioinformatics/btt242 | 10 / 0 | 8 | 2.50 | Same melanoma family as 24376455; count once |
| 23764028 | 23764028.txt | 10.1016/j.jtbi.2013.05.028 | 3 / 2 | 3 | 1.33 | Mosquito immune module; no link |
| 25163068 | 25163068.txt | 10.1109/tnb.2014.2345439 | 23 / 7 | 8 | 1.61 | Pseudomonas aeruginosa quorum sensing; no link |
| 25780058 | 25780058.txt | 10.1093/jmcb/mjv017 | 32 / 1 | 8 | 2.59 | Rho GTPases in migration; no subject link |

## 5. Not counted, and why

- **Four models held from the cohort but not unseen:** 22192526 and 28426669 (from BBM 133), 29237040 (BBM 065) and 28381275 (BBM 079). They give 32 targets in 3 families, but each derives from a consumed source lineage.
- **Two models linked to cohort lineages:** 19524598 (BBM 008) and 32054948 (the BBM 200 to 203 family).
- **Pending:** 10 unresolved ledger cases awaiting the blinded overlap check. Five have CC BY articles: 27138333, 30024932, 30104572, 28209158, 23469179. Also the six alerts and the 19 publication overlaps.
- **Cell Collective (in the Kadelka set):** 60 of 61 files share a PMID with a consumed BBM lineage. The last one, the lac operon model (PMID 25790483, 8 variables), was not lineage-reviewed; a lac operon lineage (BBM 063) is consumed, and its licence is unknown.
- **GINsim:** two provisional groups (APL 2024, ICD 2020) still have unresolved ancestry and rights. They could add at most 16 targets, which would not lift the all-criteria total to 150.
- **BioModels qualitative models:** not enumerated; an earlier accession query failed. This is the main untried licensed source.

## 6. What would make a held replication feasible

1. **Rights:** an author decision to use the seven unlicensed files locally without redistribution (or permission from their owners). That gives 153 targets, or 145 counting each family once.
2. **Or more licensed sources:** resolve the five CC BY unresolved cases, or enumerate GINsim/Zenodo and BioModels deposits that carry explicit licences.
3. **In every case, before any body read:**
   - freeze the roster, parser semantics (equation adapter, threshold rule) and the deterministic eight-target selection;
   - run the blinded custodian overlap check against all 191 lineages;
   - compute the one, two, three and four-plus input breakdown at that step.

All counts assume that every summary "variable" is a regulated gene and that every file parses. Lineage independence is bibliographic, not certified.
