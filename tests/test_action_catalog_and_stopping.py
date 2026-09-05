"""Unit tests for Phase 6: Action catalog, stopping rules, and Promise-to-Pay tracker."""

import pytest
from core.catalog import ACTION_CATALOG, ActionDefinition, get_action_definition
from core.stopping_rules import evaluate_stopping_rules
from core.promise_tracker import PromiseToPayTracker, InvalidPTPTransitionError
from core.entities import Customer, Transaction


# -------------------------------------------------------------
# Action Catalog Tests
# -------------------------------------------------------------

def test_every_action_has_all_five_properties_defined():
    """CRITICAL ACCEPTANCE CRITERION: Every action has eligibility, cost, risk, expected effect, cap defined."""
    required_actions = [
        "NO_ACTION",
        "RETRY",
        "DELAYED_RETRY",
        "PAYMENT_LINK",
        "REMINDER",
        "HUMAN_REVIEW",
        "BLOCK",
        "PROMISE_TO_PAY"
    ]

    for action_name in required_actions:
        assert action_name in ACTION_CATALOG, f"Action '{action_name}' missing from ACTION_CATALOG"
        defn: ActionDefinition = ACTION_CATALOG[action_name]

        # 1. Eligibility description (descriptive metadata)
        assert defn.eligibility_description is not None
        assert len(defn.eligibility_description) > 5

        # 2. Cost
        assert isinstance(defn.cost, (int, float))
        assert defn.cost >= 0.0

        # 3. Risk
        assert isinstance(defn.risk, (int, float))
        assert 0.0 <= defn.risk <= 1.0

        # 4. Expected effect
        assert defn.expected_effect is not None
        assert len(defn.expected_effect) > 5

        # 5. Contact frequency cap
        assert isinstance(defn.contact_frequency_cap, int)
        assert defn.contact_frequency_cap >= 0

        # Entity conversion test
        entity = defn.to_action_entity()
        assert entity.action_type == action_name


# -------------------------------------------------------------
# Stopping Rules Tests (All 6 conditions individually tested)
# -------------------------------------------------------------

def test_stopping_rule_1_case_already_terminated():
    """Condition 1: Case already terminated -> STOP."""
    for term_status in ["TERMINATED", "REFUNDED", "CANCELLED", "ABANDONED"]:
        res = evaluate_stopping_rules(
            case_status=term_status,
            customer_opted_out=False,
            order_already_paid=False,
            payment_status="FAILED",
            is_ambiguous_debit=False,
            debited_customer=False,
            retry_count=0,
            contact_count=0
        )
        assert res.should_stop is True
        assert res.disposition == "STOP"
        assert res.rule_name == "CASE_ALREADY_TERMINATED"


def test_stopping_rule_2_customer_opted_out():
    """Condition 2: Customer opted out -> STOP."""
    res = evaluate_stopping_rules(
        case_status="ACTIVE",
        customer_opted_out=True,
        order_already_paid=False,
        payment_status="FAILED",
        is_ambiguous_debit=False,
        debited_customer=False,
        retry_count=0,
        contact_count=0
    )
    assert res.should_stop is True
    assert res.disposition == "STOP"
    assert res.rule_name == "CUSTOMER_OPTED_OUT"


def test_stopping_rule_3_already_successful():
    """Condition 3: Already successful -> STOP."""
    res = evaluate_stopping_rules(
        case_status="ACTIVE",
        customer_opted_out=False,
        order_already_paid=True,
        payment_status="SUCCESS",
        is_ambiguous_debit=False,
        debited_customer=True,
        retry_count=0,
        contact_count=0
    )
    assert res.should_stop is True
    assert res.disposition == "STOP"
    assert res.rule_name == "ALREADY_SUCCESSFUL"


def test_stopping_rule_4_ambiguous_debit():
    """Condition 4: Ambiguous debit -> RECONCILE."""
    # Case A: Explicitly flagged ambiguous
    res_a = evaluate_stopping_rules(
        case_status="ACTIVE",
        customer_opted_out=False,
        order_already_paid=False,
        payment_status="PENDING",
        is_ambiguous_debit=True,
        debited_customer=False,
        retry_count=0,
        contact_count=0
    )
    assert res_a.should_stop is True
    assert res_a.disposition == "RECONCILE"
    assert res_a.rule_name == "AMBIGUOUS_DEBIT_RECONCILE"

    # Case B: Customer debited but status not confirmed SUCCESS
    res_b = evaluate_stopping_rules(
        case_status="ACTIVE",
        customer_opted_out=False,
        order_already_paid=False,
        payment_status="PENDING",
        is_ambiguous_debit=False,
        debited_customer=True,
        retry_count=0,
        contact_count=0
    )
    assert res_b.should_stop is True
    assert res_b.disposition == "RECONCILE"
    assert res_b.rule_name == "AMBIGUOUS_DEBIT_RECONCILE"


