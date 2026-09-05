"""Promise-to-Pay (PTP) Lifecycle Tracker.

Manages the state machine: pending -> kept | broken | renegotiated.
NON-NEGOTIABLE REQUIREMENT:
A broken promise must trigger re-evaluation through stopping rules and guardrails again.
It must NEVER automatically recharge the customer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from core.entities import Customer, PromiseToPay, Transaction
from core.stopping_rules import StoppingRuleResult, evaluate_stopping_rules


class InvalidPTPTransitionError(ValueError):
    """Raised when an invalid Promise-to-Pay transition is attempted."""
    pass


class PromiseToPayTracker:
    """In-memory registry and state machine manager for customer payment promises."""

    def __init__(self):
        self.promises: Dict[str, PromiseToPay] = {}

    def register_promise(
        self,
        promise_id: str,
        case_id: str,
        promised_amount: float,
        promised_date: str
    ) -> PromiseToPay:
        """Register a new customer promise commitment in pending state."""
        ptp = PromiseToPay(
            id=promise_id,
            case_id=case_id,
            promised_amount=promised_amount,
            promised_date=promised_date,
            status="pending"
        )
        self.promises[promise_id] = ptp
        return ptp

    def get_promise(self, promise_id: str) -> Optional[PromiseToPay]:
        return self.promises.get(promise_id)

    def mark_kept(self, promise_id: str) -> PromiseToPay:
        """Fulfill promise: transitions from pending or renegotiated to kept."""
        ptp = self._get_required(promise_id)
        if ptp.status not in ("pending", "renegotiated"):
            raise InvalidPTPTransitionError(
                f"Cannot mark promise '{promise_id}' as kept from status '{ptp.status}'"
            )
        ptp.status = "kept"
        return ptp

    def mark_broken(self, promise_id: str) -> PromiseToPay:
        """Mark promise as broken when promised date elapses without payment."""
        ptp = self._get_required(promise_id)
        if ptp.status not in ("pending", "renegotiated"):
            raise InvalidPTPTransitionError(
                f"Cannot mark promise '{promise_id}' as broken from status '{ptp.status}'"
            )
        ptp.status = "broken"
        return ptp

    def renegotiate(self, promise_id: str, new_promised_date: str) -> PromiseToPay:
        """Customer renegotiates payment date prior to or upon delinquency."""
        ptp = self._get_required(promise_id)
        if ptp.status not in ("pending", "broken"):
            raise InvalidPTPTransitionError(
                f"Cannot renegotiate promise '{promise_id}' from status '{ptp.status}'"
            )
        ptp.status = "renegotiated"
        ptp.promised_date = new_promised_date
        return ptp

    def handle_broken_promise(
        self,
        promise_id: str,
        customer: Customer,
        transaction: Transaction,
        retry_count: int,
        is_ambiguous_debit: bool = False
    ) -> StoppingRuleResult:
        """Evaluate a broken promise.

        CRITICAL REQUIREMENT:
        Broken promises MUST re-enter stopping rules and guardrails.
        They must NEVER initiate an automatic recharge!
        """
        ptp = self._get_required(promise_id)
        if ptp.status != "broken":
            ptp = self.mark_broken(promise_id)

        # Enforce that customer contact count includes the reminder for broken promise
        customer.contact_count += 1

        # Re-evaluate all stopping rules
        stopping_verdict = evaluate_stopping_rules(
            case_status="BROKEN_PROMISE_RE_EVALUATION",
            customer_opted_out=customer.opted_out,
            order_already_paid=(transaction.state == "SUCCESS"),
            payment_status=transaction.state,
            is_ambiguous_debit=is_ambiguous_debit,
            debited_customer=False,
            retry_count=retry_count,
            contact_count=customer.contact_count
        )

        return stopping_verdict

    def _get_required(self, promise_id: str) -> PromiseToPay:
        if promise_id not in self.promises:
            raise KeyError(f"Promise '{promise_id}' not found in tracker.")
        return self.promises[promise_id]
