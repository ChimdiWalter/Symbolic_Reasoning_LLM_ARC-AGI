### Names used in these tables

- **Library only**: searches the retained library operations, first up to 4 nodes on 36 examples (L4-36), then up to five nodes (L5-36).
- **Smaller blocks**: searches the library together with the smaller blocks up to 4 nodes on 36 examples (LC4-36), then the blocks with the retained operations alone (C-36).
- **L4-9** and **LC4-9**: the same 4-node searches on nine examples.
- **Right** and **wrong**: the record's verdict on the final panel.
- **Selected nothing**: neither stage of the system found an expression that fits all 36 examples.

### Run

Listed 145, records 145, done 125, excluded 20, incomplete 0.

| stratum | original | eligible | excluded | generator | too few usable pooled inputs |
|---|---|---|---|---|---|
| Short | 35 | 28 | 7 | 4 | 3 |
| Longer | 90 | 80 | 10 | 0 | 10 |
| Longer, 7 to 15 nodes | 35 | 32 | 3 | 0 | 3 |
| Longer, more than 15 nodes | 55 | 48 | 7 | 0 | 7 |

Development names: 20 listed, 17 done, 3 excluded.

Longer stratum outside development (10):

- `crement`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `decrement`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `dneighbors`: too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)
- `double`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `halve`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `hfrontier`: too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)
- `increment`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `ineighbors`: too few usable pooled inputs (usability slice: 23 of 23 draws usable, need 30)
- `invert`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `merge`: too few usable pooled inputs (usability slice: 9 of 9 draws usable, need 30)

Short stratum outside development (7):

- `even`: generator: only 51 of 66 valid examples in 4000 draws
- `maximum`: too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)
- `minimum`: too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)
- `neighbors`: too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)
- `positive`: generator: only 51 of 66 valid examples in 4000 draws
- `toivec`: generator: only 41 of 66 valid examples in 4000 draws
- `tojvec`: generator: only 41 of 66 valid examples in 4000 draws

Development names (3):

- `rapply`: 66 of 66 generator examples are unusable (a container argument holds a function: 66; the output is or holds a function: 0)
- `sign`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `vfrontier`: too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)

Final panels of the primary cohort (80 done targets): generator minimum 30, pooled median 323.0, pooled minimum 34, pooled discarded sum 1197, pooled short: none, pooled not evaluated: none.

- Job costs from detached_job_record/time.txt: user 13572.99 s, system 143.71 s, wall clock 3:48:44, peak resident 2737936 kB, exit status 0.
- From full_out/RUN_COSTS.json: cpu_process_s 13713.60, wall_s 13720.10.

After-run checks (passed: True):

- 1 the freeze verifies: passed
- 2 one read-only receipt naming the freeze, the setup record and the output folder: passed
- 3 the job started once and ended once with exit 0: passed
- 4 the run's manifest names the freeze, the setup record, the whole roster and the frozen policy: passed
- 5 one record for every listed target and no other: passed
- 6 every journal holds its path's events and seals, in order, equal to the record: passed
- 7 SUMMARY.json equals a summary made now from the records: passed
- 7b the calibration set (K and its names) equals the one committed with the freeze: passed
- 8 setup decisions and counts equal the committed record: passed

- Searches within 20% of the safety limit: none.
- Guard timeouts: none.
- Guarded steps without a mark: none.
- Guard bound: shortest guard 20.0 s, margin 0.01 s, 145 targets below the bound, not excluded: none, unknown time: none.

- Freeze sha256: `391915c42f629661ba9d47d641ec186847c8ac2600128c35307ac12d09427144`.
- Setup record sha256: `1c7018c478ff88bfaf48f6d331929e43e9ac13da50d1a9e99015e701ba3a1732`.

### Primary comparison

Cohort: done records with stratum longer, outside the development names (N = 80).

| system | right | selected and wrong | selected nothing | of |
|---|---|---|---|---|
| library only | 7 | 3 | 70 | 80 |
| smaller blocks | 10 | 3 | 67 | 80 |

- Right in both (7): `asobject`, `hconcat`, `leftmost`, `lowermost`, `product`, `rightmost`, `uppermost`.
- Right in smaller blocks only (3): `difference`, `rot270`, `rot90`.
- Right in library only only (0): none.
- Right in neither (70): `apply`, `asindices`, `bordering`, `bottomhalf`, `canvas`, `cellwise`, `center`, `centerofmass`, `cmirror`, `colorcount`, `colorfilter`, `combine`, `connect`, `corners`, `crop`, `dedupe`, `delta`, `divide`, `dmirror`, `extract`, `fgpartition`, `fill`, `frontiers`, `gravitate`, `height`, `hline`, `hmatching`, `hperiod`, `hsplit`, `hupscale`, `inbox`, `index`, `leastcolor`, `llcorner`, `lrcorner`, `manhattan`, `mostcolor`, `move`, `multiply`, `normalize`, `occurrences`, `outbox`, `paint`, `palette`, `papply`, `partition`, `position`, `prapply`, `recolor`, `remove`, `repeat`, `replace`, `sfilter`, `shift`, `shoot`, `sizefilter`, `square`, `subtract`, `toindices`, `toobject`, `ulcorner`, `underfill`, `underpaint`, `urcorner`, `vline`, `vmatching`, `vmirror`, `vperiod`, `vsplit`, `vupscale`.

