"""True End-to-End Integration Test for AI Revenue Recovery Agent.

Executes the complete pipeline for a single case from generator to batch report:
1. Simulator generates one degraded case
2. Transaction Truth Engine validates initial state
3. Payment Integrity Engine verifies safety invariants
4. Root-cause diagnosis (Rule-based + Structured LLM)
5. Stopping Rules pre-action evaluation
6. Action Catalog eligibility check
7. Expected Value calculation (Stratified lift with Wilson score CI)
8. Safety & Regulatory Guardrail evaluation (TRAI / RBI / DPDP)
9. Decision Engine routing (AUTO / HUMAN / BLOCK)
10. Execution Adapter dispatch (Idempotent sandbox)
11. Authoritative Webhook settlement verification
12. Tripartite Reconciliation
13. Immutable Append-Only Ledger recording & hash-chain verification
14. Batch Report reflection & complete lifecycle reconstruction
"""

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from core.catalog import ACTION_CATALOG, get_action_definition
from core.decision_engine import route_decision
from core.entities import Customer, Payment, Transaction
from core.ev import calculate_action_ev, rank_actions_by_ev
from core.execution_adapter import SandboxPaymentExecutionAdapter
from core.guardrails import SafetyGuardrails
from core.integrity import evaluate_payment_integrity
from core.ledger import AppendOnlyLedger
from core.reconciliation import ReconciliationEngine
from core.rule_classifier import classify_rule_based
from core.state_machine import PaymentState, normalize_state, validate_transition
from core.stopping_rules import evaluate_stopping_rules
from core.verification import (
    AuthoritativeVerificationEngine,
    AuthoritativeWebhookEvent,
    VerificationResult
)
from evaluation.runner import ArmMetrics, EvaluationRunResult
from llm.client import LLMDiagnosisClient
from report.generator import generate_markdown_report
from simulator.world import SimulatedWorld


