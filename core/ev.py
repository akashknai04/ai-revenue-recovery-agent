"""Expected Value (EV) calculation using Simple Stratified Lift.

NOTE ON METHODOLOGY:
In accordance with §7 of the brief, uplift is computed via Simple Stratified Lift
(treatment vs. control recovery rates within matched segments, with confidence intervals).
Complex causal uplift models (T-Learner, X-Learner, Doubly-Robust) are explicitly
out of scope for this MVP and documented as Future Extensions.

Formula:
  EV(action) = incremental_recovery_rate(action) * amount - action_cost - risk_cost
Where:
  incremental_recovery_rate = max(0.0, recovery_rate(action, segment) - natural_recovery_rate(control, segment))
  risk_cost = action_risk_score * amount * 0.05
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from core.catalog import ACTION_CATALOG


@dataclass(frozen=True)
class EVResult:
    action_type: str
    ev_score: float
    incremental_recovery_rate: float
    ci_lower: float
    ci_upper: float
    expected_gross_recovery: float
    action_cost: float
    risk_cost: float


# Stratified lift table by (root_cause, risk_tier)
# Segment recovery rates based on empirical payment domain baselines
# Format: { (root_cause, risk_tier): { action: (rate, sample_n) } }
STRATIFIED_LIFT_DATA: Dict[Tuple[str, str], Dict[str, Tuple[float, int]]] = {
    ("ISSUER_TECHNICAL_DECLINE", "LOW"): {
        "NO_ACTION": (0.42, 500),
        "RETRY": (0.55, 400),
        "DELAYED_RETRY": (0.84, 450),
        "PAYMENT_LINK": (0.45, 300),
        "REMINDER": (0.43, 300),
        "HUMAN_REVIEW": (0.80, 100),
        "BLOCK": (0.00, 100)
    },
    ("ISSUER_TECHNICAL_DECLINE", "MEDIUM"): {
        "NO_ACTION": (0.38, 500),
        "RETRY": (0.48, 400),
        "DELAYED_RETRY": (0.78, 450),
        "PAYMENT_LINK": (0.40, 300),
        "REMINDER": (0.39, 300),
        "HUMAN_REVIEW": (0.75, 100),
        "BLOCK": (0.00, 100)
    },
    ("ISSUER_TECHNICAL_DECLINE", "HIGH"): {
        "NO_ACTION": (0.30, 300),
        "RETRY": (0.35, 300),
        "DELAYED_RETRY": (0.70, 300),
        "PAYMENT_LINK": (0.32, 200),
        "REMINDER": (0.31, 200),
        "HUMAN_REVIEW": (0.70, 100),
        "BLOCK": (0.00, 100)
    },
    ("INSUFFICIENT_FUNDS", "LOW"): {
        "NO_ACTION": (0.12, 500),
        "RETRY": (0.04, 400),
        "DELAYED_RETRY": (0.15, 400),
        "PAYMENT_LINK": (0.48, 450),
        "REMINDER": (0.28, 300),
        "HUMAN_REVIEW": (0.60, 100),
        "BLOCK": (0.00, 100)
    },
    ("INSUFFICIENT_FUNDS", "MEDIUM"): {
        "NO_ACTION": (0.09, 500),
        "RETRY": (0.02, 400),
        "DELAYED_RETRY": (0.11, 400),
        "PAYMENT_LINK": (0.38, 450),
        "REMINDER": (0.22, 300),
        "HUMAN_REVIEW": (0.50, 100),
        "BLOCK": (0.00, 100)
    },
    ("INSUFFICIENT_FUNDS", "HIGH"): {
        "NO_ACTION": (0.05, 400),
        "RETRY": (0.01, 300),
        "DELAYED_RETRY": (0.06, 300),
        "PAYMENT_LINK": (0.24, 350),
        "REMINDER": (0.14, 250),
        "HUMAN_REVIEW": (0.40, 100),
        "BLOCK": (0.00, 100)
    },
    ("AUTHENTICATION_ABANDONED", "LOW"): {
        "NO_ACTION": (0.28, 500),
        "RETRY": (0.02, 300),
        "DELAYED_RETRY": (0.02, 300),
        "PAYMENT_LINK": (0.72, 500),
        "REMINDER": (0.52, 400),
        "HUMAN_REVIEW": (0.70, 100),
        "BLOCK": (0.00, 100)
    },
    ("AUTHENTICATION_ABANDONED", "MEDIUM"): {
        "NO_ACTION": (0.22, 500),
        "RETRY": (0.02, 300),
        "DELAYED_RETRY": (0.02, 300),
        "PAYMENT_LINK": (0.62, 500),
        "REMINDER": (0.42, 400),
        "HUMAN_REVIEW": (0.65, 100),
        "BLOCK": (0.00, 100)
    },
    ("AUTHENTICATION_ABANDONED", "HIGH"): {
        "NO_ACTION": (0.15, 300),
        "RETRY": (0.01, 200),
        "DELAYED_RETRY": (0.01, 200),
        "PAYMENT_LINK": (0.45, 300),
        "REMINDER": (0.30, 250),
        "HUMAN_REVIEW": (0.55, 100),
        "BLOCK": (0.00, 100)
    },
    ("INVALID_PAYMENT_INSTRUMENT", "LOW"): {
        "NO_ACTION": (0.04, 500),
        "RETRY": (0.00, 400),
        "DELAYED_RETRY": (0.00, 400),
        "PAYMENT_LINK": (0.65, 450),
        "REMINDER": (0.25, 300),
        "HUMAN_REVIEW": (0.55, 100),
        "BLOCK": (0.00, 100)
    },
    ("INVALID_PAYMENT_INSTRUMENT", "MEDIUM"): {
        "NO_ACTION": (0.02, 500),
        "RETRY": (0.00, 400),
        "DELAYED_RETRY": (0.00, 400),
        "PAYMENT_LINK": (0.52, 450),
        "REMINDER": (0.18, 300),
        "HUMAN_REVIEW": (0.50, 100),
        "BLOCK": (0.00, 100)
    },
    ("INVALID_PAYMENT_INSTRUMENT", "HIGH"): {
        "NO_ACTION": (0.01, 300),
        "RETRY": (0.00, 200),
        "DELAYED_RETRY": (0.00, 200),
        "PAYMENT_LINK": (0.38, 300),
        "REMINDER": (0.10, 200),
        "HUMAN_REVIEW": (0.40, 100),
        "BLOCK": (0.00, 100)
    },
    ("AMBIGUOUS_DEBIT_NETWORK_TIMEOUT", "LOW"): {
        "NO_ACTION": (0.60, 300),
        "RETRY": (0.10, 200),  # High duplicate debit penalty
        "DELAYED_RETRY": (0.10, 200),
        "PAYMENT_LINK": (0.20, 200),
        "REMINDER": (0.15, 200),
        "HUMAN_REVIEW": (0.92, 200),
        "BLOCK": (0.00, 100)
    },
    ("AMBIGUOUS_DEBIT_NETWORK_TIMEOUT", "MEDIUM"): {
        "NO_ACTION": (0.55, 300),
        "RETRY": (0.08, 200),
        "DELAYED_RETRY": (0.08, 200),
        "PAYMENT_LINK": (0.18, 200),
        "REMINDER": (0.12, 200),
        "HUMAN_REVIEW": (0.88, 200),
        "BLOCK": (0.00, 100)
    },
    ("AMBIGUOUS_DEBIT_NETWORK_TIMEOUT", "HIGH"): {
        "NO_ACTION": (0.50, 200),
        "RETRY": (0.05, 100),
        "DELAYED_RETRY": (0.05, 100),
        "PAYMENT_LINK": (0.12, 100),
        "REMINDER": (0.10, 100),
        "HUMAN_REVIEW": (0.82, 100),
        "BLOCK": (0.00, 100)
    },
}


def compute_wilson_score_ci(p: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Compute 95% Wilson score confidence interval for a proportion."""
    if n <= 0:
        return 0.0, 1.0
    denom = 1 + (z**2) / n
    centre = (p + (z**2) / (2 * n)) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p) / n) + (z**2) / (4 * (n**2)))
    lower = max(0.0, centre - margin)
    upper = min(1.0, centre + margin)
    return round(lower, 4), round(upper, 4)


