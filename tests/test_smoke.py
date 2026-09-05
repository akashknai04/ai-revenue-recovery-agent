"""Smoke tests for Phase 1 entities."""

import pytest
from core.entities import (
    RevenueEvent,
    Transaction,
    Payment,
    Customer,
    Diagnosis,
    Action,
    Decision,
    PromiseToPay,
    LedgerEvent,
    Experiment,
)


def test_revenue_event_creation():
    event = RevenueEvent(
        source="payment_gateway",
        entity_id="txn_123",
        amount=1500.0,
        status="FAILED",
        timestamps={"initiated": "2026-09-05T00:00:00Z"},
        raw_payload={"code": "BAD_CVV"}
    )
    assert event.source == "payment_gateway"
    assert event.amount == 1500.0
    assert event.to_dict()["status"] == "FAILED"


def test_transaction_and_payment_creation():
    txn = Transaction(
        id="case_001",
        customer_id="cust_001",
        amount=4999.0,
        currency="INR",
        state="FAILED",
        failure_code="INSUFFICIENT_FUNDS"
    )
    payment = Payment(
        id="pay_001",
        transaction_id=txn.id,
        provider_reference="ref_abc123",
        amount=4999.0,
        status="FAILED",
        debited_customer=False,
        confirmed_merchant=False
    )
    assert txn.state == "FAILED"
    assert payment.debited_customer is False


def test_customer_creation():
    cust = Customer(
        id="cust_001",
        name="Aarav Sharma",
        phone="+919876543210",
        email="aarav@example.com",
        risk_score=0.25,
        opted_out=False,
        contact_count=1,
        timezone="Asia/Kolkata"
    )
    assert cust.name == "Aarav Sharma"
    assert cust.risk_score == 0.25


def test_diagnosis_and_action_creation():
    diag = Diagnosis(
        case_id="case_001",
        root_cause="INSUFFICIENT_FUNDS",
        confidence=0.92,
        evidence=["bank_error_code: 51", "balance_check_failed"]
    )
    act = Action(
        action_type="DELAYED_RETRY",
        cost=2.5,
        risk=0.1,
        expected_effect="Wait for salary credit before retry",
        contact_frequency_cap=2,
        stopping_condition="MAX_RETRIES_REACHED"
    )
    assert diag.confidence == 0.92
    assert act.action_type == "DELAYED_RETRY"


def test_decision_creation():
    decision = Decision(
        case_id="case_001",
        action="DELAYED_RETRY",
        routing="AUTO",
        ev_score=420.5,
        guardrail_verdict="PASSED"
    )
    assert decision.routing == "AUTO"
    assert decision.ev_score == 420.5


def test_promise_to_pay_creation():
    ptp = PromiseToPay(
        id="ptp_001",
        case_id="case_001",
        promised_amount=4999.0,
        promised_date="2026-09-10",
        status="pending"
    )
    assert ptp.status == "pending"

    # Test invalid status
    with pytest.raises(ValueError):
        PromiseToPay(
            id="ptp_002",
            case_id="case_001",
            promised_amount=4999.0,
            promised_date="2026-09-10",
            status="invalid_status"
        )


def test_ledger_event_and_experiment():
    ledger = LedgerEvent(
        event_id="evt_001",
        case_id="case_001",
        event_type="DIAGNOSIS_RECORDED",
        payload={"root_cause": "INSUFFICIENT_FUNDS"},
        prev_hash="genesis"
    )
    exp = Experiment(
        id="exp_001",
        config_version="v1.0",
        seed=42,
        status="PENDING"
    )
    assert ledger.prev_hash == "genesis"
    assert exp.seed == 42
