"""The INDEPENDENT forensic reference for the agreement audit, hand-encoded from
records/LOO_V1_DIAGNOSIS_20261012.md (fold table and mechanism section) and
records/CTL0_PHASE1_FEASIBILITY_20261012.md (sections 2-3). Used ONLY to audit
v0's output; diagnose.py and arc_adapter.py never import it. Categories outside
v0's vocabulary (INSUFFICIENT_EVIDENCE) are kept, so v0 is charged for missing them.
unit -> (primary, set)"""
RE, RN, MP, ER, CU, RX, IE = ("REPRESENTATION_EXCLUDED", "REPAIR_NOT_GENERATED", "MULTIPLE_PLAUSIBLE_REPAIRS",
                              "ENGINE_REJECTED", "CERTIFICATION_UNSTABLE", "RESOURCE_EXHAUSTED", "INSUFFICIENT_EVIDENCE")
LOO_FAIL = {RE, ER, CU}
REFERENCE = {
    "kf892487f1049:full": (None, set()),                  # accepted and used at full data
    "kf892487f1049:f0": (RE, LOO_FAIL), "kf892487f1049:f2": (RE, LOO_FAIL), "kf892487f1049:f3": (RE, LOO_FAIL),
    "kf892487f1049:f1": (MP, LOO_FAIL | {MP}),            # two fitting repairs; the inner cap still cuts the view
    "k5a49896251a2:full": (RE, LOO_FAIL), "k5a49896251a2:f1": (RE, LOO_FAIL),
    "k5a49896251a2:f0": (RN, {RN, RE}), "k5a49896251a2:f2": (RN, {RN, RE}),   # the extraction cuts the view
    "k017955a77fc5:full": (RX, {RX, RE}),                 # hard cap; the view is incoherent at full data
    "k017955a77fc5:f0": (RN, {RN, IE}), "k017955a77fc5:f1": (RN, {RN, IE}),   # support lost
    "k017955a77fc5:f2": (IE, {RX, IE}),                   # cap; identifiability from one demonstration
    "k5991e227189e:full": (RX, {RX, RE}), "k5991e227189e:f0": (RE, LOO_FAIL),
    "k5991e227189e:f1": (RN, {RN, RE}), "k5991e227189e:f2": (RX, {RX, RE}), "k5991e227189e:f3": (RX, {RX, RE}),
}
