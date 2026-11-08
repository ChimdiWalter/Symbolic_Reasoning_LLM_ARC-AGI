"""The guide and the linear model (PROTOCOL.md section 5), plain NumPy.

Inputs: block features (features.NAMES), standardised with the training data's mean and standard deviation (a
feature with no spread is set to 0). Outputs: the chance that the block succeeds (logistic output, cross-entropy
loss) and log(1 + operations) (linear output on the standardised target, squared loss); the loss is their sum.
The guide has two hidden layers of 32 ReLU units; the linear model has none. Adam (learning rate 0.003, beta 0.9 and
0.999), mini-batches of 512 in an order drawn from numpy.random.default_rng(20261106), 40 passes, weight decay 0.0001
on the weights. Score of a block: p x exp(-c), with c the predicted log(1 + operations).
"""
import numpy as np

SEED = 20261106
HIDDEN = (32, 32)
LR, BATCH, EPOCHS, WD = 0.003, 512, 40, 1e-4


class Model:
    def __init__(self, hidden=HIDDEN):
        self.hidden = tuple(hidden)
        self.params = None

    # -------------------------------------------------------------- training
    def fit(self, X, y_succ, y_cost):
        X = np.asarray(X, dtype=np.float64)
        ys = np.asarray(y_succ, dtype=np.float64)
        yc = np.asarray(y_cost, dtype=np.float64)
        rng = np.random.default_rng(SEED)
        self.mu = X.mean(0)
        sd = X.std(0)
        self.sd = np.where(sd > 0, sd, 1.0)
        self.keep = (sd > 0).astype(np.float64)
        self.c_mu, self.c_sd = float(yc.mean()), float(yc.std() or 1.0)
        Z = self._std(X)
        zc = (yc - self.c_mu) / self.c_sd
        sizes = [X.shape[1]] + list(self.hidden) + [2]
        W, b = [], []
        for a, o in zip(sizes[:-1], sizes[1:]):
            W.append(rng.normal(0.0, np.sqrt(2.0 / a), size=(a, o)))
            b.append(np.zeros(o))
        params = W + b
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]
        t = 0
        n = len(Z)
        nl = len(W)
        for _ in range(EPOCHS):
            order = rng.permutation(n)
            for s in range(0, n, BATCH):
                idx = order[s:s + BATCH]
                grads = self._grads(params, nl, Z[idx], ys[idx], zc[idx])
                t += 1
                for k, (p, g) in enumerate(zip(params, grads)):
                    if k < nl:
                        g = g + WD * p
                    m[k] = 0.9 * m[k] + 0.1 * g
                    v[k] = 0.999 * v[k] + 0.001 * g * g
                    mh = m[k] / (1 - 0.9 ** t)
                    vh = v[k] / (1 - 0.999 ** t)
                    p -= LR * mh / (np.sqrt(vh) + 1e-8)
        self.params = params
        self.nl = nl
        return self

    def _std(self, X):
        return (np.asarray(X, dtype=np.float64) - self.mu) / self.sd * self.keep

    @staticmethod
    def _forward(params, nl, Z):
        W, b = params[:nl], params[nl:]
        hs = [Z]
        h = Z
        for k in range(nl - 1):
            h = np.maximum(0.0, h @ W[k] + b[k])
            hs.append(h)
        out = h @ W[-1] + b[-1]
        return hs, out

    def _grads(self, params, nl, Z, ys, zc):
        W = params[:nl]
        hs, out = self._forward(params, nl, Z)
        nb = len(Z)
        p = 1.0 / (1.0 + np.exp(-np.clip(out[:, 0], -40, 40)))
        d = np.zeros_like(out)
        d[:, 0] = (p - ys) / nb
        d[:, 1] = 2.0 * (out[:, 1] - zc) / nb
        gW, gb = [None] * nl, [None] * nl
        for k in range(nl - 1, -1, -1):
            gW[k] = hs[k].T @ d
            gb[k] = d.sum(0)
            if k > 0:
                d = (d @ W[k].T) * (hs[k] > 0)
        return gW + gb

    # -------------------------------------------------------------- use
    def predict(self, X):
        """(chance of success, predicted log(1 + operations)) per row."""
        _, out = self._forward(self.params, self.nl, self._std(X))
        p = 1.0 / (1.0 + np.exp(-np.clip(out[:, 0], -40, 40)))
        c = out[:, 1] * self.c_sd + self.c_mu
        return p, c

    def scores(self, X):
        if len(X) == 0:
            return []
        p, c = self.predict(X)
        return list(p * np.exp(-c))

    def to_json(self):
        return {"hidden": list(self.hidden), "mu": self.mu.tolist(), "sd": self.sd.tolist(),
                "keep": self.keep.tolist(), "c_mu": self.c_mu, "c_sd": self.c_sd, "nl": self.nl,
                "params": [p.tolist() for p in self.params]}

    @classmethod
    def from_json(cls, d):
        m = cls(d["hidden"])
        m.mu, m.sd, m.keep = np.array(d["mu"]), np.array(d["sd"]), np.array(d["keep"])
        m.c_mu, m.c_sd, m.nl = d["c_mu"], d["c_sd"], d["nl"]
        m.params = [np.array(p) for p in d["params"]]
        return m


class Frequency:
    """The static frequency table over (block kind, view, edit type): (successes + 1) / (trials + 2) and the mean
    log(1 + operations); unseen keys take the pooled values. Score p x exp(-c)."""

    def fit(self, keys, y_succ, y_cost):
        acc = {}
        for k, s, c in zip(keys, y_succ, y_cost):
            a = acc.setdefault(tuple(k), [0, 0, 0.0])
            a[0] += 1
            a[1] += int(s)
            a[2] += float(c)
        n = sum(a[0] for a in acc.values())
        self.pooled = ((sum(a[1] for a in acc.values()) + 1) / (n + 2), sum(a[2] for a in acc.values()) / max(1, n))
        self.table = {k: ((a[1] + 1) / (a[0] + 2), a[2] / a[0]) for k, a in acc.items()}
        return self

    def scores_keys(self, keys):
        out = []
        for k in keys:
            p, c = self.table.get(tuple(k), self.pooled)
            out.append(p * float(np.exp(-c)))
        return out

    def to_json(self):
        return {"pooled": list(self.pooled), "table": [[list(k), list(v)] for k, v in sorted(self.table.items())]}

    @classmethod
    def from_json(cls, d):
        f = cls()
        f.pooled = tuple(d["pooled"])
        f.table = {tuple(k): tuple(v) for k, v in d["table"]}
        return f
