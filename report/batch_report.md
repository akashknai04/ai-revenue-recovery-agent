# AI Revenue Recovery Agent — 4-Arm Batch Evaluation Report
**Experiment Seed:** `2002` | **Config Version:** `1.0.0` | **Batch:** `Batch_B`  
**Evaluation Timestamp:** `2026-09-05T02:23:01.034618+00:00`  

### Safety Invariant Status by Arm (Rule 7 Compliance):
- **AGENT Arm:** <span style="color:green">**PASSED**</span> (0 duplicate charges, 0 off-hours contacts, 100% compliant)
- **RULES Arm:** <span style="color:green">**PASSED**</span> (0 duplicate charges)
- **CONTROL Arm:** <span style="color:green">**PASSED**</span> (0 duplicate charges)
- **NAIVE Arm:** <span style="color:red">**FAILED**</span> (9 duplicate charge violations: `INVARIANT_FAIL_DUPLICATE_CHARGES`)
- **Overall Multi-Arm Run Status:** <span style="color:red">**FAILED**</span> (because NAIVE arm breached safety invariants; per Rule 7, failures are explicitly surfaced, never hidden)

---

## 1. Executive Summary & Headline Financial Impact

> [!IMPORTANT]
> **Honest Incremental Recovery Attribution (Non-Negotiable Rule 5):**
> The system strictly distinguishes between *natural recovery* (failures that self-heal without merchant intervention) and *incremental recovery*. AI recovery performance is **never** reported as gross post-intervention payments. It is reported exclusively as lift over the control baseline.

- **Total At-Risk Volume (Batch B, 100 cases):** ₹1,610,520.43
- **Control Arm Natural Recovery (Zero Intervention):** ₹428,676.08 (26.62%)
- **Agent Gross Recovery:** ₹995,546.12 (61.82%)
- **Headline Measured Incremental Recovery:** **₹566,870.04** (+35.20% lift over control)
- **Total Operational Execution Cost:** ₹2,293.50
- **Net Incremental Money Recovered:** **₹564,576.54**

### Duplicate Charges & Safety Breakdown by Arm:
- **CONTROL:** 0 duplicate charges | Status: PASSED
- **NAIVE:** **9 duplicate charges** | Status: **FAILED** (`INVARIANT_FAIL_DUPLICATE_CHARGES`)
- **RULES:** 0 duplicate charges | Status: PASSED
- **AGENT:** **0 duplicate charges** | Status: **PASSED** (all safety invariants strictly satisfied)

---

## 2. Four-Arm Side-by-Side Comparative Matrix

| Metric | CONTROL (No Action) | NAIVE (Blind Retry) | RULES (Deterministic) | AGENT (Full AI Pipeline) |
| :--- | :--- | :--- | :--- | :--- |
| **Total Cases** | 100 | 100 | 100 | 100 |
| **At-Risk Amount** | ₹1,610,520.43 | ₹1,610,520.43 | ₹1,610,520.43 | ₹1,610,520.43 |
| **Gross Recovery** | ₹428,676.08 | ₹260,040.21 | ₹770,418.91 | ₹995,546.12 |
| **Natural Recovery** | ₹428,676.08 | ₹428,676.08 | ₹428,676.08 | ₹428,676.08 |
| **INCREMENTAL RECOVERY** | **₹0.00** | **-₹168,635.87** | **₹341,742.83** | **₹566,870.04** |
| **Incremental Lift (%)** | 0.00% | -10.47% | +21.22% | **+35.20%** |
| **Recovery Rate (%)** | 26.62% | 16.15% | 47.84% | **61.82%** |
| **Total Cost** | ₹0.00 | ₹300.00 | ₹694.50 | ₹2,293.50 |
| **NET RECOVERED VALUE** | ₹428,676.08 | -₹168,935.87 | ₹341,048.33 | **₹564,576.54** |
| **Duplicate Charges** | 0 | **9 (VIOLATION)** | 0 | **0 (SAFE)** |
| **Ambiguous Reconciled** | 0 | 0 | 12 | **12** |
| **Guardrail Blocks** | 0 | 0 | 7 | **15** |
| **Human Reviews** | 0 | 0 | 12 | **49** |
| **Safety Invariants** | PASSED | **FAILED** | PASSED | **PASSED** |

---

## 3. Root-Cause Diagnosis Accuracy Comparison

Diagnosis accuracy was evaluated against simulator ground truth across all 100 cases:

- **Rule-Based Baseline Accuracy:** **100.00%**
- **LLM Structured Diagnosis Accuracy:** **100.00%**
- **Diagnosis Schema Compliance:** **100.0%** (Strict JSON schema validation with persistent disk caching in `llm/diagnoses.jsonl`).

> [!NOTE]
> **Architectural Disclosure on Diagnosis Layer & 4-Arm Lift Drivers:**
> The current diagnosis layer in `llm/client.py` uses a deterministic local expert heuristic as a reliable, hermetic stand-in for the LLM interface (zero external model API calls). Because the root-cause diagnosis output is identical between the RULES arm and the AGENT arm for every case, the incremental lift difference observed between RULES (+21.22%) and AGENT (+35.20%) is driven entirely by downstream decisioning components (Expected Value ranking with Wilson score CI, contextual action selection, and statutory guardrail escalations like HUMAN_REVIEW for high-value orders), not by diagnosis-quality differences.

---

## 4. Safety & Regulatory Compliance Invariant Audit

All runs are automatically evaluated against the 6 core invariants. If any invariant fails, the entire run is halted and marked `FAILED`.

1. **Duplicate Charge Protection:** PASSED (0 duplicate debits in Agent arm).
2. **Recovered $\le$ At-Risk:** PASSED (Recovered ₹995,546.12 $\le$ At-Risk ₹1,610,520.43).
3. **Contact Limits (RBI Fair Practices Code):** PASSED (Maximum 2 contacts per case respected).
4. **Contact Hours (TRAI DND Regulations):** PASSED (Zero contacts outside 09:00 - 21:00 customer local time).
5. **Opt-out Honoring (DPDP Act / TRAI DND):** PASSED (Zero contacts to opted-out customers).
6. **Valid Terminal State:** PASSED (100% of cases reached verified terminal states).

---

## 5. Cryptographic Ledger Traceability (Audit Sample)

Every single decision, state transition, and financial verification in the metrics above is immutably recorded in the hash-chained append-only ledger:

| Event ID | Case ID | Event Type | Prev Hash Anchor |
| :--- | :--- | :--- | :--- |
| `evt_000000` | `case_0001` | `CONTROL_ARM_EVALUATION` | `0000000000000000...` |
| `evt_000001` | `case_0002` | `CONTROL_ARM_EVALUATION` | `8ea9eba16ab1363a...` |
| `evt_000002` | `case_0003` | `CONTROL_ARM_EVALUATION` | `6059937ffb2429b9...` |
| `evt_000003` | `case_0004` | `CONTROL_ARM_EVALUATION` | `2d290600f3ef700c...` |
| `evt_000004` | `case_0005` | `CONTROL_ARM_EVALUATION` | `30c0c2b1895fb17c...` |
| `evt_000005` | `case_0006` | `CONTROL_ARM_EVALUATION` | `4709a938545f935c...` |
| `evt_000006` | `case_0007` | `CONTROL_ARM_EVALUATION` | `d59b1260007add34...` |
| `evt_000007` | `case_0008` | `CONTROL_ARM_EVALUATION` | `80547607b68ccdfd...` |

*(Total events recorded in ledger for this run: `761`)*

---
*Report automatically generated by AI Revenue Recovery Agent Evaluation Harness.*
