"""Append-only, hash-chained audit ledger.

NON-NEGOTIABLE RULE 3:
Every state transition is recorded as an event.
Never overwrite or delete history — append-only ledger from the start.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.entities import LedgerEvent


class LedgerMutationError(RuntimeError):
    """Raised when an illegal attempt to mutate or delete ledger history is detected."""
    pass


def calculate_event_hash(
    event_id: str,
    case_id: str,
    event_type: str,
    payload: Dict[str, Any],
    timestamp: str,
    prev_hash: str
) -> str:
    """Calculate cryptographic SHA-256 hash of a ledger entry."""
    serialized = json.dumps(
        {
            "event_id": event_id,
            "case_id": case_id,
            "event_type": event_type,
            "payload": payload,
            "timestamp": timestamp,
            "prev_hash": prev_hash
        },
        sort_keys=True
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class AppendOnlyLedger:
    """Tamper-evident, hash-chained append-only event ledger."""

    def __init__(self, persistence_path: Optional[Path] = None):
        self._events: List[LedgerEvent] = []
        self._hashes: List[str] = []
        self._case_index: Dict[str, List[int]] = {}
        self.persistence_path = persistence_path
        self._last_hash = "0" * 64  # Genesis hash

    def append_event(
        self,
        case_id: str,
        event_type: str,
        payload: Dict[str, Any],
        timestamp: Optional[str] = None
    ) -> LedgerEvent:
        """Append a new immutable event to the hash-chained ledger."""
        now_str = timestamp or datetime.now(timezone.utc).isoformat()
        event_index = len(self._events)
        event_id = f"evt_{event_index:06d}"

        # Current hash chains to the previous hash
        prev_h = self._last_hash
        current_hash = calculate_event_hash(
            event_id=event_id,
            case_id=case_id,
            event_type=event_type,
            payload=payload,
            timestamp=now_str,
            prev_hash=prev_h
        )

        event = LedgerEvent(
            event_id=event_id,
            case_id=case_id,
            event_type=event_type,
            payload=payload,
            timestamp=now_str,
            prev_hash=prev_h
        )

        self._events.append(event)
        self._hashes.append(current_hash)
        self._last_hash = current_hash

        if case_id not in self._case_index:
            self._case_index[case_id] = []
        self._case_index[case_id].append(event_index)

        # Append to disk if persistence configured
        if self.persistence_path:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persistence_path, "a", encoding="utf-8") as f:
                record = {**event.to_dict(), "current_hash": current_hash}
                f.write(json.dumps(record) + "\n")

        return event

    def __setitem__(self, index, value):
        """Disallow mutation of past records."""
        raise LedgerMutationError("AppendOnlyLedger is immutable. Overwriting past entries is prohibited.")

    def __delitem__(self, index):
        """Disallow deletion of past records."""
        raise LedgerMutationError("AppendOnlyLedger is immutable. Deleting past entries is prohibited.")

    def verify_chain_integrity(self) -> bool:
        """Cryptographically verify the hash chain from genesis to head."""
        expected_prev = "0" * 64
        for idx, (event, stored_hash) in enumerate(zip(self._events, self._hashes)):
            if event.prev_hash != expected_prev:
                raise LedgerMutationError(f"Tamper detected: event {idx} prev_hash broken.")

            recalculated = calculate_event_hash(
                event_id=event.event_id,
                case_id=event.case_id,
                event_type=event.event_type,
                payload=event.payload,
                timestamp=event.timestamp,
                prev_hash=event.prev_hash
            )
            if recalculated != stored_hash:
                raise LedgerMutationError(f"Tamper detected: event {idx} payload or header mutated.")

            expected_prev = stored_hash
        return True

    def reconstruct_case_lifecycle(self, case_id: str) -> List[Dict[str, Any]]:
        """Reconstruct the entire lifecycle for a case exclusively from the ledger.

        CRITICAL ACCEPTANCE CRITERION:
        Lifecycle can be fully reconstructed with no external data dependencies.
        """
        indices = self._case_index.get(case_id, [])
        lifecycle = []
        for idx in indices:
            evt = self._events[idx]
            lifecycle.append({
                "event_id": evt.event_id,
                "event_type": evt.event_type,
                "timestamp": evt.timestamp,
                "payload": evt.payload,
                "prev_hash": evt.prev_hash,
                "current_hash": self._hashes[idx]
            })
        return lifecycle

    def get_all_events(self) -> List[LedgerEvent]:
        """Return shallow copy of all ledger events."""
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)
