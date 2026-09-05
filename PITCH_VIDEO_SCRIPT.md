# AI Revenue Recovery Agent — 5-Minute Pitch Video Script
**Track 03:** AI Revenue Recovery | **Razorpay AI Buildathon 2026**  
**Target Duration:** Exactly 5:00 minutes (300 seconds)

---

## 0:00–0:30 — The Problem (30s)
*(Visual: Camera on presenter, transitioning to a split screen showing degraded payment flows and angry customer tweets about double-debits.)*

"Every merchant loses substantial revenue at the payment gateway checkout stage. But recovering that degraded revenue is notoriously treacherous. If an acquirer switch times out, is the payment truly failed, or was the customer's account debited while the merchant order stayed pending? Most automated systems take a naive approach: they immediately fire a blind retry. That causes disastrous duplicate debits, customer chargebacks, and severe regulatory violations under RBI and TRAI guidelines. True revenue recovery cannot just blindly retry—it requires strict state truth, deterministic stopping rules, and mathematical proof of incremental recovery."

---

## 0:30–1:15 — What Was Built (45s)
*(Visual: Full screen pan across `docs/architecture.png`, highlighting the 14-stage pipeline flow.)*

"To solve this, we built a bounded, fully auditable AI Revenue Recovery Agent designed specifically around non-negotiable consumer safety and financial truth. As you can see in our architecture diagram, our system enforces a strict 14-stage pipeline. Incoming payment degradations first pass through the Transaction Truth Engine and Payment Integrity Engine to guarantee that pending transactions are never mistaken for failures. Stopping rules run before any action is even considered. Root cause diagnosis happens via structured JSON schemas, feeds into contextual Expected Value ranking with Wilson score confidence intervals, and must clear hard statutory guardrails under RBI Fair Practices, TRAI DND, and DPDP Act 2023. Crucially, the LLM never moves money directly—every action routes deterministically to AUTO, HUMAN review, or BLOCK, executed through an idempotent sandbox adapter and anchored into an immutable SHA-256 hash-chained ledger."

---

## 1:15–2:30 — Live Demo: The Pipeline Running (75s)
*(Visual: Screen recording of terminal running `python -m pytest tests/test_end_to_end_pipeline.py -v -s` and `python -m pytest tests/test_four_arms.py::test_rules_vs_agent_decision_divergence_for_same_diagnosis -v`.)*

"Let's see this in action live. First, we run our end-to-end pipeline test on a live degraded case. Notice the terminal output: the agent ingests the degradation, normalizes the state to FAILED, passes integrity checks, and diagnoses an abandoned 3DS authentication challenge. The Expected Value engine ranks a payment link as optimal, verifies that contact hours comply with TRAI DND regulations, dispatches the action with an idempotency key, and only marks the revenue recovered after receiving an authoritative settlement webhook. Every single one of these 11 state transitions is cryptographically chained into our append-only ledger with a SHA-256 hash anchor.

Now, let's look at why AI decisioning outperforms static rules. On case 16—a high-value transaction of ₹87,410—both our rules baseline and our agent diagnose an invalid payment instrument. But while static rule-based recovery blindly issues a payment link, our AI agent evaluates portfolio risk and triggers Guardrail 5, automatically escalating the case to mandatory human review to protect against major financial exposure. That dynamic nuance is what drives real recovery without taking existential risk."

---

## 2:30–3:45 — The Numbers, and Why They're Honest (75s)
*(Visual: Screen displaying `report/batch_report.md` side-by-side matrix and console output of `evaluation.runner`.)*

"Here are our headline numbers from a standardized 100-case benchmark run on Batch B. Total at-risk payment volume was ₹1,610,520. In the passive Control arm, self-healing transactions naturally recovered ₹428,676. Unlike dishonest AI claims that boast of gross recovery, we report strictly incremental lift over control. Our Agent arm recovered ₹995,546 gross, achieving an incremental recovery lift of ₹566,870.04—a 35.20% net improvement—for an operating cost of just ₹2,293.50, yielding ₹564,576.54 in net recovered value.

Now, look at the safety status row: the overall multi-arm benchmark run is marked FAILED. Why? Because under Non-Negotiable Rule 7, we refuse to hide failure. Our NAIVE blind-retry arm triggered 9 duplicate debit violations when it blindly retried ambiguous timeouts. That failure is surfaced explicitly in bright red as evidence that our safety invariants actually work. Meanwhile, our AGENT arm achieved a perfect 0 duplicate debits and 100% compliance across all statutory rules."

---

## 3:45–4:30 — What's Out of Scope and Why (45s)
*(Visual: Presenter on camera with summary slide highlighting scope boundaries.)*

"We want to be completely transparent about what we chose to keep out of scope. First, we do not perform live bank money movement; all dispatch is confined to an authoritative idempotent sandbox adapter. Second, dynamic multi-acquirer treasury routing and portfolio optimization were deferred to keep the single-case state machine provably sound. Third, pre-checkout cart abandonment and recurring SaaS subscription dunning were excluded because this system is laser-focused on consumer checkout degradations. And finally, rather than using opaque black-box machine learning uplift models, we used empirical stratified lift with Wilson score confidence intervals to ensure every financial decision is explainable and verifiable."

---

## 4:30–5:00 — Close (30s)
*(Visual: Presenter on camera, displaying GitHub repo URL `https://github.com/akashknai04/ai-revenue-recovery-agent.git`.)*

"Every claim, number, and test in this project is 100% reproducible today. You can clone the public repository, run `pytest`, and re-execute the evaluation benchmark in under 5 minutes without needing an external API key. If given more time, our next milestone would be deploying an on-premise local Ollama inference sidecar and integrating real-time NPCI UPI settlement webhooks. Thank you, and we welcome your review on Track 03."
