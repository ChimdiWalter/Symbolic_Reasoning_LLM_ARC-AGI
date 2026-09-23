# CORA: Separating Search, Hypothesis Selection, and Capability Growth in ARC-AGI-2

Status: skeleton for the ARC Prize 2026 paper track. Written before results exist.
The title changes to match the measured result, never the desired one.

## 1. Problem
ARC-AGI-2 under a 12-hour offline budget, two outputs per test input, exact match.
One research question: can a task-local, executable program construction improve
held-out predictions beyond ordinary search over the same building blocks, under
matched total compute?

## 2. The system, in one page
Three-layer certified induction. A program is accepted only if, rebuilt from all
demonstrations but one, it predicts the one left out, for every fold. Two outputs:
attempt 1 certified, attempt 2 error-diverse. One global time governor.

## 3. The distinction the paper is built on
Search improvement, selection improvement and capability growth are three different
things. Prior measurement: every policy solved the same 188 of 256 targets, so the
learned system searched more cheaply and changed some predictions without gaining reach.
A score gain is never reported as invention.

## 4. The controlled comparison
BASE, BASE_PLUS_INTERVENTION, MATCHED_EXPANDED_SEARCH, ABLATION, under one fixed
budget and a schedule frozen before scoring. Paired wins and losses, not net.

## 5. Results
To be filled from the frozen evaluation. Report pass@2, pass@1, second-answer rescue,
candidate-pool coverage as a diagnostic only, timeouts, end-to-end runtime.

## 6. Why it helps or fails
The diagnosis table: no useful candidate, candidate present but not selected,
demonstration-fitting but wrong, verification rejection, resource exhaustion,
packaging loss.

## 7. Limitations
Certification does not transfer off distribution: 40 of 42 on training against 0 of 11
on the evaluation development split. No training-set headline number appears here.

## 8. Related work
DreamCoder, LILO, POPPI, AlphaEvolve and non-LLM ARC systems. The novelty case is the
conjunction under an immutable verifier, never a component name. Sweep primary sources
before any precedence wording.

## Out of scope
Step B, the capability-growth gate, VDCG, biological applications. Step B is named as
ongoing with no result claimed.
