# Found expressions of experiments/below_library_20261114/full_out, for reading

Author: Chimdi Walter Ndubuisi. Printed from the records; nothing computed. "right" and "wrong" are the records' verdicts on the final panel.

## add (done; stratum longer; development)

```
def add(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a + b
    elif isinstance(a, tuple) and isinstance(b, tuple):
        return (a[0] + b[0], a[1] + b[1])
    elif isinstance(a, int) and isinstance(b, tuple):
        return (a + b[0], a + b[1])
    return (a[0] + b, a[1] + b)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## adjacent (done; stratum short; outside development)

```
def adjacent(a, b):
    return manhattan(a, b) == 1
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `contained(TWO_BY_ZERO, x0)` (3 nodes): wrong (agree 346 of 430; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `contained(TWO_BY_ZERO, x0)` (3 nodes): wrong (agree 346 of 430; errors 0; guard timeout False)

## apply (done; stratum longer; outside development)

```
def apply(function, container):
    return type(container)((function(e) for e in container))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## argmax (done; stratum short; control)

```
def argmax(container, compfunc):
    return max(container, key=compfunc)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_max_key(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_max_key(x0, x1)` (3 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_max_key(x0, x1)` (3 nodes): right
  - LC4-9: `c_max_key(x0, x1)` (3 nodes): right
  - witness `c_max_key(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## argmin (done; stratum short; control)

```
def argmin(container, compfunc):
    return min(container, key=compfunc)
```

- **library_only** selected `first(order(x0, x1))` (L4-36, 4 nodes): **right**
- **smaller_blocks** selected `c_min_key(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_min_key(x0, x1)` (3 nodes): right
  - L4-36: `first(order(x0, x1))` (4 nodes): right
  - L4-9: `first(order(x0, x1))` (4 nodes): right
  - L5-36: `first(order(x0, x1))` (4 nodes): right
  - LC4-36: `c_min_key(x0, x1)` (3 nodes): right
  - LC4-9: `c_min_key(x0, x1)` (3 nodes): right
  - witness `c_min_key(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## asindices (done; stratum longer; outside development)

```
def asindices(grid):
    return frozenset(((i, j) for i in range(len(grid)) for j in range(len(grid[0]))))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## asobject (done; stratum longer; outside development)

```
def asobject(grid):
    return frozenset(((v, (i, j)) for i, r in enumerate(grid) for j, v in enumerate(r)))
```

- **library_only** selected `merge(partition(x0))` (L4-36, 3 nodes): **right**
- **smaller_blocks** selected `merge(partition(x0))` (LC4-36, 3 nodes): **right**
  - C-36: none (size_limit_completed)
  - L4-36: `merge(partition(x0))` (3 nodes): right
  - L4-9: `merge(partition(x0))` (3 nodes): right
  - L5-36: `merge(partition(x0))` (3 nodes): right
  - LC4-36: `merge(partition(x0))` (3 nodes): right
  - LC4-9: `merge(partition(x0))` (3 nodes): right

## astuple (done; stratum short; control)

```
def astuple(a, b):
    return (a, b)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_pair(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_pair(x0, x1)` (3 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_pair(x0, x1)` (3 nodes): right
  - LC4-9: `c_pair(x0, x1)` (3 nodes): right
  - witness `c_pair(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## backdrop (done; stratum longer; development)

```
def backdrop(patch):
    if len(patch) == 0:
        return frozenset({})
    indices = toindices(patch)
    si, sj = ulcorner(indices)
    ei, ej = lrcorner(patch)
    return frozenset(((i, j) for i in range(si, ei + 1) for j in range(sj, ej + 1)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## bordering (done; stratum longer; outside development)

```
def bordering(patch, grid):
    return uppermost(patch) == 0 or leftmost(patch) == 0 or lowermost(patch) == len(grid) - 1 or (rightmost(patch) == len(grid[0]) - 1)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `flip(square(x1))` (3 nodes): wrong (agree 294 of 430; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `flip(square(x1))` (3 nodes): wrong (agree 294 of 430; errors 0; guard timeout False)

## bottomhalf (done; stratum longer; outside development)

```
def bottomhalf(grid):
    return grid[len(grid) // 2 + len(grid) % 2:]
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## box (done; stratum longer; development)

```
def box(patch):
    if len(patch) == 0:
        return patch
    ai, aj = ulcorner(patch)
    bi, bj = lrcorner(patch)
    si, sj = (min(ai, bi), min(aj, bj))
    ei, ej = (max(ai, bi), max(aj, bj))
    vlines = {(i, sj) for i in range(si, ei + 1)} | {(i, ej) for i in range(si, ei + 1)}
    hlines = {(si, j) for j in range(sj, ej + 1)} | {(ei, j) for j in range(sj, ej + 1)}
    return frozenset(vlines | hlines)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## branch (done; stratum short; control)

```
def branch(condition, a, b):
    return a if condition else b
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_if_else(x0, x1, x2)` (LC4-36, 4 nodes): **right**
  - C-36: `c_if_else(x0, x1, x2)` (4 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_if_else(x0, x1, x2)` (4 nodes): right
  - LC4-9: `c_if_else(x0, x1, x2)` (4 nodes): right
  - witness `c_if_else(x0, x1, x2)`: evaluated; agrees on all 36: True; on the final panel: True

## canvas (done; stratum longer; outside development)

```
def canvas(value, dimensions):
    return tuple((tuple((value for j in range(dimensions[1]))) for i in range(dimensions[0])))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## cellwise (done; stratum longer; outside development)

```
def cellwise(a, b, fallback):
    h, w = (len(a), len(a[0]))
    resulting_grid = tuple()
    for i in range(h):
        row = tuple()
        for j in range(w):
            a_value = a[i][j]
            value = a_value if a_value == b[i][j] else fallback
            row = row + (value,)
        resulting_grid = resulting_grid + (row,)
    return resulting_grid
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## center (done; stratum longer; outside development)

```
def center(patch):
    return (uppermost(patch) + height(patch) // 2, leftmost(patch) + width(patch) // 2)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## centerofmass (done; stratum longer; outside development)

```
def centerofmass(patch):
    return tuple(map(lambda x: sum(x) // len(patch), zip(*toindices(patch))))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## cmirror (done; stratum longer; outside development)

```
def cmirror(piece):
    if isinstance(piece, tuple):
        return tuple(zip(*(r[::-1] for r in piece[::-1])))
    return vmirror(dmirror(vmirror(piece)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## color (done; stratum short; development)

```
def color(obj):
    return next(iter(obj))[0]
```

- **library_only** selected `first(first(x0))` (L4-36, 3 nodes): **right**
- **smaller_blocks** selected `first(first(x0))` (LC4-36, 3 nodes): **right**
  - C-36: `c_first(c_first(x0))` (3 nodes): right
  - L4-36: `first(first(x0))` (3 nodes): right
  - L4-9: `first(first(x0))` (3 nodes): right
  - L5-36: `first(first(x0))` (3 nodes): right
  - LC4-36: `first(first(x0))` (3 nodes): right
  - LC4-9: `first(first(x0))` (3 nodes): right
  - witness `c_item0(c_first(x0))`: evaluated; agrees on all 36: True; on the final panel: True

## colorcount (done; stratum longer; outside development)

```
def colorcount(element, value):
    if isinstance(element, tuple):
        return sum((row.count(value) for row in element))
    return sum((v == value for v, _ in element))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## colorfilter (done; stratum longer; outside development)

```
def colorfilter(objs, value):
    return frozenset((obj for obj in objs if next(iter(obj))[0] == value))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## combine (done; stratum longer; outside development)

```
def combine(a, b):
    return type(a)((*a, *b))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## connect (done; stratum longer; outside development)

```
def connect(a, b):
    ai, aj = a
    bi, bj = b
    si = min(ai, bi)
    ei = max(ai, bi) + 1
    sj = min(aj, bj)
    ej = max(aj, bj) + 1
    if ai == bi:
        return frozenset(((ai, j) for j in range(sj, ej)))
    elif aj == bj:
        return frozenset(((i, aj) for i in range(si, ei)))
    elif bi - ai == bj - aj:
        return frozenset(((i, j) for i, j in zip(range(si, ei), range(sj, ej))))
    elif bi - ai == aj - bj:
        return frozenset(((i, j) for i, j in zip(range(si, ei), range(ej - 1, sj - 1, -1))))
    return frozenset()
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## contained (done; stratum short; control)

```
def contained(value, container):
    return value in container
```

- **library_only** selected `valmax(x1, matcher(identity, x0))` (L5-36, 5 nodes): **right**
- **smaller_blocks** selected `c_in(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_in(x0, x1)` (3 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: `valmax(x1, matcher(identity, x0))` (5 nodes): right
  - LC4-36: `c_in(x0, x1)` (3 nodes): right
  - LC4-9: `c_in(x0, x1)` (3 nodes): right
  - witness `c_in(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## corners (done; stratum longer; outside development)

```
def corners(patch):
    return frozenset({ulcorner(patch), urcorner(patch), llcorner(patch), lrcorner(patch)})
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## cover (done; stratum short; outside development)

```
def cover(grid, patch):
    return fill(grid, mostcolor(grid), toindices(patch))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## crement (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)

## crop (done; stratum longer; outside development)

```
def crop(grid, start, dims):
    return tuple((r[start[1]:start[1] + dims[1]] for r in grid[start[0]:start[0] + dims[0]]))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## decrement (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)

## dedupe (done; stratum longer; outside development)

```
def dedupe(tup):
    return tuple((e for i, e in enumerate(tup) if tup.index(e) == i))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `x0` (1 nodes): wrong (agree 44 of 80; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `x0` (1 nodes): wrong (agree 44 of 80; errors 0; guard timeout False)

## delta (done; stratum longer; outside development)

```
def delta(patch):
    if len(patch) == 0:
        return frozenset({})
    return backdrop(patch) - toindices(patch)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## difference (done; stratum longer; outside development)

```
def difference(a, b):
    return type(a)((e for e in a if e not in b))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_set_difference(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_set_difference(x0, x1)` (3 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_set_difference(x0, x1)` (3 nodes): right
  - LC4-9: `c_set_difference(x0, x1)` (3 nodes): right

## divide (done; stratum longer; outside development)

```
def divide(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a // b
    elif isinstance(a, tuple) and isinstance(b, tuple):
        return (a[0] // b[0], a[1] // b[1])
    elif isinstance(a, int) and isinstance(b, tuple):
        return (a // b[0], a // b[1])
    return (a[0] // b, a[1] // b)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## dmirror (done; stratum longer; outside development)

```
def dmirror(piece):
    if isinstance(piece, tuple):
        return tuple(zip(*piece))
    a, b = ulcorner(piece)
    if isinstance(next(iter(piece))[1], tuple):
        return frozenset(((v, (j - b + a, i - a + b)) for v, (i, j) in piece))
    return frozenset(((j - b + a, i - a + b) for i, j in piece))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## dneighbors (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)

## double (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)

## equality (done; stratum short; control)

```
def equality(a, b):
    return a == b
```

- **library_only** selected `contained(x0, initset(x1))` (L4-36, 4 nodes): **right**
- **smaller_blocks** selected `c_eq(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_eq(x0, x1)` (3 nodes): right
  - L4-36: `contained(x0, initset(x1))` (4 nodes): right
  - L4-9: `contained(x0, initset(x1))` (4 nodes): right
  - L5-36: `contained(x0, initset(x1))` (4 nodes): right
  - LC4-36: `c_eq(x0, x1)` (3 nodes): right
  - LC4-9: `c_eq(x0, x1)` (3 nodes): right
  - witness `c_eq(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## even (excluded; stratum short; control)

generator: only 51 of 66 valid examples in 4000 draws

## extract (done; stratum longer; outside development)

```
def extract(container, condition):
    return next((e for e in container if condition(e)))
```

- **library_only** selected `argmin(x0, flip)` (L4-36, 3 nodes): **wrong**
- **smaller_blocks** selected `argmin(x0, flip)` (LC4-36, 3 nodes): **wrong**
  - C-36: none (size_limit_completed)
  - L4-36: `argmin(x0, flip)` (3 nodes): wrong (agree 283 of 292; errors 0; guard timeout False)
  - L4-9: `first(x0)` (2 nodes): wrong (agree 281 of 292; errors 0; guard timeout False)
  - L5-36: `argmin(x0, flip)` (3 nodes): wrong (agree 283 of 292; errors 0; guard timeout False)
  - LC4-36: `argmin(x0, flip)` (3 nodes): wrong (agree 283 of 292; errors 0; guard timeout False)
  - LC4-9: `first(x0)` (2 nodes): wrong (agree 281 of 292; errors 0; guard timeout False)

## fgpartition (done; stratum longer; outside development)

```
def fgpartition(grid):
    return frozenset((frozenset(((v, (i, j)) for i, r in enumerate(grid) for j, v in enumerate(r) if v == value)) for value in palette(grid) - {mostcolor(grid)}))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## fill (done; stratum longer; outside development)

```
def fill(grid, value, patch):
    h, w = (len(grid), len(grid[0]))
    grid_filled = list((list(row) for row in grid))
    for i, j in toindices(patch):
        if 0 <= i < h and 0 <= j < w:
            grid_filled[i][j] = value
    return tuple((tuple(row) for row in grid_filled))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## first (done; stratum short; control)

```
def first(container):
    return next(iter(container))
```

- **library_only** selected `argmax(x0, flip)` (L4-36, 3 nodes): **wrong**
- **smaller_blocks** selected `c_first(x0)` (LC4-36, 2 nodes): **right**
  - C-36: `c_first(x0)` (2 nodes): right
  - L4-36: `argmax(x0, flip)` (3 nodes): wrong (agree 204 of 213; errors 0; guard timeout False)
  - L4-9: `argmax(x0, flip)` (3 nodes): wrong (agree 204 of 213; errors 0; guard timeout False)
  - L5-36: `argmax(x0, flip)` (3 nodes): wrong (agree 204 of 213; errors 0; guard timeout False)
  - LC4-36: `c_first(x0)` (2 nodes): right
  - LC4-9: `c_first(x0)` (2 nodes): right
  - witness `c_first(x0)`: evaluated; agrees on all 36: True; on the final panel: True

## frontiers (done; stratum longer; outside development)

```
def frontiers(grid):
    h, w = (len(grid), len(grid[0]))
    row_indices = tuple((i for i, r in enumerate(grid) if len(set(r)) == 1))
    column_indices = tuple((j for j, c in enumerate(dmirror(grid)) if len(set(c)) == 1))
    hfrontiers = frozenset({frozenset({(grid[i][j], (i, j)) for j in range(w)}) for i in row_indices})
    vfrontiers = frozenset({frozenset({(grid[i][j], (i, j)) for i in range(h)}) for j in column_indices})
    return hfrontiers | vfrontiers
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## gravitate (done; stratum longer; outside development)

```
def gravitate(source, destination):
    si, sj = center(source)
    di, dj = center(destination)
    i, j = (0, 0)
    if vmatching(source, destination):
        i = 1 if si < di else -1
    else:
        j = 1 if sj < dj else -1
    gi, gj = (i, j)
    c = 0
    while not adjacent(source, destination) and c < 42:
        c += 1
        gi += i
        gj += j
        source = shift(source, (i, j))
    return (gi - i, gj - j)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## greater (done; stratum short; control)

```
def greater(a, b):
    return a > b
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_lt(x1, x0)` (LC4-36, 3 nodes): **right**
  - C-36: `c_lt(x1, x0)` (3 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: `even(divide(NINE, x0))` (4 nodes): wrong (agree 296 of 430; errors 4; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_lt(x1, x0)` (3 nodes): right
  - LC4-9: `c_lt(x1, x0)` (3 nodes): right
  - witness `c_gt(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## halve (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)

## hconcat (done; stratum longer; outside development)

```
def hconcat(a, b):
    return tuple((i + j for i, j in zip(a, b)))
```

- **library_only** selected `papply(combine, x0, x1)` (L4-36, 4 nodes): **right**
- **smaller_blocks** selected `papply(combine, x0, x1)` (LC4-36, 4 nodes): **right**
  - C-36: none (size_limit_completed)
  - L4-36: `papply(combine, x0, x1)` (4 nodes): right
  - L4-9: `papply(combine, x0, x1)` (4 nodes): right
  - L5-36: `papply(combine, x0, x1)` (4 nodes): right
  - LC4-36: `papply(combine, x0, x1)` (4 nodes): right
  - LC4-9: `papply(combine, x0, x1)` (4 nodes): right

## height (done; stratum longer; outside development)

```
def height(piece):
    if len(piece) == 0:
        return 0
    if isinstance(piece, tuple):
        return len(piece)
    return lowermost(piece) - uppermost(piece) + 1
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## hfrontier (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)

## hline (done; stratum longer; outside development)

```
def hline(patch):
    return width(patch) == len(patch) and height(patch) == 1
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `equality(T, size(x0))` (4 nodes): wrong (agree 327 of 341; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `equality(T, size(x0))` (4 nodes): wrong (agree 327 of 341; errors 0; guard timeout False)

## hmatching (done; stratum longer; outside development)

```
def hmatching(a, b):
    return len(set((i for i, j in toindices(a))) & set((i for i, j in toindices(b)))) > 0
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `portrait(totuple(x0))` (3 nodes): wrong (agree 296 of 430; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `portrait(totuple(x0))` (3 nodes): wrong (agree 296 of 430; errors 0; guard timeout False)

## hmirror (done; stratum longer; development)

```
def hmirror(piece):
    if isinstance(piece, tuple):
        return piece[::-1]
    d = ulcorner(piece)[0] + lrcorner(piece)[0]
    if isinstance(next(iter(piece))[1], tuple):
        return frozenset(((v, (d - i, j)) for v, (i, j) in piece))
    return frozenset(((d - i, j) for i, j in piece))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## hperiod (done; stratum longer; outside development)

```
def hperiod(obj):
    normalized = normalize(obj)
    w = width(normalized)
    for p in range(1, w):
        offsetted = shift(normalized, (0, -p))
        pruned = frozenset({(c, (i, j)) for c, (i, j) in offsetted if j >= 0})
        if pruned.issubset(normalized):
            return p
    return w
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## hsplit (done; stratum longer; outside development)

```
def hsplit(grid, n):
    h, w = (len(grid), len(grid[0]) // n)
    offset = len(grid[0]) % n != 0
    return tuple((crop(grid, (0, w * i + i * offset), (h, w)) for i in range(n)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## hupscale (done; stratum longer; outside development)

```
def hupscale(grid, factor):
    g = tuple()
    for row in grid:
        r = tuple()
        for value in row:
            r = r + tuple((value for num in range(factor)))
        g = g + (r,)
    return g
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## identity (done; stratum short; control)

```
def identity(x):
    return x
```

- **library_only** selected `x0` (L4-36, 1 nodes): **right**
- **smaller_blocks** selected `x0` (LC4-36, 1 nodes): **right**
  - C-36: `x0` (1 nodes): right
  - L4-36: `x0` (1 nodes): right
  - L4-9: `x0` (1 nodes): right
  - L5-36: `x0` (1 nodes): right
  - LC4-36: `x0` (1 nodes): right
  - LC4-9: `x0` (1 nodes): right
  - witness `x0`: evaluated; agrees on all 36: True; on the final panel: True

## inbox (done; stratum longer; outside development)

```
def inbox(patch):
    ai, aj = (uppermost(patch) + 1, leftmost(patch) + 1)
    bi, bj = (lowermost(patch) - 1, rightmost(patch) - 1)
    si, sj = (min(ai, bi), min(aj, bj))
    ei, ej = (max(ai, bi), max(aj, bj))
    vlines = {(i, sj) for i in range(si, ei + 1)} | {(i, ej) for i in range(si, ei + 1)}
    hlines = {(si, j) for j in range(sj, ej + 1)} | {(ei, j) for j in range(sj, ej + 1)}
    return frozenset(vlines | hlines)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## increment (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)

## index (done; stratum longer; outside development)

```
def index(grid, loc):
    i, j = loc
    h, w = (len(grid), len(grid[0]))
    if not (0 <= i < h and 0 <= j < w):
        return None
    return grid[loc[0]][loc[1]]
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `valmin(x0, maximum)` (3 nodes): wrong (agree 127 of 155; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `valmin(x0, maximum)` (3 nodes): wrong (agree 127 of 155; errors 0; guard timeout False)

## ineighbors (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 23 of 23 draws usable, need 30)

## initset (done; stratum short; control)

```
def initset(value):
    return frozenset({value})
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_set1(x0)` (LC4-36, 2 nodes): **right**
  - C-36: `c_set1(x0)` (2 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_set1(x0)` (2 nodes): right
  - LC4-9: `c_set1(x0)` (2 nodes): right
  - witness `c_set1(x0)`: evaluated; agrees on all 36: True; on the final panel: True

## insert (done; stratum short; control)

```
def insert(value, container):
    return container.union(frozenset({value}))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_union(x1, c_set1(x0))` (LC4-36, 4 nodes): **right**
  - C-36: `c_union(x1, c_set1(x0))` (4 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_union(x1, c_set1(x0))` (4 nodes): right
  - LC4-9: `c_union(x1, c_set1(x0))` (4 nodes): right
  - witness `c_union(x1, c_set1(x0))`: evaluated; agrees on all 36: True; on the final panel: True

## intersection (done; stratum short; control)

```
def intersection(a, b):
    return a & b
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_intersection(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_intersection(x0, x1)` (3 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: `sfilter(x0, flip)` (3 nodes): wrong (agree 372 of 430; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_intersection(x0, x1)` (3 nodes): right
  - LC4-9: `EMPTY_SET` (1 nodes): wrong (agree 404 of 430; errors 0; guard timeout False)
  - witness `c_intersection(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## interval (done; stratum short; control)

```
def interval(start, stop, step):
    return tuple(range(start, stop, step))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_range3(x0, x1, x2)` (LC4-36, 4 nodes): **right**
  - C-36: `c_range3(x0, x1, x2)` (4 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_range3(x0, x1, x2)` (4 nodes): right
  - LC4-9: `c_range3(x0, x1, x2)` (4 nodes): right
  - witness `c_range3(x0, x1, x2)`: evaluated; agrees on all 36: True; on the final panel: True

## invert (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)

## last (done; stratum short; control)

```
def last(container):
    return max(enumerate(container))[1]
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_first(c_reverse(c_tuple(x0)))` (LC4-36, 4 nodes): **right**
  - C-36: `c_first(c_reverse(c_tuple(x0)))` (4 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_first(c_reverse(c_tuple(x0)))` (4 nodes): right
  - LC4-9: `c_first(c_reverse(c_tuple(x0)))` (4 nodes): right
  - witness `c_item1(c_max(c_enumerate(x0)))`: evaluated; agrees on all 36: True; on the final panel: True

## leastcolor (done; stratum longer; outside development)

```
def leastcolor(element):
    values = [v for r in element for v in r] if isinstance(element, tuple) else [v for v, _ in element]
    return min(set(values), key=values.count)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## leastcommon (done; stratum short; control)

```
def leastcommon(container):
    return min(set(container), key=container.count)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)
  - witness `c_min_key(c_frozenset(x0), lbind(c_count, x0))`: evaluated; agrees on all 36: True; on the final panel: True

## lefthalf (done; stratum short; development)

```
def lefthalf(grid):
    return rot270(tophalf(rot90(grid)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## leftmost (done; stratum longer; outside development)

```
def leftmost(patch):
    return min((j for i, j in toindices(patch)))
```

- **library_only** selected `valmin(toindices(x0), last)` (L4-36, 4 nodes): **right**
- **smaller_blocks** selected `valmin(toindices(x0), last)` (LC4-36, 4 nodes): **right**
  - C-36: none (size_limit_completed)
  - L4-36: `valmin(toindices(x0), last)` (4 nodes): right
  - L4-9: `valmin(toindices(x0), last)` (4 nodes): right
  - L5-36: `valmin(toindices(x0), last)` (4 nodes): right
  - LC4-36: `valmin(toindices(x0), last)` (4 nodes): right
  - LC4-9: `valmin(toindices(x0), last)` (4 nodes): right

## llcorner (done; stratum longer; outside development)

```
def llcorner(patch):
    return tuple(map(lambda ix: {0: max, 1: min}[ix[0]](ix[1]), enumerate(zip(*toindices(patch)))))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## lowermost (done; stratum longer; outside development)

```
def lowermost(patch):
    return max((i for i, j in toindices(patch)))
```

- **library_only** selected `valmax(toindices(x0), first)` (L4-36, 4 nodes): **right**
- **smaller_blocks** selected `valmax(toindices(x0), first)` (LC4-36, 4 nodes): **right**
  - C-36: none (size_limit_completed)
  - L4-36: `valmax(toindices(x0), first)` (4 nodes): right
  - L4-9: `valmax(toindices(x0), first)` (4 nodes): right
  - L5-36: `valmax(toindices(x0), first)` (4 nodes): right
  - LC4-36: `valmax(toindices(x0), first)` (4 nodes): right
  - LC4-9: `valmax(toindices(x0), first)` (4 nodes): right

## lrcorner (done; stratum longer; outside development)

```
def lrcorner(patch):
    return tuple(map(max, zip(*toindices(patch))))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## manhattan (done; stratum longer; outside development)

```
def manhattan(a, b):
    return min((abs(ai - bi) + abs(aj - bj) for ai, aj in toindices(a) for bi, bj in toindices(b)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## mapply (done; stratum short; development)

```
def mapply(function, container):
    return merge(apply(function, container))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## maximum (excluded; stratum short; control)

too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)

## merge (excluded; stratum longer; outside development)

too few usable pooled inputs (usability slice: 9 of 9 draws usable, need 30)

## mfilter (done; stratum short; development)

```
def mfilter(container, function):
    return merge(sfilter(container, function))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## minimum (excluded; stratum short; control)

too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)

## mostcolor (done; stratum longer; outside development)

```
def mostcolor(element):
    values = [v for r in element for v in r] if isinstance(element, tuple) else [v for v, _ in element]
    return max(set(values), key=values.count)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `minimum(palette(x0))` (3 nodes): wrong (agree 44 of 65; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `minimum(palette(x0))` (3 nodes): wrong (agree 44 of 65; errors 0; guard timeout False)

## move (done; stratum longer; outside development)

```
def move(grid, obj, offset):
    return paint(cover(grid, obj), shift(obj, offset))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## mpapply (done; stratum short; outside development)

```
def mpapply(function, a, b):
    return merge(papply(function, a, b))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## multiply (done; stratum longer; outside development)

```
def multiply(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a * b
    elif isinstance(a, tuple) and isinstance(b, tuple):
        return (a[0] * b[0], a[1] * b[1])
    elif isinstance(a, int) and isinstance(b, tuple):
        return (a * b[0], a * b[1])
    return (a[0] * b, a[1] * b)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## neighbors (excluded; stratum short; outside development)

too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)

## normalize (done; stratum longer; outside development)

```
def normalize(patch):
    if len(patch) == 0:
        return patch
    return shift(patch, (-uppermost(patch), -leftmost(patch)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## numcolors (done; stratum short; development)

```
def numcolors(element):
    return len(palette(element))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## objects (done; stratum longer; development)

```
def objects(grid, univalued, diagonal, without_bg):
    bg = mostcolor(grid) if without_bg else None
    objs = set()
    occupied = set()
    h, w = (len(grid), len(grid[0]))
    unvisited = asindices(grid)
    diagfun = neighbors if diagonal else dneighbors
    for loc in unvisited:
        if loc in occupied:
            continue
        val = grid[loc[0]][loc[1]]
        if val == bg:
            continue
        obj = {(val, loc)}
        cands = {loc}
        while len(cands) > 0:
            neighborhood = set()
            for cand in cands:
                v = grid[cand[0]][cand[1]]
                if val == v if univalued else v != bg:
                    obj.add((v, cand))
                    occupied.add(cand)
                    neighborhood |= {(i, j) for i, j in diagfun(cand) if 0 <= i < h and 0 <= j < w}
            cands = neighborhood - occupied
        objs.add(frozenset(obj))
    return frozenset(objs)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## occurrences (done; stratum longer; outside development)

```
def occurrences(grid, obj):
    occs = set()
    normed = normalize(obj)
    h, w = (len(grid), len(grid[0]))
    oh, ow = shape(obj)
    h2, w2 = (h - oh + 1, w - ow + 1)
    for i in range(h2):
        for j in range(w2):
            occurs = True
            for v, (a, b) in shift(normed, (i, j)):
                if not (0 <= a < h and 0 <= b < w and (grid[a][b] == v)):
                    occurs = False
                    break
            if occurs:
                occs.add((i, j))
    return frozenset(occs)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## ofcolor (done; stratum longer; development)

```
def ofcolor(grid, value):
    return frozenset(((i, j) for i, r in enumerate(grid) for j, v in enumerate(r) if v == value))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## order (done; stratum short; control)

```
def order(container, compfunc):
    return tuple(sorted(container, key=compfunc))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_sorted_key(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_sorted_key(x0, x1)` (3 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_sorted_key(x0, x1)` (3 nodes): right
  - LC4-9: `c_sorted_key(x0, x1)` (3 nodes): right
  - witness `c_sorted_key(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## other (done; stratum short; development)

```
def other(container, value):
    return first(remove(value, container))
```

- **library_only** selected `argmin(x0, matcher(identity, x1))` (L5-36, 5 nodes): **wrong**
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: `argmin(x0, matcher(identity, x1))` (5 nodes): wrong (agree 395 of 411; errors 0; guard timeout False)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## outbox (done; stratum longer; outside development)

```
def outbox(patch):
    ai, aj = (uppermost(patch) - 1, leftmost(patch) - 1)
    bi, bj = (lowermost(patch) + 1, rightmost(patch) + 1)
    si, sj = (min(ai, bi), min(aj, bj))
    ei, ej = (max(ai, bi), max(aj, bj))
    vlines = {(i, sj) for i in range(si, ei + 1)} | {(i, ej) for i in range(si, ei + 1)}
    hlines = {(si, j) for j in range(sj, ej + 1)} | {(ei, j) for j in range(sj, ej + 1)}
    return frozenset(vlines | hlines)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## paint (done; stratum longer; outside development)

```
def paint(grid, obj):
    h, w = (len(grid), len(grid[0]))
    grid_painted = list((list(row) for row in grid))
    for value, (i, j) in obj:
        if 0 <= i < h and 0 <= j < w:
            grid_painted[i][j] = value
    return tuple((tuple(row) for row in grid_painted))
```

- **library_only** selected `x0` (L4-36, 1 nodes): **wrong**
- **smaller_blocks** selected `x0` (LC4-36, 1 nodes): **wrong**
  - C-36: `x0` (1 nodes): wrong (agree 139 of 430; errors 0; guard timeout False)
  - L4-36: `x0` (1 nodes): wrong (agree 139 of 430; errors 0; guard timeout False)
  - L4-9: `x0` (1 nodes): wrong (agree 139 of 430; errors 0; guard timeout False)
  - L5-36: `x0` (1 nodes): wrong (agree 139 of 430; errors 0; guard timeout False)
  - LC4-36: `x0` (1 nodes): wrong (agree 139 of 430; errors 0; guard timeout False)
  - LC4-9: `x0` (1 nodes): wrong (agree 139 of 430; errors 0; guard timeout False)

## pair (done; stratum short; control)

```
def pair(a, b):
    return tuple(zip(a, b))
```

- **library_only** selected `papply(astuple, x0, x1)` (L4-36, 4 nodes): **right**
- **smaller_blocks** selected `c_zip(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_zip(x0, x1)` (3 nodes): right
  - L4-36: `papply(astuple, x0, x1)` (4 nodes): right
  - L4-9: `papply(astuple, x0, x1)` (4 nodes): right
  - L5-36: `papply(astuple, x0, x1)` (4 nodes): right
  - LC4-36: `c_zip(x0, x1)` (3 nodes): right
  - LC4-9: `c_zip(x0, x1)` (3 nodes): right
  - witness `c_zip(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## palette (done; stratum longer; outside development)

```
def palette(element):
    if isinstance(element, tuple):
        return frozenset({v for r in element for v in r})
    return frozenset({v for v, _ in element})
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## papply (done; stratum longer; outside development)

```
def papply(function, a, b):
    return tuple((function(i, j) for i, j in zip(a, b)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## partition (done; stratum longer; outside development)

```
def partition(grid):
    return frozenset((frozenset(((v, (i, j)) for i, r in enumerate(grid) for j, v in enumerate(r) if v == value)) for value in palette(grid)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## portrait (done; stratum short; outside development)

```
def portrait(piece):
    return height(piece) > width(piece)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `contained(SEVEN, first(x0))` (4 nodes): wrong (agree 65 of 101; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `contained(SEVEN, first(x0))` (4 nodes): wrong (agree 65 of 101; errors 0; guard timeout False)

## position (done; stratum longer; outside development)

```
def position(a, b):
    ia, ja = center(toindices(a))
    ib, jb = center(toindices(b))
    if ia == ib:
        return (0, 1 if ja < jb else -1)
    elif ja == jb:
        return (1 if ia < ib else -1, 0)
    elif ia < ib:
        return (1, 1 if ja < jb else -1)
    elif ia > ib:
        return (-1, 1 if ja < jb else -1)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## positive (excluded; stratum short; control)

generator: only 51 of 66 valid examples in 4000 draws

## prapply (done; stratum longer; outside development)

```
def prapply(function, a, b):
    return frozenset((function(i, j) for j in b for i in a))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## product (done; stratum longer; outside development)

```
def product(a, b):
    return frozenset(((i, j) for j in b for i in a))
```

- **library_only** selected `prapply(astuple, x0, x1)` (L4-36, 4 nodes): **right**
- **smaller_blocks** selected `prapply(astuple, x0, x1)` (LC4-36, 4 nodes): **right**
  - C-36: `c_frozenset(c_pairs(x0, x1))` (4 nodes): right
  - L4-36: `prapply(astuple, x0, x1)` (4 nodes): right
  - L4-9: `prapply(astuple, x0, x1)` (4 nodes): right
  - L5-36: `prapply(astuple, x0, x1)` (4 nodes): right
  - LC4-36: `prapply(astuple, x0, x1)` (4 nodes): right
  - LC4-9: `prapply(astuple, x0, x1)` (4 nodes): right

## rapply (excluded; stratum longer; development)

66 of 66 generator examples are unusable (a container argument holds a function: 66; the output is or holds a function: 0)

## recolor (done; stratum longer; outside development)

```
def recolor(value, patch):
    return frozenset(((value, index) for index in toindices(patch)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## remove (done; stratum longer; outside development)

```
def remove(value, container):
    return type(container)((e for e in container if e != value))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## repeat (done; stratum longer; outside development)

```
def repeat(item, num):
    return tuple((item for i in range(num)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## replace (done; stratum longer; outside development)

```
def replace(grid, replacee, replacer):
    return tuple((tuple((replacer if v == replacee else v for v in r)) for r in grid))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## righthalf (done; stratum short; development)

```
def righthalf(grid):
    return rot270(bottomhalf(rot90(grid)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## rightmost (done; stratum longer; outside development)

```
def rightmost(patch):
    return max((j for i, j in toindices(patch)))
```

- **library_only** selected `valmax(toindices(x0), last)` (L4-36, 4 nodes): **right**
- **smaller_blocks** selected `valmax(toindices(x0), last)` (LC4-36, 4 nodes): **right**
  - C-36: none (size_limit_completed)
  - L4-36: `valmax(toindices(x0), last)` (4 nodes): right
  - L4-9: `valmax(toindices(x0), last)` (4 nodes): right
  - L5-36: `valmax(toindices(x0), last)` (4 nodes): right
  - LC4-36: `valmax(toindices(x0), last)` (4 nodes): right
  - LC4-9: `valmax(toindices(x0), last)` (4 nodes): right

## rot180 (done; stratum longer; development)

```
def rot180(grid):
    return tuple((tuple(row[::-1]) for row in grid[::-1]))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `apply(c_reverse, c_reverse(x0))` (LC4-36, 4 nodes): **right**
  - C-36: `c_reverse(c_map_tuple(c_reverse, x0))` (4 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `apply(c_reverse, c_reverse(x0))` (4 nodes): right
  - LC4-9: `apply(c_reverse, c_reverse(x0))` (4 nodes): right

## rot270 (done; stratum longer; outside development)

```
def rot270(grid):
    return tuple((tuple(row[::-1]) for row in zip(*grid[::-1])))[::-1]
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_reverse(c_zip_star(x0))` (LC4-36, 3 nodes): **right**
  - C-36: `c_reverse(c_zip_star(x0))` (3 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_reverse(c_zip_star(x0))` (3 nodes): right
  - LC4-9: `c_reverse(c_zip_star(x0))` (3 nodes): right

## rot90 (done; stratum longer; outside development)

```
def rot90(grid):
    return tuple((row for row in zip(*grid[::-1])))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_zip_star(c_reverse(x0))` (LC4-36, 3 nodes): **right**
  - C-36: `c_zip_star(c_reverse(x0))` (3 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_zip_star(c_reverse(x0))` (3 nodes): right
  - LC4-9: `c_zip_star(c_reverse(x0))` (3 nodes): right

## sfilter (done; stratum longer; outside development)

```
def sfilter(container, condition):
    return type(container)((e for e in container if condition(e)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## shape (done; stratum short; outside development)

```
def shape(piece):
    return (height(piece), width(piece))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## shift (done; stratum longer; outside development)

```
def shift(patch, directions):
    if len(patch) == 0:
        return patch
    di, dj = directions
    if isinstance(next(iter(patch))[1], tuple):
        return frozenset(((value, (i + di, j + dj)) for value, (i, j) in patch))
    return frozenset(((i + di, j + dj) for i, j in patch))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## shoot (done; stratum longer; outside development)

```
def shoot(start, direction):
    return connect(start, (start[0] + 42 * direction[0], start[1] + 42 * direction[1]))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## sign (excluded; stratum longer; development)

too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)

## size (done; stratum short; control)

```
def size(container):
    return len(container)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_len(x0)` (LC4-36, 2 nodes): **right**
  - C-36: `c_len(x0)` (2 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_len(x0)` (2 nodes): right
  - LC4-9: `c_len(x0)` (2 nodes): right
  - witness `c_len(x0)`: evaluated; agrees on all 36: True; on the final panel: True

## sizefilter (done; stratum longer; outside development)

```
def sizefilter(container, n):
    return frozenset((item for item in container if len(item) == n))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `connect(UNITY, LEFT)` (3 nodes): wrong (agree 320 of 325; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `EMPTY_SET` (1 nodes): wrong (agree 320 of 325; errors 0; guard timeout False)

## square (done; stratum longer; outside development)

```
def square(piece):
    return len(piece) == len(piece[0]) if isinstance(piece, tuple) else height(piece) * width(piece) == len(piece) and height(piece) == width(piece)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `contained(size(x0), DOWN)` (4 nodes): wrong (agree 98 of 101; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `contained(size(x0), DOWN)` (4 nodes): wrong (agree 98 of 101; errors 0; guard timeout False)

## subgrid (done; stratum short; outside development)

```
def subgrid(patch, grid):
    return crop(grid, ulcorner(patch), shape(patch))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## subtract (done; stratum longer; outside development)

```
def subtract(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a - b
    elif isinstance(a, tuple) and isinstance(b, tuple):
        return (a[0] - b[0], a[1] - b[1])
    elif isinstance(a, int) and isinstance(b, tuple):
        return (a - b[0], a - b[1])
    return (a[0] - b, a[1] - b)
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## switch (done; stratum longer; development)

```
def switch(grid, a, b):
    return tuple((tuple((v if v != a and v != b else {a: b, b: a}[v] for v in r)) for r in grid))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## toindices (done; stratum longer; outside development)

```
def toindices(patch):
    if len(patch) == 0:
        return frozenset()
    if isinstance(next(iter(patch))[1], tuple):
        return frozenset((index for value, index in patch))
    return patch
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## toivec (excluded; stratum short; control)

generator: only 41 of 66 valid examples in 4000 draws

## tojvec (excluded; stratum short; control)

generator: only 41 of 66 valid examples in 4000 draws

## toobject (done; stratum longer; outside development)

```
def toobject(patch, grid):
    h, w = (len(grid), len(grid[0]))
    return frozenset(((grid[i][j], (i, j)) for i, j in toindices(patch) if 0 <= i < h and 0 <= j < w))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## tophalf (done; stratum longer; development)

```
def tophalf(grid):
    return grid[:len(grid) // 2]
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## totuple (done; stratum short; control)

```
def totuple(container):
    return tuple(container)
```

- **library_only** selected `order(x0, initset)` (L4-36, 3 nodes): **right**
- **smaller_blocks** selected `c_tuple(x0)` (LC4-36, 2 nodes): **right**
  - C-36: `c_tuple(x0)` (2 nodes): right
  - L4-36: `order(x0, initset)` (3 nodes): right
  - L4-9: `order(x0, initset)` (3 nodes): right
  - L5-36: `order(x0, initset)` (3 nodes): right
  - LC4-36: `c_tuple(x0)` (2 nodes): right
  - LC4-9: `c_tuple(x0)` (2 nodes): right
  - witness `c_tuple(x0)`: evaluated; agrees on all 36: True; on the final panel: True

## ulcorner (done; stratum longer; outside development)

```
def ulcorner(patch):
    return tuple(map(min, zip(*toindices(patch))))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## underfill (done; stratum longer; outside development)

```
def underfill(grid, value, patch):
    h, w = (len(grid), len(grid[0]))
    bg = mostcolor(grid)
    g = list((list(r) for r in grid))
    for i, j in toindices(patch):
        if 0 <= i < h and 0 <= j < w:
            if g[i][j] == bg:
                g[i][j] = value
    return tuple((tuple(r) for r in g))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## underpaint (done; stratum longer; outside development)

```
def underpaint(grid, obj):
    h, w = (len(grid), len(grid[0]))
    bg = mostcolor(grid)
    g = list((list(r) for r in grid))
    for value, (i, j) in obj:
        if 0 <= i < h and 0 <= j < w:
            if g[i][j] == bg:
                g[i][j] = value
    return tuple((tuple(r) for r in g))
```

- **library_only** selected `x0` (L4-36, 1 nodes): **wrong**
- **smaller_blocks** selected `x0` (LC4-36, 1 nodes): **wrong**
  - C-36: `x0` (1 nodes): wrong (agree 138 of 430; errors 0; guard timeout False)
  - L4-36: `x0` (1 nodes): wrong (agree 138 of 430; errors 0; guard timeout False)
  - L4-9: `x0` (1 nodes): wrong (agree 138 of 430; errors 0; guard timeout False)
  - L5-36: `x0` (1 nodes): wrong (agree 138 of 430; errors 0; guard timeout False)
  - LC4-36: `x0` (1 nodes): wrong (agree 138 of 430; errors 0; guard timeout False)
  - LC4-9: `x0` (1 nodes): wrong (agree 138 of 430; errors 0; guard timeout False)

## uppermost (done; stratum longer; outside development)

```
def uppermost(patch):
    return min((i for i, j in toindices(patch)))
```

- **library_only** selected `valmin(toindices(x0), first)` (L4-36, 4 nodes): **right**
- **smaller_blocks** selected `valmin(toindices(x0), first)` (LC4-36, 4 nodes): **right**
  - C-36: none (size_limit_completed)
  - L4-36: `valmin(toindices(x0), first)` (4 nodes): right
  - L4-9: `valmin(toindices(x0), first)` (4 nodes): right
  - L5-36: `valmin(toindices(x0), first)` (4 nodes): right
  - LC4-36: `valmin(toindices(x0), first)` (4 nodes): right
  - LC4-9: `valmin(toindices(x0), first)` (4 nodes): right

## urcorner (done; stratum longer; outside development)

```
def urcorner(patch):
    return tuple(map(lambda ix: {0: min, 1: max}[ix[0]](ix[1]), enumerate(zip(*toindices(patch)))))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## valmax (done; stratum short; control)

```
def valmax(container, compfunc):
    return compfunc(max(container, key=compfunc, default=0))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected `c_max(c_map_tuple(x1, x0))` (LC4-36, 4 nodes): **right**
  - C-36: `c_max(c_map_tuple(x1, x0))` (4 nodes): right
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: `c_max(c_map_tuple(x1, x0))` (4 nodes): right
  - LC4-9: `c_max(c_map_tuple(x1, x0))` (4 nodes): right
  - witness `c_call1(x1, c_max_key_default0(x0, x1))`: evaluated; agrees on all 36: True; on the final panel: True

## valmin (done; stratum short; control)

```
def valmin(container, compfunc):
    return compfunc(min(container, key=compfunc, default=0))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)
  - witness `c_call1(x1, c_min_key_default0(x0, x1))`: evaluated; agrees on all 36: True; on the final panel: True

## vconcat (done; stratum short; control)

```
def vconcat(a, b):
    return a + b
```

- **library_only** selected `combine(x0, x1)` (L4-36, 3 nodes): **right**
- **smaller_blocks** selected `combine(x0, x1)` (LC4-36, 3 nodes): **right**
  - C-36: `c_concat(x0, x1)` (3 nodes): right
  - L4-36: `combine(x0, x1)` (3 nodes): right
  - L4-9: `combine(x0, x1)` (3 nodes): right
  - L5-36: `combine(x0, x1)` (3 nodes): right
  - LC4-36: `combine(x0, x1)` (3 nodes): right
  - LC4-9: `combine(x0, x1)` (3 nodes): right
  - witness `c_concat(x0, x1)`: evaluated; agrees on all 36: True; on the final panel: True

## vfrontier (excluded; stratum longer; development)

too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)

## vline (done; stratum longer; outside development)

```
def vline(patch):
    return height(patch) == len(patch) and width(patch) == 1
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## vmatching (done; stratum longer; outside development)

```
def vmatching(a, b):
    return len(set((j for i, j in toindices(a))) & set((j for i, j in toindices(b)))) > 0
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: `flip(square(x0))` (3 nodes): wrong (agree 317 of 430; errors 0; guard timeout False)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: `flip(square(x0))` (3 nodes): wrong (agree 317 of 430; errors 0; guard timeout False)

## vmirror (done; stratum longer; outside development)

```
def vmirror(piece):
    if isinstance(piece, tuple):
        return tuple((row[::-1] for row in piece))
    d = ulcorner(piece)[1] + lrcorner(piece)[1]
    if isinstance(next(iter(piece))[1], tuple):
        return frozenset(((v, (i, d - j)) for v, (i, j) in piece))
    return frozenset(((i, d - j) for i, j in piece))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## vperiod (done; stratum longer; outside development)

```
def vperiod(obj):
    normalized = normalize(obj)
    h = height(normalized)
    for p in range(1, h):
        offsetted = shift(normalized, (-p, 0))
        pruned = frozenset({(c, (i, j)) for c, (i, j) in offsetted if i >= 0})
        if pruned.issubset(normalized):
            return p
    return h
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## vsplit (done; stratum longer; outside development)

```
def vsplit(grid, n):
    h, w = (len(grid) // n, len(grid[0]))
    offset = len(grid) % n != 0
    return tuple((crop(grid, (h * i + i * offset, 0), (h, w)) for i in range(n)))
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## vupscale (done; stratum longer; outside development)

```
def vupscale(grid, factor):
    g = tuple()
    for row in grid:
        g = g + tuple((row for num in range(factor)))
    return g
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

## width (done; stratum longer; development)

```
def width(piece):
    if len(piece) == 0:
        return 0
    if isinstance(piece, tuple):
        return len(piece[0])
    return rightmost(piece) - leftmost(piece) + 1
```

- **library_only** selected nothing (neither stage (L4-36, L5-36) found a fit)
- **smaller_blocks** selected nothing (neither stage (LC4-36, C-36) found a fit)
  - C-36: none (size_limit_completed)
  - L4-36: none (size_limit_completed)
  - L4-9: none (size_limit_completed)
  - L5-36: none (combination_budget_used_up)
  - LC4-36: none (size_limit_completed)
  - LC4-9: none (size_limit_completed)

