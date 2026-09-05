"""Recovery Action Catalog.

Defines all permissible recovery actions with mandatory economic and
regulatory attributes: eligibility rule, cost, risk, expected effect,
contact frequency cap, and stopping condition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from core.entities import Action


@dataclass(frozen=True)
class ActionDefinition:
    action_type: str
    cost: float
    risk: float
    expected_effect: str
    contact_frequency_cap: int
    stopping_condition: str
    # This field is descriptive metadata only; actual eligibility is enforced by stopping_rules.py and guardrails.py, not by this string.
    eligibility_description: str

    def to_action_entity(self) -> Action:
        return Action(
            action_type=self.action_type,
            cost=self.cost,
            risk=self.risk,
            expected_effect=self.expected_effect,
            contact_frequency_cap=self.contact_frequency_cap,
            stopping_condition=self.stopping_condition
        )


ACTION_CATALOG: Dict[str, ActionDefinition] = {
    "NO_ACTION": ActionDefinition(
        action_type="NO_ACTION",
        cost=0.0,
        risk=0.0,
        expected_effect="Passive observation; relies exclusively on natural recovery or customer-initiated re-checkout.",
        contact_frequency_cap=0,
        stopping_condition="CASE_TERMINATED",
        eligibility_description="Always eligible; fallback baseline action."
    ),
    "RETRY": ActionDefinition(
        action_type="RETRY",
        cost=3.0,
        risk=0.35,  # Moderate risk of repeated bank decline or duplicate debit if status uncertain
        expected_effect="Immediate automated backend API retry without contacting the customer.",
        contact_frequency_cap=0,
        stopping_condition="MAX_RETRIES_EXCEEDED_OR_AMBIGUOUS_DEBIT",
        eligibility_description="Eligible only when status is definitely FAILED, customer was NOT debited, and retry count < 3."
    ),
    "DELAYED_RETRY": ActionDefinition(
        action_type="DELAYED_RETRY",
        cost=3.0,
        risk=0.15,
        expected_effect="Automated backend retry scheduled after an optimal cooldown window (15-60m) to allow bank switch recovery.",
        contact_frequency_cap=0,
        stopping_condition="MAX_RETRIES_EXCEEDED_OR_TIMEOUT",
        eligibility_description="Eligible for ISSUER_TECHNICAL_DECLINE when customer was NOT debited and retry count < 2."
    ),
    "PAYMENT_LINK": ActionDefinition(
        action_type="PAYMENT_LINK",
        cost=1.5,
        risk=0.10,
        expected_effect="Outbound SMS/WhatsApp message containing an alternate payment link enabling checkout via other rails.",
        contact_frequency_cap=2,
        stopping_condition="CONTACT_BUDGET_EXCEEDED_OR_OPT_OUT",
        eligibility_description="Eligible for AUTHENTICATION_ABANDONED, INVALID_PAYMENT_INSTRUMENT, or INSUFFICIENT_FUNDS with DND compliant contact."
    ),
    "REMINDER": ActionDefinition(
        action_type="REMINDER",
        cost=1.0,
        risk=0.05,
        expected_effect="Soft informational notification reminding customer of pending cart/payment attempt.",
        contact_frequency_cap=1,
        stopping_condition="CONTACT_BUDGET_EXCEEDED_OR_OPT_OUT",
        eligibility_description="Eligible for low-risk customers within permissible contact hours (09:00 - 21:00)."
    ),
    "HUMAN_REVIEW": ActionDefinition(
        action_type="HUMAN_REVIEW",
        cost=45.0,
        risk=0.05,
        expected_effect="Escalation to human operations specialist for bank reconciliation, high-value settlement, or manual fraud review.",
        contact_frequency_cap=0,
        stopping_condition="RESOLVED_OR_RECONCILED",
        eligibility_description="Eligible for ambiguous debits, high-value orders (> INR 50,000), or suspicious anomaly signals."
    ),
    "BLOCK": ActionDefinition(
        action_type="BLOCK",
        cost=0.0,
        risk=0.0,
        expected_effect="Hard block on all automated and manual recovery attempts to prevent financial or compliance damage.",
        contact_frequency_cap=0,
        stopping_condition="IMMEDIATE_TERMINATION",
        eligibility_description="Eligible when duplicate debit is detected, customer opted out, or severe risk invariant triggered."
    ),
    "PROMISE_TO_PAY": ActionDefinition(
        action_type="PROMISE_TO_PAY",
        cost=0.0,
        risk=0.10,
        expected_effect="Customer commitment state established following PAYMENT_LINK/REMINDER; halts active contacts until promised date.",
        contact_frequency_cap=0,
        stopping_condition="PROMISE_DUE_DATE_REACHED",
        eligibility_description="Eligible only upon customer explicit commitment to pay by a specified date."
    ),
    "VOICE_CALL": ActionDefinition(
        action_type="VOICE_CALL",
        cost=6.0,
        risk=0.25,
        expected_effect="Interactive conversational call in Hinglish to explain degradation and collect payment or promise.",
        contact_frequency_cap=1,
        stopping_condition="CONTACT_BUDGET_EXCEEDED_OR_OPT_OUT",
        eligibility_description="Eligible for Phase 12 stretch under strict TRAI contact hours and frequency caps."
    )
}


def get_action_definition(action_type: str) -> ActionDefinition:
    """Retrieve the action definition from the catalog."""
    if action_type not in ACTION_CATALOG:
        raise KeyError(f"Action '{action_type}' is not registered in the recovery action catalog.")
    return ACTION_CATALOG[action_type]
