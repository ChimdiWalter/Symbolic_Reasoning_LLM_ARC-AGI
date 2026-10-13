# CORA-NVG literature and novelty review (2026-10-12)

**Provenance.** A delegated review compiled this on 2026-10-12. It opened every source with WebFetch (abstract page or better); sources it could not open are marked UNVERIFIED or listed as blocked in section 5.

**Verified independently on 2026-10-12** (before this record was committed):
- **KAAR.** The full-text Limitations section says the authors prompted LLMs "with raw 2D matrices of each ARC problem to select one or three relevant abstractions" and that "the results are unsatisfactory". It adds that accurate abstraction inference "often depends on validation through viable solutions". KAAR's own method iterates over abstractions from simple to complex and "proceeds to the next abstraction when the solver backbone fails to solve" (Appendix F).
- **ABPR.** Title, authors and dates are confirmed (v1 2026-03-20, v4 2026-05-23), as are 56.67% Pass@2 with Gemini-3-Flash and the absence of any shuffled-trace control in the abstract. The 34.0 and 49.2 baselines were not rechecked.

The review follows; the delegated text is unchanged below this line.

---


Sources opened with WebFetch on 2026-10-12. NVG = CORA-NVG; B–F = its ablation arms. UNVERIFIED = I could not open it.

## 1. Comparison

