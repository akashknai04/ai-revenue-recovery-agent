"""Ground truth module for simulator.

STRICT BOUNDARY INVARIANT:
This module contains the synthetic world's ground truth.
Code in `core/` must NEVER import or reference this module or its symbols.
Enforced via static AST inspection in `tests/leakage/test_ground_truth_leakage.py`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class GroundTruthState:
    """Isolated ground-truth reality unknown to the agent at decision time."""
    case_id: str
    true_root_cause: str  # e.g., ISSUER_TECHNICAL_DECLINE, INSUFFICIENT_FUNDS, etc.
    will_naturally_recover: bool  # True if payment would succeed without any recovery intervention
    natural_recovery_delay_hours: float
    true_customer_debited: bool  # True if customer account was actually debited
    true_merchant_order_paid: bool  # True if merchant order is settled
    has_duplicate_charge_risk: bool  # True if customer initiated a secondary parallel transaction
    ptp_propensity: float  # Likelihood to respond with a promise-to-pay commitment
    ptp_fulfillment_likelihood: float  # Likelihood to keep a promise if made
    optimal_action: str  # Benchmark optimal recovery action for evaluation scoring

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
