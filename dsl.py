from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Union, Optional
import numpy as np

# Local deps
from components import Grid, extract_scene

# ---------- AST NODES ----------
@dataclass(frozen=True)
class Var:
    name: str

@dataclass(frozen=True)
class CColor:
    value: int

@dataclass(frozen=True)
class CInt:
    value: int

@dataclass(frozen=True)
class CVec:
    dr: int
    dc: int

@dataclass(frozen=True)
class Apply:
    op: str
    args: List[Any]   # nested AST nodes or constants

@dataclass
class Program:
    term: Any
    description: str = ""

    def run(self, grid: Grid, bundle: Any = None) -> Grid:
        env = {"grid": grid}
        return _eval(self.term, env)

# ---------- EVALUATOR ----------
def _eval(node: Any, env: Dict[str, Any]) -> Any:
    if isinstance(node, Var):
        return env[node.name]
    if isinstance(node, CColor):
        return int(node.value)
    if isinstance(node, CInt):
        return int(node.value)
    if isinstance(node, CVec):
        return (int(node.dr), int(node.dc))
    if isinstance(node, Apply):
        op = node.op
        args = [_eval(a, env) for a in node.args]
        return _dispatch(op, args, env)
    # Raw literals (rare)
    return node

# ---------- RUNTIME HELPERS ----------
def _copy_grid(g: Grid) -> Grid:
    return Grid(np.array(g.data, copy=True))

def _objs_by_color(grid: Grid, color: int):
    scene = extract_scene(grid, connectivity=4)
    return [c for c in scene.comps if int(c.color) == int(color)]

def _largest(objs):
    if not objs: return None
    return max(objs, key=lambda c: int(getattr(c, "area", len(c.pixels))))

def _paint(grid: Grid, objs, color: int) -> Grid:
    g = _copy_grid(grid)
    color = int(color)
    if objs is None: return g
    if not isinstance(objs, (list, tuple)): objs = [objs]
    for comp in objs:
        px = comp.pixels
        g.data[(px[:,0], px[:,1])] = color
    return g

def _translate_objs(grid: Grid, objs, dr: int, dc: int) -> Grid:
    g = _copy_grid(grid)
    H, W = g.data.shape
    if not isinstance(objs, (list, tuple)): objs = [objs]
    for comp in objs:
        px = comp.pixels
        nr = px[:,0] + dr
        nc = px[:,1] + dc
        # clear old pixels
        g.data[(px[:,0], px[:,1])] = 0
        # write only in-bounds
        mask = (nr >= 0) & (nr < H) & (nc >= 0) & (nc < W)
        g.data[(nr[mask], nc[mask])] = int(comp.color)
    return g

def _reflect_objs(grid: Grid, objs, axis: int) -> Grid:
    g = _copy_grid(grid); H, W = g.data.shape
    if not isinstance(objs, (list, tuple)): objs = [objs]
    for comp in objs:
        px = comp.pixels
        g.data[(px[:,0], px[:,1])] = 0
        if axis == 0:   # horizontal mirror (flip vertically)
            nr = H - 1 - px[:,0]; nc = px[:,1]
        else:           # vertical mirror (flip horizontally)
            nr = px[:,0]; nc = W - 1 - px[:,1]
        g.data[(nr, nc)] = int(comp.color)
    return g

def _complete_mirror(grid: Grid, axis: int) -> Grid:
    g = _copy_grid(grid)
    arr = g.data
    if axis == 0:   # mirror top->bottom
        mid = arr.shape[0] // 2
        arr[-mid:, :] = np.flipud(arr[:mid, :])
    else:           # axis==1 mirror left->right
        mid = arr.shape[1] // 2
        arr[:, -mid:] = np.fliplr(arr[:, :mid])
    return g

def _snap_to_border(grid: Grid, objs, side: int) -> Grid:
    g = _copy_grid(grid); H, W = g.data.shape
    if not isinstance(objs, (list, tuple)): objs = [objs]
    for comp in objs:
        px = comp.pixels; r0, c0, r1, c1 = comp.bbox
        dr = dc = 0
        if side == 0:   dr = -r0
        elif side == 1: dr = (H - r1)
        elif side == 2: dc = -c0
        elif side == 3: dc = (W - c1)
        g = _translate_objs(g, comp, dr, dc)
    return g

def _rect_outline(grid: Grid, objs, color: int) -> Grid:
    g = _copy_grid(grid)
    if not isinstance(objs, (list, tuple)): objs = [objs]
    color = int(color)
    for comp in objs:
        r0, c0, r1, c1 = comp.bbox
        r0, c0, r1, c1 = int(r0), int(c0), int(r1), int(c1)
        # top/bottom
        g.data[r0, c0:c1] = color
        g.data[r1-1, c0:c1] = color
        # left/right
        g.data[r0:r1, c0] = color
        g.data[r0:r1, c1-1] = color
    return g

# ---------- DISPATCH ----------
def _dispatch(op: str, args: List[Any], env: Dict[str, Any]) -> Any:
    if op == "objects":
        grid, color = env["grid"], int(args[0])
        return _objs_by_color(grid, color)
    if op == "largest":
        return _largest(args[0])
    if op == "paint":
        grid, objs, color = args
        return _paint(grid, objs, int(color))
    if op == "translate":
        objs, (dr, dc) = args
        return _translate_objs(env["grid"], objs, int(dr), int(dc))
    if op == "reflect":
        objs, axis = args
        return _reflect_objs(env["grid"], objs, int(axis))
    if op == "complete_mirror":
        grid, axis = args
        return _complete_mirror(grid, int(axis))
    if op == "snap_to_border":
        objs, side = args
        return _snap_to_border(env["grid"], objs, int(side))
    if op == "rect_outline":
        grid, objs, color = args
        return _rect_outline(grid, objs, int(color))
    raise NotImplementedError(f"Unknown op: {op}")
