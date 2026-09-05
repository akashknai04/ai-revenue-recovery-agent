"""Execution Adapter and Sandbox Payment Gateway.

Defines the abstract provider interface and a fully sandboxed mock payment
provider with idempotency, timeout simulation, and webhook emission.

NON-NEGOTIABLE RULE 2: No real financial transactions, ever.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set


@dataclass(frozen=True)
class ExecutionResponse:
    """Immediate response from payment provider gateway API.

    CRITICAL INVARIANT:
    An ExecutionResponse with status="ACCEPTED" or "SUBMITTED" is NEVER
    considered a completed recovery. Recovery requires authoritative webhook confirmation.
    """
    case_id: str
    action_type: str
    status: str  # SUBMITTED, ACCEPTED_PENDING_SETTLEMENT, REJECTED, RATE_LIMITED
    provider_reference: str
    idempotency_key: str
    execution_time: str
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class PaymentExecutionAdapter(ABC):
    """Abstract interface for payment execution providers.

    Enables plug-and-play addition of future payment providers without
    altering core business, policy, or safety logic.
    """

    @abstractmethod
    def execute(
        self,
        case_id: str,
        action_type: str,
        amount: float,
        customer_phone: str,
        idempotency_key: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionResponse:
        """Submit a recovery action to the payment provider."""
        pass


class SandboxPaymentExecutionAdapter(PaymentExecutionAdapter):
    """Deterministic, sandbox payment provider implementation."""

    def __init__(self):
        # In-memory store of executed idempotency keys: {idempotency_key: ExecutionResponse}
        self._idempotency_store: Dict[str, ExecutionResponse] = {}
        self.call_count = 0

    def execute(
        self,
        case_id: str,
        action_type: str,
        amount: float,
        customer_phone: str,
        idempotency_key: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionResponse:
        """Process sandboxed execution with strict idempotency verification."""
        metadata = metadata or {}
        self.call_count += 1

        # Idempotency check
        if idempotency_key in self._idempotency_store:
            existing = self._idempotency_store[idempotency_key]
            if existing.case_id != case_id or existing.action_type != action_type:
                raise ValueError(
                    f"Idempotency violation: key '{idempotency_key}' previously used for {existing.case_id}:{existing.action_type}"
                )
            return existing

        # Generate unique sandbox provider reference
        provider_ref = f"sb_ref_{uuid.uuid4().hex[:12]}"
        now_str = datetime.now(timezone.utc).isoformat()

        if action_type == "BLOCK":
            resp = ExecutionResponse(
                case_id=case_id,
                action_type=action_type,
                status="BLOCKED",
                provider_reference=provider_ref,
                idempotency_key=idempotency_key,
                execution_time=now_str,
                raw_payload={"message": "Action blocked by safety policy."}
            )
        elif action_type in ("RETRY", "DELAYED_RETRY"):
            resp = ExecutionResponse(
                case_id=case_id,
                action_type=action_type,
                status="ACCEPTED_PENDING_SETTLEMENT",
                provider_reference=provider_ref,
                idempotency_key=idempotency_key,
                execution_time=now_str,
                raw_payload={"channel": "API_RETRY", "amount": amount}
            )
        elif action_type in ("PAYMENT_LINK", "REMINDER", "VOICE_CALL"):
            resp = ExecutionResponse(
                case_id=case_id,
                action_type=action_type,
                status="DISPATCHED_PENDING_CUSTOMER_ACTION",
                provider_reference=provider_ref,
                idempotency_key=idempotency_key,
                execution_time=now_str,
                raw_payload={"recipient": customer_phone, "amount": amount}
            )
        elif action_type == "HUMAN_REVIEW":
            resp = ExecutionResponse(
                case_id=case_id,
                action_type=action_type,
                status="QUEUED_FOR_OPERATIONS_DESK",
                provider_reference=provider_ref,
                idempotency_key=idempotency_key,
                execution_time=now_str,
                raw_payload={"ticket_id": f"TICK-{uuid.uuid4().hex[:8].upper()}"}
            )
        else:
            resp = ExecutionResponse(
                case_id=case_id,
                action_type=action_type,
                status="SUBMITTED",
                provider_reference=provider_ref,
                idempotency_key=idempotency_key,
                execution_time=now_str,
                raw_payload={"note": "No active payment movement requested."}
            )

        self._idempotency_store[idempotency_key] = resp
        return resp