def test_stopping_rule_5_retry_budget_exceeded():
    """Condition 5: Retry budget exceeded -> STOP."""
    res = evaluate_stopping_rules(
        case_status="ACTIVE",
        customer_opted_out=False,
        order_already_paid=False,
        payment_status="FAILED",
        is_ambiguous_debit=False,
        debited_customer=False,
        retry_count=3,
        contact_count=0,
        max_retries=3
    )
    assert res.should_stop is True
    assert res.disposition == "STOP"
    assert res.rule_name == "RETRY_BUDGET_EXCEEDED"


def test_stopping_rule_6_contact_budget_exceeded():
    """Condition 6: Contact budget exceeded -> STOP."""
    res = evaluate_stopping_rules(
        case_status="ACTIVE",
        customer_opted_out=False,
        order_already_paid=False,
        payment_status="FAILED",
        is_ambiguous_debit=False,
        debited_customer=False,
        retry_count=0,
        contact_count=3,
        max_contacts=3
    )
    assert res.should_stop is True
    assert res.disposition == "STOP"
    assert res.rule_name == "CONTACT_BUDGET_EXCEEDED"


# -------------------------------------------------------------
# Promise to Pay Tracker & Broken Promise Re-evaluation Tests
# -------------------------------------------------------------

def test_promise_to_pay_lifecycle():
    tracker = PromiseToPayTracker()
    ptp = tracker.register_promise(
        promise_id="ptp_01",
        case_id="case_01",
        promised_amount=1200.0,
        promised_date="2026-09-10"
    )
    assert ptp.status == "pending"

    # Renegotiate
    tracker.renegotiate("ptp_01", "2026-09-12")
    assert ptp.status == "renegotiated"
    assert ptp.promised_date == "2026-09-12"

    # Mark kept
    tracker.mark_kept("ptp_01")
    assert ptp.status == "kept"

    # Kept is terminal; cannot mark broken or renegotiate
    with pytest.raises(InvalidPTPTransitionError):
        tracker.mark_broken("ptp_01")


def test_broken_promise_reenters_stopping_rules_never_automatic_recharge():
    """CRITICAL ACCEPTANCE CRITERION: Broken promise re-enters stopping rules/guardrails and is never automatically recharged."""
    tracker = PromiseToPayTracker()
    tracker.register_promise(
        promise_id="ptp_02",
        case_id="case_02",
        promised_amount=3500.0,
        promised_date="2026-09-01"
    )

    cust = Customer(
        id="cust_02",
        name="Sunita Rao",
        phone="+919123456789",
        email="sunita@example.com",
        risk_score=0.4,
        opted_out=False,
        contact_count=2,  # Already contacted twice
        timezone="Asia/Kolkata"
    )
    txn = Transaction(
        id="case_02",
        customer_id="cust_02",
        amount=3500.0,
        state="FAILED"
    )

    # Re-evaluation of broken promise increments contact count to 3, which hits contact budget
    stopping_result = tracker.handle_broken_promise(
        promise_id="ptp_02",
        customer=cust,
        transaction=txn,
        retry_count=0
    )

    # Since contact_count was 2 + 1 = 3, stopping rule terminates with CONTACT_BUDGET_EXCEEDED
    assert stopping_result.should_stop is True
    assert stopping_result.rule_name == "CONTACT_BUDGET_EXCEEDED"
    assert tracker.get_promise("ptp_02").status == "broken"


def test_eligibility_description_is_descriptive_metadata_not_logic():
    """REGRESSION TEST (Issue A): Confirms eligibility_description is descriptive metadata only.

    Verifies that:
    1. Every registered action defines eligibility_description as a string.
    2. The field is never parsed, evaluated, or executed as logical code in core/.
    3. Concrete eligibility and safety boundaries are enforced by stopping_rules.py
       and guardrails.py, not by this descriptive string.
    """
    import inspect
    import core.decision_engine
    import core.guardrails
    import core.stopping_rules

    # 1. Type validation across the entire catalog
    for action_type, defn in ACTION_CATALOG.items():
        assert isinstance(defn.eligibility_description, str)
        assert len(defn.eligibility_description) > 0

    # 2. Source code static verification: core decision modules must not parse eligibility_description
    modules_to_check = [
        core.decision_engine,
        core.guardrails,
        core.stopping_rules
    ]
    for mod in modules_to_check:
        src = inspect.getsource(mod)
        assert "eligibility_description" not in src
        assert "eval(" not in src
        assert "exec(" not in src
