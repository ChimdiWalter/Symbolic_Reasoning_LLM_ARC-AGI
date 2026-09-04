# Protocol v1.1 constructive pilot: postmortem (immutable record)

This document records a completed, prospectively frozen null result. It does
not modify, replace, or reinterpret any v1.1 artifact. Every v1.1 file named
below remains immutable, including the rejected-target records.

## 1. Identifiers

| Artifact | Value |
|---|---|
| Protocol v1.1 manifest | `66780880697d5557a8c79aa100c30cd4a653dd2d62ddc13559d90eb5ac78acd3` |
| Block-A commit | `0269ef8` |
| Block-B implementation commit | `6ca5a43` |
| Block-B generation-manifest commit | `8cb3071` |
| Block-B generation manifest | `36b6989ab77f96a0e68bafe36fd008aa8e51d3388b4b9861ba76c1ccebf03960` |
| Block-B result commit | `71151d9` |
| Ledger tip after Block B | `c191e7c3e55db7c91175015b9137d0ecc3cc712caf5580e21384d38e5986e0b2` |

## 2. Observed result

Scheduled slots 60/60 completed. Target attempts 1,500. Admitted 0.
Infrastructure failures 0. Independent audit verdict PASS.

Primary rejections: `target_schema_failed` 1,159, `execution_undefined` 263,
`base_search_solved` 78.

No target was replaced. No structural-family shortfall was backfilled. No
admission criterion was weakened. No decoder or model was trained.

## 3. What the null does and does not show

The v1.1 constructive AST language was NOT shown to be empty. What was shown
is that a specific combination made the admission requirements contradictory:

    constructive AST language
    + type-keyed induced-slot learner
    + fixed single-block meta-search

Mechanism. The sole registered learner for `Map[FeatureValue,Colour]` obtains
one flat (partition, predicate, feature) context through
`meta_ast.bound_values`, whose dictionary is keyed by TYPE, so the last
occurrence in the AST wins. The fixed base search enumerates exactly the
corresponding product of 4 partitions x 5 predicates x 10 key features = 200
schemas. Therefore whenever the learner could fit a target well enough to
satisfy requirement 5, the same behaviour was available to the base search,
violating requirement 4 or the bounded witness-separation requirement.

In short, under v1.1: **R5 success implies R4 failure of admission.**

Supporting measurement taken before the freeze, on disposable fixtures: of
266 family-(2,) targets that passed requirement 5, 262 were solved by the
base search and 4 were witness-equivalent to a fitted baseline schema; 0
were admissible.

Second, independent issue. Schemas with no Select stage provide no predicate
to `bound_values`, so `induce_feature_colour_map` returns None immediately.
Families (0,0) and (0,0,0) were therefore unfittable despite having
well-defined execution semantics. Measured 0/240 requirement-5 survivors for
each; families with at least one Select survived at 6 to 9 percent and then
met the same requirement-4 wall.

This is a substrate-learning limitation. It is NOT evidence that multi-block
semantic programs are unnecessary, NOT evidence that constructive AST
generation is impossible, and NOT a positive invention result.

## 4. Why occurrence-scoped fitting is the minimal next hypothesis

The distinction the null exposes is between semantic expressivity and
parameter identifiability. The evaluator already executes multi-block,
repeated-selection programs. The old fitter cannot identify several same-type
maps inside such a program without collapsing them into one flat context.

The minimal general change is therefore to fit induced values by typed
LEXICAL OCCURRENCE rather than by type alone, while giving the fixed base
search and the target path equal fitting power. The intended symmetry break
is "same fitting power, different schema reach", never "weak baseline
learner, privileged target learner".

## 5. Why this is a new protocol version, not a repair inside v1.1

The v1.1 behaviour followed its declared semantics exactly. Nothing here is
a bug fix. Protocol v2 is a human-designed methodological revision motivated
by a prospectively frozen null, and it is frozen separately, with its own
manifest, seeds, exclusion set, and audit. The two experiments are never
merged, and v1.1 is never regenerated under changed code.

Permissible wording: "The first frozen pilot exposed a learner-search
symmetry that made its admission set empty. We retained that null result and
introduced a second, separately frozen protocol in which repeated
induced-slot occurrences are fitted by lexical occurrence rather than
collapsed by type."

Impermissible: "v1.1 almost worked", or describing v2 as fixing a bug.

## 6. Immutable v1.1 artifacts

`outputs/tti/constructive_protocol_manifest.json` and its hash file;
`outputs/tti/constructive_pilot_generation_manifest.json` and its hash file;
`outputs/tti/constructive_pilot_slots/` (all 60 slot records, including every
rejected attempt); `outputs/tti/constructive_pilot_audit.json`;
`outputs/tti/constructive_pilot_summary.json`; the v1.1 entries in
`outputs/tti/ledger.jsonl`; and
`docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL.md` with its errata file.

## 7. Claims

Earned: a deterministic, hash-pinned, independently audited generation and
admission pipeline exists; and the frozen v1.1 target space is empirically
demonstrated to be empty, with the mechanism identified.

Unearned: any constructive corpus, any model result, constructive semantic
recovery, candidate semantic self-extension, semantic invention, family
transfer, or ARC improvement. The earlier 5/12 result remains known-operator
reconstruction.
