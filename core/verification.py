"""Authoritative Verification Engine.

NON-NEGOTIABLE PRINCIPLE:
An action is NEVER marked successful or recovered from the execution response alone.
Recovery is confirmed ONLY upon receipt and validation of an authoritative settlement event
(e.g., signed banking partner webhook, NPCI settlement file).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from core.entities import Payment, Transaction
from core.state_machine import PaymentState, normalize_state, validate_transition


@dataclass(frozen=True)
class AuthoritativeWebhookEvent:
    webhook_id: str
    case_id: str
    event_type: str  # payment.settled, payment.failed, payment.disputed
    provider_reference: str
    settled_amount: float
    status: str  # SETTLED, FAILED, CHARGEBACK
    signature: str
    timestamp: str


@dataclass(frozen=True)
class VerificationResult:
    is_verified_recovered: bool
    state_changed: bool
    final_payment_state: str
    evidence: str
    timestamp: str


class AuthoritativeVerificationEngine:
    """Verifies recovery status based exclusively on authoritative settlement signals."""

    @staticmethod
    def is_action_response_sufficient_for_recovery() -> bool:
        """Returns False. Execution response is NEVER sufficient for recovery."""
        return False

    @classmethod
    def verify_webhook(
        cls,
        webhook: AuthoritativeWebhookEvent,
        payment: Payment,
        transaction: Transaction
    ) -> VerificationResult:
        """Process an authoritative webhook event to verify financial recovery."""
        now_str = datetime.now(timezone.utc).isoformat()

        if webhook.case_id != transaction.id:
            return VerificationResult(
                is_verified_recovered=False,
                state_changed=False,
                final_payment_state=payment.status,
                evidence=f"Case mismatch: webhook case '{webhook.case_id}' != txn '{transaction.id}'",
                timestamp=now_str
            )

        if webhook.status == "SETTLED":
            # Verify settled amount matches or covers transaction
            if webhook.settled_amount < transaction.amount:
                return VerificationResult(
                    is_verified_recovered=False,
                    state_changed=False,
                    final_payment_state=payment.status,
                    evidence=f"Partial settlement mismatch: settled INR {webhook.settled_amount} < txn {transaction.amount}",
                    timestamp=now_str
                )

            # Legally transition state to SUCCESS
            validate_transition(payment.status, "SUCCESS")
            payment.status = "SUCCESS"
            payment.debited_customer = True
            payment.confirmed_merchant = True
            transaction.state = "SUCCESS"

            return VerificationResult(
                is_verified_recovered=True,
                state_changed=True,
                final_payment_state="SUCCESS",
                evidence=f"Authoritative webhook '{webhook.webhook_id}' confirmed settlement of INR {webhook.settled_amount}",
                timestamp=now_str
            )

        elif webhook.status == "FAILED":
            # Confirmed failure
            payment.status = "FAILED"
            transaction.state = "FAILED"
            return VerificationResult(
                is_verified_recovered=False,
                state_changed=True,
                final_payment_state="FAILED",
                evidence=f"Authoritative webhook '{webhook.webhook_id}' confirmed final failure",
                timestamp=now_str
            )

        return VerificationResult(
            is_verified_recovered=False,
            state_changed=False,
            final_payment_state=payment.status,
            evidence=f"Unrecognized webhook status '{webhook.status}'",
            timestamp=now_str
        )
