"""Core entity schemas for AI Revenue Recovery Agent.

Freezes all primary data models across transactions, payments,
customers, diagnoses, recovery actions, decisions, promises-to-pay,
ledger events, and experiments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_str() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RevenueEvent:
    """Generalized envelope for streaming financial and system events."""
    source: str
    entity_id: str
    amount: float
    status: str
    timestamps: Dict[str, Any]
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Transaction:
    """Representation of an order or checkout attempt at risk."""
    id: str
    customer_id: str
    amount: float
    currency: str = "INR"
    created_at: str = field(default_factory=utc_now_str)
    state: str = "INITIATED"  # INITIATED, PENDING, SUCCESS, FAILED, UNKNOWN, REFUNDED
    failure_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Payment:
    """Payment transaction attempt processed with provider."""
    id: str
    transaction_id: str
    provider_reference: Optional[str]
    amount: float
    status: str  # INITIATED, PENDING, SUCCESS, FAILED, UNKNOWN, REFUNDED
    debited_customer: bool = False
    confirmed_merchant: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Customer:
    """Customer profile and compliance state."""
    id: str
    name: str
    phone: str
    email: str
    risk_score: float  # 0.0 (lowest risk) to 1.0 (highest risk)
    opted_out: bool = False
    contact_count: int = 0
    timezone: str = "Asia/Kolkata"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Diagnosis:
    """Structured root-cause diagnosis emitted by rule baseline or LLM layer."""
    case_id: str
    root_cause: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now_str)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Alias for explicit LLM diagnosis output schema contract
DiagnosisOutput = Diagnosis



@dataclass(frozen=True)
class Action:
    """Definition of a recovery action with economic and regulatory attributes."""
    action_type: str  # NO_ACTION, RETRY, DELAYED_RETRY, PAYMENT_LINK, REMINDER, HUMAN_REVIEW, BLOCK, PROMISE_TO_PAY, VOICE_CALL
    cost: float
    risk: float
    expected_effect: str
    contact_frequency_cap: int
    stopping_condition: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Decision:
    """Auditable decision routing an action through policy and guardrails."""
    case_id: str
    action: str
    routing: str  # AUTO, HUMAN, BLOCK
    ev_score: float
    guardrail_verdict: str  # PASSED, OVERRIDDEN, BLOCKED
    timestamp: str = field(default_factory=utc_now_str)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromiseToPay:
    """Promise-to-pay commitment tracked until fulfillment or renegotiation."""
    id: str
    case_id: str
    promised_amount: float
    promised_date: str  # ISO date string e.g. YYYY-MM-DD
    status: str = "pending"  # pending, kept, broken, renegotiated
    created_at: str = field(default_factory=utc_now_str)

    def __post_init__(self):
        valid_statuses = {"pending", "kept", "broken", "renegotiated"}
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid PromiseToPay status '{self.status}'. Must be one of {valid_statuses}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LedgerEvent:
    """Immutable event stored in the append-only ledger with cryptographic hash chaining."""
    event_id: str
    case_id: str
    event_type: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=utc_now_str)
    prev_hash: str = "0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Experiment:
    """Experiment run metadata and tracking."""
    id: str
    config_version: str
    seed: int
    created_at: str = field(default_factory=utc_now_str)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