| Citation (opened URL) | Already shows | Shared | May differ | Evidence needed | Not novel |
|---|---|---|---|---|---|
| **A** ARC Prize, *ARC-AGI Guide* (web), https://arcprize.org/guide/1 | Program/DSL search, ensembles, test-time fine-tuning; Chollet: deep learning should suggest where search goes next | Neural model steers symbolic search | Steering comes from a typed failure diagnosis | D > C at matched compute | DL-guided ARC search |
| **B** Grand et al., *LILO*, ICLR 2024, https://proceedings.iclr.cc/paper_files/paper/2024/hash/819cebb05f993840e8a52d7564c5c282-Abstract-Conference.html | LLM synthesis + Stitch compression + AutoDoc; no ARC or failure traces in abstract | Neural proposals inside a symbolic loop | Nothing learned; ranks fixed views | n/a | LLM + symbolic synthesizer |
| **C** Franzen, Disselhoff, Hartmann, *Product of Experts*, ICML 2025, https://proceedings.mlr.press/v267/franzen25a.html | 16 augmented "perspectives"; product scoring 71.6% vs 66.6% for averaging; TTT; transductive, no symbolic verifier | Views matter | Fixed symmetry views, not a segmentation choice made after failure | Adaptive choice beats fixed multi-view at equal calls | Multiple views help ARC |
| **D** Pourcel, Colas, Oudeyer, *SOAR*, ICML 2025, https://proceedings.mlr.press/v267/pourcel25a.html | LLM sample-and-refine shown actual vs expected outputs; fine-tunes on its own traces; 52% | Authentic failures reused | Frozen model; writes no code; selects views | Gain without weight updates; D > E | Learning from failed ARC programs |
| **E** Hu et al., *ARC Is a Vision Problem!*, https://arxiv.org/abs/2511.14761 (CVPR 2026 page returned 403, so venue UNVERIFIED) | 18M ViT trained from scratch on a canvas, with TTT: ARC-1 54.5% (60.4% ensemble); no pretrained encoder | Grids treated as images | Vision used only as a frozen prior | Frozen features beat grid descriptors | Vision models for ARC |
| **F** Singhal & Shroff, *ConceptSearch*, AAAI 2025, https://ojs.aaai.org/index.php/AAAI/article/view/35300 (full paper /34259) | LLM program evolution over ARC-DSL; the LLM-hypothesis scorer solves 29/50 vs 25/50 for Hamming distance or CNN, and the CNN needs fewer iterations | Learned scorer steers search | Scores programs, not views | Solves trace to the choice of view | Learned scoring for ARC search |
| **G** Ellis et al., *DreamCoder*, PLDI 2021, https://arxiv.org/abs/2006.08381; Balog et al., *DeepCoder*, ICLR 2017, https://arxiv.org/abs/1611.01989 | A trained neural policy ranks DSL choices; DeepCoder gives about 10× speedup | Neural prior over search | Frozen; conditioned on the failure | D > C | Neural-guided synthesis |
| Wang et al., *Hypothesis Search*, ICLR 2024, https://arxiv.org/abs/2309.05660 | Natural-language hypotheses → Python checked on examples; 3 feedback rounds: ARC-100 24→30% | Abstraction, then feedback, then verification | Hypotheses are rules; the LLM writes the code | Gains with no LLM-written code | Feedback improves LLM ARC programs |
| Greenblatt, Redwood blog 2024, https://blog.redwoodresearch.org/p/getting-50-sota-on-arc-agi-with-gpt | ~8k GPT-4o programs per task; component, shape, diff and image representations; diff-based revision; 50% | Multiple representations | All shown at once; nothing selected | Selection beats all-at-once at equal cost | Multi-representation prompting |
| Xu, Khalil, Sanner, *ARGA*, AAAI 2023, https://ojs.aaai.org/index.php/AAAI/article/view/25527 | Several graph abstractions share one search; a Tabu list suspends abstractions "generating increasingly worse results" | Failure-sensitive control of views | Typed diagnosis plus neural ranking | D > B (Tabu-like) | Pruning failing abstractions |
| Lei, Lipovetzky, Ehinger, *GPAR*, AAAI 2024, https://arxiv.org/abs/2401.07426 | 8 abstractions (4/8-connected, colour, multicolour, lines, pixels, image, max-rectangle), simplest first | Same family of views | Fixed order | D > that order with equal views searched | Fixed-order fallback |
| Lei et al., *KAAR*, https://arxiv.org/html/2505.17482v2 | A failure on training pairs escalates prior levels; fixed abstraction order; LLM choosing abstractions from raw grids was "unsatisfactory"; about +5 points | LLM + abstractions + failure trigger | Selection used the task only; the LLM is the solver | D > C; D > E | LLM choosing abstractions; failure escalation |
| Qiu et al., *ABPR*, https://arxiv.org/abs/2603.20334 | Prolog derivation traces guide LLM refinement; ARC-AGI-2 with Gemini-3-Flash 34.0 → 49.2% (execution feedback) → 56.7% (traces); no shuffled control in the part I read | Structured traces condition the model | Frontier LLMs revise programs | D > E; D > F | Traces beat plain feedback on ARC |
| Gehring et al., *RLEF*, ICML 2025, https://proceedings.mlr.press/v267/gehring25a.html | Feedback from another problem's wrong solution clearly impairs repair | Shuffled control (E) | Trained repair model | E must score below D | Mismatched-feedback control |
| Trinh et al., *AlphaGeometry*, Nature 2024, https://deepmind.google/blog/alphageometry-an-olympiad-level-ai-system-for-geometry/ | When deduction runs out, the LM adds one construct and the engine resumes | Neural proposal after a symbolic stall | Not shown to be conditioned on a typed trace | D > F; D > E | Proposer invoked when search stalls |
| Clarke et al., *CEGAR*, CAV 2000, https://nicolas.markey.fr/cnrs/biblio/cav2000-CGJLV (abstract UNVERIFIED) | A spurious counterexample drives abstraction refinement | A failure changes the abstraction, checked symbolically | The transition is predicted by a learned model | Predictions are precise against the probe and beat random or heuristic ones | Failure-driven abstraction refinement |

**Also checked:**
- Olausson et al. (ICLR 2024): repair gains are modest once cost is counted.
- REx (NeurIPS 2024): a bandit chooses which program to refine.
- Piriyakulkij et al. (NeurIPS 2024): designs experiments to test hypotheses.
- Pendharkar (arXiv 2606.09026): grid descriptors read mid-run predict ARC solver success (AUC 0.885).
- Xu et al. (TMLR 2024): object representations help GPT-4.
- Others: CodeIt, test-time training, Self-Debugging, Reflexion, ExeDec, LEVER, LLM-Modulo, Popper, SATzilla, ARC Prize reports.

## 2. Closest prior work

- **KAAR** pairs an LLM with GPAR abstractions, escalating after failure in a fixed order. It reports that LLMs choosing abstractions from the task alone gave unsatisfactory results, so arm C has already been tried, with a negative result.
- **ABPR** shows symbolic traces beat plain execution feedback on ARC-AGI-2, but for frontier-LLM program revision and with no shuffled control.
- **ARGA**'s Tabu list is a non-neural, failure-sensitive view controller that arm B should copy.

