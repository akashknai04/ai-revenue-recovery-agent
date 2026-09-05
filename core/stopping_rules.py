"""Pre-action Stopping Rules Engine.

Evaluated deterministically BEFORE any recovery action ranking or execution.
Enforces hard termination and diversion rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from core.state_machine import PaymentState, normalize_state


@dataclass(frozen=True)
class StoppingRuleResult:
    should_stop: bool
    disposition: str  # PROCEED, STOP, RECONCILE
    rule_name: str
    reason: str


def evaluate_stopping_rules(
    case_status: str,
    customer_opted_out: bool,
    order_already_paid: bool,
    payment_status: str,
    is_ambiguous_debit: bool,
    debited_customer: bool,
    retry_count: int,
    contact_count: int,
    max_retries: int = 3,
    max_contacts: int = 3
) -> StoppingRuleResult:
    """Evaluate the six mandatory stopping conditions in strict precedence.

    Rules:
    1. Case already terminated -> STOP
    2. Customer opted out -> STOP
    3. Already successful -> STOP
    4. Ambiguous debit -> RECONCILE
    5. Retry budget exceeded -> STOP
    6. Contact budget exceeded -> STOP
    """
    clean_case_status = case_status.strip().upper()
    norm_pay_status = normalize_state(payment_status)

    # 1. Case already terminated -> STOP
    if clean_case_status in ("TERMINATED", "REFUNDED", "CANCELLED", "ABANDONED"):
        return StoppingRuleResult(
            should_stop=True,
            disposition="STOP",
            rule_name="CASE_ALREADY_TERMINATED",
            reason=f"Case is already in terminal state '{clean_case_status}'. No further recovery actions permitted."
        )

    # 2. Customer opted out -> STOP
    if customer_opted_out:
        return StoppingRuleResult(
            should_stop=True,
            disposition="STOP",
            rule_name="CUSTOMER_OPTED_OUT",
            reason="Customer has opted out of communication / DND registered. All outbound recovery halted."
        )

    # 3. Already successful -> STOP
    if order_already_paid and norm_pay_status == PaymentState.SUCCESS:
        return StoppingRuleResult(
            should_stop=True,
            disposition="STOP",
            rule_name="ALREADY_SUCCESSFUL",
            reason="Transaction and order are already successfully paid. Recovery redundant."
        )

    # 4. Ambiguous debit -> RECONCILE
    # Triggered if explicitly flagged ambiguous or if customer is debited without merchant confirmation
    if is_ambiguous_debit or (debited_customer and norm_pay_status != PaymentState.SUCCESS):
        return StoppingRuleResult(
            should_stop=True,
            disposition="RECONCILE",
            rule_name="AMBIGUOUS_DEBIT_RECONCILE",
            reason="Uncertain debit state detected. Diverting to reconciliation queue before any action."
        )

    # 5. Retry budget exceeded -> STOP
    if retry_count >= max_retries:
        return StoppingRuleResult(
            should_stop=True,
            disposition="STOP",
            rule_name="RETRY_BUDGET_EXCEEDED",
            reason=f"Retry budget reached ({retry_count}/{max_retries} attempts made). Automatic retries halted."
        )

    # 6. Contact budget exceeded -> STOP
    if contact_count >= max_contacts:
        return StoppingRuleResult(
            should_stop=True,
            disposition="STOP",
            rule_name="CONTACT_BUDGET_EXCEEDED",
            reason=f"Customer contact budget reached ({contact_count}/{max_contacts} contacts made). Halting customer outreach."
        )

    # All stopping rules passed -> Safe to proceed with action ranking
    return StoppingRuleResult(
        should_stop=False,
        disposition="PROCEED",
        rule_name="ALL_PASSED",
        reason="All stopping conditions cleared. Proceeding to action selection."
    )
