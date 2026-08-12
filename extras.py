
# -----------------------------
# 8-neighborhood adjacency (component-level)
# -----------------------------
def adjacency8(obj):
    """
    If obj is a Scene: returns {comp_id: [neighbor_ids...]} where components touch
    in 8-neighborhood (orthogonal or diagonal).
    If obj is a Grid/np.ndarray: returns color adjacency {color: [neighbor_colors...]}.
    """
    import numpy as _np
    # Scene path (what pipeline calls)
    if hasattr(obj, "comps"):
        scene = obj
        # recover shape from component bboxes
        H = int(max((int(c.bbox[2]) for c in scene.comps), default=0))
        W = int(max((int(c.bbox[3]) for c in scene.comps), default=0))
        lab = -_np.ones((H, W), dtype=_np.int32)
        for i, comp in enumerate(scene.comps):
            rrcc = comp.pixels
            lab[(rrcc[:,0], rrcc[:,1])] = i
        # 8-neigh edges
        adj = {i: set() for i in range(len(scene.comps))}
        def _add_edges(a, b):
            m = (a != b) & (a >= 0) & (b >= 0)
            if not m.any(): return
            us = a[m].ravel(); vs = b[m].ravel()
            for u, v in zip(us.tolist(), vs.tolist()):
                if u != v:
                    adj[u].add(v); adj[v].add(u)
        if W > 1:
            _add_edges(lab[:, :-1], lab[:, 1:])        # right
        if H > 1:
            _add_edges(lab[:-1, :], lab[1:, :])        # down
        if H > 1 and W > 1:
            _add_edges(lab[:-1, :-1], lab[1:, 1:])     # down-right
            _add_edges(lab[:-1, 1:],  lab[1:, :-1])    # down-left
        return {i: sorted(v) for i, v in adj.items()}
    # Grid / ndarray fallback → color adjacency
    arr = obj.data if hasattr(obj, "data") else _np.asarray(obj, dtype=_np.int16)
    arr = arr.astype(_np.int16)
    H, W = arr.shape
    adj = {}
    def _edge(a, b):
        if a == b: return
        adj.setdefault(int(a), set()).add(int(b))
        adj.setdefault(int(b), set()).add(int(a))
    # right, down, diagonals
    if W > 1:
        a, b = arr[:, :-1], arr[:, 1:]
        m = a != b
        if m.any():
            for u, v in zip(a[m].ravel().tolist(), b[m].ravel().tolist()):
                _edge(u, v)
    if H > 1:
        a, b = arr[:-1, :], arr[1:, :]
        m = a != b
        if m.any():
            for u, v in zip(a[m].ravel().tolist(), b[m].ravel().tolist()):
                _edge(u, v)
    if H > 1 and W > 1:
        a, b = arr[:-1, :-1], arr[1:, 1:]
        m = a != b
        if m.any():
            for u, v in zip(a[m].ravel().tolist(), b[m].ravel().tolist()):
                _edge(u, v)
        a, b = arr[:-1, 1:], arr[1:, :-1]
        m = a != b
        if m.any():
            for u, v in zip(a[m].ravel().tolist(), b[m].ravel().tolist()):
                _edge(u, v)
    return {k: sorted(v) for k, v in adj.items()}
