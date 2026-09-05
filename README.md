# AI Revenue Recovery Agent

> **Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery**  
> 📌 **Quick Links:** [Start here for the 2-minute version](./EXECUTIVE_SUMMARY.md) | [Run it yourself in 5 minutes](./DEMO_RUNBOOK.md) | [5-Minute Pitch Script](./PITCH_VIDEO_SCRIPT.md)  
> 💰 **Headline Result:** **Verified incremental recovery: ₹566,870.04 (+35.20% lift over control)**, 100% reproducible and ledger-traceable with zero safety violations.

---

## System Architecture

![End-to-End System Architecture](./docs/architecture.png)

A bounded, auditable, and reproducible agent designed to detect degraded payments, diagnose failure root causes, select the safest economically-valuable recovery action (including tracking promise-to-pay commitments), execute solely via deterministic policy and hard safety guardrails, verify actual financial outcomes via authoritative webhooks, and report measured **incremental recovery** across a 4-arm benchmark with a full immutable audit ledger.

---


## 1. Project Objective & Scope

### Primary Objective
Recover lost revenue from payment degradations (e.g. gateway timeouts, temporary bank decline, drop-offs) while strictly adhering to regulatory consumer protection guidelines (TRAI DND, RBI Fair Practices Code, DPDP Act 2023), preventing duplicate debits, and computing true incremental recovery over control.

### Success Metrics
- **True Incremental Recovery Lift**: $(Agent\ Outcome - Control\ Outcome)$ — never attributing natural recoveries to AI.
- **Safety Invariant Violations**: Exactly 0 duplicate charges, 0 off-hours contacts, 0 contacts to opted-out/terminated cases.
- **Audit Completeness**: 100% of state transitions and recovery decisions traceable to the hash-linked append-only ledger.
- **Economic Value (Net Recovery)**: Gross recovery minus execution costs and risk penalties.

### Scope Boundaries

#### In Scope:
- Payment degradation detection and recovery (UPI, cards, net banking).
- Structured, JSON-only LLM root-cause diagnosis.
- Promise-to-pay (PTP) tracking (`pending`, `kept`, `broken`, `renegotiated`).
- Deterministic stopping rules and RBI/TRAI safety guardrails.
- Sandboxed payment gateway and webhook verification.
- Tripartite reconciliation (Customer debit vs. Gateway status vs. Merchant order state).
- 4-arm comparative evaluation (`CONTROL`, `NAIVE`, `RULES`, `AGENT`).
- Automated markdown/HTML batch reporting with hash-traceable metrics.
- (Phase 12 Stretch) Hinglish voice call recovery adapter with identical schemas and safety constraints.

#### Explicitly Out of Scope (Future Extensions):
- **Real Financial Movement**: Sandbox/simulated provider only.
- **Multi-Provider Routing**: Single sandbox adapter interface in MVP.
- **Portfolio-Level Allocation**: Case-by-case bounded evaluation only.
- **Checkout Abandonment Recovery**: Payment-stage degradation only.
- **Subscription/Dunning Recovery**: Recurring billing dunning is not in scope.
- **B2B Receivables / Invoice Chasing**: Consumer payment degradation only.
- **Complex Uplift Models (T-Learner, X-Learner, Doubly-Robust)**: Simple stratified lift with confidence intervals used for EV.
- **Direct LLM Tool/Execution Access**: LLM outputs structured diagnosis JSON only; execution is strictly deterministic.

---

## 2. Non-Negotiable Invariants

1. **No LLM Direct Action**: Diagnosis $\to$ Deterministic Policy $\to$ Guardrails $\to$ Execution.
2. **Ground Truth Isolation**: The agent's `core/` package never imports `simulator/ground_truth.py`.
3. **Append-Only Ledger**: History is immutable; past ledger events cannot be modified or deleted.
4. **Authoritative Verification**: Execution completion does NOT equal recovery; recovery requires verified webhooks.
5. **Fail-Closed Safety**: Any safety invariant violation aborts and marks the entire run `FAILED`.

---

## 3. Diagnosis Layer Architecture & Benchmark Disclosure

