# Replayable demonstration: specification

Case selection rule, fixed before looking: the first development task, in sorted id
order, where BASE fails and BASE_PLUS_INTERVENTION produces a correct held-out output.
If none exists, the replay shows the best selection or efficiency effect instead, and
says so. An example chosen after evaluation is labelled illustrative, never evidence.

## What the replay must show, in order
1. the task demonstrations
2. the baseline candidate pool, or the recorded failure
3. the constructed program, exactly as executed
4. its prediction on the unseen input
5. the verification evidence behind it
6. external correctness, scored outside the inference path
7. the same task with the mechanism removed
8. runtime for both

## Rules
Executable replay, not an animation of the intended architecture.
At least one representative failure accompanies every success.
A hand-built positive control is labelled a control.
Reference outputs reach the scorer only, never the inference path.
