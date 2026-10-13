# Kaggle native_v1 deployment log (2026-10-12)

**Status: STAGED, AWAITING THE USER'S KAGGLE LOGIN.** Nothing is uploaded,
nothing is run on Kaggle and nothing is submitted.

The package is the frozen NATIVE_BASELINE native_v1
(`records/KAGGLE_NATIVE_V1_DELIVERY_20261012.md`), deployed unchanged. This log
is updated at every external step so the work resumes without duplicate
uploads, runs or submissions.

## 1. Environment

| role | machine and method |
|---|---|
| Claude Code | Athe (`athe.rnet.missouri.edu`), the VS Code extension running remotely over Remote SSH (`~/.vscode-server`, anthropic.claude-code 2.1.296 linux-x64) |
| repository commands | Athe, directly in this repository |
| Kaggle authentication | Athe. The official Kaggle CLI 2.2.4 is in its own venv, `~/.venvs/kaggle-cli`. The user runs the OAuth login `kaggle auth login --no-launch-browser` in the VS Code terminal. The credential stays in `~/.kaggle/credentials.json` (mode 600, outside the repository) and is never printed |
| Kaggle uploads | Athe, from the git-ignored staging folder `outputs/kaggle_deploy/native_v1/` |

The laptop provides only VS Code and the browser for the login. The two
machines share no filesystem, and none is needed.

**Kaggle MCP is not configured.**
- An MCP OAuth flow cannot run inside this non-interactive session, and MCP
  tools load only when a session starts.
- The CLI covers every step needed (datasets create; kernels push, status
  and output; `competitions submit -k -v` for code competitions;
  submissions; submission limits). It also logs in by OAuth, so no API token
  is handled.
- One credential path is simpler and safer than two.
- The endpoint `https://www.kaggle.com/mcp` answers an MCP `initialize` with
  HTTP 200 and can be added later with
  `claude mcp add --transport http --scope user kaggle https://www.kaggle.com/mcp`.

## 2. Pre-upload verification

| check | result |
|---|---|
| repository | HEAD 47f2cd1 at the start, clean |
| tarball sha256 | `4b320ba2fe92b12bcc4345ef4523ca45115f7694e3ab999dfea6b1cfe3c9a088`, equal to DELIVERY_MANIFEST |
| DELIVERY_MANIFEST | all 11 listed files match |
| tarball contents | 273 regular files: the 272 PACKAGE_MANIFEST entries plus MANIFEST.json itself (the delivery record's "272 files" counts the manifest entries). The only JSON files are MANIFEST.json, library.json and learned_verbs.json |
| assets inside the tarball | library.json `cdacd018...`, learned_verbs.json `b1f07ba5...`, both the sealed hashes |
| credentials | no secret patterns in any file (Kaggle keys or tokens, GitHub, OpenAI or AWS keys, private keys, passwords); no kaggle.json or token file |
| evaluator data | no solutions, holdout or lockbox file. `src/reasoning_project/evaluation.py` is code |
| freezes | reach_v1, pilot_v2 reasoner and evaluator, diagnosis, recheck coordinator and worker, p3: 0 problems each |
| running jobs | none from ARC-2026 |
| notebook paths | `resolve_src` takes the unpacked dataset (the folder holding `geocat_arc/`) or the `.tar.gz`, so either Kaggle storage form works. `find_comp` walks `/kaggle/input` and hard-codes no dataset path. Before the harness starts, the notebook deletes its copy of the public `arc-agi_evaluation_solutions.json` and writes `{}`, so the solver sees no answers |

## 3. Staged upload folders (`kaggle/native_v1_deploy/deploy_check.py stage`)

**`dataset/`**
- `arc_native_baseline_v1.tar.gz` (`4b320ba2...`) and `dataset-metadata.json`
  (`0a4f0cd2...`).
- id `chimdiwalter/arc-native-baseline-v1`, private.
- Licence `copyright-authors` (all rights reserved). It can be changed
  later; making the dataset public needs the user's approval.

**`kernel/`**
- `notebook.ipynb` (`0be06005...`, the frozen notebook) and
  `kernel-metadata.json` (`13e6a1cd...`).
- id `chimdiwalter/cora-native-v23-arc-agi-2-october-baseline`, private.
- Title "CORA Native v23 - ARC-AGI-2 October Baseline". It uses an ASCII
  hyphen so the title resolves to the slug.
- Internet false, GPU and TPU false.
- Inputs: the competition `arc-prize-2026-arc-agi-2` and the dataset above.

**Internet is set off explicitly.** The Kaggle CLI 2.2.4 enables internet
when `enable_internet` is absent. `deploy_check.py` refuses to stage unless
internet is false, there is no accelerator, and both the kernel and the
dataset are private.

**Verifier self-test on the recorded dev60 emulation run.** Every identity
check passes:
- label, flags, assets, solver tree `d7856871...`;
- task file and its hash, submission hash;
- schema 0 problems, order correct.

The recomputed counts, 49 real attempt_1, 26 real attempt_2 and 15 fallback,
equal the record.

## 4. Steps after the login (each result is logged below)

1. **Identity and rules.**
   - Authenticated user = chimdiwalter.
   - Rules accepted (the competition listing).
   - Submission limits.
   - The rules and code-requirements pages (`kaggle competitions pages`).
   - My datasets and kernels.
2. **Dataset.**
   - `kaggle datasets create -p outputs/kaggle_deploy/native_v1/dataset`
     (private by default).
   - Then status, the file list, and a download of the file back for a
     sha256 comparison.
3. **Notebook.**
   - `kaggle kernels push -p outputs/kaggle_deploy/native_v1/kernel` starts
     the committed run.
   - `kaggle kernels pull -m` confirms the settings as Kaggle stored them.
   - Status polled until the run completes, at about 7 h for 240 tasks.
4. **Output.**
   - Download only `submission.json`, `execution_manifest.json` and
     `run/progress.jsonl`. The notebook's output folder also holds copies of
     the competition files, which are not needed.
   - Download only the competition's `arc-agi_test_challenges.json` (inputs).
   - Run `deploy_check.py verify`.
5. **Submission.**
   - One concise final confirmation to the user, then the user's explicit
     SUBMIT.
   - `kaggle competitions submit arc-prize-2026-arc-agi-2 -k <kernel> -v <version> -f submission.json -m "NATIVE_BASELINE native_v1 ..."`.
   - One submission only.
6. **Score.** `kaggle competitions submissions`: the submission ID, the
   status, the score once it exists. Recorded in
   `records/KAGGLE_NATIVE_V1_OFFICIAL_RESULT_202610XX.md`.

## 5. External identities (filled in as they are created)

| item | value |
|---|---|
| Kaggle account | (pending login) |
| dataset version | (not created) |
| notebook version | (not pushed) |
| committed run | (not started) |
| submission ID | (none) |
