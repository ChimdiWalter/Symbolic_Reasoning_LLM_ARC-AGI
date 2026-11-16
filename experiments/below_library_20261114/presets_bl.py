"""Every preset of the below-library experiment (BL1), in one place.
Author: Chimdi Walter Ndubuisi

A development comparison on a known constructed benchmark: every operation of the library has been through the
operations study, stage A and the run of 14 November, and their outcomes are known. Numbers taken from the 20
development names are "development only". What is not new is imported from stage A's presets (frozen, hash checked
by bl_frozen) and not repeated.

The strata and the control names below were computed ONCE from census_source.json (sha256 in CENSUS_SHA256) over
the 145 operations of the roster (consumers.roster_all()), and are written out as literals. They are never computed
again at run time; a test recomputes them from the census file and compares.
"""
import bl_frozen  # noqa: F401  (hash check, sys.path)
import presets_vf1 as V

LABEL = "development comparison on a known constructed benchmark"
SEED = V.SEED
# ---- the 66 generator examples of a target, by position
N_GEN = 66
FIT9 = (0, 9)                # the nine-example fit set
FIT36 = (0, 36)              # the 36-example fit set (contains the nine)
FINAL = (36, 66)             # the 30 generator examples of the final panel
ROLE_RANGES = {"fit9": FIT9, "fit36": FIT36, "final": FINAL}
# ---- pooled sequence: drawn as on 14 November (stage A's total and fractions) under this experiment's own tag.
# The sequence is cut by position exactly as before (R, A, UA, B, UB); only two slices are used here:
# UB, the usability slice (eligibility only), and B, the final slice.
SEQ_TAG = "bl1-seq"
SEQ_TOTAL, SEQ_FRAC_R, SEQ_FRAC_A, SEQ_FRAC_B = V.SEQ_TOTAL, V.SEQ_FRAC_R, V.SEQ_FRAC_A, V.SEQ_FRAC_B
MIN_FINAL_POOL = V.MIN_FINAL_POOL        # 30 usable pooled tuples in the usability slice, else the target is excluded
# ---- limits, the same for every search
ALLOWANCE = 60.0             # processor seconds of one search when the combination budget is OFF: the binding budget,
#                              ending "allowance_used_up" (bounded); the enumerator's own hard stop comes 30 s later
TIME_SAFETY_LIMIT_S = 600.0  # processor seconds of one search when the combination budget is ON: a safety limit only;
#                              reaching it ("time_safety_limit") or the hard stop 30 s later is an infrastructure
#                              stop: the search and the record are incomplete, never "none"
MAX_BANK = 1_500_000         # cap on bank entries
MAX_FN = 16_000              # cap on function-valued entries (the leaves count towards it)
ARITY_RULE = True            # the wrapper's arity rule for the seven retained operations (build_bl.ARITY_RULES)
MAX_COMBINATIONS = 1_900_000  # set by the lead on 14 November: N_RECORD.json (derive_n.py over ticks_measure.json).
#                              A budget counted in candidate combinations, the same for every search (search_bl's
#                              max_ticks; the unit is an offered argument tuple: one combination of arguments
#                              across the example vector, as the enumerator counts it); None: OFF, and then the
#                              allowance above is the binding budget. When ON, processor time is TIME_SAFETY_LIMIT_S.
#                              A search stopped by it ends as "combination_budget_used_up" (bounded)
# ---- value bounds: every value a block of C returns, and every value returned by a function that a block calls
MAX_ELEMENTS = 3000          # elements of a container, at any depth (also: top-level elements of a usable output)
MAX_NESTING = 8              # levels of nesting of containers
MAX_INT_BITS = 40            # bits of an integer
# ---- ceiling on the memory of the process (address space), set by the runner at the start of every run mode;
# reaching it is an infrastructure stop, reported as incomplete
MEMORY_CEILING_BYTES = 32 * 2**30
# the largest address space the process ever had is read after every search, every setup stage and every final or
# witness check; within this margin of the ceiling (or unreadable) the unit of work is an infrastructure stop and
# the process ends with the exit status below
ADDRESS_SPACE_MARGIN_BYTES = 2**30
EXIT_NEAR_CEILING = 86
# ---- guards (processor seconds)
FINAL_GUARD_S = 30.0         # one guard around each batch of evaluations on the final panel (and each witness batch)
STREAM_GUARD_S = 20.0        # one guard around each pass of the true operation over a pooled slice (as on 14 November)
# ---- sizes
SIZE_L4 = 4
SIZE_L5 = 5
SIZE_C_CANDIDATES = (4, 5, 6)
SIZE_C = 4                   # set by the lead on 14 November from pilot_s.json by the 80% rule (None would refuse an all-roster run)
PILOT_COMPLETION_SHARE = 0.8  # the rule for s: at least this share of the searches without a fit complete the level
# ---- the six searches of a target: (name, block set, role of its examples, size limit or "SIZE_C")
SEARCHES = (
    ("L4-9", "L", "fit9", SIZE_L4),
    ("LC4-9", "LC", "fit9", SIZE_L4),
    ("L4-36", "L", "fit36", SIZE_L4),
    ("L5-36", "L", "fit36", SIZE_L5),
    ("LC4-36", "LC", "fit36", SIZE_L4),
    ("C-36", "C", "fit36", "SIZE_C"),
)
SEARCH_NAMES = tuple(s[0] for s in SEARCHES)
NINE = ("L4-9", "LC4-9")
THIRTY_SIX = ("L4-36", "L5-36", "LC4-36", "C-36")
# ---- the two systems: (first stage, second stage), selected on fit alone
SYSTEMS = {"library_only": ("L4-36", "L5-36"), "smaller_blocks": ("LC4-36", "C-36")}
SYSTEM_NAMES = ("library_only", "smaller_blocks")
SYSTEM_ALLOCATION_S = 2 * ALLOWANCE      # 120 processor seconds allocated to each system for a target
# ---- the seven retained higher-order library operations of C
RETAINED = ("compose", "chain", "fork", "lbind", "rbind", "matcher", "power")
# ---- calibration (protocol section 9)
CALIBRATION_MIN_K = 19       # 20 in the drafts. Amendment by the author on 15 November 2026, AFTER the setup pass over all names
#                              gave K = 19 (SETUP_RECORD_ALL.json) and BEFORE any search outside the development names or any
#                              outcome on a control: with 20 the calibration could not have been valid. The rule for K, the
#                              controls, the witnesses, the blocks, the exclusions and the share are unchanged
CALIBRATION_MIN_K_NOTE = ("amendment of 15 November 2026 by the author: the minimum was 20 in the drafts; it was lowered to 19 after the "
                          "setup pass over all names gave K = 19 and before any search outside the development names or any outcome")
