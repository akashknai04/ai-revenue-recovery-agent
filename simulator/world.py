"""Simulated World generator for AI Revenue Recovery Agent.

Generates reproducible batches of degraded payment cases with realistic
error telemetry, customer behavior, natural recovery tendencies,
and isolated ground truth.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.entities import Customer, Payment, RevenueEvent, Transaction
from simulator.customers import generate_customer
from simulator.failures import ALL_CATEGORIES, FAILURE_PROFILES
from simulator.ground_truth import GroundTruthState
from simulator.transactions import generate_transaction_and_payment


class SimulatedCase:
    """Encapsulates a simulated degradation case."""

    def __init__(
        self,
        case_id: str,
        customer: Customer,
        transaction: Transaction,
        initial_payment: Payment,
        telemetry: Dict[str, Any],
        ground_truth: GroundTruthState,
        arm_assignment: str = "TREATMENT"
    ):
        self.case_id = case_id
        self.customer = customer
        self.transaction = transaction
        self.initial_payment = initial_payment
        self.telemetry = telemetry
        self.ground_truth = ground_truth
        self.arm_assignment = arm_assignment

    def to_revenue_event(self) -> RevenueEvent:
        """Create the generalized RevenueEvent envelope representing the initial degradation."""
        return RevenueEvent(
            source="payment_gateway_simulator",
            entity_id=self.case_id,
            amount=self.transaction.amount,
            status=self.transaction.state,
            timestamps={"created_at": self.transaction.created_at},
            raw_payload={
                "failure_code": self.transaction.failure_code,
                "telemetry": self.telemetry,
                "customer_phone": self.customer.phone,
                "customer_email": self.customer.email,
                "customer_timezone": self.customer.timezone
            }
        )


class SimulatedWorld:
    """Collection of simulated degradation cases for evaluation runs."""

    def __init__(self, seed: int, num_cases: int = 100, base_time: Optional[datetime] = None):
        self.seed = seed
        self.num_cases = num_cases
        self.base_time = base_time or datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
        self.rng = random.Random(seed)
        self.cases: Dict[str, SimulatedCase] = {}
        self._generate_world()

    def _generate_world(self) -> None:
        """Populate the synthetic world with balanced failure cases and ground truth."""
        category_weights = [0.30, 0.25, 0.20, 0.15, 0.10]

        for i in range(1, self.num_cases + 1):
            case_id = f"case_{i:04d}"
            customer_id = f"cust_{i:04d}"

            # Pick failure category
            category = self.rng.choices(ALL_CATEGORIES, weights=category_weights, k=1)[0]
            profile = FAILURE_PROFILES[category]

            # Generate customer & transaction
            customer = generate_customer(customer_id, self.rng)
            transaction, payment, telemetry = generate_transaction_and_payment(
                case_id, customer_id, category, self.rng, self.base_time
            )

            # Ground truth determination
            # Natural recovery probability: depends on category and customer risk score
            nat_base = profile["natural_recovery_base_prob"]
            # High-risk customers have slightly lower natural recovery
            nat_prob = max(0.01, min(0.95, nat_base * (1.1 - customer.risk_score * 0.4)))
            will_naturally_recover = self.rng.random() < nat_prob

            # Ambiguous debit scenario true state
            if category == "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT":
                true_debited = payment.debited_customer
                true_order_paid = False  # Merchant has not recognized order yet
                optimal_action = "HUMAN_REVIEW"
            elif category == "ISSUER_TECHNICAL_DECLINE":
                true_debited = False
                true_order_paid = False
                optimal_action = "DELAYED_RETRY"
            elif category == "INSUFFICIENT_FUNDS":
                true_debited = False
                true_order_paid = False
                optimal_action = "PAYMENT_LINK"
            elif category == "AUTHENTICATION_ABANDONED":
                true_debited = False
                true_order_paid = False
                optimal_action = "PAYMENT_LINK"
            elif category == "INVALID_PAYMENT_INSTRUMENT":
                true_debited = False
                true_order_paid = False
                optimal_action = "PAYMENT_LINK"
            else:
                true_debited = False
                true_order_paid = False
                optimal_action = "NO_ACTION"

            # Promise to pay propensity & fulfillment
            ptp_prop = profile.get("ptp_propensity", 0.15)
            # Fulfillment depends on customer risk score: low risk customers keep promises
            ptp_fulfillment = max(0.1, min(0.95, 1.0 - customer.risk_score))

            gt = GroundTruthState(
                case_id=case_id,
                true_root_cause=category,
                will_naturally_recover=will_naturally_recover,
                natural_recovery_delay_hours=round(self.rng.uniform(0.5, 4.0), 2),
                true_customer_debited=true_debited,
                true_merchant_order_paid=true_order_paid,
                has_duplicate_charge_risk=telemetry["duplicate_attempt_detected"],
                ptp_propensity=ptp_prop,
                ptp_fulfillment_likelihood=ptp_fulfillment,
                optimal_action=optimal_action
            )

            # Assign to treatment arm by default or randomized
            arm = "CONTROL" if (i % 2 == 0) else "TREATMENT"

            self.cases[case_id] = SimulatedCase(
                case_id=case_id,
                customer=customer,
                transaction=transaction,
                initial_payment=payment,
                telemetry=telemetry,
                ground_truth=gt,
                arm_assignment=arm
            )

    def get_case_ids(self) -> List[str]:
        """Return all case identifiers in the world."""
        return list(self.cases.keys())

    def get_agent_observation(self, case_id: str) -> Dict[str, Any]:
        """Return ONLY realistic public observations accessible to the agent.

        Excludes GroundTruthState.
        """
        case = self.cases[case_id]
        return {
            "case_id": case.case_id,
            "customer": case.customer.to_dict(),
            "transaction": case.transaction.to_dict(),
            "initial_payment": case.initial_payment.to_dict(),
            "telemetry": dict(case.telemetry),
            "revenue_event": case.to_revenue_event().to_dict()
        }

    def get_ground_truth(self, case_id: str) -> GroundTruthState:
        """Privileged accessor for evaluation arm ONLY. Never exposed to agent core."""
        return self.cases[case_id].ground_truth
