# Learning What to Change
## A research proposal for evidence-backed revision, from ARC to science

Prepared for Chimdi Walter Ndubuisi · University of Missouri · October 17, 2026

**The question.** When a model fails, should we search longer, change the representation, construct a new operation, or collect better evidence? We want to learn that decision—and test whether the reasoning procedure remains useful when the domain changes. Toni Kazic’s research discussion frames this as transfer of reasoning, not merely transfer of predictions. [L01]

## Why the question remains important

Powerful systems already propose hypotheses, write code and use external checks. EMET and Quine address scientific workflows; modern coding and formalization systems revise executable artifacts. The research opportunity is not “the first AI that reasons,” but a controlled account of which revisions help, which harm, and what evidence justifies them. [R16, R17, R22]

The closest comparator is Model Discovery Agent. Its model-expansion and experimental-design approach makes the broad loop prior art. A new CORA contribution must therefore be specific, independently tested, and stronger than an architecture diagram. [R28]

## What exists today

CORA provides an object-based ARC reasoner, failure instrumentation, and a bounded extension mechanism. In a supplied real 60-task object-branch audit,6 correct predictions passed checks. CORA-FHR produced a synthetic development witness in which a new composed operation was installed, independently reconstructed across 3 omitted-example folds, and used for a correct query prediction. Removing the operation removed the certified gain. [L02, L04]

**The limiting result is central:** failure-blind construction matched the witness. The latest audit reports no real 60 FHR extension certificate and a failed mixed pilot. The separately reproduced NVARC Qwen3-4B public score of 27.64 is not a CORA-FHR result. This is a working research prototype, not demonstrated general reasoning or a biological product. [L02, L04]

## The research bet

Build a small, independently checked revision kernel around interchangeable proposal sources. Every change has typed inputs/outputs, an applicability condition, executable semantics, provenance, a cost, a test boundary and a rollback. The proposal agent cannot edit the evaluator.

Compare an authentic-trace policy against an equally equipped failure-blind portfolio, matched extra search, and masked-trace controls. Counterbalance shortcuts such as object size. Measure correct gains, damaged answers, abstention, and total compute—not only training fit.

**The decisive partial result:** a useful revision policy that survives those controls and improves a second semantic domain when the policy is frozen. Reusing a Python interface is not enough.

[PAGEBREAK]

# From a benchmark to a scientific decision

## The first biological bridge

Start with a collaborator-approved molecular-measurement question, motivated by the displacement-versus-dispersion discussion. The actual definitions, data, units, replicate structure and independent validation must be agreed with Pierce and Toni. A toy example can exercise the interface but cannot count as biological evidence. [L01]

Candidate decisions could include changing a location model, a spread model, a mixture representation, a context adjustment, or requesting another measurement. The shared contribution would be how the system decides among revisions. It would not transfer an ARC ring operation into a molecule.

## A compact validation ladder

**1. Execution.** Does a proposed revision actually operate in the original solver, with correct applicability, no information leakage and reliable restoration?

**2. Causal software benefit.** Does authentic failure information improve decisions beyond matched controls, after all proposal and verification costs are counted?

**3. Transfer.** Does a frozen source-domain policy improve a different target domain relative to fresh and domain-only alternatives?

**4. Biological utility.** Does the chosen revision or experiment improve an independently validated scientific endpoint with appropriate controls and replicates?

## The startup research-lab opportunity

The first product hypothesis is a revision-assurance workflow for scientific modeling—not another universal world model. It would help a researcher answer, “Is this correction justified, what might it break, and what observation would change our conclusion?”

Its commercial value must be measured through avoided harmful revisions, better experiment prioritization, reproducible review time, or lower total cost for equivalent evidence. Existing platforms may already deliver parts of this; a durable advantage requires validation data, partnerships, integration and independent reproducibility, not simply more agents.

## The ask at the summit

Help design and independently stress-test the smallest benchmark that distinguishes useful diagnosis-guided revision from better ordinary synthesis. Seek one scientific collaborator with a costly, well-defined validation problem and appropriate data—not endorsement of an already-solved general-intelligence claim.

## A 45-second introduction

“Frontier models can already generate answers and code. My question is how a reasoning system decides what to change when an answer fails. CORA gives me a small executable setting for testing that decision. It has a verified synthetic construction example, but the failure-blind control matched it, so the key causal claim is still open. I want to test a policy that chooses among representation, program and evidence revisions, then freeze that policy and evaluate it on a specific biological measurement problem. The goal is a justified next model or next experiment, with evidence another researcher can challenge.”

## Evidence and status

This brief describes proposed work and user-supplied results, not new experiments performed for the brief. No biological transfer, commercial validation, or score improvement is claimed. The comprehensive dossier supplies primary references and the full local evidence ledger.

**Key references:** Toni conversation[L01]; latest CORA audit[L04]; EMET[R16]; Quine[R17]; formal verification example[R22]; Model Discovery Agent[R28]. See the accompanying `source_registry.json` and `Research_Dossier.pdf` for source details.
