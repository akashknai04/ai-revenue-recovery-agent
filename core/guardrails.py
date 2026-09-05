"""Safety and Policy Guardrail Engine.

NON-NEGOTIABLE PRINCIPLE:
Guardrails ALWAYS evaluate AFTER EV ranking and can override or block
the EV-preferred action. Economics NEVER bypasses safety or compliance.

Named Regulatory Anchors:
1. TRAI DND Regulations (The Telecom Commercial Communications Customer Preference Regulations, 2018)
2. RBI Fair Practices Code for Lenders / Recovery Agents (RBI Master Circular on Fair Practices Code)
3. Digital Personal Data Protection (DPDP) Act 2023
4. NPCI / Payment Aggregator Duplicate Payment Protection Guidelines
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class GuardrailEvaluationResult:
    allowed: bool
    final_action: str  # Original action if passed, or overridden action (e.g. HUMAN_REVIEW or BLOCK)
    routing_verdict: str  # PASSED, OVERRIDDEN, BLOCKED
    blocking_rule: Optional[str] = None
    regulatory_anchor: Optional[str] = None
    reason: Optional[str] = None


class SafetyGuardrails:
    """Evaluates and enforces regulatory compliance and safety invariants."""

    HIGH_VALUE_THRESHOLD: float = 50000.0  # INR 50,000 threshold requiring human oversight
    MAX_CONTACTS_PER_CASE: int = 2  # RBI Fair Practices Code limit

    @classmethod
    def evaluate(
        cls,
        candidate_action: str,
        amount: float,
        customer_opted_out: bool,
        customer_contact_count: int,
        debited_customer: bool,
        duplicate_attempt_detected: bool,
        current_time_utc: datetime,
        customer_timezone: str = "Asia/Kolkata",
        message_payload: Optional[Dict[str, Any]] = None
    ) -> GuardrailEvaluationResult:
        """Evaluate candidate action against all hard safety guardrails.

        Returns GuardrailEvaluationResult. Can OVERRIDE or BLOCK high-EV actions.
        """
        # =====================================================================
        # GUARDRAIL 1: Duplicate-Payment Protection & Idempotency Invariant
        # STATUTORY ANCHOR: RBI Payment Aggregator Guidelines / NPCI Core Invariants
        # =====================================================================
        # If customer has already been debited or duplicate attempt was flagged,
        # an automated RETRY or DELAYED_RETRY risks double debiting the customer.
        if candidate_action in ("RETRY", "DELAYED_RETRY"):
            if debited_customer or duplicate_attempt_detected:
                return GuardrailEvaluationResult(
                    allowed=False,
                    final_action="BLOCK",
                    routing_verdict="BLOCKED",
                    blocking_rule="PREVENT_DUPLICATE_DEBIT",
                    regulatory_anchor="RBI Payment Aggregator Guidelines / NPCI Core Invariants",
                    reason="Customer debited or duplicate attempt flagged. Direct retry blocked to prevent double debit."
                )

        # =====================================================================
        # GUARDRAIL 2: Customer Opt-Out / DND Registration
        # STATUTORY ANCHOR: TRAI DND regulations (TCCCPR 2018, Regulation 3)
        # =====================================================================
        # Unsolicited commercial communication to registered opt-out users is illegal.
        if customer_opted_out:
            if candidate_action in ("PAYMENT_LINK", "REMINDER", "VOICE_CALL"):
                return GuardrailEvaluationResult(
                    allowed=False,
                    final_action="BLOCK",
                    routing_verdict="BLOCKED",
                    blocking_rule="TRAI_DND_OPT_OUT",
                    regulatory_anchor="TRAI DND regulations (TCCCPR 2018, Regulation 3)",
                    reason="Customer registered on National Do Not Call / Opt-out list. Outbound contact strictly prohibited."
                )

        # =====================================================================
        # GUARDRAIL 3: Contact Hours Compliance (09:00 - 21:00)
        # STATUTORY ANCHOR: TRAI DND regulations (TCCCPR 2018, Regulation 12)
        # =====================================================================
        # Outbound contact permitted ONLY between 09:00 and 21:00 customer local time.
        if candidate_action in ("PAYMENT_LINK", "REMINDER", "VOICE_CALL"):
            try:
                local_tz = ZoneInfo(customer_timezone)
            except Exception:
                local_tz = ZoneInfo("Asia/Kolkata")

            local_time = current_time_utc.astimezone(local_tz)
            local_hour = local_time.hour

            if local_hour < 9 or local_hour >= 21:
                return GuardrailEvaluationResult(
                    allowed=False,
                    final_action="DELAYED_RETRY" if candidate_action in ("PAYMENT_LINK", "REMINDER") else "BLOCK",
                    routing_verdict="OVERRIDDEN",
                    blocking_rule="TRAI_CONTACT_HOURS_VIOLATION",
                    regulatory_anchor="TRAI DND regulations (TCCCPR 2018, Regulation 12)",
                    reason=f"Customer local time is {local_time.strftime('%H:%M %Z')}. Outbound communication prohibited outside 09:00 - 21:00."
                )

        # =====================================================================
        # GUARDRAIL 4: Recovery Conduct & Frequency Caps (No Harassment)
        # STATUTORY ANCHOR: RBI Fair Practices Code for recovery agents (RBI/2022-23/108)
        # =====================================================================
        # Repeated unwanted contact or exceeding contact caps constitutes harassment.
        if candidate_action in ("PAYMENT_LINK", "REMINDER", "VOICE_CALL"):
            if customer_contact_count >= cls.MAX_CONTACTS_PER_CASE:
                return GuardrailEvaluationResult(
                    allowed=False,
                    final_action="BLOCK",
                    routing_verdict="BLOCKED",
                    blocking_rule="RBI_CONTACT_CAP_EXCEEDED",
                    regulatory_anchor="RBI Fair Practices Code for recovery agents (RBI/2022-23/108)",
                    reason=f"Contact cap ({cls.MAX_CONTACTS_PER_CASE} attempts) exceeded. Outbound contact ceased under Fair Practices Code."
                )

        # =====================================================================
        # GUARDRAIL 5: High-Value Threshold Human Oversight
        # STATUTORY ANCHOR: Financial Prudence & RBI Large Value Transaction Supervision
        # =====================================================================
        # Transactions exceeding INR 50,000 cannot be autonomously recovered without human review.
        if amount > cls.HIGH_VALUE_THRESHOLD:
            if candidate_action in ("RETRY", "DELAYED_RETRY", "PAYMENT_LINK", "REMINDER", "VOICE_CALL"):
                return GuardrailEvaluationResult(
                    allowed=False,
                    final_action="HUMAN_REVIEW",
                    routing_verdict="OVERRIDDEN",
                    blocking_rule="HIGH_VALUE_MANDATORY_HUMAN_REVIEW",
                    regulatory_anchor="Financial Prudence & RBI Large Value Transaction Supervision",
                    reason=f"Amount INR {amount:,.2f} exceeds high-value threshold (INR 50,000). Escalated to human review."
                )

        # =====================================================================
        # GUARDRAIL 6: Handling of Customer Financial/PII Data
        # STATUTORY ANCHOR: DPDP Act 2023 (Section 8 - Data Security Safeguards)
        # =====================================================================
        # Message payloads must not expose raw financial PII (unmasked cards, CVVs, PINs).
        if message_payload:
            payload_str = str(message_payload).lower()
            if any(forbidden in payload_str for forbidden in ["cvv", "card_number", "pin", "password"]):
                return GuardrailEvaluationResult(
                    allowed=False,
                    final_action="BLOCK",
                    routing_verdict="BLOCKED",
                    blocking_rule="DPDP_PII_EXPOSURE_VIOLATION",
                    regulatory_anchor="DPDP Act 2023 (Section 8 - Data Security Safeguards)",
                    reason="Message payload contains sensitive financial authentication credentials. Blocked under DPDP Act."
                )

        # All guardrails passed
        return GuardrailEvaluationResult(
            allowed=True,
            final_action=candidate_action,
            routing_verdict="PASSED"
        )
