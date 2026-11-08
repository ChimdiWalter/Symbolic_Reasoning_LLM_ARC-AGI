"""The CORA loop on logic models: fit, describe the failure, build edges or gates, check again, keep only what helps.

Failure description (from the representative least-error model on the training columns), per readout:
- "on": the columns where the readout is measured ON but predicted OFF (want), with the columns where it is correctly
  OFF (must stay OFF);
- "off": the columns where it is measured OFF but predicted ON (want), with the columns where it is correctly ON (must
  stay ON).
Pieces built from it, all into the failing readout r, from sources that are not downstream of r in the current space.
That check is made per piece, so pieces added in the same round into different readouts can still close a loop between
readouts, and a grown program can be cyclic. A cyclic program is simulated by synchronous iteration; bits that do not
settle are NA and count as wrong (t5/model.py). The pieces are:
- for "on": a new edge (one signed input) or a new two-input AND gate whose value covers the want columns; score =
  want columns covered minus must-stay-OFF columns turned ON;
- for "off": a gate that extends an active input term of r with one more signed input (AND), so the term switches off
  on the want columns; score = want columns fixed minus must-stay-ON columns lost.
Pieces with a positive score are ranked (score, then fewer inputs, then name), at most PER_FAILURE per failure and
PER_ROUND per round. Repair (minimal change): the current program is kept and each piece, in rank order, is added when
it lowers the training errors (a gate replaces the term it extends when that is better); the failure is described
again and the next round starts, for at most ROUNDS rounds.

Acceptance (keep the pieces only if they help on held checks), with rebuilding: the training conditions are split into
K_IN internal folds; in each fold the static program is fitted without the fold and the whole growth procedure is
rebuilt without the fold; both programs predict the fold. The grown program is kept only if the summed fold errors of
the rebuilt growth are at most those of the static programs minus BAR data points; otherwise the grown arm returns the
static program.

Shuffled control: identical, except that every failure description's column sets are moved by one Sattolo cycle over
the training columns before pieces are built. The cycle runs over the t1 and t0 columns together, so a moved column can
change time point; the readout and the direction (ON or OFF) of each failure are kept. This is weaker than a shuffle
within each time point: moved sets often land on t0 columns, where most nodes are off.
"""
import hashlib

from .model import Space, simulate
from .search import fit, rng_for


def _bits(mask):
    out, k = [], 0
    while mask:
        if mask & 1:
            out.append(k)
        mask >>= 1
        k += 1
    return out


def _permute(mask, perm):
    out = 0
    for k in _bits(mask):
        out |= 1 << perm[k]
    return out


def sattolo_over(cols, rng):
    """A single cycle over the given column positions (no fixed point): returns {col: image}."""
    a = list(cols)
    n = len(a)
    idx = list(range(n))
    for i in range(n - 1, 0, -1):
        j = rng.randrange(i)
        idx[i], idx[j] = idx[j], idx[i]
    return {a[i]: a[idx[i]] for i in range(n)}


def describe_failure(space, design, obs, model, colmask):
    x, na = simulate(space, design, model)
    res = obs.residual(x, na)
    desc = []
    for j, r in enumerate(space.readouts):
        miss_on, miss_off, keep_on, keep_off = (m & colmask for m in res[j])
        if miss_on:
            desc.append({"readout": r, "dir": "on", "want": miss_on, "keep": keep_off})
        if miss_off:
            desc.append({"readout": r, "dir": "off", "want": miss_off, "keep": keep_on})
    return desc, x, na


def shuffle_description(desc, colmask, rng):
    perm = sattolo_over(_bits(colmask), rng)
    out = []
    for f in desc:
        g = dict(f)
        g["want"] = _permute(f["want"], perm)
        g["keep"] = _permute(f["keep"], perm)
        out.append(g)
    return out


def _lit_name(space, u, neg):
    return ("!" if neg else "") + space.nodes[u]


