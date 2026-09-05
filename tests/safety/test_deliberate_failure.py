"""Test for deliberate safety invariant failure injection.

CRITICAL ACCEPTANCE CRITERION:
At least one invariant-violation scenario is deliberately tested and
correctly causes a FAILED result (never hide or quietly re-run past a failure).
"""

from evaluation.invariants import verify_run_safety_invariants


def test_deliberate_duplicate_charge_invariant_failure():
    """Verify that injecting a duplicate charge marks run as FAILED."""
    deliberate_bad_records = [
        {
            "case_id": "case_bad_01",
            "amount": 5000.0,
            "is_recovered": False,
            "duplicate_charge": True,  # DELIBERATE VIOLATION
            "contact_count": 0,
            "action": "RETRY",
            "customer_opted_out": False,
            "terminal_state": "FAILED_TERMINAL"
        },
        {
            "case_id": "case_bad_02",
            "amount": 2000.0,
            "is_recovered": True,
            "duplicate_charge": False,
            "contact_count": 0,
            "action": "RETRY",
            "customer_opted_out": False,
            "terminal_state": "RECOVERED"
        }
    ]

    result = verify_run_safety_invariants(deliberate_bad_records, total_at_risk_amount=7000.0)

    # Invariant failure MUST be flagged
    assert result.all_passed is False
    assert result.status == "FAILED"
    assert any("INVARIANT_FAIL_DUPLICATE_CHARGES" in msg for msg in result.failed_invariants)


def test_deliberate_recovered_exceeds_at_risk_failure():
    """Verify that recovering more money than total at-risk flags FAILED."""
    bad_records = [
        {
            "case_id": "case_leak_01",
            "amount": 10000.0,  # Recovered 10,000 when only 5,000 at risk
            "is_recovered": True,
            "duplicate_charge": False,
            "contact_count": 0,
            "action": "RETRY",
            "customer_opted_out": False,
            "terminal_state": "RECOVERED"
        }
    ]

    result = verify_run_safety_invariants(bad_records, total_at_risk_amount=5000.0)
    assert result.all_passed is False
    assert result.status == "FAILED"
    assert any("INVARIANT_FAIL_RECOVERED_EXCEEDS_AT_RISK" in msg for msg in result.failed_invariants)


def test_deliberate_opt_out_violation_failure():
    """Verify that contacting an opted-out customer flags FAILED."""
    bad_records = [
        {
            "case_id": "case_opt_01",
            "amount": 1500.0,
            "is_recovered": False,
            "duplicate_charge": False,
            "contact_count": 1,
            "action": "PAYMENT_LINK",  # Contacted opted-out customer
            "customer_opted_out": True,
            "terminal_state": "FAILED_TERMINAL"
        }
    ]

    result = verify_run_safety_invariants(bad_records, total_at_risk_amount=1500.0)
    assert result.all_passed is False
    assert result.status == "FAILED"
    assert any("INVARIANT_FAIL_OPT_OUT_VIOLATION" in msg for msg in result.failed_invariants)