CALIBRATION_SHARE = 0.9      # passed when C-36 is right for at least ceil(0.9 * K) of the K controls
WITNESS_MANIFEST = "witness_manifest.json"
# ---- names
DEV_ROSTER = V.DEV_ROSTER
CENSUS_FILE = "census_source.json"
CENSUS_SHA256 = "587956cf18038c0999ce51d26f57f9171b7a7dc700b337116adaad3aaa1ce226"
SHORT_MAX_NODES = 6          # "short": the source body has at most six census nodes; "longer": at least seven
LONGER_SPLIT_NODES = 15      # the two halves of the longer stratum: 7 to 15 nodes, and more than 15

# 42 names of the roster (35 outside the development names): source body of at most six census nodes
STRATUM_SHORT = (
    "identity", "even", "equality", "contained", "intersection", "order", "greater", "size", "maximum", "minimum",
    "valmax", "valmin", "argmax", "argmin", "leastcommon", "initset", "positive", "toivec", "tojvec", "mfilter",
    "totuple", "first", "last", "insert", "other", "interval", "astuple", "pair", "branch", "mapply", "mpapply",
    "shape", "portrait", "neighbors", "adjacent", "numcolors", "color", "vconcat", "subgrid", "cover", "lefthalf",
    "righthalf",
)
# 39 names of the roster (35 outside the development names): 7 to 15 census nodes
STRATUM_LONGER_7_TO_15 = (
    "invert", "combine", "difference", "dedupe", "repeat", "merge", "sfilter", "extract", "remove", "product",
    "apply", "rapply", "papply", "prapply", "uppermost", "lowermost", "leftmost", "rightmost", "colorfilter",
    "sizefilter", "ulcorner", "lrcorner", "recolor", "normalize", "vline", "hline", "centerofmass", "rot90",
    "rot180", "vupscale", "hconcat", "center", "corners", "move", "tophalf", "bottomhalf", "vfrontier", "hfrontier",
    "delta",
)
# 64 names of the roster (55 outside the development names): more than 15 census nodes
STRATUM_LONGER_OVER_15 = (
    "add", "subtract", "multiply", "divide", "double", "halve", "increment", "decrement", "crement", "sign",
    "mostcolor", "leastcolor", "toindices", "height", "width", "colorcount", "asindices", "ofcolor", "urcorner",
    "llcorner", "crop", "shift", "dneighbors", "ineighbors", "objects", "palette", "partition", "fgpartition",
    "square", "hmatching", "vmatching", "manhattan", "bordering", "toobject", "asobject", "rot270", "hmirror",
    "vmirror", "dmirror", "cmirror", "fill", "paint", "underfill", "underpaint", "hupscale", "hsplit", "vsplit",
    "cellwise", "replace", "switch", "position", "index", "canvas", "connect", "backdrop", "gravitate", "inbox",
    "outbox", "box", "shoot", "occurrences", "frontiers", "hperiod", "vperiod",
)
STRATUM_LONGER = STRATUM_LONGER_7_TO_15 + STRATUM_LONGER_OVER_15       # 103 names (90 outside the development names)
# The 28 known-answer controls: the operations outside the development names whose source body is a single return
# expression of at most six census nodes with no call of a library operation, no lambda and no comprehension.
CONTROL_NAMES = (
    "identity", "even", "equality", "contained", "intersection", "order", "greater", "size", "maximum", "minimum",
    "valmax", "valmin", "argmax", "argmin", "leastcommon", "initset", "positive", "toivec", "tojvec", "totuple",
    "first", "last", "insert", "interval", "astuple", "pair", "branch", "vconcat",
)
DEV_CONTROL = "color"        # the 29th such operation is a development name: the development control


