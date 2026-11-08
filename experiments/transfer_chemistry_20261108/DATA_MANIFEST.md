# T3 data manifest (real data; downloaded 8 November 2026, 05:31Z to 05:45Z)

All downloads are in `data/raw/` (kept local and out of git by the study's `.gitignore`; re-download from the
sources below and check the sha256). They are read only by `python -I` scripts.

## 1. EnzymeMap, version 2 (BRENDA 2023 release)

- **What:** atom-mapped, balanced enzymatic reactions from BRENDA 2023.1, sorted by EC number, with a
  reaction-rule id per reaction.
- **Source:** Zenodo record 8254726, version 2, published 18 April 2023 (`https://zenodo.org/records/8254726`).
- **Licence:** Creative Commons Attribution 4.0 International (`cc-by-4.0`, read from the Zenodo record's metadata
  through the Zenodo API on 8 November 2026).
- **Citation:** E. Heid, D. Probst, W. H. Green and G. K. H. Madsen, "EnzymeMap: curation, validation and
  data-driven prediction of enzymatic reactions", Chemical Science 14, 2023 (doi 10.1039/D3SC02048G).
  The underlying data come from BRENDA (www.brenda-enzymes.org), which EnzymeMap's record asks users to credit.

| file | sha256 | Zenodo md5 |
|---|---|---|
| `data/raw/enzymemap/enzymemap_v2_brenda2023.csv.gz` | `0a70759a7cec5720b6aeb2d63c887a670b9ac2a6ada7c0a1ef3c1740ee3cc2cf` | `334ae7294018b0913c2c39c824892b37` (matches) |
| `data/raw/enzymemap/compound_to_smiles.json` | `59f1c90b600d55e818406fb4ab1746614062d459a212cb2a29ba7227ddc8c3b4` | `cd7203a9d692c218bb1754483cf76b19` (matches) |

`compound_to_smiles.json` is used only to turn the fixed list of cofactor names in `config/T3_CONFIG.json` into
structures.

## 2. Published generalized enzymatic reaction rules (Ni et al. 2021), as shipped with Pickaxe

- **What:** the 1,224 most generalized reaction rules abstracted from atom-mapped MetaCyc reactions
  (`metacyc_generalized_rules.tsv`, 1,224 rules), the matching cofactor list (`metacyc_coreactants.tsv`, 44
  entries), the more specific intermediate rules and the rule-to-reaction map (downloaded for reference, not used
  by any arm), and two Pickaxe source files read to follow how the rules are applied.
- **Source:** GitHub `tyo-nu/MINE-Database` (Pickaxe), pinned to commit
  `25acc1c835797d5ae741f7609086c3f75c5df04c`, folder `minedatabase/data/metacyc_rules/`.
- **Licence:** MIT (the repository's `LICENSE`, copied to `data/raw/pickaxe/LICENSE`; copyright 2017 James
  Jeffryes).
- **Citations:** Z. Ni, A. E. Stine, K. E. J. Tyo and L. J. Broadbelt, "Curating a comprehensive set of enzymatic
  reaction rules for efficient novel biosynthetic pathway design", Metabolic Engineering 65, 79-87, 2021
  (doi 10.1016/j.ymben.2021.02.006). K. M. Shebek, J. Strutz, L. J. Broadbelt and K. E. J. Tyo, "Pickaxe: a
  Python library for the prediction of novel metabolic reactions", BMC Bioinformatics 24, 106, 2023.

| file | sha256 |
|---|---|
| `data/raw/pickaxe/metacyc_generalized_rules.tsv` | `61d9f173f9806ac8a88c96e4886746c9437f8b9c069c2310e3e23b4606876365` |
| `data/raw/pickaxe/metacyc_coreactants.tsv` | `7084d256f59c337bd3f3b2103a4e7d6cb0d518250c02e81a9e8b729d456a1ce4` |
| `data/raw/pickaxe/metacyc_intermediate_rules.tsv` (not used) | `c30a3b5bdb680378376d59f8c66111bcb6140b99a611750d7dbd0f949693b082` |
| `data/raw/pickaxe/metacyc_mapped.tsv` (not used) | `758fb940fe3c5b1d48cfa105fb3e6d623d5f6abe802273ce26de80260b80702c` |
| `data/raw/pickaxe/LICENSE` | `480011baec8e88b369d2555e13e12990400136695076725d73869a6716887468` |
| `data/raw/pickaxe/pickaxe.py` (read only) | `2521c107918e9a4b6f82ea8455cbe6864774c762dae87b80e3350e7caff02aed` |
| `data/raw/pickaxe/rules.py` (read only) | `7fb07c5040f294fed96958e04d2ece91285a2b4a51f5a0576efcf33df57c9ecd` |
| `data/raw/pickaxe/SOURCE_COMMIT.txt` | `9dbd6ced6bb376b2ddb23c5c67d5de5029a757f649b06d43226e530f359dded1` |

## 3. Derived files (made by `t3chem/build_items.py`, deterministic)

- `data/cache/items.jsonl.gz` (local only): one line per item (family, main substrate, main product, the source
  mapped reaction). Its sha256 is in `FREEZE.json`.
- `data/POOL.json` (committed): family counts, the development families, the scoring pool and the drop reasons.

## 4. Use and redistribution

- Evaluation only. No raw file is redistributed in git; the committed files hold counts, family keys (EC number
  and rule id) and hashes, plus development outputs on development families.
- No images are embedded and no private data are used.
- Label of every result: real data; reconstruction of known enzyme transformations on held substrates, not
  discovery.
