# ARC Prize 2026: the two submitted entries, exactly as they ran

This folder holds the complete solution code of two Kaggle submissions to ARC Prize 2026 (ARC-AGI-2 track),
byte for byte as the Kaggle notebooks ran it. Nothing here was edited after the run. Each `notebook.ipynb` is
the file that was pushed (sha256 below; Kaggle's stored copy has the same cells). Every file under
`embedded/` is extracted from that notebook with exactly the bytes the notebook writes to disk at run time,
and its sha256 matches the hash recorded in the notebook or its build manifest.

A one-page overview of the results, with real puzzles and cell images: [docs/RESULTS.md](../docs/RESULTS.md).

## Names used here

- **H:** the neural entry with CORA on attempt 2 (Kaggle submission 57867631). Its builder name is `H`, and
  its rehearsal on the 120 public evaluation puzzles is `HRH`.
- **O+ v2:** the CORA-only entry (submission 57902131), version 2 of the CORA-only entry with a second CORA
  package. Its builder names are `OP2` and, for its rehearsal, `OP2RH`.
- **C4:** the frozen version of our re-implementation of NVARC's neural method that H runs.
- **CAST v1** (`cast_v1`, also called CORA-CAST): the CORA package that O+ v2 runs first.
  **cast_selective_v2:** its stricter version, which H runs on attempt 2.
- **R29** (`r29_cpu_package_20261101`): the second CORA program package in O+ v2, from an independent
  research lane.
- **Rule B3:** cast_selective_v2's strict acceptance rule. It requires a genuine top-1 leave-one-out pass, no
  disagreement between fitting programs, agreement across the leave-one-out folds and stability under restarts.
- **Tier 0 and Tier 1:** merge policies. Tier 0 fills attempt 2 only where the two neural attempts are
  identical; Tier 1 may also replace a different attempt 2 under the package's own rule.

| Entry | Kaggle notebook | Version | What it does |
|---|---|---|---|
| H | `chimdiwalter/sf-h-c4-cast-arc-agi-2` | 1 | Attempt 1 is C4's neural answer: test-time training of the public checkpoint, our implementation of the NVARC method. CORA's cast_selective_v2 may replace attempt 2 under its frozen Tier 1 rule B3; any CORA failure keeps the neural file. |
| O+ v2 | `chimdiwalter/cora-cast-r29-v2-arc-agi-2` | 1 | CORA only, on CPU, with no neural model and no external data: the CAST v1 core (45 s CPU, 90 s wall per puzzle), then the R29 package; attempt 2 is the next distinct answer from another package, else a copy of the test input. |

Licences: see `../LICENSE`. Code is MIT-0 (`LICENSE-MIT-0.txt`); text and data are CC0 1.0 (`LICENSE-CC0-1.0.txt`). The ARC-AGI-2 grids in `expected_predictions/` are ARC Prize's, under Apache 2.0 (`LICENSE-APACHE-2.0.txt`).

## H: `chimdiwalter/sf-h-c4-cast-arc-agi-2`, version 1

- Notebook sha256: `0e09afd478126d93da2fbd3e79c2063fc45df62ff84ede0a12790cda1dfc99c0`.
- Settings (`kernel-metadata.json`): GPU NvidiaL4, internet off; attached: dataset `chimdiwalter/sf-peft-wheel-0212`, model `sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1`, competition `arc-prize-2026-arc-agi-2`.
- Run environment: Kaggle GPU image, 4 x NVIDIA L4, internet off. Logged by the version 1 run: Python 3.13.15, torch 2.11.0+cu128, transformers 5.16.1, accelerate 1.14.0, numpy 2.1.3, scipy 1.16.3; peft 0.21.2 imported from the attached wheel (the image's own peft is 0.20.0).
- Cells:
  1. C4, part 1 of 2: run settings; writes the embedded sf package and the deployment guard to a fresh code folder
  2. CORA launch: writes cast_selective_v2 and the side code (each file hash-checked) and starts one CPU side process next to the neural pass
  3. C4, part 2 of 2: writes a small child driver (its fixed text is in this cell) and runs the neural pass under the guard
  4. CORA merge: may change attempt 2 under the package's frozen policy; on any failure submission.json stays the neural file

## O+ v2: `chimdiwalter/cora-cast-r29-v2-arc-agi-2`, version 1

- Notebook sha256: `f683136c2b15d94d7624d236f1b844eb0875dbd989fd748fe7b0fe8350d8b096`.
- Settings (`kernel-metadata.json`): CPU, internet off; attached: competition `arc-prize-2026-arc-agi-2`.
- Run environment: Kaggle CPU image, 4 CPUs, internet off. Logged by the version 1 run: Python 3.13.15, numpy 2.1.3, scipy 1.16.3.
- Cells:
  1. writes the embedded code (each file hash-checked): cast_v1, the R29 package, the side runner and the driver
  2. runs the packages in priority order on CPU (sfo/driver_plus.py), one fresh child process per puzzle, then a final schema guard

## Files

Origin is the file's path in the research repository; the embedded copy is byte-identical to it.

| File | Entry | Written by | Bytes | sha256 | Origin |
|---|---|---|---|---|---|
| `H_sf-h-c4-cast-arc-agi-2_v1/build_manifest.json` | H | pushed file | 3056 | `44ad7466bfa62ecd4c1972ace3badab8a3bd384678aa23e8826c74f6a713ae74` |  |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/__init__.py` | H | cell 2 | 238 | `9773129899fdb148b7ea3837228a123373e1f37cc58504b03787ccd230a3e28b` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/__init__.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/_nd.py` | H | cell 2 | 3863 | `18e53fa3cbbc6ddae32211ef99d2bb5b1dffec10bc5e4e8dae1422cdf999826f` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/_nd.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/absdom.py` | H | cell 2 | 9266 | `7a7664b78481a6c7301e329536c36ed109462157303c128207e0db97182394d6` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/absdom.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/api.py` | H | cell 2 | 15944 | `2454441f4dca916bde3dc3f2f1bb4fe49a2853c5f5da2787406ab8fffa80f355` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/api.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/candidates.py` | H | cell 2 | 4419 | `792825e4b6f067494ace0eceff766f9c78788e35a651d254ef22c1f925c200aa` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/candidates.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/grids.py` | H | cell 2 | 6233 | `42c349f4c672bc506e3bfec30ff40c63fa86056c561a2b7ea33f32dec931a7f0` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/grids.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/ops.py` | H | cell 2 | 16890 | `380102ef6cac9196bfc8c8713326196533ed83ccb1d292df459799fc9e80a18e` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/ops.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/rewrite.py` | H | cell 2 | 21411 | `86381a6ae3f37215d4919621c3be1a3393c4943174f568b8e27159f1330eb88b` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/rewrite.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/search.py` | H | cell 2 | 9916 | `a6b6261906ed1be03a823912546df486cd2ea9cacc3a4cca05f06ad0cc27e48d` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/search.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/cast_selective_v2/symmetry.py` | H | cell 2 | 9145 | `0040c861706b6ecf173bb2acb48c0d6aacad64c77fb8e73a90412ee28668b04c` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/symmetry.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/deployment_guard.py` | H | cell 1 | 11999 | `0d6bd8caac9813c72ba12d7cb70d56e026f5091eae154940e78543e447aa7771` | `kaggle/score_first_2026/configs/h/c4_frozen/deployment_guard.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sf/__init__.py` | H | cell 1 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/__init__.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sf/grids.py` | H | cell 1 | 3714 | `017174a6b53efa0da62308787fdd278155677d0aca460e59e893518866a2a883` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/grids.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sf/lm.py` | H | cell 1 | 8834 | `ba0af15fc78e51b8a916ca728382d245c53c2f08a1534af3714467cf7d1f594e` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/lm.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sf/pilot.py` | H | cell 1 | 6808 | `c9d8d7dbc5e1d3ca2ce8c8efd526db2400195978b8613ea918c82c275d4cc61c` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/pilot.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sf/predict.py` | H | cell 1 | 6571 | `d3e111db6472743cef3e964b51dba77b4ed6173ade08264234b58dbf0ab1fc78` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/predict.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sf/runner.py` | H | cell 1 | 14784 | `4d18fd80b7cd42123ca3a097ca6f844f45036541d405295c0867b5c73f1787a8` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/runner.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sf/select.py` | H | cell 1 | 2402 | `114615fbe5e167034c057e8f921e8e8c2ed48adea322966eedfa9c1457c7ba93` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/select.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sf/textfmt.py` | H | cell 1 | 3128 | `189c73c7db17a3e58f743f2eebae7a79a94369ddf9c4899cfa60ed00d2774f26` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/textfmt.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sf/ttt.py` | H | cell 1 | 6927 | `235ea4c0bd96381dc1ca1bc5b153556106e97545fcd8ade70f5780a7ac4a2d9d` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/ttt.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sfb/__init__.py` | H | cell 2 | 102 | `839f1efcafe73c661e0f7b726f169ace61e0c76c4fc1cc7623fd39533cf59829` | `kaggle/score_first_2026/configs/sfb/__init__.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sfb/cast_side.py` | H | cell 2 | 16256 | `c072eccd3595bce1a3cd3fd028cc2f378b6fcf6ada838b4e7ea772dd22494853` | `kaggle/score_first_2026/configs/sfb/cast_side.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/embedded/sfb/merge.py` | H | cell 2 | 17888 | `cd67102c6533fef06834d7194c48dc4613fdb0cdf8bbdc79fa2e484e81d279ac` | `kaggle/score_first_2026/configs/sfb/merge.py` |
| `H_sf-h-c4-cast-arc-agi-2_v1/kernel-metadata.json` | H | pushed file | 516 | `0f5875f26020e2bad5b118f5fda9b68ebd87a82939ac7450f5a8d456fc2a7f80` |  |
| `H_sf-h-c4-cast-arc-agi-2_v1/notebook.ipynb` | H | pushed file | 250701 | `0e09afd478126d93da2fbd3e79c2063fc45df62ff84ede0a12790cda1dfc99c0` |  |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/build_manifest.json` | O+ v2 | pushed file | 5008 | `2d720146c187cfbddccf501aa7d1b5fcf11a9e181d498d25c59ff8d8fbb89855` |  |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/__init__.py` | O+ v2 | cell 1 | 176 | `cc04c63281a2205d741e48d5e1571739ca737ce8518cc6f2953a08990d7e52dd` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/__init__.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/_nd.py` | O+ v2 | cell 1 | 3863 | `18e53fa3cbbc6ddae32211ef99d2bb5b1dffec10bc5e4e8dae1422cdf999826f` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/_nd.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/absdom.py` | O+ v2 | cell 1 | 9266 | `7a7664b78481a6c7301e329536c36ed109462157303c128207e0db97182394d6` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/absdom.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/api.py` | O+ v2 | cell 1 | 8317 | `5c27592033998c799bf9abf5e478efcaf86133d9c234167a65e9e448e1c0f87d` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/api.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/candidates.py` | O+ v2 | cell 1 | 4419 | `792825e4b6f067494ace0eceff766f9c78788e35a651d254ef22c1f925c200aa` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/candidates.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/grids.py` | O+ v2 | cell 1 | 6233 | `42c349f4c672bc506e3bfec30ff40c63fa86056c561a2b7ea33f32dec931a7f0` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/grids.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/ops.py` | O+ v2 | cell 1 | 16890 | `380102ef6cac9196bfc8c8713326196533ed83ccb1d292df459799fc9e80a18e` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/ops.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/rewrite.py` | O+ v2 | cell 1 | 21411 | `86381a6ae3f37215d4919621c3be1a3393c4943174f568b8e27159f1330eb88b` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/rewrite.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/search.py` | O+ v2 | cell 1 | 9916 | `a6b6261906ed1be03a823912546df486cd2ea9cacc3a4cca05f06ad0cc27e48d` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/search.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/cast_v1/symmetry.py` | O+ v2 | cell 1 | 9145 | `0040c861706b6ecf173bb2acb48c0d6aacad64c77fb8e73a90412ee28668b04c` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/symmetry.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/LICENSE_STATUS.md` | O+ v2 | cell 1 | 1080 | `961a190f57ed497a78e721803016757e0c6ad4c94643304f7e4de74c390f485c` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/LICENSE_STATUS.md` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/MANIFEST.json` | O+ v2 | cell 1 | 2521 | `11eb2ee9cd10f1507a0ffdcc6ae069de2efed79eb569788888aebcc3fd685ef7` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/MANIFEST.json` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/README.md` | O+ v2 | cell 1 | 6413 | `9c433733b3940cb438802117b0ad283cfd850cbfd3927a5fb83982f1d76359ea` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/README.md` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/VENDORED_PROVENANCE.json` | O+ v2 | cell 1 | 2921 | `32edf758c7e6032ac962fde6c49bbfc4d53042067ef3ec24105e03cdce728bc5` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/VENDORED_PROVENANCE.json` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/__init__.py` | O+ v2 | cell 1 | 209 | `101ebb8b163749f38937ca955a046e30832941f4fddcbdf14677926f1f89d556` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/__init__.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/api.py` | O+ v2 | cell 1 | 8183 | `5006260b401e41099c463835635f8af49d859d76c337f81c4ed6c9a8d7162cbc` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/api.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/cli.py` | O+ v2 | cell 1 | 897 | `52e9450ffe7e28c26ddbfb5a3bed202b4ac2502a73e97af41758180e44ad6d8d` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/cli.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/solver.py` | O+ v2 | cell 1 | 8257 | `21101fb10a55fcafe950a84ad704701c93dce3fae8739d02ac0975d7dd096706` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/solver.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/test_package.py` | O+ v2 | cell 1 | 7512 | `8f29a7472684c554baa0273f696e27992fb0c30a0ec188cfca594553233eea8f` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/test_package.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/cage/__init__.py` | O+ v2 | cell 1 | 97 | `8b671d53028b09a9a552f1b361e1a68a1ef06df067c05c41c2dae7fd4ce6417f` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/__init__.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/cage/dependencies.py` | O+ v2 | cell 1 | 1182 | `fa95fe4b143c05363e48f2cf9f2c97a68eede57fff9ed1456985c9d6b424f4df` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/dependencies.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/cage/programs.py` | O+ v2 | cell 1 | 4455 | `b6ccc7a65a19414a59bc26d101e7f15825c619d1389095bc8a1ae3febbf32a82` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/programs.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/cage/v2b/__init__.py` | O+ v2 | cell 1 | 79 | `e3c9233781d1c3b917a01e737a436be2d0b0961b19d6d34068e7d7a1c0821a8c` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/v2b/__init__.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/cage/v2b/conditional_model.py` | O+ v2 | cell 1 | 13838 | `39ce0652ce78519c0472b4627bc3e0640e2c1b9aae29f3656d9535f3df2db993` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/v2b/conditional_model.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/cage/v2b/goal_constructor.py` | O+ v2 | cell 1 | 17358 | `d067f9d3a5a696be9ec6829e5bdcc2947714bb8ab04ff88e495ef9b948f7092c` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/v2b/goal_constructor.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round25/capability_growth/library.py` | O+ v2 | cell 1 | 35406 | `974dab6c9e98df7f024081c7c4599e7b9242be39cc5f0763987fe5e60ea83dc6` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round25/capability_growth/library.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round25/diagnosis_constructor/engine.py` | O+ v2 | cell 1 | 33851 | `009788d7071929240a5231032eaeb3e783b1313e92aea14a9a81043dccb56559` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round25/diagnosis_constructor/engine.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round26/coverage_constructor/engine.py` | O+ v2 | cell 1 | 27442 | `0e513986bd94565fa0c572f4dbd6dfd5a698a8fa87188f2f876e27f607919a82` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round26/coverage_constructor/engine.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round27/learned_local_rules/model.py` | O+ v2 | cell 1 | 16433 | `110bcb0c19801d22fc27de7f38b34d1c7e7aca65afdbcb7d0b10980b00a3fbd6` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round27/learned_local_rules/model.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/r29_cpu_package_20261101/worker.py` | O+ v2 | cell 1 | 2551 | `703ab07bb55c424d7409cf7c18603ec437624fae1ac5cb650b0f5c87d1e6ac4d` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/worker.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/sfb/__init__.py` | O+ v2 | cell 1 | 102 | `839f1efcafe73c661e0f7b726f169ace61e0c76c4fc1cc7623fd39533cf59829` | `kaggle/score_first_2026/configs/sfb/__init__.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/sfb/cast_side.py` | O+ v2 | cell 1 | 16256 | `c072eccd3595bce1a3cd3fd028cc2f378b6fcf6ada838b4e7ea772dd22494853` | `kaggle/score_first_2026/configs/sfb/cast_side.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/sfo/__init__.py` | O+ v2 | cell 1 | 86 | `4247997a9b0bf1831bde45b068fecc9a51f28eb782077725b45cf3bd42f25fc0` | `kaggle/score_first_2026/configs/sfo/__init__.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/embedded/sfo/driver_plus.py` | O+ v2 | cell 1 | 9109 | `157d41b2c0caa1cf9d1afb4e5ff50144a150d673bf7f2452787dbd3955dc3077` | `kaggle/score_first_2026/configs/sfo/driver_plus.py` |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/kernel-metadata.json` | O+ v2 | pushed file | 395 | `06b9026086cff5c68d7525190ade5348aa686ee82bc91ed047bfa76ea875a3df` |  |
| `O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/notebook.ipynb` | O+ v2 | pushed file | 368790 | `f683136c2b15d94d7624d236f1b844eb0875dbd989fd748fe7b0fe8350d8b096` |  |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/MANIFEST.json` | O+ v2 | builder input | 1756 | `acd57e12f6d7b2735821c06d9dfbcfafd3eaf5754383bd62a92956fd5d2d8f7a` | `experiments/cora_cast_20261026/kaggle_pkg/MANIFEST.json` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/README.md` | O+ v2 | builder input | 3108 | `8b996690a622d6bdf5386247308330d6984f5af82973f4477f50cb631649d0bc` | `experiments/cora_cast_20261026/kaggle_pkg/README.md` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/MANIFEST.json` | H | builder input | 1955 | `aa8551ad935722ed0775570ff1bb1173108a777d3befead17eaf5ce57251f7d0` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/MANIFEST.json` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/README.md` | H | builder input | 2602 | `040f4bbeccf21ab655422c0efc99084eb2ffff0ea4f84f94606f0dd838d2cce5` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/README.md` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/__init__.py` | H | builder input | 238 | `9773129899fdb148b7ea3837228a123373e1f37cc58504b03787ccd230a3e28b` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/__init__.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/_nd.py` | H | builder input | 3863 | `18e53fa3cbbc6ddae32211ef99d2bb5b1dffec10bc5e4e8dae1422cdf999826f` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/_nd.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/absdom.py` | H | builder input | 9266 | `7a7664b78481a6c7301e329536c36ed109462157303c128207e0db97182394d6` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/absdom.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/api.py` | H | builder input | 15944 | `2454441f4dca916bde3dc3f2f1bb4fe49a2853c5f5da2787406ab8fffa80f355` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/api.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/candidates.py` | H | builder input | 4419 | `792825e4b6f067494ace0eceff766f9c78788e35a651d254ef22c1f925c200aa` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/candidates.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/grids.py` | H | builder input | 6233 | `42c349f4c672bc506e3bfec30ff40c63fa86056c561a2b7ea33f32dec931a7f0` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/grids.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/ops.py` | H | builder input | 16890 | `380102ef6cac9196bfc8c8713326196533ed83ccb1d292df459799fc9e80a18e` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/ops.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/rewrite.py` | H | builder input | 21411 | `86381a6ae3f37215d4919621c3be1a3393c4943174f568b8e27159f1330eb88b` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/rewrite.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/search.py` | H | builder input | 9916 | `a6b6261906ed1be03a823912546df486cd2ea9cacc3a4cca05f06ad0cc27e48d` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/search.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/symmetry.py` | H | builder input | 9145 | `0040c861706b6ecf173bb2acb48c0d6aacad64c77fb8e73a90412ee28668b04c` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/cast_selective_v2/symmetry.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/tests/test_validation.py` | H | test | 6698 | `939a7504864d4e8fc778c3127c2706b9978cd1a5e227d0535bef4dacde00e298` | `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/tests/test_validation.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/__init__.py` | O+ v2 | builder input | 176 | `cc04c63281a2205d741e48d5e1571739ca737ce8518cc6f2953a08990d7e52dd` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/__init__.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/_nd.py` | O+ v2 | builder input | 3863 | `18e53fa3cbbc6ddae32211ef99d2bb5b1dffec10bc5e4e8dae1422cdf999826f` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/_nd.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/absdom.py` | O+ v2 | builder input | 9266 | `7a7664b78481a6c7301e329536c36ed109462157303c128207e0db97182394d6` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/absdom.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/api.py` | O+ v2 | builder input | 8317 | `5c27592033998c799bf9abf5e478efcaf86133d9c234167a65e9e448e1c0f87d` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/api.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/candidates.py` | O+ v2 | builder input | 4419 | `792825e4b6f067494ace0eceff766f9c78788e35a651d254ef22c1f925c200aa` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/candidates.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/grids.py` | O+ v2 | builder input | 6233 | `42c349f4c672bc506e3bfec30ff40c63fa86056c561a2b7ea33f32dec931a7f0` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/grids.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/ops.py` | O+ v2 | builder input | 16890 | `380102ef6cac9196bfc8c8713326196533ed83ccb1d292df459799fc9e80a18e` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/ops.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/rewrite.py` | O+ v2 | builder input | 21411 | `86381a6ae3f37215d4919621c3be1a3393c4943174f568b8e27159f1330eb88b` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/rewrite.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/search.py` | O+ v2 | builder input | 9916 | `a6b6261906ed1be03a823912546df486cd2ea9cacc3a4cca05f06ad0cc27e48d` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/search.py` |
| `builder/experiments/cora_cast_20261026/kaggle_pkg/cast_v1/symmetry.py` | O+ v2 | builder input | 9145 | `0040c861706b6ecf173bb2acb48c0d6aacad64c77fb8e73a90412ee28668b04c` | `experiments/cora_cast_20261026/kaggle_pkg/cast_v1/symmetry.py` |
| `builder/kaggle/score_first_2026/configs/build_configs.py` | both | builder input | 38575 | `6c798f67a52aa97ca4579e732ec41320b7fcbf7d9a0ce139bb1992f552f96989` | `kaggle/score_first_2026/configs/build_configs.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/MANIFEST.json` | H | builder input | 2791 | `ff6b1c3826b5befa61984a5e225ca4b7c95a780fb3964bd8115d977bf1d54e54` | `kaggle/score_first_2026/configs/h/c4_frozen/MANIFEST.json` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/deployment_guard.py` | H | builder input | 11999 | `0d6bd8caac9813c72ba12d7cb70d56e026f5091eae154940e78543e447aa7771` | `kaggle/score_first_2026/configs/h/c4_frozen/deployment_guard.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/notebook/kernel-metadata.json` | H | builder input | 563 | `6c706d5431e222151e679b756e7c22e460e68fd6652a933857a62e70c9e0f00a` | `kaggle/score_first_2026/configs/h/c4_frozen/notebook/kernel-metadata.json` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/notebook/notebook.ipynb` | H | builder input | 84366 | `b571233a9afae5a6374cd569d448285e3f6006bddd3e5e9d013f5f8dcb2409bc` | `kaggle/score_first_2026/configs/h/c4_frozen/notebook/notebook.ipynb` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/__init__.py` | H | builder input | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/__init__.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/grids.py` | H | builder input | 3714 | `017174a6b53efa0da62308787fdd278155677d0aca460e59e893518866a2a883` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/grids.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/lm.py` | H | builder input | 8834 | `ba0af15fc78e51b8a916ca728382d245c53c2f08a1534af3714467cf7d1f594e` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/lm.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/pilot.py` | H | builder input | 6808 | `c9d8d7dbc5e1d3ca2ce8c8efd526db2400195978b8613ea918c82c275d4cc61c` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/pilot.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/predict.py` | H | builder input | 6571 | `d3e111db6472743cef3e964b51dba77b4ed6173ade08264234b58dbf0ab1fc78` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/predict.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/runner.py` | H | builder input | 14784 | `4d18fd80b7cd42123ca3a097ca6f844f45036541d405295c0867b5c73f1787a8` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/runner.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/select.py` | H | builder input | 2402 | `114615fbe5e167034c057e8f921e8e8c2ed48adea322966eedfa9c1457c7ba93` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/select.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/textfmt.py` | H | builder input | 3128 | `189c73c7db17a3e58f743f2eebae7a79a94369ddf9c4899cfa60ed00d2774f26` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/textfmt.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/ttt.py` | H | builder input | 6927 | `235ea4c0bd96381dc1ca1bc5b153556106e97545fcd8ade70f5780a7ac4a2d9d` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/sf/ttt.py` |
| `builder/kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/tools/build_kernel.py` | H | builder input | 11782 | `feeb98e7430f3846991798391df987722876ad26081f0a6e77b0edf5008b9ea2` | `kaggle/score_first_2026/configs/h/c4_frozen/source/kaggle/score_first_2026/tools/build_kernel.py` |
| `builder/kaggle/score_first_2026/configs/h/verify_c4_copy.py` | H | builder input | 5498 | `a83cc1e4b75c4bf30abd6d09678a47e184e256fdf5541af0aea59759b3f89602` | `kaggle/score_first_2026/configs/h/verify_c4_copy.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/LICENSE_STATUS.md` | O+ v2 | builder input | 1080 | `961a190f57ed497a78e721803016757e0c6ad4c94643304f7e4de74c390f485c` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/LICENSE_STATUS.md` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/MANIFEST.json` | O+ v2 | builder input | 2521 | `11eb2ee9cd10f1507a0ffdcc6ae069de2efed79eb569788888aebcc3fd685ef7` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/MANIFEST.json` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/README.md` | O+ v2 | builder input | 6413 | `9c433733b3940cb438802117b0ad283cfd850cbfd3927a5fb83982f1d76359ea` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/README.md` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/VENDORED_PROVENANCE.json` | O+ v2 | builder input | 2921 | `32edf758c7e6032ac962fde6c49bbfc4d53042067ef3ec24105e03cdce728bc5` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/VENDORED_PROVENANCE.json` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/__init__.py` | O+ v2 | builder input | 209 | `101ebb8b163749f38937ca955a046e30832941f4fddcbdf14677926f1f89d556` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/__init__.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/api.py` | O+ v2 | builder input | 8183 | `5006260b401e41099c463835635f8af49d859d76c337f81c4ed6c9a8d7162cbc` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/api.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/cli.py` | O+ v2 | builder input | 897 | `52e9450ffe7e28c26ddbfb5a3bed202b4ac2502a73e97af41758180e44ad6d8d` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/cli.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/solver.py` | O+ v2 | builder input | 8257 | `21101fb10a55fcafe950a84ad704701c93dce3fae8739d02ac0975d7dd096706` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/solver.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/test_package.py` | O+ v2 | test | 7512 | `8f29a7472684c554baa0273f696e27992fb0c30a0ec188cfca594553233eea8f` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/test_package.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/__init__.py` | O+ v2 | builder input | 97 | `8b671d53028b09a9a552f1b361e1a68a1ef06df067c05c41c2dae7fd4ce6417f` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/__init__.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/dependencies.py` | O+ v2 | builder input | 1182 | `fa95fe4b143c05363e48f2cf9f2c97a68eede57fff9ed1456985c9d6b424f4df` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/dependencies.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/programs.py` | O+ v2 | builder input | 4455 | `b6ccc7a65a19414a59bc26d101e7f15825c619d1389095bc8a1ae3febbf32a82` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/programs.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/v2b/__init__.py` | O+ v2 | builder input | 79 | `e3c9233781d1c3b917a01e737a436be2d0b0961b19d6d34068e7d7a1c0821a8c` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/v2b/__init__.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/v2b/conditional_model.py` | O+ v2 | builder input | 13838 | `39ce0652ce78519c0472b4627bc3e0640e2c1b9aae29f3656d9535f3df2db993` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/v2b/conditional_model.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/v2b/goal_constructor.py` | O+ v2 | builder input | 17358 | `d067f9d3a5a696be9ec6829e5bdcc2947714bb8ab04ff88e495ef9b948f7092c` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/cage/v2b/goal_constructor.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round25/capability_growth/library.py` | O+ v2 | builder input | 35406 | `974dab6c9e98df7f024081c7c4599e7b9242be39cc5f0763987fe5e60ea83dc6` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round25/capability_growth/library.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round25/diagnosis_constructor/engine.py` | O+ v2 | builder input | 33851 | `009788d7071929240a5231032eaeb3e783b1313e92aea14a9a81043dccb56559` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round25/diagnosis_constructor/engine.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round26/coverage_constructor/engine.py` | O+ v2 | builder input | 27442 | `0e513986bd94565fa0c572f4dbd6dfd5a698a8fa87188f2f876e27f607919a82` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round26/coverage_constructor/engine.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round27/learned_local_rules/model.py` | O+ v2 | builder input | 16433 | `110bcb0c19801d22fc27de7f38b34d1c7e7aca65afdbcb7d0b10980b00a3fbd6` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/vendor/experiments/independent_synthesis_20261029/round27/learned_local_rules/model.py` |
| `builder/kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/worker.py` | O+ v2 | builder input | 2551 | `703ab07bb55c424d7409cf7c18603ec437624fae1ac5cb650b0f5c87d1e6ac4d` | `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/worker.py` |
| `builder/kaggle/score_first_2026/configs/sfb/__init__.py` | both | builder input | 102 | `839f1efcafe73c661e0f7b726f169ace61e0c76c4fc1cc7623fd39533cf59829` | `kaggle/score_first_2026/configs/sfb/__init__.py` |
| `builder/kaggle/score_first_2026/configs/sfb/cast_side.py` | both | builder input | 16256 | `c072eccd3595bce1a3cd3fd028cc2f378b6fcf6ada838b4e7ea772dd22494853` | `kaggle/score_first_2026/configs/sfb/cast_side.py` |
| `builder/kaggle/score_first_2026/configs/sfb/merge.py` | H | builder input | 17888 | `cd67102c6533fef06834d7194c48dc4613fdb0cdf8bbdc79fa2e484e81d279ac` | `kaggle/score_first_2026/configs/sfb/merge.py` |
| `builder/kaggle/score_first_2026/configs/sfo/__init__.py` | O+ v2 | builder input | 86 | `4247997a9b0bf1831bde45b068fecc9a51f28eb782077725b45cf3bd42f25fc0` | `kaggle/score_first_2026/configs/sfo/__init__.py` |
| `builder/kaggle/score_first_2026/configs/sfo/driver_plus.py` | O+ v2 | builder input | 9109 | `157d41b2c0caa1cf9d1afb4e5ff50144a150d673bf7f2452787dbd3955dc3077` | `kaggle/score_first_2026/configs/sfo/driver_plus.py` |
| `builder/kaggle/score_first_2026/configs/tests/test_cfg_b_unit.py` | both | test | 16608 | `092c885e771a06ae221c985f9d4144e4c36c92cffecb6875d336a0935df3b2ee` | `kaggle/score_first_2026/configs/tests/test_cfg_b_unit.py` |
| `builder/kaggle/score_first_2026/configs/tests/test_cfg_dress.py` | H | test | 13950 | `0d663734f022b37f69b3105d96595715d21491a29887338834851ea8ec8861c7` | `kaggle/score_first_2026/configs/tests/test_cfg_dress.py` |
| `builder/kaggle/score_first_2026/configs/tests/test_h_dress.py` | H | test | 11675 | `aec81dba4fb27a93937f4d0e13eb3fcb0de0eee94733c37e2d05eb10fd254854` | `kaggle/score_first_2026/configs/tests/test_h_dress.py` |
| `builder/kaggle/score_first_2026/configs/tests/test_h_unit.py` | H | test | 14974 | `e71b7b3b545dd970cbfb727d0ca618e1995a5527eb9dce7a59baae6d5b06e354` | `kaggle/score_first_2026/configs/tests/test_h_unit.py` |
| `builder/kaggle/score_first_2026/configs/tests/test_op2_caps.py` | O+ v2 | test | 3693 | `eda4b738a4b6961db3abe74298664838da0076cec7e3eb5b1365e28ea1a514d6` | `kaggle/score_first_2026/configs/tests/test_op2_caps.py` |
| `expected_predictions/H_eval120_submission.json` | H | expected predictions | 458136 | `558b6ab15b7b22894648f2923aecb240ab12a27c00c7a1333403b6c22a7a7c19` | `kaggle/score_first_2026/configs/results/h_rehearsal_v1/submission_B.json` |
| `expected_predictions/O_plus_v2_eval120_submission.json` | O+ v2 | expected predictions | 543856 | `d1899a46d0ce2e38d8e73195e65dabb98da047595db5c689a00f251483aa9f4e` | `kaggle/score_first_2026/configs/results/op2_local/eval120/submission.json` |
| `score_rehearsal.py` | both | scorer | 5632 | `0bd62f7c9d39f8935570e61068b502b1d7ba70bd6b1cbc0bdd400c34790dbff8` | `scripts/open_source_release/score_rehearsal.py` |

## Third-party components and data

All but the last row are loaded at run time and are not included here.

| Component | Used by | Attached as | Licence | Availability |
|---|---|---|---|---|
| Model checkpoint `sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1` (Kaggle Models, version id 627758), trained by the NVARC team (Ivan Sorokin and Jean-Francois Puget) on the Qwen3-4B base | H (attempt 1) | Kaggle model attachment | Apache 2.0 (its Kaggle page); base model Apache 2.0 | public |
| peft 0.21.2, the unmodified PyPI wheel `peft-0.21.2-py3-none-any.whl` (sha256 106ab6077ff72c54d21577f9af5970e34bac7582cb14209f7b2b511e322a4eae; Hugging Face) | H | Kaggle dataset `chimdiwalter/sf-peft-wheel-0212` | Apache 2.0 (the wheel carries its LICENSE) | the dataset must be public before H can be rerun; the same file is on PyPI |
| Python, torch, transformers, accelerate, numpy and scipy of the Kaggle image (versions above) | H; O+ v2 uses Python, numpy and scipy | Kaggle's docker image | PSF; BSD-3-Clause; Apache 2.0; Apache 2.0; BSD-3-Clause; BSD-3-Clause | public |
| ARC Prize 2026 competition data (`arc-prize-2026-arc-agi-2`) | both | Kaggle competition attachment | the competition's terms | not redistributed here, and never the solutions file; for the public evaluation grids in `expected_predictions/`, see the next row |
| ARC-AGI-2 public evaluation puzzles with their answers, by ARC Prize ([github.com/arcprize/ARC-AGI-2](https://github.com/arcprize/ARC-AGI-2)) | both, for the rehearsals | the same 120 puzzles are the competition's evaluation files; `expected_predictions/` contains their right answers and the test inputs that fallback attempts copy | Apache 2.0, Copyright 2019 ARC Prize Foundation (text in `LICENSE-APACHE-2.0.txt`) | public |

## How to rerun

### On Kaggle

1. Open the public notebook (or create one and upload `notebook.ipynb`), with the same settings and
   attachments as its `kernel-metadata.json`.
2. Run all cells. The first cell writes the embedded code; the copies under `embedded/` are for reading.

As pushed, each notebook predicts the hidden test set, which only Kaggle can score. Locally, the code needs
the competition files under a Kaggle-style root (`SF_KAGGLE_ROOT`, default `/kaggle`).

### Rehearsal on the 120 public evaluation puzzles

To run either entry on the public evaluation set instead, add this first cell:

```python
import os
os.environ['SF_REHEARSE_ON'] = 'evaluation'
```

That is the only difference between each entry and its rehearsal notebook (version 1 of
`chimdiwalter/sf-h-rehearsal-eval120` and `chimdiwalter/cora-cast-r29-v2-rehearsal-eval120`):
- H's rehearsal has exactly this first cell.
- O+ v2's sets the same variable among its first cell's settings. That cell sets only the variables it lists,
  so a first cell works the same.

With the flag, the notebook reads `arc-agi_evaluation_challenges.json` from the competition data and writes
`/kaggle/working/submission.json` for the 120 puzzles (172 test outputs).

O+ v2 also runs locally on CPU, with Python 3 and numpy (scipy is optional). H needs the checkpoint and GPUs
(4 x L4 on Kaggle).

```sh
W=$PWD/o_plus_v2_run                      # a new folder
mkdir -p $W/kaggle/input/competitions/arc-prize-2026-arc-agi-2 $W/kaggle/working
cp PATH/TO/arc-agi_evaluation_challenges.json $W/kaggle/input/competitions/arc-prize-2026-arc-agi-2/
python3 -c "import json,sys; print('\n'.join(c['source'] for c in json.load(open(sys.argv[1]))['cells']))" \
    kaggle_entries/O_plus_v2_cora-cast-r29-v2-arc-agi-2_v1/notebook.ipynb > $W/notebook_src.py
(cd $W && SF_KAGGLE_ROOT=$W/kaggle SF_REHEARSE_ON=evaluation python3 notebook_src.py)
```

The predictions are then in `$W/kaggle/working/submission.json`.

### Expected predictions and scoring

`expected_predictions/` holds each rehearsal's `submission.json`, as Kaggle wrote it:

| File | Entry | Rehearsal notebook | sha256 | Right, of 172 test outputs | Attempts that copy the test input |
|---|---|---|---|---|---|
| `expected_predictions/O_plus_v2_eval120_submission.json` | O+ v2 | `chimdiwalter/cora-cast-r29-v2-rehearsal-eval120` v1 | `d1899a46d0ce2e38d8e73195e65dabb98da047595db5c689a00f251483aa9f4e` | 3 (per_output 0.017442, task_mean 0.016667) | first 169, second 172 |
| `expected_predictions/H_eval120_submission.json` | H | `chimdiwalter/sf-h-rehearsal-eval120` v1 | `558b6ab15b7b22894648f2923aecb240ab12a27c00c7a1333403b6c22a7a7c19` | 43 (per_output 0.25, task_mean 0.266667) | first 3, second 9 |

- O+ v2's file is byte-identical to a local CPU run of the same notebook, so a rerun should reproduce it
  exactly. Check with the scorer's `--compare` (below).
- In H's run, CORA changed no answer: the file equals the neural pass's own `submission_A.json`. GPU
  test-time training is not bitwise reproducible, so a rerun of H differs in some outputs (see Notes).
- Both files hold task ids and answer grids only.
- Their right answers (44 distinct test outputs) are public ARC-AGI-2 evaluation answers. The test inputs that
  fallback attempts copy come from the same public puzzles. Both are published by ARC Prize in
  [github.com/arcprize/ARC-AGI-2](https://github.com/arcprize/ARC-AGI-2) (Copyright 2019 ARC Prize Foundation) under the Apache License 2.0
  (`LICENSE-APACHE-2.0.txt`) and keep that licence.

The scorer needs your own copy of the solutions, which this release does not include: they are competition
data. Download `arc-agi_evaluation_solutions.json` from the competition's data page, then run:

```sh
python3 kaggle_entries/score_rehearsal.py --solutions PATH/TO/arc-agi_evaluation_solutions.json
python3 kaggle_entries/score_rehearsal.py --solutions PATH/TO/arc-agi_evaluation_solutions.json --pred NEW.json
python3 kaggle_entries/score_rehearsal.py --compare NEW.json --pred kaggle_entries/expected_predictions/O_plus_v2_eval120_submission.json
```

- The first command scores both expected files; the results are in the table.
- The second scores a rerun's `submission.json`.
- The third compares a rerun with an expected file, output by output, and needs no solutions.

A test output is right if either attempt equals its solution exactly. `per_output` is Kaggle's metric, the
right outputs over all outputs; `task_mean` averages each puzzle's fraction of right outputs. The scorer uses
the standard library only and prints counts and output names, never a grid.

### Rebuilding the notebooks

`builder/` holds the builder and every file it reads for these entries, at their paths in the research
repository. It uses the standard library only:

```sh
python3 kaggle_entries/builder/kaggle/score_first_2026/configs/build_configs.py --kernels /tmp/rebuild --only H,HRH,OP2,OP2RH
sha256sum /tmp/rebuild/*/notebook.ipynb
python3 kaggle_entries/builder/kaggle/score_first_2026/configs/h/verify_c4_copy.py --out /tmp/c4_copy.json
```

| Build | What it is | Notebook sha256 |
|---|---|---|
| H | entry H | `0e09afd478126d93da2fbd3e79c2063fc45df62ff84ede0a12790cda1dfc99c0` |
| HRH | H's rehearsal | `86ea13868e6e94ec60dff9069235b398d18bf8a8a57933783e4c05eff4b8bcdd` |
| OP2 | entry O+ v2 | `f683136c2b15d94d7624d236f1b844eb0875dbd989fd748fe7b0fe8350d8b096` |
| OP2RH | O+ v2's rehearsal | `6b95126dafad8a20896de06800c63418fd95c6596de9cab2867181759c0ea024` |

- The last command checks the copy of C4 against its manifest.
- Always pass `--kernels`: without it the builder writes into `outputs/score_first/kernels/` under `builder/`.
- The builder also defines earlier configurations, whose inputs are not included; name only these four.
- Each package folder keeps its `MANIFEST.json`, which pins every file's sha256.
- Left out although a manifest lists it: `experiments/cora_cast_20261026/kaggle_pkg/tests/test_pkg.py`. CAST v1's own test file names a local data path (lines 17 and 104), so it is left out rather than edited.

### Tests

Run them from `kaggle_entries/builder/`, on CPU; on a machine with GPUs, set `CUDA_VISIBLE_DEVICES=`.

| Test | What it checks | Needs |
|---|---|---|
| `kaggle/score_first_2026/configs/tests/test_h_unit.py` | H's merge under rule B3 with the package's own insert function; every failure keeps the neural answer; package priority; the real cast_selective_v2 through the side process | numpy, pytest; the competition's `arc-agi_evaluation_challenges.json` in `outputs/score_first/data/` |
| `kaggle/score_first_2026/configs/tests/test_op2_caps.py` | O+ v2's caps at process level: the parent's kill at 90 + 10 s, the child's RLIMIT_CPU at 56 CPU seconds, then the next puzzle runs | pytest; about 3 minutes |
| `kaggle/score_first_2026/configs/tests/test_cfg_b_unit.py` | the side process both entries use: caps, reaping, state reset between puzzles, the total budget, fail-safe errors and imports; the Tier 0 merge | numpy, pytest |
| `kaggle/score_first_2026/configs/tests/test_h_dress.py` | every cell of H's notebook on CPU against a fake Kaggle root, with a tiny random model in place of the checkpoint, under an offline network guard | torch, transformers, accelerate, pytest; the peft 0.21.2 wheel in `outputs/score_first/wheels/`; the evaluation challenges as above |
| `experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/tests/test_validation.py` | cast_selective_v2's validation rules | numpy, pytest |
| `kaggle/score_first_2026/configs/op/r29_frozen/r29_cpu_package_20261101/test_package.py` | the R29 package's own tests | Python 3 |

```sh
cd kaggle_entries/builder
T=kaggle/score_first_2026/configs/tests
python3 -m pytest -q -p no:cacheprovider $T/test_h_unit.py $T/test_op2_caps.py $T/test_cfg_b_unit.py -k 'not matches_frozen'
python3 -m pytest -q -p no:cacheprovider $T/test_h_dress.py
python3 -m pytest -q -p no:cacheprovider experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/tests
(cd kaggle/score_first_2026/configs/op/r29_frozen && python3 -m unittest r29_cpu_package_20261101.test_package)
```

- `-k 'not matches_frozen'` leaves out one test of `test_cfg_b_unit.py`, which compares with research output
  that is not included.
- `test_h_dress.py` reads its network guard from `test_cfg_dress.py`. That file's own tests cover earlier
  configurations and need files that are not included.
- Run from this layout on 2 Nov 2026, on CPU, with Python 3.12.3, numpy 2.4.3, scipy 1.17.0, pytest 9.1.1,
  torch 2.12.1, transformers 5.14.0 and accelerate 1.14.0: the first command 49 passed (1 deselected),
  `test_h_dress.py` 5 passed, cast_selective_v2's tests 8 passed, and R29's 10 tests passed. The local O+ v2
  steps above, followed on 4 of the puzzles, reproduced the expected file's 6 outputs for them.

## Notes

- The files are byte-identical to what ran, so notes inside them that predate this release are unchanged.
  The R29 package's `LICENSE_STATUS.md`, written before any licence was chosen, says that no public licence
  had been granted yet; `../LICENSE` now grants one.
- GPU test-time training is not bitwise reproducible. Two runs of H's neural pass on the 120 public evaluation
  puzzles agreed on 115 of 172 outputs, with the same score.
- H's checkpoint was trained by the NVARC team. Their paper says its training data include descriptions of
  ARC-AGI-2 public evaluation puzzles, so public-evaluation numbers of H are contaminated.
- H's neural code (`sf/`) is described in its module docstrings as an own implementation on the public peft
  and transformers APIs.
