# Adapter card: world models (T4)

**What was reused.** No code from CORA's core is imported. The loop's structure is CORA's:
1. propose;
2. check;
3. describe the failure;
4. build the missing piece;
5. check again;
6. keep the piece only if it helps on a held check.

That structure is rebuilt inside the adapter. The shared failure record and diagnostician
(`cora_neural_hybrid.feedback`, `cora_cross_domain_transfer.interface.diagnose`) import cleanly here but are not used.
A later version could route the stop and revise decision through them.

**What the adapter supplies.**

| Part | What it is here | File |
|---|---|---|
| Building blocks, base | Move (an actor's colour shifts by a displacement learned for each action, through passable colours; the cells left behind become background) and ClickMap (a clicked cell's colour changes by a learned map) | `wm/model.py` |
| Building blocks, grown | 23 kinds of piece, each one selector, one effect and one trigger (listed below), plus two switches on Move: slide (repeat until blocked) and wrap (torus) | `wm/model.py`, `wm/induce.py` |
| Checker | exact equality of the predicted and observed next grid on the observed transitions; the error is the count of wrong cells | `wm/induce.py` (`wrong_vec`) |
| Failure description | the wrong cells of the current model; for each kind of piece, the F1 score of its footprint's coverage and precision against those cells at its best parameter. The ranked list is the description | `wm/induce.py` (`describe`) |
| Construction | fit the parameters of the top 3 kinds on the observed transitions: colours, scan order, corner, direction, and colour maps estimated from the observed changes | `wm/induce.py` (`fit_skeleton`) |
| Selection rule | keep a piece if three things hold: it lowers the wrong cells; it breaks no transition that was right; and a held check passes, meaning that a refit without one transition the piece fixes still predicts that transition exactly (at most 5 tries). At most 4 rounds | `wm/induce.py` (`accept`, `grow`) |
| Shuffled control | the same loop, with another game's failure ranking | `wm/induce.py` (`grow(fixed_ranking=...)`) |
| ARC-AGI-3 bridge | frames reduced by block size; actions become `A1`..`A7` or `C:y:x`; items, scoring and changed-cell accuracy | `wm/arc3.py` |
| Kernel | isolation, collection, key handling, and the analysis inside the kernel | `kernel/probe_template.py`, `kernel/build.py` |

**The 23 kinds of piece.**

| Selectors | Effects |
|---|---|
| the object ahead of the actor (one cell, or the whole touched object) | shift by the action's displacement (push) |
| the cells the actor left | recolour to one colour |
| the 4 or 8 neighbours of a click | recolour by a map |
| the clicked region | recolour to the clicked colour |
| the region of a corner | shift by a fixed direction |
| the first cell of a colour in one of four scan orders | |
| all cells of a colour | |

The triggers are: a non-click action, a click, or any action.

**Lines of code.** The adapter has 1,611 lines; nothing is reused from the core:

| File | Lines |
|---|---|
| `wm/model.py` | 257 |
| `wm/induce.py` | 359 |
| `wm/arc3.py` | 133 |
| `wm/envs.py` (feasibility substitute) | 336 |
| `wm/classical.py` (substitute comparator) | 57 |
| `kernel/probe_template.py` | 287 |
| `kernel/build.py` | 23 |
| `run.py` | 159 |

**Designer exposure, stated plainly.**
- The piece kinds were first written for the substitute simulators in `wm/envs.py`. I wrote those simulators myself,
  so for the substitute the gain is partly by construction.
- On the real ARC-AGI-3 games the piece kinds were not designed with knowledge of the games' rules.
- Before the first development analysis (kernel version 2) I looked at statistics of the development games, such as
  how many pixels change and the block size. After that look I made changes for speed only:
  - vectorised moves;
  - piece colours limited to colours that change;
  - size caps on big colours and on actors;
  - a cap of 5 held checks.

  A regression check on the substitute gave the same counts before and after these changes.
- After the development numbers were seen, the only changes were to the statistics and the dev or held mode. No change
  touched the models or their predictions. Kernel version 3 reruns development to check that.
- The held games have never been seen.