> **Important Disclosure on Diagnosis Layer & 4-Arm Lift Drivers:**  
> The current diagnosis layer in `llm/client.py` uses a deterministic local expert heuristic as a reliable, hermetic stand-in for the LLM interface (zero external model API calls). Because the root-cause diagnosis output is identical between the RULES arm and the AGENT arm for every case, the incremental lift difference observed between RULES (+21.22%) and AGENT (+35.20%) reflects downstream decisioning components (Expected Value ranking with Wilson score CI, contextual action selection, and statutory guardrail escalations like HUMAN_REVIEW for high-value orders), not differences in diagnosis quality.

---

## 4. LLM Integration Status

The LLM diagnosis layer (`llm/client.py`) is currently running a deterministic local diagnosis generator by design rather than making live external API calls to remote model providers (such as Anthropic, OpenAI, or a local Ollama instance).

### Rationale & Architectural Design Constraints
1. **Rule 6 Compliance (Hermetic Local Execution)**: All unit tests, integration tests, and benchmark evaluations must execute entirely locally with zero external API keys and zero outbound network dependencies.
2. **Bit-for-Bit Reproducibility**: Financial recovery benchmarking and counterfactual lift calculations require strictly deterministic, reproducible runs across repeated evaluations.
3. **Cost, Rate Limit, and Latency Elimination**: Production test suites and simulation batches execute in milliseconds without external quota limits, network latency spikes, or API billing costs.

### Swapping to a Live Model Provider
If a developer wishes to connect a live model provider (e.g. `claude-3-haiku` or `gpt-4o-mini`), **only `_generate_raw_diagnosis` in `llm/client.py` needs to change for production execution**. 

All surrounding components are completely decoupled:
- **Schema Validation (`DiagnosisOutput`)**: Strictly validates JSON taxonomy compliance, confidence bounds $[0.0, 1.0]$, and non-empty evidence arrays.
- **Replay & Disk Caching**: The JSONL cache (`llm/diagnoses.jsonl`) automatically caches diagnoses to avoid redundant inference calls and costs.
- **Retry & Graceful Fallback**: Malformed JSON responses are retried up to 3 times before gracefully falling back to deterministic rule-based diagnosis (`core/rule_classifier.py`).
- **Audit Logging**: The append-only, SHA-256 hash-chained ledger (`core/ledger.py`) records all diagnosis events with complete cryptographic integrity.
- **Downstream Decision Engine**: The entire recovery policy, EV ranking, stopping rules, and regulatory safety guardrails (`core/decision_engine.py`, `core/ev.py`, `core/guardrails.py`, `core/stopping_rules.py`, `evaluation/runner.py`) consume the resulting `DiagnosisOutput` identically without depending on model provider details.

### Test Suite Impact & Known Blockers
While the production decisioning pipeline is completely decoupled, **the test suite is not completely decoupled from deterministic output**:
- **Production Decisioning Pipeline**: Requires **zero changes** across `core/decision_engine.py`, `core/ev.py`, `core/guardrails.py`, `core/stopping_rules.py`, `core/ledger.py`, and `evaluation/runner.py`, because the pipeline solely consumes the validated `DiagnosisOutput` entity.
- **Known Test Suite Blocker (`tests/test_four_arms.py`)**: `test_rules_vs_agent_decision_divergence_for_same_diagnosis` currently hardcodes `assert rule_diag.root_cause == llm_diag.root_cause` and `assert llm_diag.root_cause == "INVALID_PAYMENT_INSTRUMENT"` for case `case_0016` to verify that decision divergence stems solely from downstream EV ranking and guardrails. Because a live, non-deterministic model could return different taxonomy categories or confidence scores, this test would need to change—ideally by pinning this specific test case's LLM diagnosis via the existing `llm/diagnoses.jsonl` cache mechanism rather than dispatching a live call—before a live model can be safely plugged in without risking CI flakiness or test failure.

---

## 5. Evaluation Reports & Audit Trail
- **Automated Markdown Batch Report:** [`report/batch_report.md`](./report/batch_report.md)
- **Standalone HTML Report:** [`report/batch_report.html`](./report/batch_report.html)

---

## 6. Build & Review History

For the complete project lifecycle record, refer to [`PROGRESS.md`](./PROGRESS.md). It contains the full phase-by-phase build log (Phases 1–12), detailed logs of all 7 rounds of post-review verifications and corrections, and the final verified state summary across all financial, safety, and architectural metrics.





