# Razorpay AI Buildathon 2026 — Track 03: Submission Kit

> **Project Name:** AI Revenue Recovery Agent  
> **Track:** Track 03 — AI Revenue Recovery  
> **Live Dashboard:** [https://akashknai04.github.io/revenue-recovery-dashboard/](https://akashknai04.github.io/revenue-recovery-dashboard/)  
> **Source Repository:** [https://github.com/akashknai04/ai-revenue-recovery-agent](https://github.com/akashknai04/ai-revenue-recovery-agent)  
> **Presentation Runbook:** [`DEMO_RUNBOOK.md`](./DEMO_RUNBOOK.md)  
> **Pitch Video Script:** [`PITCH_VIDEO_SCRIPT.md`](./PITCH_VIDEO_SCRIPT.md)  

---

## 1. Fast Copy-Paste Submission Fields

### Project Title
`AI Revenue Recovery Agent — Safe, Auditable Payment Recovery with Measured Incremental Lift`

### One-Line Tagline
`An autonomous, auditable payment recovery agent that diagnoses transaction degradations, enforces RBI/TRAI guardrails to eliminate duplicate charges, and mathematically proves incremental recovery over control via an immutable SHA-256 ledger.`

### Short Description (Elevator Pitch)
When payments degrade at the checkout stage, most automated systems execute blind retries that trigger disastrous duplicate debits, customer chargebacks, and regulatory violations. We built a bounded, auditable AI Revenue Recovery Agent that diagnoses degraded transactions via structured schemas, computes contextual Expected Value (EV) with Wilson score confidence intervals, enforces non-negotiable statutory consumer protection guardrails (RBI, TRAI, DPDP), and records all state transitions into an append-only SHA-256 hash-chained ledger. Across a 100-case evaluation benchmark (Batch B, seed 2002), the agent achieved **+₹566,870.04 incremental recovery lift (+35.20% over control)** with **zero duplicate debits**, while proving that blind naive retries caused 9 duplicate charge violations.

---

## 2. Headline Benchmark Results (Batch B, Seed 2002, 100 Cases)

| Arm | Strategy | Gross Recovery | Natural Recovery | Incremental Lift | Lift (%) | Duplicate Debits | Status |
| :--- | :--- | ---:| ---:| ---:| ---:| :---: | :---: |
| **CONTROL** | No Intervention (Baseline) | ₹428,676.08 | ₹428,676.08 | ₹0.00 | +0.00% | 0 | **PASSED** |
| **NAIVE** | Blind Immediate Retry | ₹260,040.21 | ₹428,676.08 | -₹168,635.87 | -10.47% | **9 (BREACH)** | **FAILED** |
| **RULES** | Deterministic Heuristic | ₹770,418.91 | ₹428,676.08 | ₹341,742.83 | +21.22% | 0 | **PASSED** |
| **AGENT** | Full AI Decision Pipeline | **₹995,546.12** | ₹428,676.08 | **₹566,870.04** | **+35.20%** | **0 (SAFE)** | **PASSED** |

- **Total At-Risk Volume:** ₹1,610,520.43
- **Operational Execution Cost:** ₹2,293.50
- **Net Incremental Gain:** **₹564,576.54**
- **Safety Invariant Honesty (Rule 7):** The NAIVE arm's 9 duplicate debits trigger `INVARIANT_FAIL_DUPLICATE_CHARGES`. Rather than sanitizing this result, the multi-arm run is honestly reported as `FAILED` as mathematical proof that the safety invariants genuinely detect and halt hazardous behaviors.

---

## 3. Key Architectural Innovations

1. **Transaction Truth & Payment Integrity Engines:**
   - Strict finite state machine prohibiting illegal state jumps (e.g. direct `FAILED -> SUCCESS` is rejected).
   - Guarantee that `PENDING` is never treated as `FAILED` anywhere in the codebase.
   - Tripartite reconciliation matching Customer bank debit vs. Gateway status vs. Merchant order fulfillment.

2. **Pre-Action Stopping Rules & Promise-to-Pay (PTP) Tracker:**
   - 6 hard stopping conditions evaluated before any recovery action is considered.
   - Complete PTP lifecycle (`pending` $\to$ `renegotiated` $\to$ `kept`/`broken`). Broken commitments re-enter contact frequency budgets instead of triggering unauthorized re-debits.

3. **Statutory Guardrail Hierarchy (Consumer Protection First):**
   - **RBI Fair Practices Code:** Maximum 2 contact attempts per case; mandatory Human Review for high-value orders (>₹50,000).
   - **TRAI DND Regulations:** Strict contact window between 09:00 and 21:00 customer local time.
   - **DPDP Act 2023:** Immediate permanent cessation of outreach upon customer opt-out.
   - Guardrails evaluate *after* EV ranking, guaranteeing that consumer compliance strictly overrides financial incentives.

4. **Authoritative Webhook Verification & Cryptographic Ledger:**
   - Execution completion $\neq$ recovery success. Recovery is only recorded upon cryptographic webhook settlement confirmation.
   - 100% of pipeline events (761 events for Batch B) anchored into an append-only SHA-256 hash chain with complete lifecycle reconstruction.

---

## 4. How Judges Can Verify the Project in 60 Seconds

Clone the repository and run the automated verification suite:

```bash
# Clone
git clone https://github.com/akashknai04/ai-revenue-recovery-agent.git
cd ai-revenue-recovery-agent

# Install dependencies (pytest, anyio)
pip install -r requirements.txt

# One-shot verification (runs unit tests, e2e trace, 4-arm benchmark, and report check)
python scripts/verify_submission.py
```

*Expected output: 68 passing tests, an 11-step cryptographic trace for case 1, side-by-side benchmark table with +₹566,870.04 lift, and green verification status.*

---

## 5. Repository Documentation Directory

- [`README.md`](./README.md) — Comprehensive technical architecture, non-negotiable invariants, and setup guide.
- [`EXECUTIVE_SUMMARY.md`](./EXECUTIVE_SUMMARY.md) — Concise 2-minute decision-maker summary.
- [`DEMO_RUNBOOK.md`](./DEMO_RUNBOOK.md) — Step-by-step commands for 5 live demo scenarios.
- [`PITCH_VIDEO_SCRIPT.md`](./PITCH_VIDEO_SCRIPT.md) — Complete 5:00 minute presentation script with timestamps and visual directions.
- [`PROGRESS.md`](./PROGRESS.md) — Complete 12-phase build history and 7 rounds of post-review audit logs.
- [`report/batch_report.md`](./report/batch_report.md) — Full automated evaluation report with ledger audit anchors.
- [`report/batch_report.html`](./report/batch_report.html) — Standalone styled HTML report.