- Two-sided exact sign test: p = 0.25.
- W (rebuilt by smaller blocks only): 3. L (rebuilt by library only only): 0. W minus L: 3.
- Concordant: both right 7, neither right 70.

Criterion parts:

- W greater than L: True
- p below 0.05: False
- calibration valid and passed: True
- cohort complete: True

- Status: not met. Provisional: False.

### Calibration

- K = 19. Minimum K: 19.
- Minimum K note: amendment of 15 November 2026 by the author: the minimum was 20 in the drafts; it was lowered to 19 after the setup pass over all names gave K = 19 and before any search outside the development names or any outcome
- Share: 0.9. Threshold (right): 18. Right: 19. Passed: True. Valid: True. State: passed.

| operation | witness | nodes | within limit | agrees on all 36 | agrees on the final panel | C-36 expr | C-36 verdict | smaller blocks expr | smaller blocks verdict | library only expr | library only search | library only verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| argmax | `c_max_key(x0, x1)` | 3 | yes | yes | yes | `c_max_key(x0, x1)` | right | `c_max_key(x0, x1)` | right |  |  | selected nothing |
| argmin | `c_min_key(x0, x1)` | 3 | yes | yes | yes | `c_min_key(x0, x1)` | right | `c_min_key(x0, x1)` | right | `first(order(x0, x1))` | L4-36 | right |
| astuple | `c_pair(x0, x1)` | 3 | yes | yes | yes | `c_pair(x0, x1)` | right | `c_pair(x0, x1)` | right |  |  | selected nothing |
| branch | `c_if_else(x0, x1, x2)` | 4 | yes | yes | yes | `c_if_else(x0, x1, x2)` | right | `c_if_else(x0, x1, x2)` | right |  |  | selected nothing |
| contained | `c_in(x0, x1)` | 3 | yes | yes | yes | `c_in(x0, x1)` | right | `c_in(x0, x1)` | right | `valmax(x1, matcher(identity, x0))` | L5-36 | right |
| equality | `c_eq(x0, x1)` | 3 | yes | yes | yes | `c_eq(x0, x1)` | right | `c_eq(x0, x1)` | right | `contained(x0, initset(x1))` | L4-36 | right |
| first | `c_first(x0)` | 2 | yes | yes | yes | `c_first(x0)` | right | `c_first(x0)` | right | `argmax(x0, flip)` | L4-36 | wrong |
| greater | `c_gt(x0, x1)` | 3 | yes | yes | yes | `c_lt(x1, x0)` | right | `c_lt(x1, x0)` | right |  |  | selected nothing |
| identity | `x0` | 1 | yes | yes | yes | `x0` | right | `x0` | right | `x0` | L4-36 | right |
| initset | `c_set1(x0)` | 2 | yes | yes | yes | `c_set1(x0)` | right | `c_set1(x0)` | right |  |  | selected nothing |
| insert | `c_union(x1, c_set1(x0))` | 4 | yes | yes | yes | `c_union(x1, c_set1(x0))` | right | `c_union(x1, c_set1(x0))` | right |  |  | selected nothing |
| intersection | `c_intersection(x0, x1)` | 3 | yes | yes | yes | `c_intersection(x0, x1)` | right | `c_intersection(x0, x1)` | right |  |  | selected nothing |
| interval | `c_range3(x0, x1, x2)` | 4 | yes | yes | yes | `c_range3(x0, x1, x2)` | right | `c_range3(x0, x1, x2)` | right |  |  | selected nothing |
| last | `c_item1(c_max(c_enumerate(x0)))` | 4 | yes | yes | yes | `c_first(c_reverse(c_tuple(x0)))` | right | `c_first(c_reverse(c_tuple(x0)))` | right |  |  | selected nothing |
| leastcommon | `c_min_key(c_frozenset(x0), lbind(c_count, x0))` | 6 | no | yes | yes |  | none |  | selected nothing |  |  | selected nothing |
| order | `c_sorted_key(x0, x1)` | 3 | yes | yes | yes | `c_sorted_key(x0, x1)` | right | `c_sorted_key(x0, x1)` | right |  |  | selected nothing |
| pair | `c_zip(x0, x1)` | 3 | yes | yes | yes | `c_zip(x0, x1)` | right | `c_zip(x0, x1)` | right | `papply(astuple, x0, x1)` | L4-36 | right |
| size | `c_len(x0)` | 2 | yes | yes | yes | `c_len(x0)` | right | `c_len(x0)` | right |  |  | selected nothing |
| totuple | `c_tuple(x0)` | 2 | yes | yes | yes | `c_tuple(x0)` | right | `c_tuple(x0)` | right | `order(x0, initset)` | L4-36 | right |
| valmax | `c_call1(x1, c_max_key_default0(x0, x1))` | 5 | no | yes | yes | `c_max(c_map_tuple(x1, x0))` | right | `c_max(c_map_tuple(x1, x0))` | right |  |  | selected nothing |
| valmin | `c_call1(x1, c_min_key_default0(x0, x1))` | 5 | no | yes | yes |  | none |  | selected nothing |  |  | selected nothing |
| vconcat | `c_concat(x0, x1)` | 3 | yes | yes | yes | `c_concat(x0, x1)` | right | `combine(x0, x1)` | right | `combine(x0, x1)` | L4-36 | right |

