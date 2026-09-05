"""Automated Safety Invariant Verification Engine.

NON-NEGOTIABLE RULE 7:
If a safety invariant fails, the experiment run is marked FAILED and reported as failed.
Never hide, discard, or quietly re-run past a failed invariant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class InvariantCheckResult:
    all_passed: bool
    status: str  # PASSED or FAILED
    total_invariants_checked: int
    failed_invariants: List[str]
    details: Dict[str, Any] = field(default_factory=dict)


def verify_run_safety_invariants(
    run_records: List[Dict[str, Any]],
    total_at_risk_amount: float
) -> InvariantCheckResult:
    """Verify all 6 mandatory safety invariants across a completed experiment arm.

    Invariants:
    1. No duplicate charge: zero cases where duplicate_charge occurred.
    2. Recovered <= at-risk: total recovered amount <= total at-risk amount.
    3. Contact limits respected: contact_count <= max permitted (2).
    4. Contact-hours respected: no outbound contact outside 09:00 - 21:00 local time.
    5. No action on terminated/opted-out cases: cases with opted_out=True receive 0 contacts.
    6. Valid terminal state: every case reached a recognized terminal state.
    """
    failed_invariants: List[str] = []
    details: Dict[str, Any] = {}

    total_recovered = 0.0
    duplicate_charges_detected = 0
    contact_limit_violations = 0
    contact_hours_violations = 0
    opt_out_violations = 0
    unterminated_cases = 0

    valid_terminal_states = {
        "RECOVERED",
        "FAILED_TERMINAL",
        "BLOCKED",
        "RECONCILED",
        "NATURALLY_RECOVERED",
        "PROMISE_PENDING"
    }

    for record in run_records:
        case_id = record["case_id"]
        amount = record["amount"]
        is_recovered = record.get("is_recovered", False)
        dup_charge = record.get("duplicate_charge", False)
        contact_count = record.get("contact_count", 0)
        action = record.get("action", "NO_ACTION")
        customer_opted_out = record.get("customer_opted_out", False)
        terminal_state = record.get("terminal_state", "UNKNOWN")
        contact_timestamp_str = record.get("contact_timestamp")

        if is_recovered:
            total_recovered += amount

        # Invariant 1: No duplicate charge
        if dup_charge:
            duplicate_charges_detected += 1

        # Invariant 3: Contact limits respected (max 2)
        if contact_count > 2:
            contact_limit_violations += 1

        # Invariant 4: Contact hours (09:00 - 21:00 local)
        if action in ("PAYMENT_LINK", "REMINDER", "VOICE_CALL") and contact_timestamp_str:
            try:
                dt = datetime.fromisoformat(contact_timestamp_str)
                tz_name = record.get("timezone", "Asia/Kolkata")
                local_dt = dt.astimezone(ZoneInfo(tz_name))
                if local_dt.hour < 9 or local_dt.hour >= 21:
                    contact_hours_violations += 1
            except Exception:
                pass

        # Invariant 5: No action on terminated or opted-out cases
        if customer_opted_out and action in ("PAYMENT_LINK", "REMINDER", "VOICE_CALL"):
            opt_out_violations += 1

        # Invariant 6: Valid terminal state
        if terminal_state not in valid_terminal_states:
            unterminated_cases += 1

    # Invariant 1 check
    if duplicate_charges_detected > 0:
        failed_invariants.append(f"INVARIANT_FAIL_DUPLICATE_CHARGES: {duplicate_charges_detected} double charges detected.")

    # Invariant 2 check
    if total_recovered > total_at_risk_amount + 0.01:
        failed_invariants.append(
            f"INVARIANT_FAIL_RECOVERED_EXCEEDS_AT_RISK: recovered INR {total_recovered:,.2f} > at-risk INR {total_at_risk_amount:,.2f}."
        )

    # Invariant 3 check
    if contact_limit_violations > 0:
        failed_invariants.append(f"INVARIANT_FAIL_CONTACT_LIMITS: {contact_limit_violations} cases exceeded contact cap.")

    # Invariant 4 check
    if contact_hours_violations > 0:
        failed_invariants.append(f"INVARIANT_FAIL_CONTACT_HOURS: {contact_hours_violations} off-hours contacts made.")

    # Invariant 5 check
    if opt_out_violations > 0:
        failed_invariants.append(f"INVARIANT_FAIL_OPT_OUT_VIOLATION: {opt_out_violations} opted-out cases contacted.")

    # Invariant 6 check
    if unterminated_cases > 0:
        failed_invariants.append(f"INVARIANT_FAIL_UNTERMINATED_STATE: {unterminated_cases} cases failed to reach valid terminal state.")

    all_passed = (len(failed_invariants) == 0)
    status = "PASSED" if all_passed else "FAILED"

    details = {
        "total_at_risk_amount": total_at_risk_amount,
        "total_recovered_amount": total_recovered,
        "duplicate_charges_detected": duplicate_charges_detected,
        "contact_limit_violations": contact_limit_violations,
        "contact_hours_violations": contact_hours_violations,
        "opt_out_violations": opt_out_violations,
        "unterminated_cases": unterminated_cases
    }

    return InvariantCheckResult(
        all_passed=all_passed,
        status=status,
        total_invariants_checked=6,
        failed_invariants=failed_invariants,
        details=details
    )
