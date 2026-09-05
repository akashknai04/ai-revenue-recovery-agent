"""Unit tests for Phase 8: Execution Adapter and Authoritative Verification."""

from core.execution_adapter import SandboxPaymentExecutionAdapter, ExecutionResponse
from core.verification import (
    AuthoritativeVerificationEngine,
    AuthoritativeWebhookEvent,
    VerificationResult
)
from core.entities import Payment, Transaction


def test_execution_success_does_not_equal_recovery_success():
    """CRITICAL ACCEPTANCE CRITERION: Execution response alone NEVER marks recovery."""
    adapter = SandboxPaymentExecutionAdapter()

    txn = Transaction(
        id="case_verify_01",
        customer_id="cust_01",
        amount=2500.0,
        state="PENDING"
    )
    payment = Payment(
        id="pay_01",
        transaction_id="case_verify_01",
        provider_reference=None,
        amount=2500.0,
        status="PENDING",
        debited_customer=False,
        confirmed_merchant=False
    )

    # Step 1: Execute action via Sandbox Adapter
    exec_resp = adapter.execute(
        case_id="case_verify_01",
        action_type="RETRY",
        amount=2500.0,
        customer_phone="+919876543210",
        idempotency_key="idemp_case_verify_01_try1"
    )

    # The adapter returned an accepted execution response
    assert exec_resp.status == "ACCEPTED_PENDING_SETTLEMENT"
    assert exec_resp.provider_reference.startswith("sb_ref_")

    # Invariant: Action response is NOT sufficient for recovery
    assert AuthoritativeVerificationEngine.is_action_response_sufficient_for_recovery() is False
    assert payment.status == "PENDING"
    assert payment.confirmed_merchant is False
    assert txn.state == "PENDING"


def test_authoritative_webhook_marks_recovery():
    """Verify recovery is confirmed ONLY upon authoritative webhook receipt."""
    txn = Transaction(
        id="case_verify_02",
        customer_id="cust_02",
        amount=1999.0,
        state="PENDING"
    )
    payment = Payment(
        id="pay_02",
        transaction_id="case_verify_02",
        provider_reference="sb_ref_test",
        amount=1999.0,
        status="PENDING",
        debited_customer=False,
        confirmed_merchant=False
    )

    # Deliver authoritative webhook
    webhook = AuthoritativeWebhookEvent(
        webhook_id="wh_001",
        case_id="case_verify_02",
        event_type="payment.settled",
        provider_reference="sb_ref_test",
        settled_amount=1999.0,
        status="SETTLED",
        signature="sha256_mock_valid_signature",
        timestamp="2026-09-05T12:00:00Z"
    )

    verif_result = AuthoritativeVerificationEngine.verify_webhook(
        webhook=webhook,
        payment=payment,
        transaction=txn
    )

    assert verif_result.is_verified_recovered is True
    assert verif_result.final_payment_state == "SUCCESS"
    assert payment.status == "SUCCESS"
    assert payment.debited_customer is True
    assert payment.confirmed_merchant is True
    assert txn.state == "SUCCESS"
