"""Deterministic recovery policy for the RULES baseline arm."""

from __future__ import annotations


def select_rules_action(root_cause: str, customer_opted_out: bool) -> str:
    """Map root cause and opt-out state deterministically for the RULES arm baseline.

    Faithful extraction of the baseline heuristic from evaluation/runner.py:
    - ISSUER_TECHNICAL_DECLINE -> DELAYED_RETRY
    - AMBIGUOUS_DEBIT_NETWORK_TIMEOUT -> HUMAN_REVIEW
    - All other causes -> PAYMENT_LINK (or BLOCK if customer opted out)
    """
    if root_cause == "ISSUER_TECHNICAL_DECLINE":
        action = "DELAYED_RETRY"
    elif root_cause == "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT":
        action = "HUMAN_REVIEW"
    else:
        action = "PAYMENT_LINK"

    if customer_opted_out and action == "PAYMENT_LINK":
        action = "BLOCK"

    return action
