"""Failure code definitions and observation generator."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Failure category identifiers
CAT_ISSUER_TECH = "ISSUER_TECHNICAL_DECLINE"
CAT_INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
CAT_AUTH_ABANDONED = "AUTHENTICATION_ABANDONED"
CAT_INVALID_INSTRUMENT = "INVALID_PAYMENT_INSTRUMENT"
CAT_AMBIGUOUS_DEBIT = "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT"

ALL_CATEGORIES = [
    CAT_ISSUER_TECH,
    CAT_INSUFFICIENT_FUNDS,
    CAT_AUTH_ABANDONED,
    CAT_INVALID_INSTRUMENT,
    CAT_AMBIGUOUS_DEBIT,
]

FAILURE_PROFILES: Dict[str, Dict[str, Any]] = {
    CAT_ISSUER_TECH: {
        "codes": ["BANK_DOWN_503", "SWITCH_TIMEOUT", "ISSUER_UNAVAILABLE"],
        "http_status": 503,
        "natural_recovery_base_prob": 0.40,  # Banks often recover within 15-30 mins
        "ptp_propensity": 0.05,
        "sample_messages": [
            "Bank host did not respond in 30 seconds",
            "Issuer core banking switch is temporarily down",
            "UPI gateway communication timeout"
        ]
    },
    CAT_INSUFFICIENT_FUNDS: {
        "codes": ["INSUFFICIENT_BALANCE_51", "LOW_BALANCE"],
        "http_status": 402,
        "natural_recovery_base_prob": 0.10,  # May recover if customer transfers money
        "ptp_propensity": 0.50,  # High likelihood customer says "Will pay on 1st / salary day"
        "sample_messages": [
            "Decline code 51: Insufficient funds in account",
            "Available balance is less than transaction amount"
        ]
    },
    CAT_AUTH_ABANDONED: {
        "codes": ["OTP_EXPIRED", "USER_DROPPED", "AUTH_TIMED_OUT"],
        "http_status": 400,
        "natural_recovery_base_prob": 0.25,  # Customer may return and try on their own
        "ptp_propensity": 0.20,
        "sample_messages": [
            "Customer closed 3DS authentication modal",
            "OTP validation timed out after 180 seconds",
            "Payment session dropped before authentication completed"
        ]
    },
    CAT_INVALID_INSTRUMENT: {
        "codes": ["INVALID_CARD_NUMBER", "EXPIRED_CARD", "INVALID_VPA"],
        "http_status": 422,
        "natural_recovery_base_prob": 0.02,  # Retrying same card will never work
        "ptp_propensity": 0.35,  # Customer needs a payment link to use a different method
        "sample_messages": [
            "Luhn algorithm check failed for card number",
            "Card expiration date is in the past",
            "VPA handle does not exist on UPI directory"
        ]
    },
    CAT_AMBIGUOUS_DEBIT: {
        "codes": ["GATEWAY_TIMEOUT_DEBIT_UNCERTAIN", "PENDING_BANK_RECON"],
        "http_status": 504,
        "natural_recovery_base_prob": 0.65,  # Settlement often arrives via delayed webhook
        "ptp_propensity": 0.02,
        "sample_messages": [
            "UPI debited SMS reported by user but gateway response timed out",
            "Bank network drop at settlement handoff; customer debit uncertain"
        ]
    }
}