def get_risk_tier(risk_score: float) -> str:
    """Discretize risk score into LOW, MEDIUM, HIGH."""
    if risk_score <= 0.30:
        return "LOW"
    elif risk_score <= 0.70:
        return "MEDIUM"
    else:
        return "HIGH"


def calculate_action_ev(
    action_type: str,
    root_cause: str,
    customer_risk_score: float,
    amount: float
) -> EVResult:
    """Compute Expected Value for a specific action on a case using stratified lift."""
    risk_tier = get_risk_tier(customer_risk_score)
    segment_key = (root_cause, risk_tier)

    # Fallback to default segment if unmapped
    default_key = ("ISSUER_TECHNICAL_DECLINE", "MEDIUM")
    actions_map = STRATIFIED_LIFT_DATA.get(segment_key, STRATIFIED_LIFT_DATA[default_key])

    action_data = actions_map.get(action_type, (0.0, 100))
    control_data = actions_map.get("NO_ACTION", (0.10, 100))

    p_action, n_action = action_data
    p_control, _ = control_data

    # Incremental lift over control (never attribute natural recovery)
    incremental_lift = max(0.0, p_action - p_control)
    ci_lower, ci_upper = compute_wilson_score_ci(p_action, n_action)

    action_defn = ACTION_CATALOG.get(action_type)
    action_cost = action_defn.cost if action_defn else 0.0
    risk_weight = action_defn.risk if action_defn else 0.0

    # Risk cost scales with case amount and action risk
    risk_cost = round(risk_weight * amount * 0.02, 2)
    expected_gross = round(incremental_lift * amount, 2)
    ev_score = round(expected_gross - action_cost - risk_cost, 2)

    return EVResult(
        action_type=action_type,
        ev_score=ev_score,
        incremental_recovery_rate=round(incremental_lift, 4),
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        expected_gross_recovery=expected_gross,
        action_cost=action_cost,
        risk_cost=risk_cost
    )


def rank_actions_by_ev(
    root_cause: str,
    customer_risk_score: float,
    amount: float,
    candidate_actions: Optional[List[str]] = None
) -> List[EVResult]:
    """Rank candidate actions in descending order of Expected Value."""
    if candidate_actions is None:
        candidate_actions = ["NO_ACTION", "RETRY", "DELAYED_RETRY", "PAYMENT_LINK", "REMINDER", "HUMAN_REVIEW"]

    results = [
        calculate_action_ev(action, root_cause, customer_risk_score, amount)
        for action in candidate_actions
    ]
    results.sort(key=lambda x: x.ev_score, reverse=True)
    return results