- Blocks-alone search (C-36) expression equals the witness expression for the 19 calibration names: 17 match, 2 differ.
  - `greater`: found `c_lt(x1, x0)`, witness `c_gt(x0, x1)`
  - `last`: found `c_first(c_reverse(c_tuple(x0)))`, witness `c_item1(c_max(c_enumerate(x0)))`
- Smaller-blocks selection expression equals the witness expression: 16 match, 3 differ.
  - `greater`: selected `c_lt(x1, x0)`, witness `c_gt(x0, x1)`
  - `last`: selected `c_first(c_reverse(c_tuple(x0)))`, witness `c_item1(c_max(c_enumerate(x0)))`
  - `vconcat`: selected `combine(x0, x1)`, witness `c_concat(x0, x1)`

Eligible controls without a witness within the size limit (3):

- `leastcommon`: the witness has more than 4 nodes (6)
- `valmax`: the witness has more than 4 nodes (5)
- `valmin`: the witness has more than 4 nodes (5)

Controls not eligible (6):

- `even`: generator: only 51 of 66 valid examples in 4000 draws
- `maximum`: too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)
- `minimum`: too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)
- `positive`: generator: only 51 of 66 valid examples in 4000 draws
- `toivec`: generator: only 41 of 66 valid examples in 4000 draws
- `tojvec`: generator: only 41 of 66 valid examples in 4000 draws

### Secondary comparisons (descriptive, uncorrected)

| block | N | library only right | smaller blocks right | both | smaller blocks only | library only only | neither | p | library only selected and wrong | smaller blocks selected and wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| Short stratum | 28 | 7 | 20 | 7 | 13 | 0 | 8 | 0.0002441 | `first` | none |
| Longer, 7 to 15 nodes | 32 | 6 | 8 | 6 | 2 | 0 | 24 | 0.5 | `extract` | `extract` |
| Longer, more than 15 nodes | 48 | 1 | 2 | 1 | 1 | 0 | 46 | 1 | `paint`, `underpaint` | `paint`, `underpaint` |
| All strata outside development | 108 | 14 | 30 | 14 | 16 | 0 | 78 | 3.052e-05 | `extract`, `first`, `paint`, `underpaint` | `extract`, `paint`, `underpaint` |
| Development names (development only) | 17 | 1 | 2 | 1 | 1 | 0 | 15 | 1 | `other` | none |

- Short stratum: smaller blocks only: `argmax`, `astuple`, `branch`, `first`, `greater`, `initset`, `insert`, `intersection`, `interval`, `last`, `order`, `size`, `valmax`. Library only only: none.
- Longer, 7 to 15 nodes: smaller blocks only: `difference`, `rot90`. Library only only: none.
- Longer, more than 15 nodes: smaller blocks only: `rot270`. Library only only: none.
- All strata outside development: smaller blocks only: `argmax`, `astuple`, `branch`, `difference`, `first`, `greater`, `initset`, `insert`, `intersection`, `interval`, `last`, `order`, `rot270`, `rot90`, `size`, `valmax`. Library only only: none.
- Development names (development only): smaller blocks only: `rot180`. Library only only: none.

Short operations outside development that are not controls (6):

- `adjacent`: library only: selected nothing; smaller blocks: selected nothing.
- `cover`: library only: selected nothing; smaller blocks: selected nothing.
- `mpapply`: library only: selected nothing; smaller blocks: selected nothing.
- `portrait`: library only: selected nothing; smaller blocks: selected nothing.
- `shape`: library only: selected nothing; smaller blocks: selected nothing.
- `subgrid`: library only: selected nothing; smaller blocks: selected nothing.

### The six searches

Primary cohort (longer stratum outside development, N = 80):

