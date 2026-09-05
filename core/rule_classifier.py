"""Rule-based root-cause baseline classifier.

Provides deterministic, explainable classification of payment degradations
into the official 5-part failure taxonomy without any LLM calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from core.entities import Diagnosis
from core.taxonomy import TAXONOMY, TAXONOMY_CATEGORIES

# Explicit mapping of error codes to categories
ERROR_CODE_MAP: Dict[str, str] = {
    # Issuer technical decline
    "BANK_DOWN_503": "ISSUER_TECHNICAL_DECLINE",
    "SWITCH_TIMEOUT": "ISSUER_TECHNICAL_DECLINE",
    "ISSUER_UNAVAILABLE": "ISSUER_TECHNICAL_DECLINE",

    # Insufficient funds
    "INSUFFICIENT_BALANCE_51": "INSUFFICIENT_FUNDS",
    "LOW_BALANCE": "INSUFFICIENT_FUNDS",

    # Authentication abandoned
    "OTP_EXPIRED": "AUTHENTICATION_ABANDONED",
    "USER_DROPPED": "AUTHENTICATION_ABANDONED",
    "AUTH_TIMED_OUT": "AUTHENTICATION_ABANDONED",

    # Invalid payment instrument
    "INVALID_CARD_NUMBER": "INVALID_PAYMENT_INSTRUMENT",
    "EXPIRED_CARD": "INVALID_PAYMENT_INSTRUMENT",
    "INVALID_VPA": "INVALID_PAYMENT_INSTRUMENT",

    # Ambiguous debit
    "GATEWAY_TIMEOUT_DEBIT_UNCERTAIN": "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT",
    "PENDING_BANK_RECON": "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT",
}


def classify_rule_based(
    case_id: str,
    failure_code: Optional[str],
    telemetry: Optional[Dict[str, Any]] = None
) -> Diagnosis:
    """Classify a payment failure into the taxonomy deterministically.

    Uses zero LLM calls. Always produces a valid Diagnosis entity.
    """
    telemetry = telemetry or {}
    evidence: List[str] = []

    # Check for ambiguous debit flags in telemetry first
    if telemetry.get("is_ambiguous_debit") or failure_code in ("GATEWAY_TIMEOUT_DEBIT_UNCERTAIN", "PENDING_BANK_RECON"):
        evidence.append(f"Ambiguous debit detected via failure_code={failure_code} or telemetry flag")
        return Diagnosis(
            case_id=case_id,
            root_cause="AMBIGUOUS_DEBIT_NETWORK_TIMEOUT",
            confidence=0.95,
            evidence=evidence
        )

    # Check explicit error code map
    if failure_code and failure_code in ERROR_CODE_MAP:
        category = ERROR_CODE_MAP[failure_code]
        evidence.append(f"Direct rule match on failure_code='{failure_code}'")
        if "http_status" in telemetry:
            evidence.append(f"Matching HTTP status: {telemetry['http_status']}")
        return Diagnosis(
            case_id=case_id,
            root_cause=category,
            confidence=0.99,
            evidence=evidence
        )

    # Fallback heuristic using HTTP status and error message
    http_status = telemetry.get("http_status")
    err_msg = str(telemetry.get("error_message", "")).lower()

    if http_status == 503 or "switch" in err_msg or "timeout" in err_msg:
        category = "ISSUER_TECHNICAL_DECLINE"
        evidence.append(f"Heuristic match on http_status={http_status} or message keywords")
        confidence = 0.80
    elif http_status == 402 or "balance" in err_msg or "funds" in err_msg:
        category = "INSUFFICIENT_FUNDS"
        evidence.append(f"Heuristic match on http_status={http_status} or balance keywords")
        confidence = 0.85
    elif "otp" in err_msg or "auth" in err_msg or "modal" in err_msg:
        category = "AUTHENTICATION_ABANDONED"
        evidence.append("Heuristic match on authentication/OTP keywords")
        confidence = 0.80
    elif "card" in err_msg or "vpa" in err_msg or "expired" in err_msg:
        category = "INVALID_PAYMENT_INSTRUMENT"
        evidence.append("Heuristic match on invalid instrument keywords")
        confidence = 0.80
    else:
        # Default conservative fallback
        category = "ISSUER_TECHNICAL_DECLINE"
        evidence.append("Default fallback classification for unrecognized error pattern")
        confidence = 0.50

    return Diagnosis(
        case_id=case_id,
        root_cause=category,
        confidence=confidence,
        evidence=evidence
    )
