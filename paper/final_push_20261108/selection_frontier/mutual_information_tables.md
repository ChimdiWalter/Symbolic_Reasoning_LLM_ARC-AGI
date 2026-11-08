# Tables for mutual_information.md (post hoc, development data)

Every number in this file is post hoc, development data: source-half records of the learned search-order test, never a held record. Written by mutual_information.py.

## Which family succeeds, from the features (post hoc, development data)

Holes with an exact multi-pair program: 633 of 1275, from 306 units. Label: the operation family of the exact program that costs the fewest operations (the same family as the first exact program in the hand-set order in 100.0% of holes). Entropy of the family base rate: 2.93 bits (as uncertain as a fair choice among 7.6 families). The pair analysis offers 6.1 families per hole on average.

| predictor (out of fold, the study's 5 folds by task) | cross-entropy, bits | mutual information, at least, bits | share of the entropy | names the exact family | names a family that succeeds | its first block succeeds |
|---|---:|---:|---:|---:|---:|---:|
| base rate alone | 3.01 | 0.00 | 0.0% | 29.9% | 40.8% |  |
| base rate, available families only | 1.36 | 1.57 | 53.7% | 59.1% | 86.1% |  |
| linear classifier on availability | 0.24 | 2.70 | 92.0% | 95.1% | 95.6% |  |
| forest on availability | 0.25 | 2.68 | 91.4% | 94.6% | 95.4% |  |
| linear classifier on description | 0.18 | 2.75 | 93.9% | 97.5% | 97.8% |  |
| forest on description | 0.15 | 2.78 | 94.9% | 98.4% | 98.7% |  |
| linear classifier on availability + description | 0.13 | 2.80 | 95.6% | 98.1% | 98.4% |  |
| forest on availability + description | 0.14 | 2.79 | 95.2% | 98.4% | 98.7% |  |
| linear classifier on availability + description + per-family block summaries | 0.11 | 2.82 | 96.3% | 98.1% | 98.3% |  |
| forest on availability + description + per-family block summaries | 0.12 | 2.81 | 95.7% | 98.7% | 98.9% |  |
| first block of the hand-set order |  |  |  | 48.5% | 48.5% | 36.2% |
| first block of the frequency table |  |  |  | 67.1% | 95.9% | 95.6% |
| first block of the linear model |  |  |  | 66.2% | 94.0% | 81.5% |
| first block of the guide |  |  |  | 73.6% | 97.8% | 93.8% |
| first block of the family-only table (post hoc) |  |  |  | 62.2% | 91.3% | 65.4% |

Task-clustered bootstrap, 95% intervals (post hoc, development data; best feature model: linear classifier on availability + description + per-family block summaries):

- bits removed by keeping only the offered families (base rate, no learning): 1.658 bits, 1.530 to 1.796
- bits removed by the best feature model, against the base rate alone: 2.905 bits, 2.786 to 3.025
- bits the best feature model removes beyond the base rate over offered families: 1.247 bits, 1.144 to 1.347
- exact family named by the best feature model: 0.981 (share of holes), 0.967 to 0.992
- exact family named by the base rate over offered families: 0.591 (share of holes), 0.530 to 0.649
- exact-family gain of the best feature model over that base rate: 0.390 (share of holes), 0.331 to 0.451
- succeeding-family gain of the best feature model over that base rate: 0.122 (share of holes), 0.082 to 0.166
- exact-family gain of the guide's first block over the table's first block: 0.065 (share of holes), 0.024 to 0.106
- succeeding-family gain of the guide's first block over the table's first block: 0.019 (share of holes), 0.003 to 0.038

## By benchmark (post hoc, development data; pooled out-of-fold predictions scored on each benchmark's holes)

| benchmark | holes | entropy of its own family base rate, bits | base rate over offered families: cross-entropy, exact family | best feature model: cross-entropy, exact family | table's first block: exact family | guide's first block: exact family |
|---|---:|---:|---:|---:|---:|---:|
| ConceptARC | 33 | 2.66 | 1.18, 66.7% | 0.88, 84.8% | 63.6% | 81.8% |
| Mini-ARC | 13 | 2.57 | 2.04, 61.5% | 2.01, 46.2% | 38.5% | 76.9% |
| 1D-ARC | 587 | 2.73 | 1.35, 58.6% | 0.02, 100.0% | 68.0% | 73.1% |

## Folds that hold out whole task families (post hoc, development data; 97 task families)

| predictor | cross-entropy, bits | mutual information, at least, bits | names the exact family | names a family that succeeds |
|---|---:|---:|---:|---:|
| base rate alone | 4.47 | 0.00 | 11.1% | 11.1% |
| base rate, available families only | 2.31 | 0.62 | 46.0% | 62.1% |
| linear classifier on availability | 1.75 | 1.19 | 71.4% | 83.4% |
| linear classifier on everything | 1.17 | 1.76 | 78.0% | 93.0% |
| forest on everything | 1.11 | 1.83 | 75.0% | 82.8% |

## Does the guide order like the table? (post hoc, development data; 633 holes with an exact program)

- same first block: 8.5%; same first family: 78.0%
- rank correlation of the two scores inside a hole: median 0.56, mean 0.50

## Single features (post hoc, development data)

243 components with more than one value, each cut into at most 4 bins; mutual information with the family label, minus its mean under 300 label shuffles. 95th percentile of the largest shuffled value over all components: 0.031 bits; components above it: 208.

| feature | mutual information, bits | shuffle mean, bits | corrected, bits | share of the entropy |
|---|---:|---:|---:|---:|
| edits common to every pair (log), view single cells, background colour 0 | 1.392 | 0.043 | 1.349 | 46.0% |
| covering two-part rules (log), view single cells, background colour 0 | 1.313 | 0.043 | 1.270 | 43.3% |
| covering selection rules (log), view single cells, background colour 0 | 1.238 | 0.043 | 1.195 | 40.8% |
| covering two-part rules (log), view one-colour objects, 8-connected, background colour 0 | 1.217 | 0.042 | 1.175 | 40.1% |
| covering two-part rules (log), view one-colour objects, 4-connected, background colour 0 | 1.217 | 0.042 | 1.175 | 40.1% |
| covering two-part rules (log), view any-colour objects, 4-connected, background colour 0 | 1.206 | 0.042 | 1.163 | 39.7% |
| covering two-part rules (log), view any-colour objects, 8-connected, background colour 0 | 1.205 | 0.042 | 1.163 | 39.7% |
| edits common to every pair (log), view any-colour objects, 4-connected, background colour 0 | 1.170 | 0.043 | 1.127 | 38.4% |
| covering two-part rules (log), view one object per colour, background colour 0 | 1.166 | 0.044 | 1.123 | 38.3% |
| edits common to every pair (log), view one-colour objects, 4-connected, background colour 0 | 1.158 | 0.043 | 1.115 | 38.0% |

## Block success, from the study's cross-fitted models (post hoc, development data)

62109 blocks of the trace; 19.0% give an exact multi-pair program; entropy 0.702 bits per block.

| scores | cross-entropy, bits per block |
|---|---:|
| one success rate for every block | 0.706 |
| family-only table (post hoc) | 0.364 |
| frequency table (kind, view, edit type) | 0.291 |
| linear model | 0.153 |
| guide | 0.125 |

- frequency table over one success rate: 0.415 bits per block, 0.349 to 0.477 (task-clustered 95%)
- linear model over the frequency table: 0.138 bits per block, 0.094 to 0.180 (task-clustered 95%)
- guide over the frequency table: 0.166 bits per block, 0.100 to 0.220 (task-clustered 95%)
- guide over the linear model: 0.028 bits per block, -0.022 to 0.069 (task-clustered 95%)
- family-only table over one success rate: 0.343 bits per block, 0.287 to 0.395 (task-clustered 95%)

| where the block sits | blocks | exact programs | share of the guide's gain over the table | share of the linear model's gain |
|---|---:|---:|---:|---:|
| no exact program in the hole | 21402 | 0 | 15.2% | 18.8% |
| before the table's first exact program | 640 | 6 | 0.1% | 0.4% |
| the table's first exact program or later | 40067 | 11814 | 84.7% | 80.9% |

## Early successes: the first exact program each order reaches within 500 operations (post hoc, development data)

| order | holes with an early success | top family | top 3 families | top 5 programs | broadest selection (every object or every horizontal line) |
|---|---:|---:|---:|---:|---:|
| hand-set order | 470 | 34.7% | 72.6% | 55.5% | 85.3% |
| frequency table | 618 | 30.6% | 72.2% | 52.1% | 84.6% |
| linear model | 619 | 30.5% | 72.2% | 34.2% | 84.2% |
| guide | 617 | 35.5% | 63.5% | 17.2% | 81.8% |

Families of the frequency table's early successes: shift 189, connect 148, gravitate 109, recolor 68, recolor by colour table 60, hollow 15, whole-output form (crop, token, count) 14, delete 8, move 3, extend 2, two-rule paint 2.

Its five most frequent early programs: 105 holes; 78 holes; 58 holes; 44 holes; 37 holes.

| units fitted at 500 operations | fits | top family | top 3 families | top 5 families | distinct programs | top 8 programs | broadest selection |
|---|---:|---:|---:|---:|---:|---:|---:|
| hand-set order | 213 | 31.9% | 64.8% | 81.7% | 76 | 59.2% | 83.1% |
| frequency table | 285 | 28.4% | 59.3% | 77.9% | 96 | 53.0% | 83.2% |
| linear model | 286 | 28.3% | 59.1% | 77.6% | 95 | 55.2% | 82.5% |
| guide | 284 | 28.5% | 59.5% | 77.5% | 93 | 55.6% | 83.1% |

| family | holes where the pair analysis offers it | holes where it gives an exact program |
|---|---:|---:|
| shift | 328 | 258 |
| connect | 161 | 149 |
| extend | 183 | 148 |
| move | 185 | 109 |
| gravitate | 109 | 109 |
| recolor | 670 | 91 |
| fill box | 86 | 73 |
| recolor by colour table | 280 | 60 |
| delete | 621 | 43 |
| hollow | 21 | 15 |
| whole-output form (crop, token, count) | 1275 | 14 |
| two-rule paint | 1035 | 11 |
| duplicate | 191 | 9 |
| recolor by attribute | 30 | 2 |
| fill holes | 3 | 0 |
| outline | 153 | 0 |
| outer box | 133 | 0 |
| scale | 8 | 0 |
| mirror copy | 174 | 0 |

## Holes reaching an exact program, by budget (post hoc, development data; of 633)

| order | 125 | 500 | 2,000 | 20,000 | median operations to the first exact program | within 10 operations |
|---|---:|---:|---:|---:|---:|---:|
| hand-set order | 401 | 470 | 575 | 633 | 3 | 57.2% |
| frequency table | 618 | 618 | 620 | 632 | 3 | 97.0% |
| linear model | 619 | 619 | 619 | 624 | 3 | 97.5% |
| guide | 617 | 617 | 619 | 630 | 3 | 97.3% |
| family-only table (post hoc) | 543 | 576 | 622 | 630 | 3 | 82.6% |
| best possible order | 624 | 624 | 625 | 633 | 3 | 98.6% |

## Units fitted (post hoc, development data; of 425)

"unknown": units whose answer needs a retry never computed in development.

| order | 125 | 500 | 2,000 | 20,000 |
|---|---:|---:|---:|---:|
| hand-set order | 181 | 213 | 264 | 298 |
| frequency table | 279 (+6 unknown) | 285 | 283 (+4 unknown) | 296 (+1 unknown) |
| linear model | 284 (+2 unknown) | 286 | 285 (+1 unknown) | 289 |
| guide | 284 | 284 | 286 | 295 |
| family-only table (post hoc) | 237 (+10 unknown) | 254 (+8 unknown) | 286 (+1 unknown) | 295 |
| any order, upper bound (programs known to fit; + units whose reachable programs were never retried) | 289 (+8) | 289 (+8) | 290 (+8) | 298 (+8) |

Units with any exact multi-pair program: 306; with a program known to fit: 298.

Check: this script's simulation reproduces every development arm in dev/curves.json it covers, unit by unit (fit, fitting program, operations, capped holes): frequency@500 0 mismatches, guide@125 0 mismatches, guide@2000 0 mismatches, guide@20000 0 mismatches, guide@500 0 mismatches, hand@125 0 mismatches, hand@2000 0 mismatches, hand@20000 0 mismatches, hand@500 0 mismatches, linear@500 0 mismatches.

Compute: 47.1 CPU-seconds.

