# Native baseline assets: provenance (2026-10-07)

The sealed v23 run (185 of 1,000 = 183 in-run + 2 arbitration recoveries)
ran the unified harness with five chain flags and two files in the object
layer's directory (`outputs/unified_harness_v23/object/` in the main
project, read only):

| asset | sha256 | role |
|---|---|---|
| library.json | cdacd018...3ce03 | promoted fragment library, byte-identical v20 to v23 |
| learned_verbs.json | b1f07ba5...b585c | learned-verb registry (one verb, verb_mirror_h), loaded by the engine at start from its output directory; identical in the v22 and v23 run directories |

Learned generators are NOT part of the sealed configuration: they load only
when ARC_LEARNED_GENERATORS_DIR is set, nothing in the code sets it (the
comment in generative.py saying the engine sets it is inaccurate), no
recorded chain command sets it, and the v23 object directory holds no
learned_generators.json.

Correction: before this record, `cora_pilot/native.py` installed only
library.json, so the 6 native rows of the real ARC pilot development dry run
(ce123e8) ran without learned_verbs.json. Those rows were engineering
checks; the 0 of 60 CORA result does not depend on them. Both assets are now
installed and hash-checked.