AlphaGeometry and RLEF set the general pattern.

## 3. Novelty

**What may be novel:** a controlled test that the *content* of an authentic, typed failure diagnosis improves a *frozen* model's choice of segmentation view for an *unchanged* symbolic ARC engine. It must beat arms C, E, F and B at matched compute, counting the advisor's cost, with the leave-one-out verifier untouched and lost-correct and false-acceptance counts reported. I also found no precedent for counterfactual failure-transition prediction gated by symbolic probes.

This would be an empirical finding, not an architecture. It disappears if D ≈ F, D ≈ B or D ≈ E. The documented failure set is tiny, so statistical power must be shown first. My search was bounded.

**NOT novel:**
- An LLM or neural model guiding a symbolic synthesizer (DeepCoder, DreamCoder, ConceptSearch).
- The model proposes and a verifier certifies (Hypothesis Search, LLM-Modulo, AlphaGeometry).
- Using execution feedback to repair programs (Self-Debugging, SOAR, REx).
- Traces beating plain feedback on ARC (ABPR).
- Multiple representations of ARC grids, and the choice of view mattering (ARGA, GPAR, Greenblatt, Product of Experts).
- Fixed-order or failure-triggered abstraction fallback, and suspending failing abstractions (GPAR, KAAR, ARGA).
- Asking an LLM to choose abstractions from the task alone (KAAR).
- Shuffled-feedback controls and compute-matched evaluation of repair (RLEF, Olausson).
- Failure-driven abstraction refinement (CEGAR, Popper).
- Predicting solver failure from traces (Pendharkar).
- Vision models for ARC, and JEPA priors for ARC search (VARC, ARC-JEPA).

## 4. JEPA

- **I-JEPA** (Assran et al., CVPR 2023; the arXiv comment says ICCV). It predicts the representations of target blocks from a context block. On Hugging Face:
  - `facebook/ijepa_vith14_1k`: card says 0.6B parameters, ImageNet-1K, licence **cc-by-nc-4.0**.
  - `ijepa_vitg16_22k`: 1B parameters, ImageNet-22K, cc-by-nc-4.0.
  - `ijepa_vith16_1k` and `vith14_22k`: listed, not checked.
- **V-JEPA 2** (Assran et al., arXiv 2506.09985, 2025). Pretrained on more than 1M hours of video and images.
  - `facebook/vjepa2-vitl-fpc64-256`: 0.3B parameters, licence "**mit**"; a single image is fed by repeating it as frames.
  - `vjepa2-vitg-fpc64-256`: 1B parameters, **Apache-2.0**.
  - vith, vitg-384 and fine-tuned variants are also listed.
- **On ARC:** no peer-reviewed use. The only one is the **ARC-JEPA v1** GitHub pre-release (September 2026): an ARC-trained, 0.56M-parameter JEPA prior for DSL search. It scored 1/172 outputs on the ARC-AGI-2 public eval and calls itself "not a competitive model". The nearest non-JEPA evidence is Acuaviva et al. (ICML 2026): adapted video-diffusion models were more data-efficient than LLMs on ARC, though they were adapted, not frozen.
- **Assessment: low plausibility.** These encoders learn invariances from photos and video. ARC needs exact colour, counts and adjacency on grids of at most 30×30, and rasterised cells straddle the 14–16 px patches. CORA's views share pixels and differ only in topology. Use this only as an exploratory arm: frozen embeddings of view renderings must predict the solving view better than chance and better than component-count descriptors, or the arm is dropped. The I-JEPA licence is non-commercial.

## 5. URLs opened

