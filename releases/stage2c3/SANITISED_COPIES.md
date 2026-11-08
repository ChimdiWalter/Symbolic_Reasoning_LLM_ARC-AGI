# Sanitised public copies, stage 2c-3 (the failure-guided choice test, revision 2, the library-rivals test and the two Boolean review records; the final paper PDFs and Writeup follow as stage 2d)

These files are published as copies. Their originals, which ran and which the freeze records
hash, stay unchanged in the author's private repository. Each copy differs from its original only
in what its row lists:
- private absolute folders, private Python environments and job folders, replaced by neutral names;
- in one launcher, one whole line that quoted an instruction, rewritten as a general description
  (the line count is unchanged; `SANITISED_COPIES.json` gives the new line);
- where marked 'wording', the standard wording neutralization of this branch's text files.

No other byte differs. `MANIFEST.json` gives the sha256 of every file this release adds or
replaces.

| file | sha256 of the original | sha256 of the public copy | what was replaced |
|---|---|---|---|
| `experiments/failure_choice_r2_20261108/FREEZE.json` | `fae62f8842bebc68baee8927051bcceb89fb75bef30ac7a3715df7fb7ee53e92` | `464075a3c596e2579bd5068de1437611999cbebce81ed612531be06208e6791a` | the folder that holds the ARC-AGI-2 files on the study machine (now `<ARC data folder>/`, 1x) |
| `experiments/failure_choice_r2_20261108/fgc/freeze.py` | `66b8422de030202dd7debb0821125c3a21ac378ef772e74ea90a64e3410b9ff2` | `ae090ed80f1f6186d841f23dc33172608682d1cce025c09fdb5fc233471fb04d` | the folder that holds the ARC-AGI-2 files on the study machine (now `<ARC data folder>/`, 1x) |
| `experiments/failure_choice_r2_20261108/fgc/kaggle_build.py` | `28b668fdcf9df4c843be3cfd93f58b8296cebefd2479f93a7b5db3d1c7c1fc01` | `6896b58e340e7306dbf2af2d2ca7e4fd6e76ffd3ad119c90080b3bb5f9a31523` | the folder that holds the ARC-AGI-2 files on the study machine (now `<ARC data folder>/`, 1x) |
| `experiments/failure_choice_r2_20261108/launch/poll_kaggle.sh` | `e7912643b18a47bc6fb650c3629adf5452aa556626dc49655b8b17b1c45eef62` | `8fb6d560b5ffa6e682f97af178e78837a09d179e574276b76fe55eaefffb8940` | the repository's absolute folder on the study machine (now `/path/to/repository`, 1x) |
| `experiments/failure_choice_r2_20261108/launch/push_when_free.sh` | `1d1422102c68635b2efab3ea4c5de790a90cfb753ef0c21b6320e4f11b30b407` | `a190ae46715184b8dda0918730ce46ea0455cc61cd302d9d9b6e4eab12067a90` | the repository's absolute folder on the study machine (now `/path/to/repository`, 1x) |
| `experiments/failure_choice_r2_20261108/launch/run_job.sh` | `6689599d55bf0837ffdd93f3edc96abfd54900682c15b5f3cbbad7eb4eeb2462` | `5c124aa112b980b708f4fcb5a888daea251089c69867ec7c0ce7eef0c4c2f388` | line 2: a quoted instruction (now paraphrased), rewritten as a general description; the repository's absolute folder on the study machine (now `/path/to/repository`, 1x) |
| `experiments/failure_choice_r2_20261108/reviews/PRE_RUN_REVIEW.md` | `a490564d302abbeffd565c703d91a262c7320068c2c77be286c1c1e2657f5eac` | `64997318b3d39d92c49a656a8355e742553f979047c407ddf8eb484e5aa6c8df` | the interpreter of another private Python environment, by absolute path (now `python3`, 3x); the folder that holds the ARC-AGI-2 files on the study machine (now `<ARC data folder>/`, 1x) |
| `experiments/library_rivals_20261108/FREEZE.json` | `0ce263495c9b9c4de80360bff2682b3435c259e0f82f4327af5dcfcdee456911` | `21665dcef7f3e10cf8839d81ca33171956c2cb666a2b2980a8ad76a0b0457fad` | the benchmark data folder on the study machine (now `/path/to/benchmark_data`, 1x) |
| `experiments/library_rivals_20261108/config/CONFIG.json` | `e2b690c4e9209ef9308434e783afccfb0eb43b7a0b395ecb3efbe7276147e9f0` | `7650ca233d62a6b4460c1347e81748c3d0f7266cefa977f1363b95cba2461d0b` | the companion study's runtime folder, by absolute path (now `<companion runtime folder>`, 3x) |
| `experiments/library_rivals_20261108/launch/run_dry_twice.sh` | `a16ac6a21bbe7e72b9194f77887350811787849180cc39e30df46325d6086473` | `a5827806b1c754d57a285b332b3f1368b6d0462db81fc690e8922071ee781516` | the repository's absolute folder on the study machine (now `/path/to/repository`, 1x); the interpreter of another private Python environment, by absolute path (now `python3`, 1x) |
| `experiments/library_rivals_20261108/launch/run_main.sh` | `7fff308b057434a3f17c77b14f07395da971a72e951b6a59f6a2c285117a8098` | `aafefdd980573ea638e7d16aece358e2af770886de34dce488d12cdb2843adf9` | the repository's absolute folder on the study machine (now `/path/to/repository`, 1x); the interpreter of another private Python environment, by absolute path (now `python3`, 1x) |
| `experiments/library_rivals_20261108/lr/env.py` | `8710f46da3394cef26c7af5e857e8dbe88dae9467c9f07c0f4464425ac004350` | `6e2a06cbfca9666f08cf40baed693ab74c7f3abc1cb77d136c3a008c4be28484` | the repository's absolute folder on the study machine (now `/path/to/repository`, 1x); the benchmark data folder on the study machine (now `/path/to/benchmark_data`, 1x) |
| `records/boolean_selection_review_20261108/V2_PRECHECK_CHECK.md` | `cba9460ff50f97795811980bc36a509316dae733b966a3ebffffb0182651c769` | `5cf36deab06f18704fae10d0435f43d0ed46919158b95086b47742742a2ae3c1` | another project's job folder under /tmp, in guard lists (now `/tmp/reserved`, 1x) |
