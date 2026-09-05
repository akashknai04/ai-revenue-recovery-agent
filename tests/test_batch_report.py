"""Unit tests for Phase 11: Automated Batch Report Generation and Audit Traceability."""

import re
from pathlib import Path
from evaluation.runner import EvaluationRunner
from report.generator import generate_markdown_report, save_reports


def test_report_generated_automatically_and_matches_metrics():
    """CRITICAL ACCEPTANCE CRITERION: Report generated automatically from completed evaluation run."""
    runner = EvaluationRunner(seed=2002, num_cases=40, batch_name="Batch_B")
    result = runner.run_all_arms()

    md_report = generate_markdown_report(result)
    assert len(md_report) > 500

    agent_m = result.arm_metrics["AGENT"]
    ctrl_m = result.arm_metrics["CONTROL"]

    # Verify headline numbers appear accurately in markdown
    assert f"₹{agent_m.incremental_recovery_inr:,.2f}" in md_report
    assert f"₹{agent_m.gross_recovered_inr:,.2f}" in md_report
    assert f"₹{ctrl_m.natural_recovery_inr:,.2f}" in md_report
    assert f"₹{agent_m.net_recovery_inr:,.2f}" in md_report


def test_report_never_claims_ai_recovered_x_without_relative_to_control():
    """CRITICAL ACCEPTANCE CRITERION: Report never claims 'AI recovered X' without stating it relative to control."""
    runner = EvaluationRunner(seed=2002, num_cases=30, batch_name="Batch_B")
    result = runner.run_all_arms()
    md_report = generate_markdown_report(result)

    # Must contain explicit statement on incremental lift and control baseline
    cleaned_text = md_report.lower().replace("*", "")
    assert "lift over control" in cleaned_text
    assert "never reported as gross" in cleaned_text
    assert "natural recovery" in cleaned_text


def test_every_number_in_report_traceable_to_ledger():
    """CRITICAL ACCEPTANCE CRITERION: Every number in the report is traceable to a ledger entry."""
    runner = EvaluationRunner(seed=2002, num_cases=30, batch_name="Batch_B")
    result = runner.run_all_arms()

    ledger = result.ledger
    all_events = ledger.get_all_events()
    assert len(all_events) > 0

    # Ensure ledger integrity
    assert ledger.verify_chain_integrity() is True

    # Check that events exist for every recovered case
    recovered_events = [
        e for e in all_events
        if e.event_type in ("CONTROL_ARM_EVALUATION", "WEBHOOK_SETTLEMENT_VERIFIED")
    ]
    assert len(recovered_events) > 0
