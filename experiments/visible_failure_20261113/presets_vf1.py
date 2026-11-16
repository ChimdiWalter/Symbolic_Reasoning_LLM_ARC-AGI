"""Every preset of stage A of the visible-failure construction (VF1), in one place.
Author: Chimdi Walter Ndubuisi

Inherited from the operations study (experiments/core_operations_20261113, frozen; imported read-only): the typed
generator, the lesion rule, the enumerator's order and type filter, the caps. New here: the numbers below.
All numbers are "development only" until a freeze is written by the author after the development rehearsal.
"""
import hashlib

SEED = 20261113
# ---- examples
# Five disjoint record sets per target (66 generator examples; the first 36 are the operations study's):
#   acquisition 0-2 | admission grid 3-14 | reuse support 15-17 | setup 18-35 | final 36-65
N_GEN = 66
N_ACQ = 3                    # acquisition examples: generator inputs 0-2 (the three shown examples)
GRID_FROM = 3                # admission grid: generator inputs 3-14 (12), nested prefixes of 3, 6, 12; opened after sealing
N_GRID = 12
GRID_NS = (3, 6, 12)
RULE_N = 6                   # THE RULE: adm_both at n = 6 (6 generator plus 6 pooled examples of the admission consumer) plus the bank
SUPPORT_FROM = 15            # reuse support: generator inputs 15-17 (opened after the library is sealed)
N_SUPPORT = 3
SETUP_FROM = 18              # setup: generator inputs 18-35, used ONLY to choose the three post operations
SETUP_TO = 36
FINAL_FROM = 36              # final evaluation: generator inputs 36-65 (30), opened only in the last step
N_FINAL_GEN = 30
N_TEACH = 6                  # declared teacher examples (arm T): generator inputs 0-5 (3-5 overlap the admission grid)
N_ADM_POOL = 12              # pooled admission inputs (stream A); the rule uses the first RULE_N
SEQ_TOTAL = 1600             # unique pooled tuples sought per target (fewer exist for some targets)
SEQ_FRAC_R = 0.10            # the sequence is cut by position into five disjoint slices: R (setup redraw) 10%,
SEQ_FRAC_A = 0.20            # A (admission) 20%, UA (setup usability, same size as A) 20%,
SEQ_FRAC_B = 0.25            # B (final) 25%, UB (setup usability, same size as B) 25%
MIN_FINAL_POOL = 30          # the final panel should have at least this many usable pooled inputs (else flagged, never excluded after a search)
MAX_REDRAW = 5               # redraws of acquisition (and admission) examples when a trivial repair passes
N_CONSUMERS = 3              # acquisition, admission, reuse
# ---- search
SIZE_V = 4                   # missing call: at most 4 nodes (inherited)
SIZE_S = 5                   # whole program: one node more (post), so every program V can reach is within reach
MAX_FN = 300                 # inherited cap on function-valued entries
MAX_BANK = 250000            # inherited cap on bank entries
N_COLLECT = 20               # fitting candidates kept by the selection controls
N_SEEDS = 5                  # seeds of every random control
# ---- CPU allowance B: process CPU seconds per acquisition arm (proposed from the development rehearsal)
B = 10.0
DIAG_FRACTION = 0.1          # nothing-hidden diagnosis search: B/10
FIXED_LIB_BIG = 10           # fixed-library search with 10 B, only for targets where V admitted something
GUARD_CPU = 30.0             # guard on one batch of evaluations of a library expression (CPU seconds)
# ---- development roster: the operations study's 13 plus 7 from families it did NOT hold out
DEV_SEEN_OPS = ("hmirror", "rot180", "width", "switch", "objects", "lefthalf", "add", "mapply", "ofcolor", "tophalf",
                "mfilter", "other", "righthalf")
# rule: names outside held_out_names() and outside DEV_SEEN_OPS that the generator can serve, sorted by
# sha256("vf1-dev:" + name), the first 7. Written out by name (tests re-derive it).
DEV_EXTRA_RULE_TAG = "vf1-dev:"
DEV_EXTRA_OPS = ("vfrontier", "sign", "rapply", "backdrop", "color", "box", "numcolors")
DEV_ROSTER = DEV_SEEN_OPS + DEV_EXTRA_OPS
PRESERVATION_BANK_OPS = ("hmirror", "vmirror", "rot90", "height", "width", "mostcolor", "palette", "numcolors",
                         "size", "first", "last", "dmirror")
N_BANK_GRIDS = 4


def derive_dev_extra(candidates_ok, held_out, k=7):
    """Re-derive DEV_EXTRA_OPS from the library names the generator serves (`candidates_ok`)."""
    c = [o for o in candidates_ok if o not in held_out and o not in DEV_SEEN_OPS]
    c.sort(key=lambda n: hashlib.sha256((DEV_EXTRA_RULE_TAG + n).encode()).hexdigest())
    return tuple(c[:k])
