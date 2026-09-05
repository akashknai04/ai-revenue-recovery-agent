"""Recovery outcome simulation engine."""

import random
from typing import Any, Dict, Optional, Tuple
from simulator.ground_truth import GroundTruthState


def simulate_recovery_outcome(
    action_type: str,
    ground_truth: GroundTruthState,
    rng: random.Random
) -> Dict[str, Any]:
    """Simulate the real-world outcome of applying an action to a case.

    Returns a dict with:
      - success: bool (whether money was successfully recovered)
      - duplicate_charge: bool (whether an illegal duplicate debit occurred)
      - ptp_generated: Optional[Dict[str, Any]] (if customer committed to promise to pay)
      - provider_status: str
      - customer_debited: bool
      - merchant_confirmed: bool
      - cost: float
    """
    result = {
        "success": False,
        "duplicate_charge": False,
        "ptp_generated": None,
        "provider_status": "FAILED",
        "customer_debited": ground_truth.true_customer_debited,
        "merchant_confirmed": ground_truth.true_merchant_order_paid,
        "cost": 0.0
    }

    # Action-specific costs (in INR)
    costs = {
        "NO_ACTION": 0.0,
        "RETRY": 3.0,          # Gateway API call fee
        "DELAYED_RETRY": 3.0,
        "PAYMENT_LINK": 1.5,  # SMS / WhatsApp messaging fee
        "REMINDER": 1.0,      # Notification fee
        "HUMAN_REVIEW": 45.0, # Human agent review time cost
        "BLOCK": 0.0,
        "VOICE_CALL": 6.0     # Interactive voice call cost
    }
    result["cost"] = costs.get(action_type, 0.0)

    # 1. NO ACTION (Baseline / Control arm)
    if action_type == "NO_ACTION":
        if ground_truth.will_naturally_recover:
            result["success"] = True
            result["provider_status"] = "SUCCESS"
            result["customer_debited"] = True
            result["merchant_confirmed"] = True
        return result

    # 2. IMMEDIATE RETRY
    if action_type == "RETRY":
        # Check duplicate debit risk: if customer was already debited (ambiguous debit), immediate retry causes double charge!
        if ground_truth.true_customer_debited:
            result["duplicate_charge"] = True
            result["success"] = False  # Not a valid incremental recovery, violates safety
            result["provider_status"] = "DUPLICATE_DEBIT"
            return result

        if ground_truth.true_root_cause == "ISSUER_TECHNICAL_DECLINE":
            # 50% chance bank has already recovered
            if rng.random() < 0.50:
                result["success"] = True
                result["provider_status"] = "SUCCESS"
                result["customer_debited"] = True
                result["merchant_confirmed"] = True
        elif ground_truth.true_root_cause == "INSUFFICIENT_FUNDS":
            # Retrying immediately with insufficient funds almost always fails (98% fail)
            if rng.random() < 0.02:
                result["success"] = True
                result["provider_status"] = "SUCCESS"
                result["customer_debited"] = True
                result["merchant_confirmed"] = True
        elif ground_truth.true_root_cause == "AUTHENTICATION_ABANDONED":
            # Retrying without customer auth cannot succeed
            result["success"] = False
        elif ground_truth.true_root_cause == "INVALID_PAYMENT_INSTRUMENT":
            # Invalid card/VPA can never succeed on direct retry
            result["success"] = False
        return result

    # 3. DELAYED RETRY
    if action_type == "DELAYED_RETRY":
        if ground_truth.true_customer_debited:
            # Still risks duplicate debit if not reconciled first
            result["duplicate_charge"] = True
            result["provider_status"] = "DUPLICATE_DEBIT"
            return result

        if ground_truth.true_root_cause == "ISSUER_TECHNICAL_DECLINE":
            # High recovery rate after cooldown (82%)
            if rng.random() < 0.82:
                result["success"] = True
                result["provider_status"] = "SUCCESS"
                result["customer_debited"] = True
                result["merchant_confirmed"] = True
        elif ground_truth.true_root_cause == "INSUFFICIENT_FUNDS":
            # If delayed, slight chance funds deposited (12%)
            if rng.random() < 0.12:
                result["success"] = True
                result["provider_status"] = "SUCCESS"
                result["customer_debited"] = True
                result["merchant_confirmed"] = True
        return result

    # 4. PAYMENT LINK / REMINDER / VOICE CALL
    if action_type in ("PAYMENT_LINK", "REMINDER", "VOICE_CALL"):
        # If customer already debited, sending payment link will confuse or anger customer, but might reveal debit
        if ground_truth.true_customer_debited:
            # Customer says: "I already paid! See my debit SMS" -> requires reconciliation
            result["provider_status"] = "CUSTOMER_DISPUTES_ALREADY_DEBITED"
            return result

        # Check for Promise-to-Pay behavior
        if rng.random() < ground_truth.ptp_propensity:
            # Customer offers a promise to pay by date X
            result["ptp_generated"] = {
                "promised_amount": 0.0,  # Filled by caller with case amount
                "promised_days_ahead": rng.randint(2, 5),
                "will_fulfill": rng.random() < ground_truth.ptp_fulfillment_likelihood
            }
            result["provider_status"] = "PROMISE_RECEIVED"
            return result

        # If no PTP, direct payment conversion via link
        conv_rates = {
            "PAYMENT_LINK": {
                "AUTHENTICATION_ABANDONED": 0.65,
                "INVALID_PAYMENT_INSTRUMENT": 0.55,
                "INSUFFICIENT_FUNDS": 0.30,
                "ISSUER_TECHNICAL_DECLINE": 0.40,
                "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT": 0.20
            },
            "REMINDER": {
                "AUTHENTICATION_ABANDONED": 0.45,
                "INVALID_PAYMENT_INSTRUMENT": 0.20,
                "INSUFFICIENT_FUNDS": 0.25,
                "ISSUER_TECHNICAL_DECLINE": 0.30,
                "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT": 0.15
            },
            "VOICE_CALL": {
                "AUTHENTICATION_ABANDONED": 0.70,
                "INVALID_PAYMENT_INSTRUMENT": 0.60,
                "INSUFFICIENT_FUNDS": 0.40,
                "ISSUER_TECHNICAL_DECLINE": 0.45,
                "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT": 0.25
            }
        }
        rate = conv_rates[action_type].get(ground_truth.true_root_cause, 0.25)
        if rng.random() < rate:
            result["success"] = True
            result["provider_status"] = "SUCCESS"
            result["customer_debited"] = True
            result["merchant_confirmed"] = True
        return result

    # 5. HUMAN REVIEW
    if action_type == "HUMAN_REVIEW":
        # Human agent inspects banking portal / network logs
        if ground_truth.true_customer_debited:
            # Human discovers money was debited, forces settlement without duplicate charge
            result["success"] = True
            result["provider_status"] = "SUCCESS_RECONCILED"
            result["customer_debited"] = True
            result["merchant_confirmed"] = True
            result["duplicate_charge"] = False
        else:
            # Human contacts customer with appropriate channel or clarifies bank issue
            if rng.random() < 0.75:
                result["success"] = True
                result["provider_status"] = "SUCCESS"
                result["customer_debited"] = True
                result["merchant_confirmed"] = True
        return result

    # 6. BLOCK
    if action_type == "BLOCK":
        # System blocked further action (e.g. duplicate risk, fraud)
        result["provider_status"] = "BLOCKED"
        result["success"] = False
        return result

    return result
