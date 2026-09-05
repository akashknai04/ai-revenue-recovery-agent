"""Voice Recovery Channel Adapter (Phase 12 Stretch).

Plugs into the existing PaymentExecutionAdapter interface and PromiseToPayTracker
with zero modifications to the Decision Engine, safety guardrails, or ledger.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from core.entities import Customer, Diagnosis, PromiseToPay, Transaction
from core.execution_adapter import ExecutionResponse, PaymentExecutionAdapter
from core.promise_tracker import PromiseToPayTracker


@dataclass(frozen=True)
class VoiceCallDisposition:
    case_id: str
    disposition: str  # PAID, PROMISED, REFUSED, UNREACHABLE
    script_used: str
    call_duration_sec: int
    ptp_promise: Optional[PromiseToPay] = None
    timestamp: str = ""


class VoiceRecoveryService:
    """Manages Hinglish script synthesis and voice call disposition tracking."""

    def __init__(
        self,
        execution_adapter: PaymentExecutionAdapter,
        promise_tracker: PromiseToPayTracker
    ):
        self.execution_adapter = execution_adapter
        self.promise_tracker = promise_tracker

    def generate_hinglish_script(
        self,
        customer_name: str,
        amount: float,
        diagnosis: Diagnosis
    ) -> Dict[str, Any]:
        """Synthesize a compliant, structured Hinglish call script adhering to JSON schema."""
        script_text = (
            f"Namaste {customer_name} ji, main payment assistance desk se bol raha hoon. "
            f"Aapka INR {amount:,.2f} ka payment bank switch issue ({diagnosis.root_cause}) "
            f"ke kaaran complete nahi ho paya tha. Kya main aapko ek safe alternate payment link bhejun, "
            f"ya aap kisi aage ki date par pay karna chahenge?"
        )

        response_payload = {
            "script_hinglish": script_text,
            "call_objective": "ASSIST_PAYMENT_OR_PROMISE",
            "disposition_options": ["PAID", "PROMISED", "REFUSED", "UNREACHABLE"]
        }
        return response_payload

    def dispatch_and_record_call(
        self,
        case_id: str,
        customer: Customer,
        transaction: Transaction,
        diagnosis: Diagnosis,
        simulated_disposition: str = "PROMISED",
        promised_days: int = 3
    ) -> VoiceCallDisposition:
        """Dispatch VOICE_CALL through existing ExecutionAdapter and handle disposition."""
        # 1. Execute via existing adapter interface
        exec_resp: ExecutionResponse = self.execution_adapter.execute(
            case_id=case_id,
            action_type="VOICE_CALL",
            amount=transaction.amount,
            customer_phone=customer.phone,
            idempotency_key=f"idemp_voice_{case_id}_{transaction.amount}"
        )

        # 2. Generate structured script
        script_data = self.generate_hinglish_script(customer.name, transaction.amount, diagnosis)

        # 3. Handle disposition
        ptp: Optional[PromiseToPay] = None
        now = datetime.now(timezone.utc)

        if simulated_disposition == "PROMISED":
            # Feeds into the exact same PromiseToPay tracker from Phase 6
            promised_date = (now + timedelta(days=promised_days)).strftime("%Y-%m-%d")
            ptp = self.promise_tracker.register_promise(
                promise_id=f"ptp_voice_{case_id}",
                case_id=case_id,
                promised_amount=transaction.amount,
                promised_date=promised_date
            )

        return VoiceCallDisposition(
            case_id=case_id,
            disposition=simulated_disposition,
            script_used=script_data["script_hinglish"],
            call_duration_sec=45,
            ptp_promise=ptp,
            timestamp=now.isoformat()
        )
