"""The frozen baseline B and the novelty classes (docs/CORA_FHR_GGROW_v1.md section 4).

B_native: native's own detect_grow (nothing installed) explains an instance when it returns a mode other than
the constant `pattern` (fill_holes is gated off natively by ARC_EXPR_GRAMMAR). B_reach: the frozen cora_reach
grammar, 9 families / 210 settings, explains an instance set when one setting reproduces every instance's
added cells.

Classes for a set of instances that a constructed operator explains:
  AVAILABLE_NATIVE  every instance is explained by a native growth mode  (selection; not growth)
  AVAILABLE_REACH   one B_reach setting reproduces every instance        (selection; not growth)
  NEW_COMPOSITION   neither                                              (compositional growth, L2)
"""
import numpy as np


def native_explains(O, A, colour, G) -> bool:
    from geocat_arc.object_reasoning import growth as GR
    G = np.asarray(G, dtype=int)
    in_cc = {(int(r), int(c)): int(v) for (r, c), v in O.items()}
    out_cc = dict(in_cc)
    out_cc.update({(int(r), int(c)): int(colour) for r, c in A})
    res = GR.detect_grow(in_cc, out_cc, G.shape, G)
    return res is not None and res.get("mode") != "pattern"


def reach_setting(instances):
    """The first B_reach setting reproducing every instance's added cells, or None.
    instances: list of (O dict, A set, G)."""
    from cora_reach import construct as CN
    from cora_reach import relations as REL
    for fam, params in REL.settings(CN.GRAMMAR):
        if all(REL.apply(fam, params, set(O), np.asarray(G, dtype=int)) == set(A) for O, A, G in instances):
            return {"family": fam, "params": params}
    return None


def classify(instances, colours):
    """Novelty class of the instance set a constructed operator explains (colours: the single added colour per
    instance)."""
    if instances and all(native_explains(O, A, col, G) for (O, A, G), col in zip(instances, colours)):
        return {"class": "AVAILABLE_NATIVE", "reach": None}
    hit = reach_setting(instances)
    if hit is not None:
        return {"class": "AVAILABLE_REACH", "reach": hit}
    return {"class": "NEW_COMPOSITION", "reach": None}
