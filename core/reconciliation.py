"""Reconciliation Engine: Tripartite state alignment.

Compares customer bank debit, payment provider status, and merchant order fulfillment
to detect and resolve financial discrepancies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from core.state_machine import PaymentState, normalize_state


@dataclass(frozen=True)
class ReconciliationResult:
    case_id: str
    mismatch_type: Optional[str]  # None, SUCCESS_BUT_ORDER_UNPAID, DEBIT_BUT_PROVIDER_UNCERTAIN, DUPLICATE_SUCCESSFUL_PAYMENT
    resolution_action: str  # NONE, FORCE_ORDER_FULFILLMENT_SYNC, HOLD_SETTLEMENT_INQUIRY, QUEUE_AUTO_REFUND_SECOND_CHARGE
    is_balanced: bool
    explanation: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReconciliationEngine:
    """Executes tripartite reconciliation across Customer, Provider, and Merchant."""

    @classmethod
    def reconcile(
        cls,
        case_id: str,
        customer_debited: bool,
        provider_status: str,
        merchant_order_paid: bool,
        successful_payment_count: int = 1,
        transaction_amount: float = 0.0,
        settled_amount: float = 0.0
    ) -> ReconciliationResult:
        """Reconcile the 3 financial states and determine resolution action."""
        norm_status = normalize_state(provider_status)

        # Mismatch Case 3: Duplicate Successful Payment
        # Two or more debits succeeded for the same checkout
        if successful_payment_count > 1 or (customer_debited and settled_amount > transaction_amount * 1.5):
            excess_amount = max(transaction_amount, settled_amount - transaction_amount)
            return ReconciliationResult(
                case_id=case_id,
                mismatch_type="DUPLICATE_SUCCESSFUL_PAYMENT",
                resolution_action="QUEUE_AUTO_REFUND_SECOND_CHARGE",
                is_balanced=False,
                explanation=f"Duplicate payment detected ({successful_payment_count} charges). Queued automated refund of secondary charge.",
                details={
                    "refund_amount": excess_amount,
                    "primary_charge_retained": True
                }
            )

        # Mismatch Case 1: Success-but-order-unpaid
        # Provider succeeded and customer was debited, but merchant order is still marked unpaid
        if norm_status == PaymentState.SUCCESS and not merchant_order_paid:
            return ReconciliationResult(
                case_id=case_id,
                mismatch_type="SUCCESS_BUT_ORDER_UNPAID",
                resolution_action="FORCE_ORDER_FULFILLMENT_SYNC",
                is_balanced=False,
                explanation="Payment settled at provider but merchant order is unpaid. Forcing fulfillment sync.",
                details={
                    "order_paid_update": True,
                    "settled_amount": settled_amount or transaction_amount
                }
            )

        # Mismatch Case 2: Debit-but-provider-uncertain
        # Customer was debited at bank switch, but provider status is UNKNOWN, PENDING, or FAILED
        if customer_debited and norm_status in (PaymentState.UNKNOWN, PaymentState.PENDING, PaymentState.FAILED):
            return ReconciliationResult(
                case_id=case_id,
                mismatch_type="DEBIT_BUT_PROVIDER_UNCERTAIN",
                resolution_action="HOLD_SETTLEMENT_INQUIRY",
                is_balanced=False,
                explanation="Customer account was debited, but provider settlement is uncertain. Placing on settlement inquiry hold.",
                details={
                    "prevent_recharge": True,
                    "inquiry_disposition": "HOLD_PENDING_BANK_RECON"
                }
            )

        # Balanced clean state
        return ReconciliationResult(
            case_id=case_id,
            mismatch_type=None,
            resolution_action="NONE",
            is_balanced=True,
            explanation="Customer, provider, and merchant states are consistent and balanced.",
            details={"status": norm_status.value}
        )
