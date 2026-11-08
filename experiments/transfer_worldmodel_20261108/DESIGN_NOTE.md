# T4 world-model probe on real ARC-AGI-3 games: design note (written before any game frame is seen)

**Label.** This is a development probe on public ARC-AGI-3 games, and its numbers are not a score. It tests world-model
induction, not game play. It is reconstruction of rules that already exist in the games, not discovery.

**Authority.** The author approved a bounded probe if it was wise, and the coordinator relayed the approval. The bounded version
follows.

## Isolation and limits

- **Where things run.** Everything that touches game code runs inside a private Kaggle CPU kernel on the author's
  account (`chimdiwalter/t4-arcagi3-worldmodel-probe`). Game code never runs on Athe.
- **Install.** The kernel installs the MIT toolkit and engine from PyPI: `arc-agi==0.9.9` and `arcengine==0.9.3`.
- **How the games are fetched.** The kernel uses the toolkit's documented public route: NORMAL mode with no key, which
  fetches an anonymous key.
- **Handling of the anonymous key:**
  - the toolkit's logger is replaced by a silent one, so the key is never printed;
  - before the kernel ends, every output file is scanned for the key string, and the kernel prints only "clean" or
    "redacted";
  - recordings and environment files go to `/tmp`, never to the kernel's output.
- **What is never done:**
  - no competition rules are accepted;
  - the kernel attaches no competition data source;
  - no submission is made;
  - no scorecard is opened on the server (NORMAL mode keeps scorecards local);
  - no key is saved.
- **What comes back to Athe.** Only data: for development games, the frames, actions and states as `.npz` files plus a
  JSON summary. Game source files are not copied out of the kernel.
- **Terms of the game files:** not stated (see DATA_MANIFEST.md).

## Hash rule (fixed now, before any frame is seen)

1. **Salt.** `SALT` = the full 40-character hash of the git commit that adds this file. The kernel's configuration
   records it.
2. **Order.** For every game in the toolkit's public game list, take its base id `g` (the part before "-"). Compute
   `h(g) = sha256((SALT + "|" + g).encode()).hexdigest()` and sort the games by `h`.
3. **Split.** The first floor(n/2) games in that order are HELD and the rest are DEVELOPMENT.
4. **Held games are kept unseen.** The development kernel collects no transitions from held games. Their ids are
   recorded and nothing else is.

## Items, arms and measures

**Collection.** For each game, the kernel plays E = 6 episodes, with seeds 0 to 5.
- An action is drawn uniformly from the frame's available actions, except RESET.
- A click (ACTION6) takes, with equal chance:
  - a uniform pixel of the 64 by 64 frame;
  - a uniform pixel among those not of the frame's most common colour.
- An episode ends after 80 steps, or at GAME_OVER or WIN.
- The next frame is the last frame the step returns. The kernel also records how many frames each step returned, the
  state, and the levels completed.

**Item.** One item is one (game, episode) pair.
- The *observed* transitions are the first K = 30.
- The *test* transitions are the ones after those, up to 50 of them. They are never used for fitting.

**Representation.** The grid is the frame reduced by the largest block size s, from {8, 4, 2, 1}, at which every
observed frame is constant on s by s blocks. The test frames are not used to choose s. Predictions are scored at full
64 by 64 resolution.

**Arms.**
- **copy-previous:** the next frame equals the current frame.
- **tabular:** memorise each (frame, action) pair seen in the observed transitions. An unseen pair gets copy-previous.
- **static:** the base rule language in `wm/model.py`. A learned displacement for each non-click action moves an
  actor's colour, and a colour map applies to clicks.
- **grown:** the loop in `wm/induce.py`. It describes the wrong cells, ranks 23 kinds of piece, builds the top 3, and
  keeps a piece only if it reduces the wrong cells, breaks nothing, and passes the held check that leaves one
  transition out. It runs at most 4 rounds.
- **shuffled:** the same loop, using the round-0 ranking of the item with the same episode index in the next
  development game (in sorted order) whose ranking is not empty.

**Measures.** All are on test transitions.
1. The exact next-frame rate: the share of test transitions whose whole 64 by 64 frame is predicted exactly.
2. The changed-cell accuracy: among pixels whose true next value differs from the current frame, the share predicted
   exactly. Copy-previous scores 0 on this by definition.
3. Both measures again on the transitions within a level only, where the state and the levels completed do not change.

The reported comparisons are grown against static, against shuffled, against tabular and against copy-previous. Each
is paired over items, using the per-item exact counts.

## Stop rules and custody

- Development uses the development games only.
- If the adapter can be frozen in time, a FREEZE.json is written. The held games are then scored in a second kernel,
  but only after the coordinator's GO.
- Otherwise only development numbers are reported, each tied to the kernel's slug and version.
- If there is no clear signal by about 11:00Z, stop and write result → lesson → direction.
- **Budgets:**
  - at most 30 CPU-minutes per kernel run;
  - at most 20 CPU-minutes on Athe, all development;
  - nice 19 and the CPU-slot script for any heavy step on Athe.
