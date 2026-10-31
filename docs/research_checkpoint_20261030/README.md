# CORA independent research checkpoint — October 30, 2026

The independent CORA work investigated executable grammar learning, failure-conditioned revision, object representations and neural assistance. It has **not demonstrated a new real-ARC accuracy gain or universality**. This report records working mechanisms, negative findings and the next measurable question.

## Implemented and measured

| Study | Actual result | Interpretation |
| --- | --- | --- |
| Automatic executable abstraction | Search-solved programs were anti-unified into a parameterized, compiled and versioned macro. Twelve training cases supported one grid rule with 288 expansion checks and a declared 232-bit net description-length saving. | Automatic macro discovery works on the development-synthetic training construction. It does not establish new semantic expressivity. |
| Earlier bounded synthetic reuse (R11) | Learned-library arm 6/12, guided fixed grammar 2/12, guided expanded grammar 4/12. | Development evidence with an authored call-prior confound; no independent ARC confirmation. |
| Source-development library transfer (R12) | Pure arms 1/64; strongest recorded baseline and safe portfolio 3/64; zero selected learned calls. | No measured gain from the acquired macro on these exposed source tasks. |
| Framing and object-edit composition (R14–15) | R14 completed 48 contexts with zero fits; R15 completed 16 contexts with zero fits and empty transfer selections. Query stages stayed skipped. | The declared finite languages failed to fit the retained demonstrations. This does not prove that a larger language or bounded search cannot solve the tasks. |
| Call-prior and failure-routing audit (R16) | All eleven arms scored 0/8 in both raw and matched-prefix modes; all 176 selection lists were empty. | Changing the call prior changed ordering but produced no fitting held program. Every search stopped at the validation cap. |

R16's authentic, blind and shuffled failure policies selected the same view. The causal contribution of authentic failure information is therefore non-identifiable in that experiment. Zero invalid selected query programs is vacuous because no program was selected.

A metadata-only posthoc audit found the intended generator-order AST structures in the finite pool at ranks 47–260, beyond the 24-validation budget. Those candidates were not executed during that diagnosis; their correctness was not newly verified. This points to candidate construction/ranking as a useful next target, rather than establishing an absent primitive.

## Reproducible synthetic audit

The [standalone R16 package](../../research/cora_synthetic_audit_20261030/README.md) contains the exact interpreter, abstraction learner, task generator and study sources, source hashes, an aggregate reference result and an opt-in reproduction runner. It uses the Python standard library and generated synthetic grids. Its verification command checks the export without rerunning the closed study.

The original R16 controlled run charged 7.349 CPU seconds and 15.089 active wall seconds, including declared preparation and reserves; queue time was reported separately. Its full resource envelope was 30 CPU seconds / 60 active wall seconds. Per-arm CPU cutoffs can make a reproduction hardware-sensitive; compare semantic and budget receipts as well as scores.

## Subsequent construction pilot (R17)

A new typed top-down constructor propagated demonstration shape, palette and ink constraints into partial program holes. It used the same 685-program expanded language and shared constraints for all four priorities: strong static, learned, shuffled and neutral. The six new development-synthetic composition tasks used queries distinct in canvas and foreground structure from their retained demonstrations.

All four arms constructed correct programs on **6/6** queries under the raw per-arm ceilings, with no COPY fallback or invalid query program. Under the joint cost-prefix comparison, static scored **5/6**, learned **4/6**, and shuffled and neutral **6/6**. **The learned priority added no gain.** All arms correctly reused an earlier automatically learned macro on four tasks; the macro was fixed before this experiment.

Independent review checked 1,079 constructor paths, 81 selected-program parity replays, all scores and the freeze chain. Whole cost was 10.193 CPU / 17.696 active wall seconds within 30/60 limits, with a clean exit and file-descriptor cleanup. Search coverage remained bounded: 19 searches reached a CPU cap and five a validation cap, even though correct selected programs were found.

This supports executable construction on these synthetic cases. It does not isolate the constructor against flat search, establish a learned-priority benefit, or show ARC accuracy or universality. Raw retained-input hash artifacts were not saved; the query-distinctness audit uses the frozen generator and actual saved-query geometry/topology. The [aggregate result](R17_RESULT.json) preserves that limitation. The branch is closed without retuning or an automatic source-data extension.

## Competition and local validation

The public 27.64 result belongs to the external NVARC neural-baseline reproduction. It is not a newly established CORA grammar-learning gain. The native CORA submission record and this independent research must be described separately.

The reviewed A baseline remains protected. Frozen C4 adds recovery and publication safeguards while retaining A's neural inference profile. The grammar-learning experiments described here have not been integrated into that notebook.

The local two-GPU recovery run is still in progress at this checkpoint and retains its original 12-hour deadline. It uses a smaller fp16/rank32/context profile on two 2080 Ti GPUs. Completion, memory, adapter-reset and fallback accounting are being audited. Evaluation answers remain closed. A post-freeze score of permitted source-development held demonstrations is prepared separately; it is not an independent evaluation score.

One private offline four-L4 C4 rehearsal is authorized after the local finalization review, no earlier than October 31 Central. It has not launched at this checkpoint. Actual full-context four-L4 compatibility, total runtime, tail latency and model eligibility remain open. Official entry promotion and publication decisions are separate from a technical rehearsal.

## Next controlled question

Can demonstrations constrain partial executable programs strongly enough to reach useful candidates within the same bounded budget? The R17 pilot above implements that constructor and comparison. Its neutral and shuffled controls matched or beat the learned priority. The next research question is source-development transfer of useful construction constraints under a separately frozen protocol, after competition readiness; no such transfer result is claimed here.

The supported contribution is an auditable implementation and a specific diagnosis of construction and transfer failures. Novel autonomous capability growth, real-ARC improvement, expressivity expansion and universality remain research goals.