https://arcprize.org/guide/1 · https://proceedings.iclr.cc/paper_files/paper/2024/hash/819cebb05f993840e8a52d7564c5c282-Abstract-Conference.html · https://proceedings.mlr.press/v267/franzen25a.html · https://arxiv.org/html/2505.07859v2 · https://proceedings.mlr.press/v267/pourcel25a.html · https://arxiv.org/html/2507.14172 · https://arxiv.org/abs/2511.14761 · https://arxiv.org/html/2511.14761v1 · https://ojs.aaai.org/index.php/AAAI/article/view/35300 · https://ojs.aaai.org/index.php/AAAI/article/view/34259 · https://arxiv.org/abs/2412.07322 · https://arxiv.org/html/2412.07322v1 · https://arxiv.org/abs/2006.08381 · https://pldi21.sigplan.org/details/pldi-2021-papers/55/DreamCoder-Bootstrapping-Inductive-Program-Synthesis-with-Wake-Sleep-Library-Learnin · https://arxiv.org/abs/1611.01989 · https://www.microsoft.com/en-us/research/publication/deepcoder-learning-write-programs/ · https://proceedings.mlr.press/v235/butt24a.html · https://arxiv.org/abs/2309.05660 · https://object.cloud.sdsc.edu/v1/AUTH_da4962d3368042ac8337e2dfdd3e7bf3/ml-papers-txt/ICLR/2024/hypothesis_search_inductive_reasoning_with_language_models__e9fba219.txt · https://blog.redwoodresearch.org/p/getting-50-sota-on-arc-agi-with-gpt · https://arxiv.org/abs/2411.07279 · https://proceedings.mlr.press/v267/akyurek25a.html · https://arxiv.org/abs/2210.09880 · https://ar5iv.labs.arxiv.org/html/2210.09880 · https://ojs.aaai.org/index.php/AAAI/article/view/25527 · https://github.com/khalil-research/ARGA-AAAI23 · https://arxiv.org/abs/2305.18354 · https://arxiv.org/abs/2401.07426 · https://arxiv.org/html/2401.07426 · https://arxiv.org/html/2505.17482v2 · https://arxiv.org/abs/2603.20334 · https://arxiv.org/html/2603.20334v4 · https://arxiv.org/abs/2604.02434 · https://arxiv.org/abs/2606.09026 · https://arxiv.org/abs/2304.05128 · https://iclr.cc/virtual/2024/poster/18880 · https://arxiv.org/abs/2303.11366 · https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html · https://arxiv.org/abs/2307.13883 · https://arxiv.org/abs/2302.08468 · https://arxiv.org/abs/2410.02089 · https://arxiv.org/html/2410.02089 · https://proceedings.mlr.press/v267/gehring25a.html · https://arxiv.org/abs/2306.09896 · https://arxiv.org/abs/2405.17503 · https://arxiv.org/html/2405.17503v3 · https://neurips.cc/virtual/2024/poster/93642 · https://arxiv.org/abs/2402.01817 · https://arxiv.org/abs/2005.02259 · https://jair.org/index.php/jair/article/view/10556 · https://nicolas.markey.fr/cnrs/biblio/cav2000-CGJLV · https://en.wikipedia.org/wiki/Counterexample-guided_abstraction_refinement · https://research.google/pubs/solving-olympiad-geometry-without-human-demonstrations/ · https://deepmind.google/blog/alphageometry-an-olympiad-level-ai-system-for-geometry/ · https://proceedings.neurips.cc/paper_files/paper/2024/hash/5f1b350fc0c2affd56f465faa36be343-Abstract-Conference.html · https://arxiv.org/abs/2110.11536 · https://arxiv.org/abs/2411.17708 · https://arxiv.org/abs/2402.03507 · https://arxiv.org/abs/2412.04604 · https://arxiv.org/html/2601.10904v1 · https://proceedings.mlr.press/v306/acuaviva26a.html · https://arxiv.org/abs/2510.24448 · https://arxiv.org/abs/2301.08243 · https://mlanthology.org/cvpr/2023/assran2023cvpr-selfsupervised · https://arxiv.org/abs/2506.09985 · https://arxiv.org/abs/2603.13265 · https://huggingface.co/facebook/ijepa_vith14_1k · https://huggingface.co/facebook/ijepa_vitg16_22k · https://huggingface.co/facebook/vjepa2-vitl-fpc64-256 · https://huggingface.co/facebook/vjepa2-vitg-fpc64-256 · https://huggingface.co/api/models?author=facebook&search=ijepa · https://huggingface.co/api/models?author=facebook&search=vjepa2 · https://github.com/acco-cyber/ARC-AGI-2/releases/tag/arc-jepa-v1

Blocked or unreadable, not cited as read: the CVF pages (403), ACM DL (403), Springer, Nature, PMC, OpenReview, dblp, and PDF binaries.