| search | n | right | wrong | none | found | size limit completed | combination budget used up | sum (s) | median (s) | largest (s) | largest operation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L4-9 | 80 | 7 | 12 | 61 | 19 | 61 | 0 | 253.17 | 2.92 | 8.90 | `manhattan` |
| LC4-9 | 80 | 10 | 12 | 58 | 22 | 58 | 0 | 892.49 | 12.12 | 26.75 | `manhattan` |
| L4-36 | 80 | 7 | 3 | 70 | 10 | 70 | 0 | 795.15 | 8.16 | 24.27 | `move` |
| L5-36 | 80 | 7 | 3 | 70 | 10 | 0 | 70 | 4098.50 | 56.42 | 80.86 | `fill` |
| LC4-36 | 80 | 10 | 3 | 67 | 13 | 67 | 0 | 3194.24 | 38.81 | 87.26 | `move` |
| C-36 | 80 | 4 | 2 | 74 | 6 | 74 | 0 | 305.09 | 3.76 | 7.69 | `move` |

All done records outside the development names (N = 108):

| search | n | right | wrong | none | found | size limit completed | combination budget used up | sum (s) | median (s) | largest (s) | largest operation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L4-9 | 108 | 13 | 17 | 78 | 30 | 78 | 0 | 310.91 | 2.75 | 8.90 | `manhattan` |
| LC4-9 | 108 | 29 | 15 | 64 | 44 | 64 | 0 | 1021.79 | 10.81 | 26.75 | `manhattan` |
| L4-36 | 108 | 13 | 4 | 91 | 17 | 91 | 0 | 979.33 | 7.48 | 24.27 | `move` |
| L5-36 | 108 | 14 | 4 | 90 | 18 | 0 | 90 | 5209.09 | 53.88 | 80.86 | `fill` |
| LC4-36 | 108 | 30 | 3 | 75 | 33 | 75 | 0 | 3655.19 | 35.74 | 87.26 | `move` |
| C-36 | 108 | 24 | 2 | 82 | 26 | 82 | 0 | 344.13 | 3.54 | 7.69 | `move` |

All done records, development names included (N = 125):

| search | n | right | wrong | none | found | size limit completed | combination budget used up | sum (s) | median (s) | largest (s) | largest operation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L4-9 | 125 | 14 | 17 | 94 | 31 | 94 | 0 | 367.52 | 2.75 | 8.90 | `manhattan` |
| LC4-9 | 125 | 31 | 15 | 79 | 46 | 79 | 0 | 1234.83 | 11.28 | 26.75 | `manhattan` |
| L4-36 | 125 | 14 | 4 | 107 | 18 | 107 | 0 | 1132.14 | 7.52 | 24.27 | `move` |
| L5-36 | 125 | 15 | 5 | 105 | 20 | 0 | 105 | 6104.51 | 53.95 | 80.86 | `fill` |
| LC4-36 | 125 | 32 | 3 | 90 | 35 | 90 | 0 | 4298.82 | 35.95 | 87.26 | `move` |
| C-36 | 125 | 26 | 2 | 97 | 28 | 97 | 0 | 402.64 | 3.54 | 7.69 | `move` |

Counted from the records; the summary has no block for this cohort.

- Total searches over all 125 done records: 750.
- Stop classes: found 178, size limit completed 467, combination budget used up 105.
- Searches with function cap reached: 0.
- Largest bank: 263232 (`cellwise`, L5-36) against a cap of 1500000.
- Largest search processor time: 87.26 s (`move`, LC4-36).
- Done records with at least one found expression in any search: 47. With none: 78.

### Stages and candidate sets

Primary cohort (N = 80):

- LC4-36 against L4-36: both 7, LC4-36 only 3, L4-36 only 0, neither 70.
  - LC4-36 only: `difference`, `rot270`, `rot90`.
- L5-36 against L4-36: both 7, L5-36 only 0, L4-36 only 0, neither 73.
- Operations where the four-node library search is right and the search with blocks ended by its budget without a right fit: 0.
- Library only selected by stage: stage 1: 10.
- Smaller blocks selected by stage: stage 1: 13.
- Library only candidate-set coverage (either of the system's two found expressions right on the final panel; this is not the system's result): 7.
- Smaller blocks candidate-set coverage (either of the system's two found expressions right on the final panel; this is not the system's result): 10.

All done records outside the development names (N = 108):

- LC4-36 against L4-36: both 13, LC4-36 only 17, L4-36 only 0, neither 78.
  - LC4-36 only: `argmax`, `astuple`, `branch`, `contained`, `difference`, `first`, `greater`, `initset`, `insert`, `intersection`, `interval`, `last`, `order`, `rot270`, `rot90`, `size`, `valmax`.
- L5-36 against L4-36: both 13, L5-36 only 1, L4-36 only 0, neither 94.
  - L5-36 only: `contained`.
