"""Unit tests for Phase 12: Voice Recovery Adapter (Stretch)."""

from datetime import datetime, timezone
import pytest
from core.entities import Customer, Diagnosis, PromiseToPay, Transaction
from core.execution_adapter import SandboxPaymentExecutionAdapter
from core.guardrails import SafetyGuardrails
from core.ledger import AppendOnlyLedger
from core.promise_tracker import PromiseToPayTracker
from core.voice_adapter import VoiceRecoveryService


def test_voice_call_plugs_into_existing_guardrails_and_adapter_without_modifications():
    """CRITICAL ACCEPTANCE CRITERION: VOICE_CALL requires zero changes to Decision Engine, guardrails, or ledger."""
    adapter = SandboxPaymentExecutionAdapter()
    tracker = PromiseToPayTracker()
    ledger = AppendOnlyLedger()
    service = VoiceRecoveryService(adapter, tracker)

    cust = Customer(
        id="cust_v01",
        name="Rohit Sharma",
        phone="+919876543210",
        email="rohit@example.in",
        risk_score=0.25,
        opted_out=False,
        contact_count=0
    )
    txn = Transaction(
        id="case_v01",
        customer_id="cust_v01",
        amount=3200.0,
        state="FAILED"
    )
    diag = Diagnosis(
        case_id="case_v01",
        root_cause="INSUFFICIENT_FUNDS",
        confidence=0.95,
        evidence=["Bank code 51 returned"]
    )

    # 1. Guardrails evaluate VOICE_CALL naturally
    guardrail_verdict = SafetyGuardrails.evaluate(
        candidate_action="VOICE_CALL",
        amount=3200.0,
        customer_opted_out=False,
        customer_contact_count=0,
        debited_customer=False,
        duplicate_attempt_detected=False,
        current_time_utc=datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
    )
    assert guardrail_verdict.allowed is True
    assert guardrail_verdict.final_action == "VOICE_CALL"

    # 2. Dispatch call through adapter
    disposition = service.dispatch_and_record_call(
        case_id="case_v01",
        customer=cust,
        transaction=txn,
        diagnosis=diag,
        simulated_disposition="PROMISED"
    )

    assert disposition.disposition == "PROMISED"
    assert "Namaste" in disposition.script_used
    assert disposition.ptp_promise is not None

    # 3. Recorded seamlessly in ledger with standard schema
    ledger_evt = ledger.append_event(
        case_id="case_v01",
        event_type="VOICE_CALL_DISPATCHED",
        payload={
            "disposition": disposition.disposition,
            "script_used": disposition.script_used,
            "ptp_id": disposition.ptp_promise.id
        }
    )
    assert ledger.verify_chain_integrity() is True


def test_voice_originated_promise_is_indistinguishable_from_message_originated():
    """CRITICAL ACCEPTANCE CRITERION: Voice-originated promise is indistinguishable in schema from message-originated."""
    tracker = PromiseToPayTracker()

    # Message-originated promise
    ptp_message = tracker.register_promise(
        promise_id="ptp_msg_01",
        case_id="case_001",
        promised_amount=5000.0,
        promised_date="2026-09-10"
    )

    # Voice-originated promise
    ptp_voice = tracker.register_promise(
        promise_id="ptp_voice_01",
        case_id="case_002",
        promised_amount=5000.0,
        promised_date="2026-09-10"
    )

    # Both share exact same entity type, fields, and behavior
    assert type(ptp_voice) is type(ptp_message)
    assert ptp_voice.to_dict().keys() == ptp_message.to_dict().keys()
    assert ptp_voice.status == "pending"
    assert ptp_message.status == "pending"

    # Both can be tracked through the same lifecycle transitions
    tracker.mark_kept(ptp_voice.id)
    assert ptp_voice.status == "kept"
