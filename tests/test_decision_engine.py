"""Unit tests for Phase 8: Decision Engine routing completeness."""

from simulator.world import SimulatedWorld
from core.decision_engine import route_decision
from core.rule_classifier import classify_rule_based
from core.entities import Customer, Payment, Transaction


def test_every_case_reaches_exactly_one_of_auto_human_block():
    """CRITICAL ACCEPTANCE CRITERION: Every case reaches exactly one of AUTO/HUMAN/BLOCK — no case falls through."""
    world = SimulatedWorld(seed=999, num_cases=100)
    case_ids = world.get_case_ids()

    valid_routings = {"AUTO", "HUMAN", "BLOCK"}
    routing_counts = {"AUTO": 0, "HUMAN": 0, "BLOCK": 0}

    for cid in case_ids:
        obs = world.get_agent_observation(cid)
        cust_dict = obs["customer"]
        txn_dict = obs["transaction"]
        pay_dict = obs["initial_payment"]
        telemetry = obs["telemetry"]

        customer = Customer(**cust_dict)
        txn = Transaction(**txn_dict)
        payment = Payment(**pay_dict)

        diagnosis = classify_rule_based(cid, txn.failure_code, telemetry)

        decision = route_decision(
            case_id=cid,
            diagnosis=diagnosis,
            customer=customer,
            transaction=txn,
            payment=payment,
            telemetry=telemetry
        )

        # Invariant checks
        assert decision.case_id == cid
        assert decision.routing in valid_routings, f"Invalid routing '{decision.routing}' on case {cid}"
        assert decision.action is not None
        assert len(decision.action) > 0
        assert decision.guardrail_verdict is not None

        routing_counts[decision.routing] += 1

    # Verify all 3 routing buckets were exercised across the 100 cases
    assert routing_counts["AUTO"] > 0, "Should have AUTO decisions"
    assert routing_counts["HUMAN"] > 0, "Should have HUMAN decisions"
    assert routing_counts["BLOCK"] > 0, "Should have BLOCK decisions"
    assert sum(routing_counts.values()) == 100
