# Popper baseline: environment record (25 October 2026)

The software environment for the Popper baseline (`records/POPPER_BASELINE_20261025.md`). Everything is installed in its
own environment. The project environment (`~/.venvs/lesegenv`) was not changed. No administrator rights were used.

## Locations

- Environment: `/home/cnptp/.venvs/popper_env`, a conda-forge environment created with standalone micromamba.
- Downloads: `/home/cnptp/downloads_popper_20261025/`
  - `micromamba.tar.bz2` (sha256 `8761c382127e6363bd9e0a2451aa3ef90d071a79133f736e2f759a3bf13040dd`)
  - `mm/bin/micromamba` and its package cache `mamba_root/`
  - `popper_src/`, a git clone of github.com/logic-and-learning-lab/Popper
  - the install logs `env_create.log` and `pip_install.log`
- Popper source: tag `v4.4.0`, commit `860cd0deabf20f02934b3dbe147444e5f1207214` (24 December 2024).
  - That tag's `setup.py` reports the package version as 4.2.0.
  - Newer Popper (master, v5.x) needs Python 3.14 or later and Cython, so v4.4.0 was used.

## Packages and versions

| package | version | source |
|---|---|---|
| micromamba | 2.9.0 | standalone binary (installer only) |
| python | 3.11.17 (h5f976f7_2_cpython) | conda-forge |
| swi-prolog | 10.0.0 (h22941b1_0) | conda-forge |
| clingo | 5.8.2 (py311h5f79a97_1) | conda-forge |
| pip | 26.2.2 | conda-forge, then pip |
| popper-ilp | 4.2.0 (tag v4.4.0) | `pip install` from the clone |
| janus_swi | 1.5.3 | PyPI (Python–SWI-Prolog bridge) |
| bitarray | 3.12.3 | PyPI |
| python-sat | 1.9.dev17 | PyPI |
| cffi | 2.1.1 | PyPI (dependency) |
| setuptools | 80.10.2 | PyPI; pinned below 81 because Popper v4.4.0 imports `pkg_resources` |

## Licence

Popper is MIT-licensed ("MIT License, Copyright (c) 2021 Logic and Learning lab", `popper_src/LICENSE`).
- Popper is used here only as an external comparison tool. None of its code is copied into this repository.
- The repository holds only the encoder and decoder that write Popper's input files and read its output.
- Clingo is MIT-licensed. SWI-Prolog is BSD-2-Clause.

## How it is run

`PATH=/home/cnptp/.venvs/popper_env/bin:$PATH /home/cnptp/.venvs/popper_env/bin/python popper_src/popper.py <task folder> --timeout 60`

This is called from `baselines/popper/popper_baseline.py`, which runs in the project environment at nice 10, with at
most 2 Popper processes at once. Popper was first checked on its own example `examples/1d_flip`, which it solved.

## Citation

A. Cropper and R. Morel, "Learning programs by learning from failures", Machine Learning 110, 801–856 (2021).
