"""Unit tests for Phase 10: Four-Arm Evaluation and Reproducibility."""

from evaluation.runner import EvaluationRunner


def test_four_arms_produce_comparable_metrics_on_same_batch():
    """CRITICAL ACCEPTANCE CRITERION: All four arms run on the same Batch B and produce comparable metrics."""
    runner = EvaluationRunner(seed=2002, num_cases=50, batch_name="Batch_B")
    result = runner.run_all_arms()

    assert "CONTROL" in result.arm_metrics
    assert "NAIVE" in result.arm_metrics
    assert "RULES" in result.arm_metrics
    assert "AGENT" in result.arm_metrics

    control = result.arm_metrics["CONTROL"]
    naive = result.arm_metrics["NAIVE"]
    rules = result.arm_metrics["RULES"]
    agent = result.arm_metrics["AGENT"]

    # All arms evaluated same number of cases and same at-risk amount
    assert control.total_cases == 50
    assert naive.total_cases == 50
    assert rules.total_cases == 50
    assert agent.total_cases == 50
    assert control.total_at_risk_inr == agent.total_at_risk_inr

    # Incremental recovery integrity:
    # Control incremental recovery is ALWAYS 0.0 by definition
    assert control.incremental_recovery_inr == 0.0

    # Agent incremental recovery = Agent gross - Control natural
    expected_agent_inc = round(agent.gross_recovered_inr - control.natural_recovery_inr, 2)
    assert agent.incremental_recovery_inr == expected_agent_inc

    # Agent safety invariants must pass
    assert agent.safety_invariants_status == "PASSED"
    assert agent.duplicate_charges_count == 0

    # Diagnosis accuracy comparison exists
    assert 0.0 <= result.diagnosis_accuracy_rules_pct <= 100.0
    assert 0.0 <= result.diagnosis_accuracy_llm_pct <= 100.0


def test_experiment_reproducibility_identical_across_runs():
    """CRITICAL ACCEPTANCE CRITERION: Running the same experiment config twice produces identical results."""
    runner_1 = EvaluationRunner(seed=3003, num_cases=30, batch_name="Batch_Repro")
    result_1 = runner_1.run_all_arms()

    runner_2 = EvaluationRunner(seed=3003, num_cases=30, batch_name="Batch_Repro")
    result_2 = runner_2.run_all_arms()

    # Verify identical diagnosis accuracy
    assert result_1.diagnosis_accuracy_rules_pct == result_2.diagnosis_accuracy_rules_pct
    assert result_1.diagnosis_accuracy_llm_pct == result_2.diagnosis_accuracy_llm_pct

    # Verify all arm metrics are byte-for-byte identical
    for arm_name in ["CONTROL", "NAIVE", "RULES", "AGENT"]:
        m1 = result_1.arm_metrics[arm_name]
        m2 = result_2.arm_metrics[arm_name]

        assert m1.gross_recovered_inr == m2.gross_recovered_inr
        assert m1.incremental_recovery_inr == m2.incremental_recovery_inr
        assert m1.total_cost_inr == m2.total_cost_inr
        assert m1.net_recovery_inr == m2.net_recovery_inr
        assert m1.duplicate_charges_count == m2.duplicate_charges_count
        assert m1.safety_invariants_status == m2.safety_invariants_status


