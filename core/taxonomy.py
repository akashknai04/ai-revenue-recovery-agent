"""Failure root-cause taxonomy definitions.

Defines the official 5 explainable failure categories and their characteristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class CategoryMetadata:
    name: str
    description: str
    is_transient: bool
    requires_customer_action: bool
    recommended_recovery_action: str


TAXONOMY: Dict[str, CategoryMetadata] = {
    "ISSUER_TECHNICAL_DECLINE": CategoryMetadata(
        name="ISSUER_TECHNICAL_DECLINE",
        description="Transient bank switch, core banking system, or network timeout outage.",
        is_transient=True,
        requires_customer_action=False,
        recommended_recovery_action="DELAYED_RETRY"
    ),
    "INSUFFICIENT_FUNDS": CategoryMetadata(
        name="INSUFFICIENT_FUNDS",
        description="Account balance insufficient or daily transaction limit reached.",
        is_transient=False,
        requires_customer_action=True,
        recommended_recovery_action="PAYMENT_LINK"
    ),
    "AUTHENTICATION_ABANDONED": CategoryMetadata(
        name="AUTHENTICATION_ABANDONED",
        description="User dropped off during 3DS / OTP verification or biometric challenge.",
        is_transient=True,
        requires_customer_action=True,
        recommended_recovery_action="PAYMENT_LINK"
    ),
    "INVALID_PAYMENT_INSTRUMENT": CategoryMetadata(
        name="INVALID_PAYMENT_INSTRUMENT",
        description="Expired card, invalid checksum, disabled card, or non-existent UPI VPA handle.",
        is_transient=False,
        requires_customer_action=True,
        recommended_recovery_action="PAYMENT_LINK"
    ),
    "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT": CategoryMetadata(
        name="AMBIGUOUS_DEBIT_NETWORK_TIMEOUT",
        description="Transaction drop at settlement boundary where customer debit status is uncertain.",
        is_transient=False,
        requires_customer_action=False,
        recommended_recovery_action="HUMAN_REVIEW"
    ),
}

TAXONOMY_CATEGORIES = list(TAXONOMY.keys())