- Operations where the four-node library search is right and the search with blocks ended by its budget without a right fit: 0.
- Library only selected by stage: stage 1: 17, stage 2: 1.
- Smaller blocks selected by stage: stage 1: 33.
- Library only candidate-set coverage (either of the system's two found expressions right on the final panel; this is not the system's result): 14.
- Smaller blocks candidate-set coverage (either of the system's two found expressions right on the final panel; this is not the system's result): 30.

### Order of sets

Note: for a selected expression that is right and whose output is a frozenset; nested sets are not compared; it does not change 'right'

Primary cohort:

Library only: 492 of 731 inputs with the same order.

| operation | same order | of |
|---|---|---|
| asobject | 114 | 353 |
| product | 378 | 378 |

Smaller blocks: 797 of 1047 inputs with the same order.

| operation | same order | of |
|---|---|---|
| asobject | 114 | 353 |
| difference | 305 | 316 |
| product | 378 | 378 |


All done records outside the development names:

Library only: 552 of 791 inputs with the same order.

| operation | same order | of |
|---|---|---|
| argmin | 24 | 24 |
| asobject | 114 | 353 |
| identity | 36 | 36 |
| product | 378 | 378 |

Smaller blocks: 1572 of 1822 inputs with the same order.

| operation | same order | of |
|---|---|---|
| argmax | 29 | 29 |
| argmin | 24 | 24 |
| asobject | 114 | 353 |
| branch | 181 | 181 |
| difference | 305 | 316 |
| first | 24 | 24 |
| identity | 36 | 36 |
| insert | 428 | 428 |
| intersection | 13 | 13 |
| last | 21 | 21 |
| product | 378 | 378 |
| valmax | 19 | 19 |


### Sizes of found expressions

Primary cohort (N = 80):

| search | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| L4-9 | 3 | 1 | 7 | 8 |  |
| LC4-9 | 4 | 1 | 9 | 8 |  |
| L4-36 | 2 |  | 2 | 6 |  |
| L5-36 | 2 |  | 2 | 6 |  |
| LC4-36 | 2 |  | 5 | 6 |  |
| C-36 | 2 |  | 3 | 1 |  |

All done records outside the development names (N = 108):

| search | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| L4-9 | 4 | 1 | 12 | 13 |  |
| LC4-9 | 6 | 5 | 19 | 14 |  |
| L4-36 | 3 |  | 5 | 9 |  |
| L5-36 | 3 |  | 5 | 9 | 1 |
| LC4-36 | 3 | 4 | 15 | 11 |  |
| C-36 | 3 | 4 | 13 | 6 |  |

### Costs

Note: subtotals of the targets' own records; nested subtotals are never added to the whole job

| block | listed | done | excluded at setup | searches (s) | final checks (s) | other (s) | targets total (s) | library only (s) | smaller blocks (s) |
|---|---|---|---|---|---|---|---|---|---|
| Longer stratum outside development | 90 | 80 | 10 | 9538.70 | 3.09 | 105.30 | 9650.80 | 4893.70 | 3499.30 |
| Short stratum outside development | 35 | 28 | 7 | 1981.80 | 0.96 | 29.40 | 2015.00 | 1294.80 | 500.00 |
| All strata outside development | 125 | 108 | 17 | 11520.50 | 4.05 | 134.70 | 11665.80 | 6188.40 | 3999.30 |
| Development names (development only) | 20 | 17 | 3 | 2020.10 | 0.07 | 27.00 | 2047.50 | 1048.20 | 702.10 |

- Each row covers every listed operation of its block, including those excluded at setup, whose setup time is in the total. For the first row: done records 9647.07 s, excluded records 3.76 s.
- The two system columns are the sums of that system's two 36-example searches only (library only: L4-36 and L5-36; smaller blocks: LC4-36 and C-36), so the nine-example searches, the final checks and other work are not in them.

- Whole job (from the process): cpu_process_s 13713.60, cpu_user_s 13572.80, cpu_system_s 143.70, wall_s 13720.10.
- Whole job (from detached_job_record/time.txt): user 13572.99 s, system 143.71 s, wall clock 3:48:44.
- Setup of the pools: 0.00 s. Targets: 13713.20 s.

### Every selected expression

