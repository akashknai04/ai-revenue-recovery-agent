"""Unit tests for Phase 7: Expected Value calculation and Safety Guardrails."""

from datetime import datetime, timezone
import pytest
from core.ev import calculate_action_ev, rank_actions_by_ev, compute_wilson_score_ci
from core.guardrails import SafetyGuardrails, GuardrailEvaluationResult


# -------------------------------------------------------------
# EV Calculation & Confidence Interval Tests
# -------------------------------------------------------------

def test_ev_calculation_with_confidence_intervals():
    """Verify EV formula, lift calculation, and confidence intervals."""
    # Test for ISSUER_TECHNICAL_DECLINE, LOW risk customer, amount INR 10,000
    res = calculate_action_ev(
        action_type="DELAYED_RETRY",
        root_cause="ISSUER_TECHNICAL_DECLINE",
        customer_risk_score=0.15,
        amount=10000.0
    )

    assert res.action_type == "DELAYED_RETRY"
    assert res.incremental_recovery_rate > 0.0
    assert 0.0 <= res.ci_lower <= res.ci_upper <= 1.0
    assert res.ev_score > 0.0
    assert res.action_cost == 3.0

    # Test ranking returns sorted actions
    ranked = rank_actions_by_ev(
        root_cause="ISSUER_TECHNICAL_DECLINE",
        customer_risk_score=0.2,
        amount=5000.0
    )
    assert len(ranked) > 1
    # Check monotonic descending sort
    for i in range(len(ranked) - 1):
        assert ranked[i].ev_score >= ranked[i + 1].ev_score


def test_wilson_score_confidence_interval():
    """Verify Wilson score CI math."""
    lower, upper = compute_wilson_score_ci(p=0.8, n=100)
    assert 0.70 <= lower <= 0.80
    assert 0.80 <= upper <= 0.90


# -------------------------------------------------------------
# Statutory Regulatory Anchor Verification
# -------------------------------------------------------------

def test_every_guardrail_rule_has_named_regulatory_anchor():
    """CRITICAL ACCEPTANCE CRITERION: Every guardrail rule has its named regulatory anchor."""
    # Check TRAI DND opt-out
    res_opt = SafetyGuardrails.evaluate(
        candidate_action="PAYMENT_LINK",
        amount=1000.0,
        customer_opted_out=True,
        customer_contact_count=0,
        debited_customer=False,
        duplicate_attempt_detected=False,
        current_time_utc=datetime(2026, 9, 5, 6, 0, tzinfo=timezone.utc)  # 11:30 IST
    )
    assert "TRAI DND" in (res_opt.regulatory_anchor or "")

    # Check TRAI Contact Hours
    res_hours = SafetyGuardrails.evaluate(
        candidate_action="REMINDER",
        amount=1000.0,
        customer_opted_out=False,
        customer_contact_count=0,
        debited_customer=False,
        duplicate_attempt_detected=False,
        current_time_utc=datetime(2026, 9, 5, 2, 0, tzinfo=timezone.utc)  # 07:30 IST (before 09:00)
    )
    assert "TRAI" in (res_hours.regulatory_anchor or "")

    # Check RBI Fair Practices Code contact cap
    res_rbi = SafetyGuardrails.evaluate(
        candidate_action="PAYMENT_LINK",
        amount=1000.0,
        customer_opted_out=False,
        customer_contact_count=2,  # Cap is 2
        debited_customer=False,
        duplicate_attempt_detected=False,
        current_time_utc=datetime(2026, 9, 5, 6, 0, tzinfo=timezone.utc)
    )
    assert "RBI Fair Practices Code" in (res_rbi.regulatory_anchor or "")

    # Check DPDP Act
    res_dpdp = SafetyGuardrails.evaluate(
        candidate_action="PAYMENT_LINK",
        amount=1000.0,
        customer_opted_out=False,
        customer_contact_count=0,
        debited_customer=False,
        duplicate_attempt_detected=False,
        current_time_utc=datetime(2026, 9, 5, 6, 0, tzinfo=timezone.utc),
        message_payload={"text": "Please enter CVV 123"}
    )
    assert "DPDP Act" in (res_dpdp.regulatory_anchor or "")


# -------------------------------------------------------------
# Guardrail Overrides High-EV Action Test
# -------------------------------------------------------------

def test_high_ev_action_blocked_when_violating_guardrail_guardrail_wins():
    """CRITICAL ACCEPTANCE CRITERION: A test proving high-EV action gets blocked when it violates a guardrail (guardrail wins)."""
    # Scenario A: High amount (INR 75,000). EV ranking strongly favors DELAYED_RETRY.
    # But guardrail mandates HUMAN_REVIEW for > INR 50,000.
    ev_ranked = rank_actions_by_ev(
        root_cause="ISSUER_TECHNICAL_DECLINE",
        customer_risk_score=0.1,
        amount=75000.0
    )
    top_ev_action = ev_ranked[0].action_type
    assert top_ev_action == "DELAYED_RETRY"
    assert ev_ranked[0].ev_score > 20000.0  # Massive positive EV

    # Evaluate guardrail on top EV action
    guardrail_verdict = SafetyGuardrails.evaluate(
        candidate_action=top_ev_action,
        amount=75000.0,
        customer_opted_out=False,
        customer_contact_count=0,
        debited_customer=False,
        duplicate_attempt_detected=False,
        current_time_utc=datetime(2026, 9, 5, 6, 0, tzinfo=timezone.utc)
    )

    # The high-EV action is OVERRIDDEN by the guardrail
    assert guardrail_verdict.allowed is False
    assert guardrail_verdict.final_action == "HUMAN_REVIEW"
    assert guardrail_verdict.routing_verdict == "OVERRIDDEN"
    assert guardrail_verdict.blocking_rule == "HIGH_VALUE_MANDATORY_HUMAN_REVIEW"

    # Scenario B: High EV action on duplicate debit attempt is strictly BLOCKED
    guardrail_dup = SafetyGuardrails.evaluate(
        candidate_action="RETRY",
        amount=10000.0,
        customer_opted_out=False,
        customer_contact_count=0,
        debited_customer=True,  # Customer already debited
        duplicate_attempt_detected=False,
        current_time_utc=datetime(2026, 9, 5, 6, 0, tzinfo=timezone.utc)
    )
    assert guardrail_dup.allowed is False
    assert guardrail_dup.final_action == "BLOCK"
    assert guardrail_dup.routing_verdict == "BLOCKED"
    assert guardrail_dup.blocking_rule == "PREVENT_DUPLICATE_DEBIT"
