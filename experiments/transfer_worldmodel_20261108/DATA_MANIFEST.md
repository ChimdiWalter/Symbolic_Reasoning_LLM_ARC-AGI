# Data manifest (T4 world models)

| Data | Source | Licence or terms | Where it lives | Notes |
|---|---|---|---|---|
| ARC-AGI-3 toolkit `arc-agi` 0.9.9 | PyPI, ARC Prize Foundation | MIT | installed only inside the Kaggle kernel | never installed or run on Athe |
| Game engine `arcengine` 0.9.3 | PyPI, ARC Prize Foundation | MIT | installed only inside the Kaggle kernel | its wheel was downloaded once to Athe with sha256 `5f9739d6...aef59c` (it matched PyPI); not run, then deleted |
| ARC-AGI-3 game files (public game list) | three.arcprize.org, through the toolkit's anonymous route, inside the kernel | **not stated** | `/tmp` inside the kernel only | the game code never leaves the kernel and is not redistributed |
| Frames, actions and states of the development games | collected by our kernel from the games above | game terms not stated; our collection | `data/kernel_output/` on Athe | git-ignored, so it is not committed or redistributed; the sha256 of each file is listed in PROGRESS.md |
| Toolkit and engine source files that were read (no game code) | github.com/arcprize/ARC-AGI and ARCEngine | MIT, with LICENSE files kept | `data/raw/feasibility_arcagi3_src/` | read only, never executed |
| Substitute simulators (feasibility stage) | written here from public rule sets | ours | `wm/envs.py` | synthetic |
