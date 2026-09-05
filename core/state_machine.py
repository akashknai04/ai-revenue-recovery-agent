"""Transaction Truth Engine: Payment state normalization and transition validation.

Validates authoritative transitions between normalized payment states:
INITIATED, PENDING, SUCCESS, FAILED, UNKNOWN, REFUNDED.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class PaymentState(str, Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    REFUNDED = "REFUNDED"


class IllegalStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""
    pass


# Strict allowed transition graph
ALLOWED_TRANSITIONS: Dict[PaymentState, Set[PaymentState]] = {
    PaymentState.INITIATED: {
        PaymentState.PENDING,
        PaymentState.SUCCESS,
        PaymentState.FAILED,
        PaymentState.UNKNOWN,
    },
    PaymentState.PENDING: {
        PaymentState.SUCCESS,
        PaymentState.FAILED,
        PaymentState.UNKNOWN,
        PaymentState.REFUNDED,
    },
    PaymentState.UNKNOWN: {
        PaymentState.SUCCESS,
        PaymentState.FAILED,
        PaymentState.REFUNDED,
    },
    PaymentState.SUCCESS: {
        PaymentState.REFUNDED,
    },
    PaymentState.FAILED: {
        # A failed payment record transitions to PENDING when a recovery attempt is dispatched
        PaymentState.PENDING,
        PaymentState.UNKNOWN,
    },
    PaymentState.REFUNDED: set(),  # Terminal state
}


def normalize_state(raw_state: str) -> PaymentState:
    """Normalize raw provider state into standard PaymentState enum."""
    if not isinstance(raw_state, str):
        raise ValueError(f"State must be a string, got {type(raw_state)}")
    cleaned = raw_state.strip().upper()
    try:
        return PaymentState(cleaned)
    except ValueError:
        return PaymentState.UNKNOWN


def validate_transition(current: str | PaymentState, target: str | PaymentState) -> bool:
    """Validate that transition from current to target is legally permissible.

    Raises IllegalStateTransitionError if illegal.
    """
    curr_state = normalize_state(str(current)) if not isinstance(current, PaymentState) else current
    target_state = normalize_state(str(target)) if not isinstance(target, PaymentState) else target

    if target_state == curr_state:
        return True  # Idempotent state assertion

    allowed = ALLOWED_TRANSITIONS.get(curr_state, set())
    if target_state not in allowed:
        raise IllegalStateTransitionError(
            f"Illegal payment state transition: cannot transition from '{curr_state.value}' to '{target_state.value}'"
        )
    return True


def is_failed(state: str | PaymentState) -> bool:
    """Check if state is FAILED.

    NON-NEGOTIABLE INVARIANT: PENDING or UNKNOWN is NEVER treated as FAILED.
    """
    normalized = normalize_state(str(state)) if not isinstance(state, PaymentState) else state
    return normalized == PaymentState.FAILED


def is_terminal(state: str | PaymentState) -> bool:
    """Check if state is a final immutable state."""
    normalized = normalize_state(str(state)) if not isinstance(state, PaymentState) else state
    return normalized in (PaymentState.SUCCESS, PaymentState.REFUNDED)