def build_pieces(space, design, x, na, model, desc, cfg):
    full = design.full
    existing = {(t, lits) for t, lits in space.hyper}
    cands = {}
    for f in desc:
        r = space.ix[f["readout"]]
        down = space.descendants(r)
        src = [u for u in range(space.N) if u not in down]
        col = {}
        for u in src:
            ok = full if na is None else ~na[u] & full
            col[(u, False)] = x[u] & ok
            col[(u, True)] = ~x[u] & ok
        lits = sorted(col, key=lambda t: (space.nodes[t[0]], t[1]))
        found = []
        if f["dir"] == "on":
            P, Z = f["want"], f["keep"]
            for a in lits:
                g = col[a]
                sc = (g & P).bit_count() - (g & Z).bit_count()
                if sc > 0 and (g & P):
                    found.append((sc, (a,)))
            for i, a in enumerate(lits):
                for b in lits[i + 1:]:
                    if a[0] == b[0]:
                        continue
                    g = col[a] & col[b]
                    sc = (g & P).bit_count() - (g & Z).bit_count()
                    if sc > 0 and (g & P):
                        found.append((sc, (a, b)))
        else:
            Q, K1 = f["want"], f["keep"]
            act = [h for h in space.by_tgt[r] if (model >> h) & 1]
            terms = {}
            for h in act:
                t = full
                for u, neg in space.lits[h]:
                    t &= (~x[u] & full) if neg else x[u]
                terms[h] = t
            for h in act:
                if not (terms[h] & Q):
                    continue
                others = 0
                for h2 in act:
                    if h2 != h:
                        others |= terms[h2]
                inh = {u for u, _ in space.lits[h]}
                for a in lits:
                    if a[0] in inh:
                        continue
                    rn = (others | (terms[h] & col[a]) | design.stim_mask[r]) & ~design.inh_mask[r]
                    sc = (Q & ~rn).bit_count() - (K1 & ~rn).bit_count()
                    if sc > 0:
                        found.append((sc, tuple(space.lits[h]) + (a,)))
        named = []
        for sc, ls in found:
            hl = tuple(sorted((space.nodes[u], -1 if neg else 1) for u, neg in ls))
            key = (f["readout"], hl)
            if key in existing:
                continue
            named.append((-sc, len(hl), repr(key), key))
        named.sort()
        for item in named[:cfg["per_failure"]]:
            k = item[3]
            if k not in cands or cands[k][0] > item[0]:
                cands[k] = item
    ranked = sorted(cands.values())
    return [it[3] for it in ranked[:cfg["per_round"]]]


def _fold_masks(task, label, k_in):
    keys = sorted(task.train_conds, key=lambda c: hashlib.sha256((label + "|" + task.cond_key[c]).encode()).hexdigest())
    folds = [keys[i::k_in] for i in range(k_in)]
    out = []
    for fc in folds:
        if not fc:
            continue
        test = 0
        drop = 0
        for c in fc:
            test |= task.t1_bit[c]
            drop |= task.t1_bit[c] | task.t0_bit.get(c, 0)
        out.append((task.train_all & ~drop, test))
    return out


def _err(space, task, m, colmask):
    x, na = simulate(space, task.design, m)
    return task.obs.errors(x, na, colmask)


