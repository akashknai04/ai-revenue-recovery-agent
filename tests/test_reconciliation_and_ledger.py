"""Unit tests for Phase 9: Reconciliation Engine and Append-only Hash-chained Ledger."""

import pytest
from core.reconciliation import ReconciliationEngine, ReconciliationResult
from core.ledger import AppendOnlyLedger, LedgerMutationError


# -------------------------------------------------------------
# Reconciliation Engine Tests (All 3 mismatch cases)
# -------------------------------------------------------------

def test_reconciliation_mismatch_1_success_but_order_unpaid():
    """Case 1: IF payment_success AND order_paid == FALSE -> FORCE_ORDER_FULFILLMENT_SYNC."""
    recon = ReconciliationEngine.reconcile(
        case_id="case_recon_01",
        customer_debited=True,
        provider_status="SUCCESS",
        merchant_order_paid=False,
        successful_payment_count=1,
        transaction_amount=4500.0,
        settled_amount=4500.0
    )
    assert recon.mismatch_type == "SUCCESS_BUT_ORDER_UNPAID"
    assert recon.resolution_action == "FORCE_ORDER_FULFILLMENT_SYNC"
    assert recon.is_balanced is False
    assert recon.details.get("order_paid_update") is True


def test_reconciliation_mismatch_2_debit_but_provider_uncertain():
    """Case 2: IF customer_debited AND provider uncertain -> HOLD_SETTLEMENT_INQUIRY."""
    recon = ReconciliationEngine.reconcile(
        case_id="case_recon_02",
        customer_debited=True,
        provider_status="UNKNOWN",
        merchant_order_paid=False,
        successful_payment_count=0,
        transaction_amount=3000.0,
        settled_amount=0.0
    )
    assert recon.mismatch_type == "DEBIT_BUT_PROVIDER_UNCERTAIN"
    assert recon.resolution_action == "HOLD_SETTLEMENT_INQUIRY"
    assert recon.is_balanced is False
    assert recon.details.get("prevent_recharge") is True


def test_reconciliation_mismatch_3_duplicate_successful_payment():
    """Case 3: IF duplicate successful payment -> QUEUE_AUTO_REFUND_SECOND_CHARGE."""
    recon = ReconciliationEngine.reconcile(
        case_id="case_recon_03",
        customer_debited=True,
        provider_status="SUCCESS",
        merchant_order_paid=True,
        successful_payment_count=2,  # Two charges succeeded
        transaction_amount=2500.0,
        settled_amount=5000.0
    )
    assert recon.mismatch_type == "DUPLICATE_SUCCESSFUL_PAYMENT"
    assert recon.resolution_action == "QUEUE_AUTO_REFUND_SECOND_CHARGE"
    assert recon.is_balanced is False
    assert recon.details.get("refund_amount") == 2500.0


# -------------------------------------------------------------
# Append-Only Ledger & Immutability Tests
# -------------------------------------------------------------

def test_ledger_is_provably_append_only():
    """CRITICAL ACCEPTANCE CRITERION: Ledger is provably append-only (mutation must fail)."""
    ledger = AppendOnlyLedger()

    # Append 3 events
    evt1 = ledger.append_event("case_immut_01", "CASE_INITIATED", {"amount": 1000.0})
    evt2 = ledger.append_event("case_immut_01", "DIAGNOSIS_RECORDED", {"root_cause": "ISSUER_TECHNICAL_DECLINE"})
    evt3 = ledger.append_event("case_immut_01", "ACTION_ROUTED", {"routing": "AUTO", "action": "DELAYED_RETRY"})

    assert len(ledger) == 3
    assert ledger.verify_chain_integrity() is True

    # Attempt to overwrite an existing entry index
    with pytest.raises(LedgerMutationError):
        ledger[0] = evt3

    # Attempt to delete an existing entry index
    with pytest.raises(LedgerMutationError):
        del ledger[1]


def test_case_lifecycle_reconstruction_from_ledger_alone():
    """CRITICAL ACCEPTANCE CRITERION: Given a case_id, reconstruct entire lifecycle with no other data source."""
    ledger = AppendOnlyLedger()
    target_case_id = "case_lifecycle_99"

    # Step 1: Initial degradation
    ledger.append_event(
        case_id=target_case_id,
        event_type="PAYMENT_DEGRADATION_DETECTED",
        payload={"failure_code": "SWITCH_TIMEOUT", "amount": 8500.0, "state": "FAILED"}
    )
    # Step 2: Diagnosis
    ledger.append_event(
        case_id=target_case_id,
        event_type="DIAGNOSIS_RECORDED",
        payload={"root_cause": "ISSUER_TECHNICAL_DECLINE", "confidence": 0.94}
    )
    # Step 3: EV ranking & Guardrails
    ledger.append_event(
        case_id=target_case_id,
        event_type="DECISION_EVALUATED",
        payload={"action": "DELAYED_RETRY", "routing": "AUTO", "ev_score": 3840.5}
    )
    # Step 4: Execution attempt
    ledger.append_event(
        case_id=target_case_id,
        event_type="EXECUTION_DISPATCHED",
        payload={"provider_reference": "sb_ref_12345", "status": "ACCEPTED_PENDING_SETTLEMENT"}
    )
    # Step 5: Authoritative Webhook
    ledger.append_event(
        case_id=target_case_id,
        event_type="WEBHOOK_SETTLEMENT_VERIFIED",
        payload={"status": "SETTLED", "settled_amount": 8500.0}
    )
    # Step 6: Reconciliation
    ledger.append_event(
        case_id=target_case_id,
        event_type="RECONCILIATION_COMPLETED",
        payload={"is_balanced": True, "resolution_action": "NONE"}
    )

    # Interleave an unrelated event for another case
    ledger.append_event("case_other_11", "PAYMENT_DEGRADATION_DETECTED", {"amount": 500.0})

    # Reconstruct target case lifecycle
    history = ledger.reconstruct_case_lifecycle(target_case_id)
    assert len(history) == 6

    expected_event_sequence = [
        "PAYMENT_DEGRADATION_DETECTED",
        "DIAGNOSIS_RECORDED",
        "DECISION_EVALUATED",
        "EXECUTION_DISPATCHED",
        "WEBHOOK_SETTLEMENT_VERIFIED",
        "RECONCILIATION_COMPLETED"
    ]
    actual_sequence = [entry["event_type"] for entry in history]
    assert actual_sequence == expected_event_sequence

    # Verify every reconstructed entry has hash-chain proof
    for entry in history:
        assert "current_hash" in entry
        assert "prev_hash" in entry
        assert len(entry["current_hash"]) == 64
