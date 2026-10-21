# An executable failure-to-revision controller (specification, 20 October 2026)

**Status:** a design for a later experiment (G3), not part of the real-ARC check. It addresses Toni Kazic's
question: can a system learn **which part of an inadequate explanation to reconsider**?

## 1. Information the controller may use

All of it is inference-visible:
- the visible training demonstrations;
- the execution mismatches of the current hypotheses (cells missing, extra or wrongly coloured, attributed to
  objects);
- uncertainty: the number of fitting programs, and their disagreement on the query;
- alternative hypotheses in the version space;
- fold-local validation: leave-one-out (LOO) reconstruction on the demonstrations;
- the remaining compute budget.

**Never:** test outputs, evaluator results, protected data.

## 2. Actions

Each action is an executable AST or search edit:

| action | what it changes |
|---|---|
| revise the object representation | view or segmentation |
| change the selector | which objects a rule picks |
| change the binding | which reference a rule uses |
| change an operation or parameter | what a rule does |
| add or remove a guard | where a rule applies |
| change the program composition | rule order or staging |
| allocate targeted additional search | budget on one slot |
| keep alternatives | hold several hypotheses |
| abstain | output the best attempts, labelled |

## 3. One step

1. Read the state.
2. Choose an action, with an auditable rationale.
3. **Apply it:** a concrete edit.
4. **Re-execute** on every demonstration.
5. **Measure the behaviour change:** cells fixed and cells broken.
6. Keep the edit or roll it back.
7. Repeat while budget remains.

A revision counts only if it changed a program and its execution.

## 4. Comparison (paired, matched compute)

| controller | what it uses |
|---|---|
| **authentic** | real mismatches and uncertainty; rule-based first, learned later |
| failure-blind | the same actions in a fixed or random order |
| shuffled traces | diagnoses from another task |
| try-all-actions | every action, within the budget |
| C+H-only repair | rerun the symbolic search with more budget |

**Episodes:**
- generated tasks whose first hypothesis is wrong in a known way (near-miss programs from DEV-style families),
  with held-out episodes from disjoint families;
- later, a fresh eligible real cohort.

**Metrics:**
- tasks where revision reaches a demonstration-fitting, LOO-passing **correct** program;
- revisions used;
- harmful revisions;
- compute.

**GO:** the authentic controller beats every control (paired, Holm-corrected) with a pre-registered net gain.
Wrong certificates count as errors.

## 5. Why it waits

Revision needs reachable correct programs to revise toward. The real-ARC check, then ncv2-g3, establish that first.
Earlier authentic-failure experiments (CORA-FHR) found no advantage over failure-blind controls. This must be a real
paired experiment, not a diagram.
