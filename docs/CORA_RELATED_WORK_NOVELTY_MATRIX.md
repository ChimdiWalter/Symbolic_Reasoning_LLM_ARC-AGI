# Related-work novelty matrix (claim-by-claim; UNVERIFIED cells marked)

*Purpose: no precedence claim ships until every relevant cell is verified against the
primary source. Cells: Y = yes, N = no, P = partial, U = UNKNOWN (verify before use).
Entries below are initial impressions from survey notes — treat every Y/N/P as
PROVISIONAL until a citation is attached. The novelty CORA claims is the CONJUNCTION of
columns, never any single column.*

Columns:
1 learns parameters · 2 learns programs · 3 learns macros/library · 4 invents
predicates · 5 modifies agent code · 6 modifies semantic language · 7 modifies
representation · 8 failure-triggered · 9 test-time · 10 verifier-controlled ·
11 causal ablation · 12 held-out transfer · 13 cross-domain transfer · 14 persistent
archive · 15 immutable verifier

| System | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DreamCoder | P | Y | Y | N | N | P | U | N | N | P | U | P | P | Y | U |
| LILO | P | Y | Y | N | N | P | U | N | N | P | U | U | U | Y | U |
| POPPI (LFF predicate invention) | N | Y | N | Y | N | P | N | Y | N | P | U | U | U | U | U |
| ADVENT | U | Y | U | Y | N | P | U | Y | U | U | U | U | U | Y | U |
| SOAR (ARC evolutionary PS) | P | Y | U | N | N | U | U | P | P | P | U | U | N | Y | U |
| TRM | Y | N | N | N | N | N | N | N | Y | N | U | U | N | N | N |
| NVARC | Y | P | N | N | N | N | N | N | Y | N | U | U | N | N | N |
| AlphaEvolve | P | Y | U | N | P | U | U | N | N | Y | U | U | P | Y | P |
| AlphaGeometry (2) | Y | Y | U | P | N | U | U | N | P | Y | U | U | N | U | P |
| DGM (Darwin Gödel Machine) | P | Y | U | N | Y | U | U | P | N | N | U | U | N | Y | N |
| Interwhen / verifier-guided TT reasoning | P | N | N | N | N | N | N | P | Y | Y | U | U | U | N | P |
| V-JEPA / latent world models | Y | N | N | N | N | N | P | N | P | N | U | U | U | N | N |
| Genie (world simulation) | Y | N | N | N | N | N | P | N | N | N | U | U | U | N | N |
| Ndea guided program synthesis | Y | Y | Y | U | N | U | U | U | U | P | U | U | U | U | U |
| AI Scientist (v2) | P | P | N | N | P | N | N | P | N | P | U | U | P | P | N |
| LLM-guided evolutionary PS @26% ARC2 | Y | Y | U | N | N | U | U | P | Y | P | U | U | N | U | U |
| Test-time training (MindsAI-style) | Y | N | N | N | N | N | N | N | Y | N | U | U | N | N | N |
| **CORA-PARENT (target)** | P | Y | Y | Y | N | **Y** | **Y (planned)** | **Y** | **Y (TTI)** | **Y** | **Y** | **Y** | **planned** | **Y** | **Y** |

## Verification protocol

1. Before ANY external claim: for each row cited in the paper, replace every U with a
   verified Y/N/P + citation (paper, section). A cell that cannot be verified stays U
   and the corresponding comparative sentence is NOT written.
2. Add rows discovered in the comprehensive sweep (2025–2026 ARC Prize papers, library
   learning, ILP predicate invention, self-modifying agents, neurosymbolic TTT).
3. The claimable conjunction (current form): failure-frontier-triggered + typed
   semantic production synthesis + non-LLM + frozen prior language +
   certificate-carrying invention + task-local language adaptation with reset +
   exact causal ablation + held-out transfer + efficient test-time deployment +
   domain-independent meta-extension interface. Each conjunct must map to a column
   pattern no verified row matches in full.
4. Known pressure points (write defensively): POPPI/ADVENT occupy "failure-triggered
   predicate invention"; DGM occupies "self-modification + archive"; an LLM-guided
   evolutionary system already reports 26% on ARC-AGI-2 Semi-Private (so the non-LLM
   qualifier is integral to any score claim); DreamCoder/LILO occupy library growth.
