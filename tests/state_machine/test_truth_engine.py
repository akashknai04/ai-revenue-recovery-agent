"""Unit tests for Phase 3: Transaction Truth Engine and Payment Integrity Rules."""

import pytest
from core.state_machine import (
    PaymentState,
    IllegalStateTransitionError,
    normalize_state,
    validate_transition,
    is_failed,
    is_terminal
)
from core.integrity import evaluate_payment_integrity


# ---------------------------------------------------------
# State Machine & Transition Tests
# ---------------------------------------------------------

def test_state_machine_valid_transitions():
    """Verify standard legal state progressions."""
    assert validate_transition("INITIATED", "PENDING") is True
    assert validate_transition("PENDING", "SUCCESS") is True
    assert validate_transition("SUCCESS", "REFUNDED") is True
    assert validate_transition("INITIATED", "FAILED") is True


def test_state_machine_rejects_illegal_transitions():
    """Verify that illegal transitions raise IllegalStateTransitionError."""
    # SUCCESS cannot regress to FAILED
    with pytest.raises(IllegalStateTransitionError):
        validate_transition("SUCCESS", "FAILED")

    # SUCCESS cannot regress to PENDING
    with pytest.raises(IllegalStateTransitionError):
        validate_transition("SUCCESS", "PENDING")

    # REFUNDED is terminal; cannot transition to SUCCESS or PENDING
    with pytest.raises(IllegalStateTransitionError):
        validate_transition("REFUNDED", "SUCCESS")

    with pytest.raises(IllegalStateTransitionError):
        validate_transition("REFUNDED", "PENDING")


def test_pending_is_never_treated_as_failed():
    """CRITICAL ACCEPTANCE CRITERION: PENDING is NEVER treated as FAILED."""
    assert is_failed("PENDING") is False
    assert is_failed(PaymentState.PENDING) is False
    assert is_failed("UNKNOWN") is False
    assert is_failed(PaymentState.UNKNOWN) is False
    assert is_failed("INITIATED") is False
    assert is_failed("SUCCESS") is False
    assert is_failed("REFUNDED") is False

    # Only explicitly FAILED returns True
    assert is_failed("FAILED") is True
    assert is_failed(PaymentState.FAILED) is True


# ---------------------------------------------------------
# Payment Integrity Rules Tests
# ---------------------------------------------------------

def test_integrity_rule_1_customer_debited_merchant_unknown():
    """Rule 1: IF customer_debited AND merchant_confirmation == UNKNOWN -> BLOCK_NEW_CHARGE."""
    verdict = evaluate_payment_integrity(
        payment_status="PENDING",
        debited_customer=True,
        confirmed_merchant=False,
        order_paid=False,
        duplicate_detected=False,
        is_ambiguous=False
    )
    assert verdict.is_safe is False
    assert verdict.verdict_code == "BLOCK_NEW_CHARGE"
    assert verdict.recommended_disposition == "HOLD_RECONCILE"


def test_integrity_rule_2_payment_success_order_unpaid():
    """Rule 2: IF payment_success AND order_paid == FALSE -> RECONCILIATION_REQUIRED."""
    verdict = evaluate_payment_integrity(
        payment_status="SUCCESS",
        debited_customer=True,
        confirmed_merchant=True,
        order_paid=False,
        duplicate_detected=False,
        is_ambiguous=False
    )
    assert verdict.is_safe is False
    assert verdict.verdict_code == "RECONCILIATION_REQUIRED"
    assert verdict.recommended_disposition == "HOLD_RECONCILE"


def test_integrity_rule_3_duplicate_payment_detected():
    """Rule 3: IF duplicate_payment_detected -> BLOCK."""
    verdict = evaluate_payment_integrity(
        payment_status="FAILED",
        debited_customer=False,
        confirmed_merchant=False,
        order_paid=False,
        duplicate_detected=True,
        is_ambiguous=False
    )
    assert verdict.is_safe is False
    assert verdict.verdict_code == "BLOCK_DUPLICATE"
    assert verdict.recommended_disposition == "BLOCK_IMMEDIATELY"


def test_integrity_ambiguity_rule():
    """Ambiguity Rule: IF unclear whether money moved -> STOP -> RECONCILE, never retry."""
    verdict = evaluate_payment_integrity(
        payment_status="UNKNOWN",
        debited_customer=False,
        confirmed_merchant=False,
        order_paid=False,
        duplicate_detected=False,
        is_ambiguous=True
    )
    assert verdict.is_safe is False
    assert verdict.verdict_code == "STOP_RECONCILE"
    assert verdict.recommended_disposition == "HOLD_RECONCILE"


def test_integrity_clean_failure_passes_for_recovery():
    """Verify that an ordinary clean failure passes integrity checks."""
    verdict = evaluate_payment_integrity(
        payment_status="FAILED",
        debited_customer=False,
        confirmed_merchant=False,
        order_paid=False,
        duplicate_detected=False,
        is_ambiguous=False
    )
    assert verdict.is_safe is True
    assert verdict.verdict_code == "PASS"
    assert verdict.recommended_disposition == "PROCEED"