def repair_rounds(task, hyper, model, colmask, label, shuffled, cfg):
    """Minimal repair of one program on colmask. Returns (hyper, model, history)."""
    hyper = list(hyper)
    hist = []
    for rnd in range(1, cfg["rounds"] + 1):
        sp = Space(task.nodes, hyper, task.stimuli, task.inhibitors, task.readouts)
        cur = _err(sp, task, model, colmask)
        if cur == 0:
            hist.append({"round": rnd, "stop": "no failure"})
            break
        desc, x, na = describe_failure(sp, task.design, task.obs, model, colmask)
        if shuffled:
            desc = shuffle_description(desc, colmask, rng_for(f"shuffle|{label}|{rnd}"))
        pieces = build_pieces(sp, task.design, x, na, model, desc, cfg)
        if not pieces:
            hist.append({"round": rnd, "stop": "no piece with a positive score"})
            break
        n0 = len(hyper)
        sg = Space(task.nodes, hyper + pieces, task.stimuli, task.inhibitors, task.readouts)
        m, kept = model, []
        for i, p in enumerate(pieces):
            bit = 1 << (n0 + i)
            tries = [m | bit]
            plits = set(p[1])
            for h in sg.active(m):
                t, lits = sg.hyper[h]
                if t == p[0] and set(lits) < plits:
                    tries.append((m | bit) & ~(1 << h))
            best = min(tries, key=lambda mm: (_err(sg, task, mm, colmask), sg.size(mm), mm))
            e = _err(sg, task, best, colmask)
            if e < cur:
                m, cur = best, e
                kept.append(i)
        rec = {"round": rnd, "pieces": [_fmt(p) for p in pieces], "kept": [_fmt(pieces[i]) for i in kept],
               "train_err_after": cur}
        hist.append(rec)
        if not kept:
            rec["stop"] = "no piece lowers the training errors"
            break
        keep_idx = sorted(kept)
        remap = {i: i for i in range(n0)}
        for j, i in enumerate(keep_idx):
            remap[n0 + i] = n0 + j
        mm = 0
        for h in sg.active(m):
            mm |= 1 << remap[h]
        hyper = hyper + [pieces[i] for i in keep_idx]
        model = mm
    return hyper, model, hist


def static_fit(task, cfg, memo=None, colmask=None, tag="r0"):
    """The static arm's fit: the base space on the given training columns (default: all training columns)."""
    colmask = task.train_all if colmask is None else colmask
    key = ("static", colmask)
    if memo is not None and key in memo:
        return memo[key]
    sp = Space(task.nodes, task.base_hyper, task.stimuli, task.inhibitors, task.readouts)
    st = fit(sp, task.design, task.obs, f"{task.label}|{tag}", cfg["restarts"], cfg["perturb"], colmask=colmask)
    if memo is not None:
        memo[key] = st
    return st


def grow(task, label, cfg, shuffled=False, memo=None):
    """The grown (or shuffled) arm on one task. Returns (space, model, info)."""
    st = static_fit(task, cfg, memo)
    hyper, model, hist = repair_rounds(task, task.base_hyper, st["rep"], task.train_all, label + "|main", shuffled, cfg)
    info = {"history": hist, "added": [h for r in hist for h in r.get("kept", [])]}
    if len(hyper) == len(task.base_hyper):
        info["accepted"] = None
        sp = Space(task.nodes, task.base_hyper, task.stimuli, task.inhibitors, task.readouts)
        return sp, st["rep"], info
    gain, per_fold = 0, []
    for i, (trm, tem) in enumerate(_fold_masks(task, task.label + "|folds", cfg["k_in"])):
        st_f = static_fit(task, cfg, memo, colmask=trm, tag=f"cv{i}")
        spb = Space(task.nodes, task.base_hyper, task.stimuli, task.inhibitors, task.readouts)
        e_st = _err(spb, task, st_f["rep"], tem)
        hy_f, m_f, _ = repair_rounds(task, task.base_hyper, st_f["rep"], trm, f"{label}|cv{i}", shuffled, cfg)
        spf = Space(task.nodes, hy_f, task.stimuli, task.inhibitors, task.readouts)
        e_gr = _err(spf, task, m_f, tem)
        gain += e_st - e_gr
        per_fold.append([e_st, e_gr, len(hy_f) - len(task.base_hyper)])
    info["cv_gain"], info["per_fold"] = gain, per_fold
    info["accepted"] = gain >= cfg["bar"]
    if not info["accepted"]:
        sp = Space(task.nodes, task.base_hyper, task.stimuli, task.inhibitors, task.readouts)
        return sp, st["rep"], info
    return Space(task.nodes, hyper, task.stimuli, task.inhibitors, task.readouts), model, info


def _fmt(p):
    t, lits = p
    return "+".join(("!" if s < 0 else "") + u for u, s in lits) + "=" + t
