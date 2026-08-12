# Bounded Repairability

H3 is treated as a bounded repairability hypothesis, not as full path semantics. The implemented corruption process modifies a finite DSL program by dropping a step, replacing a parameter, or replacing a step. Repair enumerates nearby candidates in the same finite DSL and selects the lowest training-error candidate with a signature-distance tie break.

The active metric is recovery-after-corruption. In `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md`, `path_repair_minus_compression_selector` has recovery-after-corruption delta `+0.968`, but no task accuracy gain. The supported claim is therefore narrow: repair machinery recovers from the injected corruption diagnostic in this finite DSL setting.
