"""Decision Engine for AI Revenue Recovery Agent.

Determines the final recovery decision by synthesizing:
1. Pre-action stopping rules
2. Stratified lift Expected Value ranking
3. Hard safety and regulatory guardrails

NON-NEGOTIABLE REQUIREMENT:
Every single case routes to exactly one of AUTO, HUMAN, BLOCK.
No case falls through without a decision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from core.catalog import ACTION_CATALOG
from core.entities import Customer, Decision, Diagnosis, Payment, Transaction
from core.ev import rank_actions_by_ev
from core.guardrails import SafetyGuardrails
from core.stopping_rules import evaluate_stopping_rules


def route_decision(
    case_id: str,
    diagnosis: Diagnosis,
    customer: Customer,
    transaction: Transaction,
    payment: Payment,
    telemetry: Dict[str, Any],
    current_time_utc: Optional[datetime] = None
) -> Decision:
    """Evaluate full pipeline and route case to exactly one of AUTO, HUMAN, or BLOCK."""
    current_time_utc = current_time_utc or datetime.now(timezone.utc)
    is_ambiguous = telemetry.get("is_ambiguous_debit", False) or (payment.status == "UNKNOWN")
    has_dup_risk = telemetry.get("duplicate_attempt_detected", False)
    retry_count = telemetry.get("attempt_count", 1) - 1

    # =========================================================================
    # STEP 1: Pre-action Stopping Rules
    # =========================================================================
    stopping_result = evaluate_stopping_rules(
        case_status=transaction.state,
        customer_opted_out=customer.opted_out,
        order_already_paid=payment.confirmed_merchant,
        payment_status=payment.status,
        is_ambiguous_debit=is_ambiguous,
        debited_customer=payment.debited_customer,
        retry_count=retry_count,
        contact_count=customer.contact_count
    )

    if stopping_result.should_stop:
        if stopping_result.disposition == "RECONCILE":
            # Ambiguous debits route to HUMAN review for bank reconciliation
            return Decision(
                case_id=case_id,
                action="HUMAN_REVIEW",
                routing="HUMAN",
                ev_score=0.0,
                guardrail_verdict=f"STOPPING_RULE_DIVERSION: {stopping_result.rule_name}"
            )
        else:
            # STOP -> BLOCK further recovery
            return Decision(
                case_id=case_id,
                action="BLOCK",
                routing="BLOCK",
                ev_score=0.0,
                guardrail_verdict=f"STOPPING_RULE_TERMINATION: {stopping_result.rule_name}"
            )

    # =========================================================================
    # STEP 2: Expected Value Ranking (Stratified Lift)
    # =========================================================================
    ranked_ev = rank_actions_by_ev(
        root_cause=diagnosis.root_cause,
        customer_risk_score=customer.risk_score,
        amount=transaction.amount
    )
    top_candidate = ranked_ev[0]
    candidate_action = top_candidate.action_type

    # =========================================================================
    # STEP 3: Hard Safety & Regulatory Guardrails
    # =========================================================================
    guardrail_result = SafetyGuardrails.evaluate(
        candidate_action=candidate_action,
        amount=transaction.amount,
        customer_opted_out=customer.opted_out,
        customer_contact_count=customer.contact_count,
        debited_customer=payment.debited_customer,
        duplicate_attempt_detected=has_dup_risk,
        current_time_utc=current_time_utc,
        customer_timezone=customer.timezone
    )

    final_action = guardrail_result.final_action

    # =========================================================================
    # STEP 4: Routing Partitioning (AUTO / HUMAN / BLOCK)
    # =========================================================================
    if final_action == "BLOCK":
        routing = "BLOCK"
    elif final_action == "HUMAN_REVIEW":
        routing = "HUMAN"
    elif final_action in ("RETRY", "DELAYED_RETRY", "PAYMENT_LINK", "REMINDER", "NO_ACTION"):
        # Bounded low-risk actions pass into AUTO execution
        routing = "AUTO"
    else:
        # Fallback safety routing
        routing = "HUMAN"

    verdict_str = f"{guardrail_result.routing_verdict}"
    if guardrail_result.blocking_rule:
        verdict_str += f" ({guardrail_result.blocking_rule})"

    return Decision(
        case_id=case_id,
        action=final_action,
        routing=routing,
        ev_score=top_candidate.ev_score,
        guardrail_verdict=verdict_str
    )
