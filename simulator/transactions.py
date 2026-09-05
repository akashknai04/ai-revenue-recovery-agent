"""Synthetic transaction generator."""

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple
from core.entities import Payment, Transaction
from simulator.failures import FAILURE_PROFILES


def generate_transaction_and_payment(
    case_id: str,
    customer_id: str,
    category: str,
    rng: random.Random,
    base_time: datetime
) -> Tuple[Transaction, Payment, Dict[str, Any]]:
    """Generate a transaction, initial payment attempt, and observation telemetry."""
    # Amount distribution: 85% normal (₹200 - ₹15,000), 15% high value (₹50,001 - ₹95,000)
    if rng.random() < 0.15:
        amount = round(rng.uniform(50001.0, 95000.0), 2)
    else:
        amount = round(rng.uniform(250.0, 12500.0), 2)

    profile = FAILURE_PROFILES[category]
    failure_code = rng.choice(profile["codes"])
    error_msg = rng.choice(profile["sample_messages"])
    http_status = profile["http_status"]

    # Ambiguous debit scenario: customer might be debited while merchant is unconfirmed
    is_ambiguous = (category == "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT")
    is_debited = True if is_ambiguous and (rng.random() < 0.70) else False

    # 8% of transactions have duplicate payment risk (e.g. user retried in another tab)
    has_dup_risk = rng.random() < 0.08

    txn_time = (base_time + timedelta(minutes=rng.randint(0, 1440))).isoformat()

    metadata = {
        "channel": rng.choice(["UPI", "CARD", "NETBANKING"]),
        "http_status": http_status,
        "error_message": error_msg,
        "attempt_count": 1,
        "is_ambiguous_debit": is_ambiguous,
        "duplicate_attempt_detected": has_dup_risk,
        "customer_reported_sms": is_debited
    }

    state = "PENDING" if is_ambiguous else "FAILED"

    txn = Transaction(
        id=case_id,
        customer_id=customer_id,
        amount=amount,
        currency="INR",
        created_at=txn_time,
        state=state,
        failure_code=failure_code,
        metadata=metadata
    )

    payment = Payment(
        id=f"pay_{case_id}",
        transaction_id=case_id,
        provider_reference=f"ref_{rng.randint(1000000, 9999999)}" if not is_ambiguous else None,
        amount=amount,
        status=state,
        debited_customer=is_debited,
        confirmed_merchant=False
    )

    return txn, payment, metadata