| operation | stratum | role | system | expression | nodes | search | verdict | agree of n | generator | pooled |
|---|---|---|---|---|---|---|---|---|---|---|
| asobject | longer |  | library only | `merge(partition(x0))` | 3 | L4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| asobject | longer |  | smaller blocks | `merge(partition(x0))` | 3 | LC4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| difference | longer |  | smaller blocks | `c_set_difference(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| extract | longer |  | library only | `argmin(x0, flip)` | 3 | L4-36 | wrong | 283 of 292 | 30 of 30 | 253 of 262 |
| extract | longer |  | smaller blocks | `argmin(x0, flip)` | 3 | LC4-36 | wrong | 283 of 292 | 30 of 30 | 253 of 262 |
| hconcat | longer |  | library only | `papply(combine, x0, x1)` | 4 | L4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| hconcat | longer |  | smaller blocks | `papply(combine, x0, x1)` | 4 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| leftmost | longer |  | library only | `valmin(toindices(x0), last)` | 4 | L4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| leftmost | longer |  | smaller blocks | `valmin(toindices(x0), last)` | 4 | LC4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| lowermost | longer |  | library only | `valmax(toindices(x0), first)` | 4 | L4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| lowermost | longer |  | smaller blocks | `valmax(toindices(x0), first)` | 4 | LC4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| paint | longer |  | library only | `x0` | 1 | L4-36 | wrong | 139 of 430 | 30 of 30 | 109 of 400 |
| paint | longer |  | smaller blocks | `x0` | 1 | LC4-36 | wrong | 139 of 430 | 30 of 30 | 109 of 400 |
| product | longer |  | library only | `prapply(astuple, x0, x1)` | 4 | L4-36 | right | 393 of 393 | 30 of 30 | 363 of 363 |
| product | longer |  | smaller blocks | `prapply(astuple, x0, x1)` | 4 | LC4-36 | right | 393 of 393 | 30 of 30 | 363 of 363 |
| rightmost | longer |  | library only | `valmax(toindices(x0), last)` | 4 | L4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| rightmost | longer |  | smaller blocks | `valmax(toindices(x0), last)` | 4 | LC4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| rot270 | longer |  | smaller blocks | `c_reverse(c_zip_star(x0))` | 3 | LC4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| rot90 | longer |  | smaller blocks | `c_zip_star(c_reverse(x0))` | 3 | LC4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| underpaint | longer |  | library only | `x0` | 1 | L4-36 | wrong | 138 of 430 | 30 of 30 | 108 of 400 |
| underpaint | longer |  | smaller blocks | `x0` | 1 | LC4-36 | wrong | 138 of 430 | 30 of 30 | 108 of 400 |
| uppermost | longer |  | library only | `valmin(toindices(x0), first)` | 4 | L4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| uppermost | longer |  | smaller blocks | `valmin(toindices(x0), first)` | 4 | LC4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| argmax | short | control | smaller blocks | `c_max_key(x0, x1)` | 3 | LC4-36 | right | 289 of 289 | 30 of 30 | 259 of 259 |
| argmin | short | control | library only | `first(order(x0, x1))` | 4 | L4-36 | right | 333 of 333 | 30 of 30 | 303 of 303 |
| argmin | short | control | smaller blocks | `c_min_key(x0, x1)` | 3 | LC4-36 | right | 333 of 333 | 30 of 30 | 303 of 303 |
| astuple | short | control | smaller blocks | `c_pair(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| branch | short | control | smaller blocks | `c_if_else(x0, x1, x2)` | 4 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| contained | short | control | library only | `valmax(x1, matcher(identity, x0))` | 5 | L5-36 | right | 414 of 414 | 30 of 30 | 384 of 384 |
| contained | short | control | smaller blocks | `c_in(x0, x1)` | 3 | LC4-36 | right | 414 of 414 | 30 of 30 | 384 of 384 |
| equality | short | control | library only | `contained(x0, initset(x1))` | 4 | L4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| equality | short | control | smaller blocks | `c_eq(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| first | short | control | library only | `argmax(x0, flip)` | 3 | L4-36 | wrong | 204 of 213 | 27 of 30 | 177 of 183 |
| first | short | control | smaller blocks | `c_first(x0)` | 2 | LC4-36 | right | 213 of 213 | 30 of 30 | 183 of 183 |
| greater | short | control | smaller blocks | `c_lt(x1, x0)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| identity | short | control | library only | `x0` | 1 | L4-36 | right | 99 of 99 | 30 of 30 | 69 of 69 |
| identity | short | control | smaller blocks | `x0` | 1 | LC4-36 | right | 99 of 99 | 30 of 30 | 69 of 69 |
| initset | short | control | smaller blocks | `c_set1(x0)` | 2 | LC4-36 | right | 98 of 98 | 30 of 30 | 68 of 68 |
| insert | short | control | smaller blocks | `c_union(x1, c_set1(x0))` | 4 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| intersection | short | control | smaller blocks | `c_intersection(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| interval | short | control | smaller blocks | `c_range3(x0, x1, x2)` | 4 | LC4-36 | right | 422 of 422 | 30 of 30 | 392 of 392 |
| last | short | control | smaller blocks | `c_first(c_reverse(c_tuple(x0)))` | 4 | LC4-36 | right | 214 of 214 | 30 of 30 | 184 of 184 |
| order | short | control | smaller blocks | `c_sorted_key(x0, x1)` | 3 | LC4-36 | right | 276 of 276 | 30 of 30 | 246 of 246 |
| pair | short | control | library only | `papply(astuple, x0, x1)` | 4 | L4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| pair | short | control | smaller blocks | `c_zip(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| size | short | control | smaller blocks | `c_len(x0)` | 2 | LC4-36 | right | 214 of 214 | 30 of 30 | 184 of 184 |
| totuple | short | control | library only | `order(x0, initset)` | 3 | L4-36 | right | 70 of 70 | 30 of 30 | 40 of 40 |
| totuple | short | control | smaller blocks | `c_tuple(x0)` | 2 | LC4-36 | right | 70 of 70 | 30 of 30 | 40 of 40 |
| valmax | short | control | smaller blocks | `c_max(c_map_tuple(x1, x0))` | 4 | LC4-36 | right | 328 of 328 | 30 of 30 | 298 of 298 |
| vconcat | short | control | library only | `combine(x0, x1)` | 3 | L4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| vconcat | short | control | smaller blocks | `combine(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| rot180 | longer | development | smaller blocks | `apply(c_reverse, c_reverse(x0))` | 4 | LC4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| color | short | development | library only | `first(first(x0))` | 3 | L4-36 | right | 82 of 82 | 30 of 30 | 52 of 52 |
| color | short | development | smaller blocks | `first(first(x0))` | 3 | LC4-36 | right | 82 of 82 | 30 of 30 | 52 of 52 |
| other | short | development | library only | `argmin(x0, matcher(identity, x1))` | 5 | L5-36 | wrong | 395 of 411 | 29 of 30 | 366 of 381 |

### Selected and wrong

| operation | stratum | system | expression | nodes | search | agree of n | generator | pooled |
|---|---|---|---|---|---|---|---|---|
| extract | longer | library only, smaller blocks | `argmin(x0, flip)` | 3 | L4-36, LC4-36 | 283 of 292 | 30 of 30 | 253 of 262 |
| first | short | library only | `argmax(x0, flip)` | 3 | L4-36 | 204 of 213 | 27 of 30 | 177 of 183 |
| other | short | library only | `argmin(x0, matcher(identity, x1))` | 5 | L5-36 | 395 of 411 | 29 of 30 | 366 of 381 |
| paint | longer | library only, smaller blocks | `x0` | 1 | L4-36, LC4-36 | 139 of 430 | 30 of 30 | 109 of 400 |
| underpaint | longer | library only, smaller blocks | `x0` | 1 | L4-36, LC4-36 | 138 of 430 | 30 of 30 | 108 of 400 |

### Nine examples against 36

Primary cohort (N = 80):

L4-9 against L4-36:

| L4-9 \ L4-36 | right | wrong | none | total |
|---|---|---|---|---|
| right | 7 | 0 | 0 | 7 |
| wrong | 0 | 3 | 9 | 12 |
| none | 0 | 0 | 61 | 61 |
| total | 7 | 3 | 70 | 80 |

LC4-9 against LC4-36:

| LC4-9 \ LC4-36 | right | wrong | none | total |
|---|---|---|---|---|
| right | 10 | 0 | 0 | 10 |
| wrong | 0 | 3 | 9 | 12 |
| none | 0 | 0 | 58 | 58 |
| total | 10 | 3 | 67 | 80 |

Operations whose nine-example first fit was wrong:

- `bordering` L4-9: `flip(square(x1))`; L4-36: none
- `dedupe` L4-9: `x0`; L4-36: none
- `extract` L4-9: `first(x0)`; L4-36: wrong `argmin(x0, flip)`
- `hline` L4-9: `equality(T, size(x0))`; L4-36: none
- `hmatching` L4-9: `portrait(totuple(x0))`; L4-36: none
- `index` L4-9: `valmin(x0, maximum)`; L4-36: none
- `mostcolor` L4-9: `minimum(palette(x0))`; L4-36: none
- `paint` L4-9: `x0`; L4-36: wrong `x0`
- `sizefilter` L4-9: `connect(UNITY, LEFT)`; L4-36: none
- `square` L4-9: `contained(size(x0), DOWN)`; L4-36: none
- `underpaint` L4-9: `x0`; L4-36: wrong `x0`
- `vmatching` L4-9: `flip(square(x0))`; L4-36: none
- `bordering` LC4-9: `flip(square(x1))`; LC4-36: none
- `dedupe` LC4-9: `x0`; LC4-36: none
- `extract` LC4-9: `first(x0)`; LC4-36: wrong `argmin(x0, flip)`
- `hline` LC4-9: `equality(T, size(x0))`; LC4-36: none
- `hmatching` LC4-9: `portrait(totuple(x0))`; LC4-36: none
- `index` LC4-9: `valmin(x0, maximum)`; LC4-36: none
- `mostcolor` LC4-9: `minimum(palette(x0))`; LC4-36: none
- `paint` LC4-9: `x0`; LC4-36: wrong `x0`
- `sizefilter` LC4-9: `EMPTY_SET`; LC4-36: none
- `square` LC4-9: `contained(size(x0), DOWN)`; LC4-36: none
- `underpaint` LC4-9: `x0`; LC4-36: wrong `x0`
- `vmatching` LC4-9: `flip(square(x0))`; LC4-36: none

All done records outside development (N = 108):

L4-9 against L4-36:

| L4-9 \ L4-36 | right | wrong | none | total |
|---|---|---|---|---|
| right | 13 | 0 | 0 | 13 |
| wrong | 0 | 4 | 13 | 17 |
| none | 0 | 0 | 78 | 78 |
| total | 13 | 4 | 91 | 108 |

LC4-9 against LC4-36:

| LC4-9 \ LC4-36 | right | wrong | none | total |
|---|---|---|---|---|
| right | 29 | 0 | 0 | 29 |
| wrong | 1 | 3 | 11 | 15 |
| none | 0 | 0 | 64 | 64 |
| total | 30 | 3 | 75 | 108 |

Operations whose nine-example first fit was wrong:

- `adjacent` L4-9: `contained(TWO_BY_ZERO, x0)`; L4-36: none
- `bordering` L4-9: `flip(square(x1))`; L4-36: none
- `dedupe` L4-9: `x0`; L4-36: none
- `extract` L4-9: `first(x0)`; L4-36: wrong `argmin(x0, flip)`
- `first` L4-9: `argmax(x0, flip)`; L4-36: wrong `argmax(x0, flip)`
- `greater` L4-9: `even(divide(NINE, x0))`; L4-36: none
- `hline` L4-9: `equality(T, size(x0))`; L4-36: none
- `hmatching` L4-9: `portrait(totuple(x0))`; L4-36: none
- `index` L4-9: `valmin(x0, maximum)`; L4-36: none
- `intersection` L4-9: `sfilter(x0, flip)`; L4-36: none
- `mostcolor` L4-9: `minimum(palette(x0))`; L4-36: none
- `paint` L4-9: `x0`; L4-36: wrong `x0`
- `portrait` L4-9: `contained(SEVEN, first(x0))`; L4-36: none
- `sizefilter` L4-9: `connect(UNITY, LEFT)`; L4-36: none
- `square` L4-9: `contained(size(x0), DOWN)`; L4-36: none
- `underpaint` L4-9: `x0`; L4-36: wrong `x0`
- `vmatching` L4-9: `flip(square(x0))`; L4-36: none
- `adjacent` LC4-9: `contained(TWO_BY_ZERO, x0)`; LC4-36: none
- `bordering` LC4-9: `flip(square(x1))`; LC4-36: none
- `dedupe` LC4-9: `x0`; LC4-36: none
- `extract` LC4-9: `first(x0)`; LC4-36: wrong `argmin(x0, flip)`
- `hline` LC4-9: `equality(T, size(x0))`; LC4-36: none
- `hmatching` LC4-9: `portrait(totuple(x0))`; LC4-36: none
- `index` LC4-9: `valmin(x0, maximum)`; LC4-36: none
- `intersection` LC4-9: `EMPTY_SET`; LC4-36: right `c_intersection(x0, x1)`
- `mostcolor` LC4-9: `minimum(palette(x0))`; LC4-36: none
- `paint` LC4-9: `x0`; LC4-36: wrong `x0`
- `portrait` LC4-9: `contained(SEVEN, first(x0))`; LC4-36: none
- `sizefilter` LC4-9: `EMPTY_SET`; LC4-36: none
- `square` LC4-9: `contained(size(x0), DOWN)`; LC4-36: none
- `underpaint` LC4-9: `x0`; LC4-36: wrong `x0`
- `vmatching` LC4-9: `flip(square(x0))`; LC4-36: none

### Comparison with the earlier study

Total: 145.

| category | count |
|---|---|
| agree: both found none | 107 |
| agree: the same expression | 18 |
| not compared: excluded here | 13 |
| not compared: excluded here (the earlier study found one) | 7 |

- agree: both found none: 107 (names not listed).
- agree: the same expression (18): `argmin`, `asobject`, `color`, `equality`, `extract`, `first`, `hconcat`, `identity`, `leftmost`, `lowermost`, `paint`, `pair`, `product`, `rightmost`, `totuple`, `underpaint`, `uppermost`, `vconcat`.
- not compared: excluded here (13): `crement`, `decrement`, `dneighbors`, `double`, `even`, `halve`, `hfrontier`, `increment`, `invert`, `merge`, `rapply`, `sign`, `vfrontier`.
- not compared: excluded here (the earlier study found one) (7): `ineighbors`, `maximum`, `minimum`, `neighbors`, `positive`, `toivec`, `tojvec`.

