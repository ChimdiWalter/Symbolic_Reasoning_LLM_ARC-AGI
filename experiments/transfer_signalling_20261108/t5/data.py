"""Signalling data for T5: SIF prior networks, MIDAS perturbation data, and CellNOpt-style preprocessing.

Conventions, following CellNOptR (readSIF, readMIDAS, makeCNOlist, preprocessing):
- SIF lines are "source <sign> target" with sign 1 (activation) or -1 (inhibition);
- MIDAS columns: TR:<cue> are treatments (a cue whose name ends in "i" inhibits the node named without the "i"; any
  other cue is a stimulus; TR:<x>:CellLine is ignored), DA:<readout> is the time, DV:<readout> the normalised value;
- a condition is one stimulus-and-inhibitor vector measured at the first time after 0 (CellNOpt's t1); time-0 rows give
  the basal observations, matched to a condition by identical cues, else by identical inhibitors, else the cue-free row;
- preprocessing removes non-observable or non-controllable nodes, compresses undesignated single-input or
  single-output nodes, and expands every node's inputs into AND gates of up to two inputs (maxInputsPerGate = 2).
"""
import itertools
import math


def _lines(path):
    with open(path, "rb") as f:
        raw = f.read().decode("utf-8", "replace")
    return [x for x in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n") if x.strip()]


def read_sif(path):
    edges = []
    for ln in _lines(path):
        p = ln.split()
        if len(p) != 3:
            raise ValueError(f"bad SIF line: {ln!r}")
        s = int(p[1])
        if s not in (1, -1):
            raise ValueError(f"bad SIF sign: {ln!r}")
        edges.append((p[0], s, p[2]))
    return sorted(set(edges))


class Midas:
    """Parsed MIDAS: stimuli, inhibitors (node names), readouts, and rows (cues, time, values with None for NaN)."""

    def __init__(self, path):
        rows = [ln.split(",") for ln in _lines(path)]
        head = [h.strip() for h in rows[0]]
        self.tr, self.da, self.dv = [], [], []
        for j, h in enumerate(head):
            if h.startswith("TR:") and not h.endswith(":CellLine"):
                self.tr.append((j, h[3:]))
            elif h.startswith("DA:"):
                self.da.append((j, h[3:]))
            elif h.startswith("DV:"):
                self.dv.append((j, h[3:]))
        self.stimuli = [c for _, c in self.tr if not c.endswith("i")]
        self.inhibitors = [c[:-1] for _, c in self.tr if c.endswith("i")]
        self.readouts = [r for _, r in self.dv]
        self.rows = []
        for r in rows[1:]:
            cues = tuple(int(float(r[j] or 0)) for j, _ in self.tr)
            times = {float(r[j]) for j, _ in self.da if r[j].strip() not in ("", "NA", "NaN")}
            if len(times) != 1:
                raise ValueError("a row with several times")
            vals = []
            for j, _ in self.dv:
                x = r[j].strip() if j < len(r) else ""
                v = float(x) if x and x.lower() not in ("nan", "na") else float("nan")
                vals.append(None if math.isnan(v) else v)
            self.rows.append((cues, times.pop(), tuple(vals)))
        self.times = sorted({t for _, t, _ in self.rows})

    def cue_split(self, cues):
        stim = tuple(v for (_, c), v in zip(self.tr, cues) if not c.endswith("i"))
        inh = tuple(v for (_, c), v in zip(self.tr, cues) if c.endswith("i"))
        return stim, inh


class Dataset:
    """Conditions at t1 with matched basal (time-0) observations. Values are floats in [0, 1] or None."""

    def __init__(self, name, sif_path, midas_path, t1=None):
        self.name = name
        self.pkn = read_sif(sif_path)
        m = Midas(midas_path)
        self.stimuli, self.inhibitors, self.readouts = m.stimuli, m.inhibitors, m.readouts
        later = [t for t in m.times if t > 0]
        self.t1 = later[0] if t1 is None else t1
        zero = {}
        for cues, t, vals in m.rows:
            if t == 0:
                zero.setdefault(cues, vals)
        self.conditions = []        # list of dicts: key, stim (tuple), inh (tuple), t1 (values), t0 (values or None)
        seen = set()
        for cues, t, vals in m.rows:
            if t != self.t1:
                continue
            if cues in seen:
                raise ValueError(f"{name}: duplicate condition rows (replicates are not supported)")
            seen.add(cues)
            stim, inh = m.cue_split(cues)
            t0 = zero.get(cues)
            if t0 is None:
                for c2, v2 in zero.items():
                    s2, i2 = m.cue_split(c2)
                    if i2 == inh and not any(s2):
                        t0 = v2
                        break
            if t0 is None:
                for c2, v2 in zero.items():
                    if not any(c2):
                        t0 = v2
                        break
            self.conditions.append({"key": self.cond_key(stim, inh), "stim": stim, "inh": inh, "t1": vals, "t0": t0})

    def cond_key(self, stim, inh):
        s = "+".join(n for n, v in zip(self.stimuli, stim) if v) or "none"
        i = "+".join(n + "i" for n, v in zip(self.inhibitors, inh) if v) or "none"
        return f"{s}|{i}"


def design_only(ds):
    """A copy of the dataset's design (cues and readouts) with every measured value removed: used by development runs
    on the held dataset's design, so that no held measurement can enter development."""
    out = Dataset.__new__(Dataset)
    out.name, out.pkn, out.t1 = ds.name + "_design", ds.pkn, ds.t1
    out.stimuli, out.inhibitors, out.readouts = ds.stimuli, ds.inhibitors, ds.readouts
    out.conditions = [{"key": c["key"], "stim": c["stim"], "inh": c["inh"], "t1": None, "t0": None}
                      for c in ds.conditions]
    return out


# ---------------------------------------------------------------------------------------------------- preprocessing
def _reach(adj, starts):
    seen, stack = set(starts), list(starts)
    while stack:
        u = stack.pop()
        for v in adj.get(u, ()):
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return seen


def cut_nonc(edges, designated, stimuli, readouts):
    """Remove undesignated nodes that no stimulus reaches (non-controllable) or that reach no readout (non-observable),
    with their edges; repeat until stable."""
    while True:
        fwd, bwd = {}, {}
        for u, _, v in edges:
            fwd.setdefault(u, set()).add(v)
            bwd.setdefault(v, set()).add(u)
        nodes = set(fwd) | set(bwd)
        ctrl = _reach(fwd, [s for s in stimuli if s in nodes])
        obs = _reach(bwd, [r for r in readouts if r in nodes])
        drop = {n for n in nodes if n not in designated and (n not in ctrl or n not in obs)}
        if not drop:
            return edges
        edges = [e for e in edges if e[0] not in drop and e[2] not in drop]


def compress(edges, designated):
    """Remove undesignated nodes with exactly one input or exactly one output, joining each input to each output with
    the product of the signs. A node is kept when joining would create a self-loop. Repeat in name order until no node
    can be removed. Duplicate edges with the same sign merge; opposite signs are kept as two edges."""
    edges = set(edges)
    changed = True
    while changed:
        changed = False
        nodes = sorted({u for u, _, _ in edges} | {v for _, _, v in edges})
        for n in nodes:
            if n in designated:
                continue
            ins = [(u, s) for u, s, v in edges if v == n]
            outs = [(v, s) for u, s, v in edges if u == n]
            if any(u == n for u, _ in ins):
                continue
            if not (len(ins) == 1 or len(outs) == 1) or not ins or not outs:
                continue
            new = {(u, s1 * s2, v) for u, s1 in ins for v, s2 in outs}
            if any(u == v for u, _, v in new):
                continue
            edges = {e for e in edges if e[0] != n and e[2] != n} | new
            changed = True
            break
    return sorted(edges)


def expand(edges, max_inputs=2):
    """Hyperedges: every single edge, plus AND gates over every combination of 2..max_inputs inputs of a node from
    distinct sources. A hyperedge is (target, ((source, sign), ...)) with inputs sorted."""
    by_t = {}
    for u, s, v in edges:
        by_t.setdefault(v, []).append((u, s))
    hyp = []
    for v in sorted(by_t):
        ins = sorted(set(by_t[v]))
        for k in range(1, max_inputs + 1):
            for combo in itertools.combinations(ins, k):
                if len({u for u, _ in combo}) < k:
                    continue
                hyp.append((v, tuple(combo)))
    return hyp


def preprocess(ds, max_inputs=2, compression=True):
    designated = set(ds.stimuli) | set(ds.inhibitors) | set(ds.readouts)
    nodes = {u for u, _, _ in ds.pkn} | {v for _, _, v in ds.pkn}
    missing = [x for x in designated if x not in nodes]
    if missing:
        raise ValueError(f"{ds.name}: designated species absent from the PKN: {missing}")
    e = cut_nonc(list(ds.pkn), designated, ds.stimuli, ds.readouts)
    if compression:
        e = compress(e, designated)
        e = cut_nonc(e, designated, ds.stimuli, ds.readouts)
    return e, expand(e, max_inputs)
