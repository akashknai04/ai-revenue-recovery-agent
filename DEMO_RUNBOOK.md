# AI Revenue Recovery Agent — Live Walkthrough Demo Runbook

This runbook guides a presenter through live, reproducible demonstrations of the five core architectural capabilities of the AI Revenue Recovery Agent. All commands run locally with zero external API keys and zero external network calls.

---

### Demo 1 — Genuine Recoverable Failure (End-to-End Pipeline)
**What this proves:** Demonstrates a degraded payment flowing through all 14 pipeline stages: root-cause diagnosis, stopping rules, EV action selection, safe execution, webhook verification, reconciliation, and append-only ledger recording.
**Command:**
```powershell
python -m pytest tests/test_end_to_end_pipeline.py::test_full_pipeline_single_case_end_to_end -v -s
```
**What to point out in the output:** Highlight the printed 11-step ledger (`Step 01` through `Step 11`), showing the cryptographic SHA-256 hash chaining at each step and `Step 10 | Event: WEBHOOK_SETTLEMENT_VERIFIED | is_verified_recovered: true`.

---

### Demo 2 — Ambiguous Debit Protection & Tripartite Reconciliation
**What this proves:** Proves that indeterminate gateway timeout debits are blocked from immediate recharge to prevent duplicate charges, routed to tripartite reconciliation, and held safely.
**Command:**
```powershell
python -m pytest tests/state_machine/test_truth_engine.py::test_integrity_ambiguity_rule tests/test_reconciliation_and_ledger.py::test_reconciliation_mismatch_2_debit_but_provider_uncertain tests/test_simulator.py::test_ambiguous_debit_immediate_retry_causes_duplicate_charge -v
```
**What to point out in the output:** Highlight `test_integrity_ambiguity_rule PASSED` (verdict `STOP_RECONCILE`), `test_reconciliation_mismatch_2_debit_but_provider_uncertain PASSED` (resolution `HOLD_SETTLEMENT_INQUIRY`), and contrast it with `test_ambiguous_debit_immediate_retry_causes_duplicate_charge` which proves that un-guarded naive retry causes duplicate charges.

---

### Demo 3 — Promise-to-Pay (PTP) Lifecycle & Broken Promise Safeguards
**What this proves:** Exercises the complete customer commitment lifecycle (`pending` → `renegotiated` → `kept`/`broken`), proving that broken promises re-enter stopping rules and contact frequency budgets rather than triggering unauthorized automatic recharges.
**Command:**
```powershell
python -m pytest tests/test_action_catalog_and_stopping.py::test_promise_to_pay_lifecycle tests/test_action_catalog_and_stopping.py::test_broken_promise_reenters_stopping_rules_never_automatic_recharge tests/test_simulator.py::test_promise_to_pay_simulation -v
```
**What to point out in the output:** Highlight `test_broken_promise_reenters_stopping_rules_never_automatic_recharge PASSED`, showing that when a customer defaults on a promise, stopping rules terminate with `CONTACT_BUDGET_EXCEEDED` rather than dispatching a blind debit.

---

### Demo 4 — Rules vs. Agent Decision Divergence on Identical Diagnosis
**What this proves:** Proves that for the exact same diagnosed failure case, the AGENT arm diverges from the static RULES arm due to contextual Expected Value (EV) ranking and statutory guardrail thresholds.
**Command:**
```powershell
python -m pytest tests/test_four_arms.py::test_rules_vs_agent_decision_divergence_for_same_diagnosis -v
```
**What to point out in the output:** Highlight that both arms diagnose `INVALID_PAYMENT_INSTRUMENT` on high-value `case_0016` (₹87,410.03); the RULES arm selects static `PAYMENT_LINK`, whereas the AGENT arm triggers Guardrail 5 (`HIGH_VALUE_MANDATORY_HUMAN_REVIEW`), overriding routing to `HUMAN_REVIEW` to protect against major financial exposure.

---

### Demo 5 — Four-Arm Financial Benchmark & Honest Failure Surfacing
**What this proves:** Executes the full 100-case comparative evaluation across CONTROL, NAIVE, RULES, and AGENT arms, proving true incremental lift (+₹566,870.04 / +35.20%) and honest surfacing of safety invariant failures.
**Command:**
```powershell
python -m evaluation.runner --config config/experiment_configs/default_config.json --seed 2002
```
**What to point out in the output:** Highlight the side-by-side comparative table: AGENT achieves `+35.20%` lift (Net ₹564,576.54) with `0` duplicate debits; NAIVE produces `9` duplicate charges and is marked `FAILED`; and the overall run status honestly reports `FAILED` per Rule 7 because NAIVE breached regulatory safety invariants.