def stratum_of(name):
    """'short' or 'longer' for a name of the roster; None for any other name."""
    if name in STRATUM_SHORT:
        return "short"
    if name in STRATUM_LONGER:
        return "longer"
    return None


def half_of(name):
    """'7_to_15' or 'over_15' for a name of the longer stratum; None otherwise."""
    if name in STRATUM_LONGER_7_TO_15:
        return "7_to_15"
    if name in STRATUM_LONGER_OVER_15:
        return "over_15"
    return None


def combination_budget():
    """The budget of a search counted in candidate combinations: None (off) or a positive whole number."""
    m = MAX_COMBINATIONS
    if m is None:
        return None
    if isinstance(m, bool) or not isinstance(m, int) or m <= 0:
        raise RuntimeError("presets MAX_COMBINATIONS must be None (off) or a positive whole number, not %r" % (m,))
    return m


def cpu_budget():
    """The processor seconds handed to the enumerator: the allowance (a binding budget) when the combination budget
    is off; the safety limit when it is on."""
    return ALLOWANCE if combination_budget() is None else TIME_SAFETY_LIMIT_S


def system_allocation():
    """What each of the two systems is allocated for a target, in the unit of the budget in force."""
    m = combination_budget()
    if m is None:
        return dict(unit="processor seconds", per_system=SYSTEM_ALLOCATION_S)
    return dict(unit="offered argument tuples (combinations counted by the enumerator); not processor time",
                per_system=2 * m, processor_seconds_safety_limit_per_search=TIME_SAFETY_LIMIT_S)


def size_limit(search_name):
    """The size limit of one of the six searches. C-36 uses SIZE_C, which must have been set."""
    for name, _, _, size in SEARCHES:
        if name == search_name:
            if size == "SIZE_C":
                if SIZE_C not in SIZE_C_CANDIDATES:
                    raise RuntimeError("SIZE_C is not set to one of %s (it is %r)" % (SIZE_C_CANDIDATES, SIZE_C))
                return SIZE_C
            return size
    raise KeyError(search_name)