def test_full_pipeline_single_case_end_to_end(capsys):
    """Executes the full pipeline for a single case start to finish and prints ledger entries."""
    fixed_time = datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc)
    ledger = AppendOnlyLedger()

    # -------------------------------------------------------------
    # 1. Simulator generates one degraded payment case
    # -------------------------------------------------------------
    world = SimulatedWorld(seed=42, num_cases=1, base_time=fixed_time)
    case_id = world.get_case_ids()[0]
    obs = world.get_agent_observation(case_id)
    gt = world.get_ground_truth(case_id)

    cust = Customer(**obs["customer"])
    txn = Transaction(**obs["transaction"])
    pay = Payment(**obs["initial_payment"])
    telem = obs["telemetry"]

    # Record case generation to ledger
    ledger.append_event(
        case_id=case_id,
        event_type="PAYMENT_DEGRADATION_DETECTED",
        payload={
            "amount": txn.amount,
            "failure_code": txn.failure_code,
            "channel": telem["channel"],
            "customer_id": cust.id
        }
    )

    # -------------------------------------------------------------
    # 2. Transaction Truth Engine validates state
    # -------------------------------------------------------------
    norm_status = normalize_state(pay.status)
    assert norm_status in (PaymentState.FAILED, PaymentState.PENDING, PaymentState.UNKNOWN)
    validate_transition("INITIATED", norm_status)

    ledger.append_event(
        case_id=case_id,
        event_type="TRANSACTION_TRUTH_ESTABLISHED",
        payload={"normalized_state": norm_status.value}
    )

    # -------------------------------------------------------------
    # 3. Payment Integrity Engine checks
    # -------------------------------------------------------------
    integrity_verdict = evaluate_payment_integrity(
        payment_status=pay.status,
        debited_customer=pay.debited_customer,
        confirmed_merchant=pay.confirmed_merchant,
        order_paid=(txn.state == "SUCCESS"),
        duplicate_detected=telem.get("duplicate_attempt_detected", False),
        is_ambiguous=telem.get("is_ambiguous_debit", False)
    )
    assert integrity_verdict.is_safe is True
    assert integrity_verdict.verdict_code == "PASS"

    ledger.append_event(
        case_id=case_id,
        event_type="PAYMENT_INTEGRITY_PASSED",
        payload={"verdict": integrity_verdict.verdict_code, "disposition": integrity_verdict.recommended_disposition}
    )

    # -------------------------------------------------------------
    # 4. Root-cause Diagnosis (Rule Baseline + Structured LLM)
    # -------------------------------------------------------------
    rule_diag = classify_rule_based(case_id, txn.failure_code, telem)
    assert rule_diag.root_cause in ["ISSUER_TECHNICAL_DECLINE", "INSUFFICIENT_FUNDS", "AUTHENTICATION_ABANDONED", "INVALID_PAYMENT_INSTRUMENT", "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT"]

    llm_client = LLMDiagnosisClient()
    llm_diag = llm_client.diagnose(
        case_id=case_id,
        failure_code=txn.failure_code,
        amount=txn.amount,
        channel=telem["channel"],
        telemetry=telem
    )
    assert llm_diag.root_cause == rule_diag.root_cause
    assert 0.0 <= llm_diag.confidence <= 1.0
    assert len(llm_diag.evidence) > 0

    ledger.append_event(
        case_id=case_id,
        event_type="DIAGNOSIS_RECORDED",
        payload=llm_diag.to_dict()
    )

    # -------------------------------------------------------------
    # 5. Stopping Rules pre-action evaluation
    # -------------------------------------------------------------
    stopping_result = evaluate_stopping_rules(
        case_status=txn.state,
        customer_opted_out=cust.opted_out,
        order_already_paid=pay.confirmed_merchant,
        payment_status=pay.status,
        is_ambiguous_debit=telem.get("is_ambiguous_debit", False),
        debited_customer=pay.debited_customer,
        retry_count=0,
        contact_count=cust.contact_count
    )
    assert stopping_result.should_stop is False
    assert stopping_result.disposition == "PROCEED"

    ledger.append_event(
        case_id=case_id,
        event_type="STOPPING_RULES_EVALUATED",
        payload={"should_stop": stopping_result.should_stop, "rule_name": stopping_result.rule_name}
    )

    # -------------------------------------------------------------
    # 6. Action Catalog & Eligibility
    # -------------------------------------------------------------
    action_defn = get_action_definition("DELAYED_RETRY" if llm_diag.root_cause == "ISSUER_TECHNICAL_DECLINE" else "PAYMENT_LINK")
    assert action_defn.cost >= 0.0
    assert 0.0 <= action_defn.risk <= 1.0
    assert action_defn.contact_frequency_cap >= 0

    # -------------------------------------------------------------
    # 7. Expected Value Calculation
    # -------------------------------------------------------------
    ev_rankings = rank_actions_by_ev(
        root_cause=llm_diag.root_cause,
        customer_risk_score=cust.risk_score,
        amount=txn.amount
    )
    top_ev_action = ev_rankings[0]
    assert top_ev_action.ev_score is not None

    ledger.append_event(
        case_id=case_id,
        event_type="EV_RANKING_COMPLETED",
        payload={
            "top_action": top_ev_action.action_type,
            "ev_score": top_ev_action.ev_score,
            "incremental_lift": top_ev_action.incremental_recovery_rate,
            "ci_lower": top_ev_action.ci_lower,
            "ci_upper": top_ev_action.ci_upper
        }
    )

    # -------------------------------------------------------------
    # 8. Safety Guardrails Evaluation
    # -------------------------------------------------------------
    guardrail_verdict = SafetyGuardrails.evaluate(
        candidate_action=top_ev_action.action_type,
        amount=txn.amount,
        customer_opted_out=cust.opted_out,
        customer_contact_count=cust.contact_count,
        debited_customer=pay.debited_customer,
        duplicate_attempt_detected=telem.get("duplicate_attempt_detected", False),
        current_time_utc=fixed_time,
        customer_timezone=cust.timezone
    )
    assert guardrail_verdict.final_action is not None

    ledger.append_event(
        case_id=case_id,
        event_type="GUARDRAIL_EVALUATION_COMPLETED",
        payload={
            "allowed": guardrail_verdict.allowed,
            "final_action": guardrail_verdict.final_action,
            "verdict": guardrail_verdict.routing_verdict
        }
    )

    # -------------------------------------------------------------
    # 9. Decision Engine Routing
    # -------------------------------------------------------------
    decision = route_decision(
        case_id=case_id,
        diagnosis=llm_diag,
        customer=cust,
        transaction=txn,
        payment=pay,
        telemetry=telem,
        current_time_utc=fixed_time
    )
    assert decision.routing in ("AUTO", "HUMAN", "BLOCK")
    assert decision.action == guardrail_verdict.final_action

    ledger.append_event(
        case_id=case_id,
        event_type="DECISION_ROUTED",
        payload=decision.to_dict()
    )

    # -------------------------------------------------------------
    # 10. Execution Adapter Dispatch
    # -------------------------------------------------------------
    adapter = SandboxPaymentExecutionAdapter()
    exec_resp = adapter.execute(
        case_id=case_id,
        action_type=decision.action,
        amount=txn.amount,
        customer_phone=cust.phone,
        idempotency_key=f"idemp_e2e_{case_id}_{decision.action}"
    )
    assert exec_resp.status in ("ACCEPTED_PENDING_SETTLEMENT", "DISPATCHED_PENDING_CUSTOMER_ACTION", "QUEUED_FOR_OPERATIONS_DESK")

    # In-flight state transitions to PENDING
    validate_transition(pay.status, "PENDING")
    pay.status = "PENDING"
    txn.state = "PENDING"

    ledger.append_event(
        case_id=case_id,
        event_type="EXECUTION_DISPATCHED",
        payload={
            "provider_reference": exec_resp.provider_reference,
            "status": exec_resp.status,
            "idempotency_key": exec_resp.idempotency_key
        }
    )

    # -------------------------------------------------------------
    # 11. Authoritative Webhook Verification
    # -------------------------------------------------------------
    # Confirm action response alone is insufficient
    assert AuthoritativeVerificationEngine.is_action_response_sufficient_for_recovery() is False

    # Simulate arrival of authoritative signed bank settlement webhook
    webhook = AuthoritativeWebhookEvent(
        webhook_id=f"wh_e2e_{case_id}",
        case_id=case_id,
        event_type="payment.settled",
        provider_reference=exec_resp.provider_reference,
        settled_amount=txn.amount,
        status="SETTLED",
        signature="sha256_mock_valid_signature",
        timestamp=fixed_time.isoformat()
    )
    verif_result = AuthoritativeVerificationEngine.verify_webhook(webhook, pay, txn)
    assert verif_result.is_verified_recovered is True
    assert verif_result.final_payment_state == "SUCCESS"
    assert pay.status == "SUCCESS"
    assert txn.state == "SUCCESS"

    ledger.append_event(
        case_id=case_id,
        event_type="WEBHOOK_SETTLEMENT_VERIFIED",
        payload={
            "webhook_id": webhook.webhook_id,
            "settled_amount": webhook.settled_amount,
            "is_verified_recovered": True
        }
    )

    # -------------------------------------------------------------
    # 12. Tripartite Reconciliation
    # -------------------------------------------------------------
    recon = ReconciliationEngine.reconcile(
        case_id=case_id,
        customer_debited=pay.debited_customer,
        provider_status=pay.status,
        merchant_order_paid=pay.confirmed_merchant,
        successful_payment_count=1,
        transaction_amount=txn.amount,
        settled_amount=txn.amount
    )
    assert recon.is_balanced is True
    assert recon.resolution_action == "NONE"

    ledger.append_event(
        case_id=case_id,
        event_type="RECONCILIATION_COMPLETED",
        payload={
            "is_balanced": recon.is_balanced,
            "resolution_action": recon.resolution_action
        }
    )

    # -------------------------------------------------------------
    # 13. Append-Only Ledger Integrity & Case Reconstruction
    # -------------------------------------------------------------
    assert ledger.verify_chain_integrity() is True
    lifecycle = ledger.reconstruct_case_lifecycle(case_id)
    assert len(lifecycle) == 11

    # -------------------------------------------------------------
    # 14. Report Traceability Check
    # -------------------------------------------------------------
    dummy_metric = ArmMetrics(
        arm_name="AGENT",
        total_cases=1,
        total_at_risk_inr=txn.amount,
        gross_recovered_inr=txn.amount,
        natural_recovery_inr=0.0,
        incremental_recovery_inr=txn.amount,
        recovery_rate_pct=100.0,
        incremental_lift_pct=100.0,
        total_cost_inr=3.0,
        net_recovery_inr=txn.amount - 3.0,
        duplicate_charges_count=0,
        ambiguous_reconciled_count=0,
        guardrail_blocks_count=0,
        human_reviews_count=0,
        contact_count=0,
        safety_invariants_status="PASSED",
        failed_invariants=[]
    )
    run_res = EvaluationRunResult(
        config_version="1.0.0",
        seed=42,
        batch_name="Batch_E2E",
        run_timestamp=fixed_time.isoformat(),
        diagnosis_accuracy_rules_pct=100.0,
        diagnosis_accuracy_llm_pct=100.0,
        arm_metrics={
            "CONTROL": dummy_metric,
            "NAIVE": dummy_metric,
            "RULES": dummy_metric,
            "AGENT": dummy_metric
        },
        ledger=ledger
    )
    report_md = generate_markdown_report(run_res)
    assert f"₹{txn.amount:,.2f}" in report_md

    # Print the full reconstructed lifecycle for verification evidence
    print(f"\n================ RECONSTRUCTED LEDGER FOR {case_id} ================")
    for step_num, entry in enumerate(lifecycle, 1):
        print(f"Step {step_num:02d} | Event: {entry['event_type']:<30} | ID: {entry['event_id']} | Hash: {entry['current_hash'][:16]}...")
        print(f"        Payload: {json.dumps(entry['payload'])}")
    print("===================================================================\n")
