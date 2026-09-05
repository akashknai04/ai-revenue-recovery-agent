"""Unit tests for Phase 2 simulator engine."""

import random
from simulator.world import SimulatedWorld
from simulator.recovery import simulate_recovery_outcome
from simulator.ground_truth import GroundTruthState


def test_simulator_reproducibility():
    """Verify that same seed produces exact identical world, different seed produces different world."""
    world_1 = SimulatedWorld(seed=42, num_cases=50)
    world_2 = SimulatedWorld(seed=42, num_cases=50)
    world_other = SimulatedWorld(seed=999, num_cases=50)

    for case_id in world_1.get_case_ids():
        obs_1 = world_1.get_agent_observation(case_id)
        obs_2 = world_2.get_agent_observation(case_id)
        gt_1 = world_1.get_ground_truth(case_id)
        gt_2 = world_2.get_ground_truth(case_id)

        assert obs_1["transaction"]["amount"] == obs_2["transaction"]["amount"]
        assert obs_1["customer"]["name"] == obs_2["customer"]["name"]
        assert gt_1.true_root_cause == gt_2.true_root_cause
        assert gt_1.will_naturally_recover == gt_2.will_naturally_recover

    # Check variation across seeds
    diff_count = sum(
        1 for cid in world_1.get_case_ids()
        if world_1.get_agent_observation(cid)["transaction"]["amount"] !=
           world_other.get_agent_observation(cid)["transaction"]["amount"]
    )
    assert diff_count > 40


def test_simulator_mixed_realistic_outcomes():
    """Verify that generated batch contains a mix of outcomes: failures, natural recoveries, ambiguous debits, and ptp."""
    world = SimulatedWorld(seed=123, num_cases=100)
    case_ids = world.get_case_ids()

    natural_recoveries = 0
    ambiguous_debits = 0
    ptp_propensities = 0
    duplicate_risks = 0
    categories = set()

    for cid in case_ids:
        obs = world.get_agent_observation(cid)
        gt = world.get_ground_truth(cid)

        categories.add(gt.true_root_cause)
        if gt.will_naturally_recover:
            natural_recoveries += 1
        if gt.true_root_cause == "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT":
            ambiguous_debits += 1
        if gt.ptp_propensity > 0.2:
            ptp_propensities += 1
        if gt.has_duplicate_charge_risk:
            duplicate_risks += 1

    # Verify all 5 categories are present
    assert len(categories) == 5
    # Verify realistic distribution
    assert natural_recoveries > 10, "Should have natural recoveries"
    assert ambiguous_debits > 2, "Should have ambiguous debits"
    assert ptp_propensities > 10, "Should have PTP propensities"
    assert duplicate_risks > 1, "Should have duplicate risks"


def test_promise_to_pay_simulation():
    """Verify simulated recovery produces promise-to-pay commitment when customer is contacted."""
    gt = GroundTruthState(
        case_id="case_ptp",
        true_root_cause="INSUFFICIENT_FUNDS",
        will_naturally_recover=False,
        natural_recovery_delay_hours=2.0,
        true_customer_debited=False,
        true_merchant_order_paid=False,
        has_duplicate_charge_risk=False,
        ptp_propensity=1.0,  # Forces PTP
        ptp_fulfillment_likelihood=0.8,
        optimal_action="PAYMENT_LINK"
    )

    rng = random.Random(42)
    outcome = simulate_recovery_outcome("PAYMENT_LINK", gt, rng)
    assert outcome["provider_status"] == "PROMISE_RECEIVED"
    assert outcome["ptp_generated"] is not None
    assert "promised_days_ahead" in outcome["ptp_generated"]


def test_ambiguous_debit_immediate_retry_causes_duplicate_charge():
    """Verify that immediate retry on an ambiguous debit causes duplicate debit."""
    gt = GroundTruthState(
        case_id="case_ambig",
        true_root_cause="AMBIGUOUS_DEBIT_NETWORK_TIMEOUT",
        will_naturally_recover=False,
        natural_recovery_delay_hours=1.0,
        true_customer_debited=True,
        true_merchant_order_paid=False,
        has_duplicate_charge_risk=False,
        ptp_propensity=0.0,
        ptp_fulfillment_likelihood=0.0,
        optimal_action="HUMAN_REVIEW"
    )

    rng = random.Random(42)
    outcome = simulate_recovery_outcome("RETRY", gt, rng)
    assert outcome["duplicate_charge"] is True
    assert outcome["provider_status"] == "DUPLICATE_DEBIT"
