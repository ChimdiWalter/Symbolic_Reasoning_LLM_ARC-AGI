# Cover image specification

One figure, for the Kaggle Media Gallery. Build script: `kaggle/cover_image.py`.

## Layout

Three panels left to right, one band underneath.

    +----------------------+  +----------------------+  +----------------------+
    | fixed K reasons      |  | semantic failure     |  | temporary K + e      |
    | and reaches failure  |  | frontier, the typed  |  | reasons again        |
    |                      |  | failure graph        |  |                      |
    | [MEASURED]           |  | [MEASURED, REPAIRED] |  | [SPECIFIED ONLY]     |
    +----------------------+  +----------------------+  +----------------------+

    Step B, durable promotion path            CORA-TTI, task-local reset path
    [ONGOING, NO VERDICT]                     [PARTIALLY IMPLEMENTED]

## Status labels

Every component carries one of three labels, rendered in a visually distinct
style so an unfinished component can never read as complete:

- MEASURED: implemented and has numbers in the paper.
- ONGOING: running, no interpretable result.
- SPECIFIED ONLY: designed and not implemented.

The right panel is SPECIFIED ONLY, because the constructive AST proposer and
the extension compiler are not implemented. It must not be drawn in the same
style as the left and centre panels.

## Content notes

The centre panel is the honest centre of the paper: the frontier is what was
broken, diagnosed and repaired. It may show the before and after contrast,
one invariant operator against twelve task-dependent operator families.

No score appears on the cover. No claim of invention appears on the cover.
