# Data manifest: spreadsheet string transformations (test T2)

Study folder: `experiments/transfer_spreadsheet_20261108/`. Author: Chimdi Walter Ndubuisi.

## Source

| item | value |
|---|---|
| dataset | SyGuS-Comp programming-by-example string benchmarks (the PBE string and SLIA tracks) |
| repository | https://github.com/SyGuS-Org/benchmarks |
| commit | `13c8deb68a873635879c9a69bc78caebd340f646` (repository head on 8 Nov 2026, dated 30 Mar 2023) |
| download | `https://codeload.github.com/SyGuS-Org/benchmarks/tar.gz/13c8deb68a873635879c9a69bc78caebd340f646` |
| archive | `data/raw/sygus_benchmarks_13c8deb6.tar.gz`, 24,996,785 bytes, sha256 `0f9fc711bc6e019f59d5938532e61b9d505772811e2fd53b4d9c767611f0a08f` |
| files used | the 210 files of `lib/PBE_SLIA_Track/euphony` (100) and `lib/PBE_SLIA_Track/from_2018` (110), the repository's "latest snapshot" folder; the sha256 of every file is in `data/SOURCE_FILES_SHA256.json` |
| files not used | `comp/2017`, `comp/2018`, `comp/2019` (older copies of the same tasks) and every non-string track |

## Licence

- **No licence is stated for the benchmark files.** The repository has no licence file (GitHub reports none), and its
  README says only that it "contains all the public benchmarks for the SyGuS competition".
- The SyGuS website (sygus.org) says that copyrights for papers and solvers belong to their owners; it states nothing
  about the benchmarks.
- **Use here.** The files are read unmodified, for research evaluation only.
- **Not redistributed.** `data/raw/` and `data/prepared/` are excluded from version control (`.gitignore`). The
  committed records hold task names, digests, programs and counts, not the benchmark examples. A reader can rebuild
  the data from the commit above and check every digest.
- No private data and no images.

## What the tasks are

- **Forum tasks** (the "euphony" folder, from the Euphony study by Lee and colleagues, PLDI 2018): real
  spreadsheet-help problems collected from Excel help sites (such as exceljet.net) and Stack Overflow. The examples
  are those in the benchmark files, and some of them were written by the benchmark authors. Real problems.
- **2017 families** (the "from_2018" folder): phone-number, person-name, university-address and bike-name families
  written by the benchmark authors, with generated values (for example random phone numbers). Constructed by the
  benchmark authors, not by this study.

## Preparation (`t2/prepare.py`, read with `python3 -I`)

- **Base problem.** The variants of one problem (`-long`, `-long-repeat`, `_short`, `-short`, `_small`) are merged into
  one task: its distinct examples, in file order, and the union of its grammar's constants.
- **Conflicts.** If the files of one problem disagree (one input with two outputs), the task keeps only its largest
  file that does not conflict by itself. This applied to univ_3, univ_4, univ_5 and univ_6, whose `-long-repeat`
  files conflict internally.
- **Eligible tasks.** A task is eligible when it has a String output, String or Int arguments and at least 3
  distinct examples.
  - Excluded: 24 tasks with integer or Boolean outputs, 17 with fewer than 3 examples, and 1 (`max3`) that is
    specified by a logical formula rather than examples.
  - Result: 125 base problems, of which 83 are eligible.
- **Training size.** A task trains on 3 examples when it has 4 or more, and otherwise on 2. All its remaining examples
  are its held checks.
- **Revision.** The eligibility rule was revised once, before any method ran. This was after seeing only the
  aggregate counts (48 eligible under "at least 4 examples"). The revision has two parts:
  - the minimum became 3 examples;
  - the conflict fallback was added.
- **Groups and the development split** (`split/DEV_SPLIT.json`):
  - **Groups.** Tasks are grouped by family: all phone tasks; all person-name tasks; all university tasks; otherwise
    the name without a trailing `_<digits>`. Groups that share an identical example are merged. This gives 59 groups.
  - **Development groups.** A group is a development group when sha256("transfer-spreadsheet-20261108|dev|" + group),
    read as a fraction from its first 12 hexadecimal digits, is below 0.30. This gives 12 groups and **30
    development tasks** (25 that train on 3 examples, 5 on 2).
  - **Held pool.** The other 47 groups hold **53 tasks** (27 that train on 3 examples, 26 on 2). No method has run on
    them, and their examples have not been read.

## Digests

| file | sha256 |
|---|---|
| `data/prepared/tasks.json` (not committed; rebuilt by `t2/prepare.py`) | `f6e68abb0c808231b207863036507c8e4ada4e9e78afe903af3e751000f32fe7` |
| `split/DEV_SPLIT.json` | `740bb73419f202658ea9b1f746741dd9a32041506c8b7c732df2fcb24f661dc6` |
