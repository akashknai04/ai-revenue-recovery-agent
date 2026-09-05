"""Payment Integrity Engine: Deterministic rules preventing double debits and integrity failures.

Operates with zero LLM dependency. Enforces strict financial safeguards
prior to any recovery action selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from core.state_machine import PaymentState, normalize_state


@dataclass(frozen=True)
class IntegrityVerdict:
    """Result of payment integrity evaluation."""
    is_safe: bool
    verdict_code: str  # PASS, BLOCK_NEW_CHARGE, RECONCILIATION_REQUIRED, BLOCK_DUPLICATE, STOP_RECONCILE
    recommended_disposition: str  # PROCEED, HOLD_RECONCILE, BLOCK_IMMEDIATELY
    reasons: List[str] = field(default_factory=list)


def evaluate_payment_integrity(
    payment_status: str,
    debited_customer: bool,
    confirmed_merchant: bool,
    order_paid: bool,
    duplicate_detected: bool,
    is_ambiguous: bool = False
) -> IntegrityVerdict:
    """Evaluate payment integrity rules deterministically.

    Rules:
    1. IF customer_debited AND merchant_confirmation == UNKNOWN -> BLOCK_NEW_CHARGE
    2. IF payment_success AND order_paid == FALSE -> RECONCILIATION_REQUIRED
    3. IF duplicate_payment_detected -> BLOCK
    4. Ambiguity Rule: IF unclear whether money moved -> STOP -> RECONCILE, never retry.
    """
    reasons: List[str] = []
    norm_status = normalize_state(payment_status)

    # Rule 3: Duplicate payment detected -> BLOCK
    if duplicate_detected:
        reasons.append("Duplicate payment detected: parallel attempt or multiple charges detected.")
        return IntegrityVerdict(
            is_safe=False,
            verdict_code="BLOCK_DUPLICATE",
            recommended_disposition="BLOCK_IMMEDIATELY",
            reasons=reasons
        )

    # Rule 1: Customer debited but merchant confirmation is UNKNOWN -> BLOCK_NEW_CHARGE
    merchant_confirmation_unknown = not confirmed_merchant
    if debited_customer and merchant_confirmation_unknown:
        reasons.append("Customer was debited at bank switch, but merchant confirmation is unknown. Immediate recharge forbidden.")
        return IntegrityVerdict(
            is_safe=False,
            verdict_code="BLOCK_NEW_CHARGE",
            recommended_disposition="HOLD_RECONCILE",
            reasons=reasons
        )

    # Rule 4 / Ambiguity rule: If unclear whether money moved -> STOP -> RECONCILE, never retry
    if is_ambiguous or norm_status == PaymentState.UNKNOWN:
        reasons.append("Transaction status is ambiguous or unknown. Settlement verification required before any retry.")
        return IntegrityVerdict(
            is_safe=False,
            verdict_code="STOP_RECONCILE",
            recommended_disposition="HOLD_RECONCILE",
            reasons=reasons
        )

    # Rule 2: Payment is SUCCESS but order_paid is FALSE -> RECONCILIATION_REQUIRED
    if norm_status == PaymentState.SUCCESS and not order_paid:
        reasons.append("Payment succeeded at gateway, but order fulfillment state is unpaid. Internal reconciliation required.")
        return IntegrityVerdict(
            is_safe=False,
            verdict_code="RECONCILIATION_REQUIRED",
            recommended_disposition="HOLD_RECONCILE",
            reasons=reasons
        )

    # If already successfully paid and order is fulfilled -> No further action needed
    if norm_status == PaymentState.SUCCESS and order_paid:
        reasons.append("Payment and order fulfillment already verified complete.")
        return IntegrityVerdict(
            is_safe=False,
            verdict_code="ALREADY_SUCCESSFUL",
            recommended_disposition="BLOCK_IMMEDIATELY",
            reasons=reasons
        )

    # Safe to evaluate standard recovery pathways
    return IntegrityVerdict(
        is_safe=True,
        verdict_code="PASS",
        recommended_disposition="PROCEED",
        reasons=["All payment integrity invariants passed."]
    )
