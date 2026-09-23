# Cover image specification

One figure, for the Kaggle Media Gallery. Build script: `kaggle/cover_image.py`.

## Layout

One vertical flow, with the two timescales branching underneath.

    INPUT TASK
        |
        v
    FIXED-LANGUAGE CORA, K                      [IMPLEMENTED]
        |
        +---- solve ----> prediction
        |
        +---- fail
               |
               v
        SEMANTIC FAILURE FRONTIER               [REPAIRED, MEASURED]
               |
               v
        CONSTRUCT e                             [SPECIFIED ONLY]
               |
               v
           K + {e}                              [SPECIFIED ONLY]
               |
               v
        VERIFY and ABLATE                       [IMPLEMENTED]
               |
               v
           prediction

    CORA-TTI: temporary e, then reset           [PARTIALLY IMPLEMENTED]
    Step B:   verified transferable e,          [ONGOING, NO VERDICT]
              then durable promotion

## Status labels

Every component carries one of three labels, rendered in a visually distinct
style so an unfinished component can never read as complete:

- MEASURED: implemented and has numbers in the paper.
- ONGOING: running, no interpretable result.
- SPECIFIED ONLY: designed and not implemented.

The construct and install steps are SPECIFIED ONLY, because the constructive
AST proposer and the extension compiler are not implemented. They must not be
drawn in the same style as the implemented and measured steps.

## Content notes

The frontier node is the honest centre of the paper: it is what was broken,
diagnosed and repaired. It may carry the before and after contrast, one
invariant operator against twelve task-dependent operator families.

No score appears on the cover. No claim of invention appears on the cover.