def test_negative_incremental_and_net_recovery_when_underperforming_control():
    """REGRESSION TEST (Issue 1): An arm with gross recovery below control natural recovery
    must report a negative incremental recovery and negative net recovery, never clamped to zero.
    """
    runner = EvaluationRunner(seed=2002, num_cases=100, batch_name="Batch_B")
    result = runner.run_all_arms()

    control = result.arm_metrics["CONTROL"]
    naive = result.arm_metrics["NAIVE"]

    # NAIVE arm underperforms control natural recovery due to blind retries triggering declines/duplicate debits
    assert naive.gross_recovered_inr < control.natural_recovery_inr

    # Incremental recovery must be strictly negative, not floored at 0.00
    expected_incremental = round(naive.gross_recovered_inr - control.natural_recovery_inr, 2)
    assert expected_incremental < 0.0
    assert naive.incremental_recovery_inr == expected_incremental
    assert naive.incremental_recovery_inr < 0.0

    # Net recovery must reflect incremental minus operating cost, also strictly negative
    expected_net = round(expected_incremental - naive.total_cost_inr, 2)
    assert naive.net_recovery_inr == expected_net
    assert naive.net_recovery_inr < naive.incremental_recovery_inr

    # Lift percentage must mathematically correspond to signed incremental over total at risk
    expected_lift = round(expected_incremental / naive.total_at_risk_inr * 100, 2)
    assert naive.incremental_lift_pct == expected_lift
    assert naive.incremental_lift_pct < 0.0


def test_rules_vs_agent_decision_divergence_for_same_diagnosis():
    """TEST (Issue 2): Explicitly proves that for the same diagnosed case (identical root_cause),
    the RULES arm and AGENT arm diverge in their chosen action and routing due to downstream
    decisioning (EV ranking and Guardrail 5 high-value threshold), driving the observed lift gap.
    """
    from datetime import datetime, timezone
    from core.decision_engine import route_decision
    from core.entities import Customer, Transaction, Payment
    from core.rule_classifier import classify_rule_based
    from llm.client import LLMDiagnosisClient
    from simulator.world import SimulatedWorld

    world = SimulatedWorld(seed=2002, num_cases=100)
    fixed_time = datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc)
    llm_client = LLMDiagnosisClient()

    # Examine case_0016: high-value card failure
    obs = world.get_agent_observation("case_0016")
    cust = Customer(**obs["customer"])
    txn = Transaction(**obs["transaction"])
    pay = Payment(**obs["initial_payment"])
    telem = obs["telemetry"]

    # 1. Both arms obtain identical root-cause diagnosis
    # Note on live model swap: This assertion requires rule_diag.root_cause == llm_diag.root_cause
    # to test divergence isolated to downstream decisioning. If a live model (e.g. claude-3-haiku
    # or gpt-4o-mini) is plugged in, these test cases must use deterministic fixture/cache replay
    # so that diagnosis remains identical across arms for this test.
    rule_diag = classify_rule_based("case_0016", txn.failure_code, telem)
    llm_diag = llm_client.diagnose("case_0016", txn.failure_code, txn.amount, telem["channel"], telem)
    assert rule_diag.root_cause == llm_diag.root_cause
    assert llm_diag.root_cause == "INVALID_PAYMENT_INSTRUMENT"

    # 2. RULES arm: Calls real production select_rules_action policy
    # Static rule mapping ignores transaction amount (INR 87,410.03) and customer risk
    from core.rules_arm_policy import select_rules_action
    rules_action = select_rules_action(rule_diag.root_cause, cust.opted_out)
    assert rules_action == "PAYMENT_LINK"

    # 3. AGENT arm: Multi-stage Decision Engine evaluates EV and triggers Guardrail 5
    # (High Value Threshold > INR 50,000 mandates HUMAN_REVIEW to prevent major financial exposure)
    agent_decision = route_decision(
        case_id="case_0016",
        diagnosis=llm_diag,
        customer=cust,
        transaction=txn,
        payment=pay,
        telemetry=telem,
        current_time_utc=fixed_time
    )

    assert agent_decision.routing == "HUMAN"
    assert agent_decision.action == "HUMAN_REVIEW"
    assert "HIGH_VALUE_MANDATORY_HUMAN_REVIEW" in agent_decision.guardrail_verdict

    # 4. Prove that decisions diverged despite identical diagnosis
    assert rules_action != agent_decision.action
    assert rules_action == "PAYMENT_LINK"
    assert agent_decision.action == "HUMAN_REVIEW"
