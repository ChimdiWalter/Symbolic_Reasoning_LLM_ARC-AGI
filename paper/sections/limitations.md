# Limitations

The strongest empirical evidence is synthetic. Synthetic tasks are useful because they expose latent programs and controlled strata, but they do not establish broad external validity.

The direct input-output baseline is a nearest-example proxy, not a trained transformer. H2 evidence is conditional and concentrated in constructed ambiguity/composition probes, with one zero-gain family. H3 is a bounded recovery-after-corruption diagnostic, not a general theory of equivalent reasoning paths. H4 is not exact algorithmic information dynamics or causal discovery, and the multi-seed alignment check does not isolate the compression selector as uniquely more causal. H5 remains weak because the full stack improves latent/recovery diagnostics but not task accuracy over the strongest partial stacks.

The new neural-guided modules are implemented only as bounded smoke evidence in this paper version. The Grid-JEPA loss is stable on the smoke mix, and the updated smoke rankers now recover synthetic held-out behavior strongly, but ARC transfer is still negative: the plain ranker reaches synthetic held-out top1/top2 `0.833/1.000`, the Grid-JEPA-conditioned ranker reaches `1.000/1.000`, and both remain at ARC exact/pass@2 `0.000/0.000` on the current 6-task labeled evaluation slice. The REMA-inspired manifold diagnostic is correspondingly limited by having no solved tasks on the current ARC refinement slice.

ARC evaluation is small and diagnostic. The current exact solve rate is zero across all tested models, including the bounded neural-guided refinement slice, so ARC supports a limitation claim rather than a capability claim. Local ARC-style provenance is also ambiguous: the files are readable and labeled on training/evaluation splits, but their names do not by themselves justify a clean ARC-AGI-2 provenance claim.

The exact mathematical claims are bounded. Exact DSL minimality holds only over the enumerated candidate set and declared coding scheme; exact small-category checks hold only over supplied finite domains and morphisms; exact topology claims hold only for audited operators and bounded support/component/hole invariants.
