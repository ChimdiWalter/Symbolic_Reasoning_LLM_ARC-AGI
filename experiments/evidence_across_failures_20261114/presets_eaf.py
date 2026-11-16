"""Every preset of the evidence-across-failures experiment (EAF1), in one place.
Author: Chimdi Walter Ndubuisi

A development comparison on a known benchmark: stage A and the operations study ran on these same operations and their
outcomes are known. Numbers taken from the development roster are "development only". The numbers below that are not
new are imported from stage A's presets (frozen, hash checked by eaf_frozen) and not repeated.
"""
import eaf_frozen  # noqa: F401  (hash check, sys.path)
import presets_vf1 as V

LABEL = "development comparison on a known benchmark"
SEED = V.SEED
# ---- the 66 generator examples of a target, by role (disjoint)
N_GEN = 66
ACQ = (0, 9)                 # acquisition: nine argument tuples
ADM = (9, 21)                # admission: twelve
SUPPORT = (21, 24)           # reuse support: three
SETUP = (24, 36)             # setup: twelve (chooses the wrappers; nothing else)
FINAL = (36, 66)             # final evaluation: thirty
N_TUPLES = 9
# ---- wrappers (the one-argument library operation around the missing call), nested cohorts
N_WRAPPERS = 5               # the first five eligible ones in the target's seeded order
MIN_WRAPPERS = 3             # construction cohort
ADM_WRAPPER = 4              # admission cohort needs this one as well
REUSE_WRAPPER = 5            # reuse cohort needs this one as well
# ---- the five arms: [(argument tuple index, wrapper number)]
ARMS = {
    "A1x3": [(i, 1) for i in range(0, 3)],
    "A1x6": [(i, 1) for i in range(0, 6)],
    "A1x9": [(i, 1) for i in range(0, 9)],
    "A2x3": [(i, 1) for i in range(0, 3)] + [(i, 2) for i in range(3, 6)],
    "A3x3": [(i, 1) for i in range(0, 3)] + [(i, 2) for i in range(3, 6)] + [(i, 3) for i in range(6, 9)],
}
ARM_ORDER = tuple(ARMS)
# ---- this experiment's own seed tags. Stage A's order of wrappers and its pooled inputs are NOT reused: with them the
# one-wrapper three-example arm would be stage A's arm V again and part of every outcome could be read from its records.
WRAPPER_TAG = "eaf1-wrapper:"            # seeds the order of a target's candidate wrappers
SEQ_TAG = "eaf1-seq"                     # seeds a target's pooled sequence (stage A used "seq")
# ---- pooled slices (as in stage A): R setup redraw, A admission, UA usability for A, B final, UB usability for B
SEQ_TOTAL, SEQ_FRAC_R, SEQ_FRAC_A, SEQ_FRAC_B = V.SEQ_TOTAL, V.SEQ_FRAC_R, V.SEQ_FRAC_A, V.SEQ_FRAC_B
MIN_FINAL_POOL = V.MIN_FINAL_POOL        # 30 usable pooled tuples in UB, else exclude
N_ADM_POOL = V.N_ADM_POOL                # 12 usable pooled tuples in UA, else the admission role is unavailable
MAX_REDRAW = V.MAX_REDRAW
# ---- admission rule (stage A's, unchanged): wrapper 4 exact on 6 generator AND 6 pooled inputs, plus the bank
RULE_N = V.RULE_N
# ---- search (inherited) and the CPU allowance B per arm search and per reuse control
SIZE_V, SIZE_S, MAX_FN, MAX_BANK = V.SIZE_V, V.SIZE_S, V.MAX_FN, V.MAX_BANK
B = V.B                                  # 10 process-CPU seconds
DEV_ROSTER = V.DEV_ROSTER
