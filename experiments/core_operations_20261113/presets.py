"""Frozen presets of the core-operations measurement (see PROTOCOL.md). Author: Chimdi Walter Ndubuisi."""
N_FIT = 6
N_VAL = 30
CHECKS = (1, 2, 3, 6)        # the K arms: a separate search that sees only the first K fit examples
MAX_SIZE = 4                 # largest expression size (number of nodes) enumerated
# process CPU seconds per search; each arm is a separate search (safety nets, see PROTOCOL.md for the division)
BUDGET_S = {"1": 5.0, "2": 6.0, "3": 8.0, "6": 10.0, "oracle": 40.0}
MAX_FN = 300                 # cap on function-valued bank entries (closures)
MAX_BANK = 250000            # cap on bank entries (memory guard)
PILOT_OPS = ("hmirror", "rot180", "width", "switch", "objects", "lefthalf", "add", "mapply", "ofcolor", "tophalf")
# every operation whose outcome was seen before the freeze: the pilot subset and the known-answer control run
DEV_SEEN_OPS = PILOT_OPS + ("mfilter", "other", "righthalf")
