"""Unit tests for Phase 5: LLM diagnosis layer, schema validation, and replay caching."""

import json
import tempfile
from pathlib import Path
import pytest
from llm.client import LLMDiagnosisClient, SchemaValidationError
from simulator.world import SimulatedWorld


def test_schema_validation_accepts_valid_json():
    """Verify that compliant JSON is successfully accepted."""
    client = LLMDiagnosisClient(cache_file_path=Path(tempfile.mktemp(suffix=".jsonl")))
    valid_payload = json.dumps({
        "root_cause": "INSUFFICIENT_FUNDS",
        "confidence": 0.95,
        "evidence": ["Bank returned decline 51", "Balance check failed"]
    })
    parsed = client.validate_schema(valid_payload)
    assert parsed["root_cause"] == "INSUFFICIENT_FUNDS"
    assert parsed["confidence"] == 0.95
    assert len(parsed["evidence"]) == 2


def test_schema_validation_accepts_markdown_code_fenced_json():
    """Verify that LLM responses wrapped in ```json ... ``` markdown code blocks are parsed cleanly."""
    client = LLMDiagnosisClient(cache_file_path=Path(tempfile.mktemp(suffix=".jsonl")))
    markdown_wrapped = """```json
{
  "root_cause": "ISSUER_TECHNICAL_DECLINE",
  "confidence": 0.92,
  "evidence": ["Bank switch timeout at settlement"]
}
```"""
    parsed = client.validate_schema(markdown_wrapped)
    assert parsed["root_cause"] == "ISSUER_TECHNICAL_DECLINE"
    assert parsed["confidence"] == 0.92


def test_schema_validation_rejects_missing_fields():
    """Verify that missing required keys (root_cause, confidence, evidence) are rejected."""
    client = LLMDiagnosisClient(cache_file_path=Path(tempfile.mktemp(suffix=".jsonl")))

    # Missing root_cause
    with pytest.raises(SchemaValidationError, match="Invalid root_cause"):
        client.validate_schema(json.dumps({
            "confidence": 0.9,
            "evidence": ["evidence 1"]
        }))

    # Missing confidence
    with pytest.raises(SchemaValidationError, match="Invalid confidence"):
        client.validate_schema(json.dumps({
            "root_cause": "INSUFFICIENT_FUNDS",
            "evidence": ["evidence 1"]
        }))

    # Missing evidence
    with pytest.raises(SchemaValidationError, match="Evidence must be a non-empty list"):
        client.validate_schema(json.dumps({
            "root_cause": "INSUFFICIENT_FUNDS",
            "confidence": 0.9
        }))


def test_schema_validation_rejects_invalid_root_cause():
    """Verify that non-taxonomy root causes are strictly rejected."""
    client = LLMDiagnosisClient(cache_file_path=Path(tempfile.mktemp(suffix=".jsonl")))
    invalid_payload = json.dumps({
        "root_cause": "RANDOM_UNREGISTERED_ERROR",
        "confidence": 0.8,
        "evidence": ["some reason"]
    })
    with pytest.raises(SchemaValidationError, match="Invalid root_cause"):
        client.validate_schema(invalid_payload)


def test_schema_validation_rejects_invalid_confidence():
    """Verify that confidence out of [0.0, 1.0] (both > 1.0 and < 0.0) is rejected."""
    client = LLMDiagnosisClient(cache_file_path=Path(tempfile.mktemp(suffix=".jsonl")))

    # Out of range: > 1.0
    with pytest.raises(SchemaValidationError, match="Invalid confidence"):
        client.validate_schema(json.dumps({
            "root_cause": "ISSUER_TECHNICAL_DECLINE",
            "confidence": 1.5,
            "evidence": ["bank timeout"]
        }))

    # Out of range: < 0.0
    with pytest.raises(SchemaValidationError, match="Invalid confidence"):
        client.validate_schema(json.dumps({
            "root_cause": "ISSUER_TECHNICAL_DECLINE",
            "confidence": -0.25,
            "evidence": ["bank timeout"]
        }))


def test_schema_validation_rejects_empty_or_non_string_evidence():
    """Verify that empty evidence list or evidence containing non-strings is rejected."""
    client = LLMDiagnosisClient(cache_file_path=Path(tempfile.mktemp(suffix=".jsonl")))

    # Empty list
    with pytest.raises(SchemaValidationError, match="Evidence must be a non-empty list"):
        client.validate_schema(json.dumps({
            "root_cause": "ISSUER_TECHNICAL_DECLINE",
            "confidence": 0.8,
            "evidence": []
        }))

    # Non-string item
    with pytest.raises(SchemaValidationError, match="must be non-empty strings"):
        client.validate_schema(json.dumps({
            "root_cause": "ISSUER_TECHNICAL_DECLINE",
            "confidence": 0.8,
            "evidence": [12345]
        }))


def test_schema_validation_rejects_malformed_json():
    """Verify that malformed JSON strings and extra conversational prose without valid JSON are rejected."""
    client = LLMDiagnosisClient(cache_file_path=Path(tempfile.mktemp(suffix=".jsonl")))
    bad_json = "{ root_cause: 'ISSUER_TECHNICAL_DECLINE' missing closing"
    with pytest.raises(SchemaValidationError, match="Malformed JSON"):
        client.validate_schema(bad_json)

    conversational_prose = "I analyzed your transaction and believe it was insufficient funds."
    with pytest.raises(SchemaValidationError, match="Malformed JSON"):
        client.validate_schema(conversational_prose)


def test_diagnose_retries_on_malformed_first_attempt():
    """Verify that diagnose() retries when initial attempt produces malformed JSON."""
    client = LLMDiagnosisClient(cache_file_path=Path(tempfile.mktemp(suffix=".jsonl")))

    attempts = [
        "Extra conversational text with no JSON brackets",  # Attempt 1: Malformed
        json.dumps({                                         # Attempt 2: Valid
            "root_cause": "INSUFFICIENT_FUNDS",
            "confidence": 0.95,
            "evidence": ["Decline code 51 returned by bank switch"]
        })
    ]

    def mock_generate(*args, **kwargs):
        return attempts.pop(0)

    client._generate_raw_diagnosis = mock_generate

    diag = client.diagnose(
        case_id="case_retry_test",
        failure_code="INSUFFICIENT_BALANCE_51",
        amount=1500.0,
        channel="UPI",
        telemetry={"http_status": 402}
    )

    assert diag.root_cause == "INSUFFICIENT_FUNDS"
    assert diag.confidence == 0.95
    assert len(attempts) == 0  # Both attempts were consumed, proved retry occurred


def test_caching_and_replay_reproducibility():
    """CRITICAL ACCEPTANCE CRITERION: Re-running evaluation on saved batch produces identical diagnoses with 0 LLM calls."""
    cache_path = Path(tempfile.mktemp(suffix=".jsonl"))

    world = SimulatedWorld(seed=555, num_cases=20)
    case_ids = world.get_case_ids()

    # Pass 1: Fresh client with empty cache
    client_1 = LLMDiagnosisClient(cache_file_path=cache_path)
    results_pass_1 = []
    for cid in case_ids:
        obs = world.get_agent_observation(cid)
        diag = client_1.diagnose(
            case_id=cid,
            failure_code=obs["transaction"]["failure_code"],
            amount=obs["transaction"]["amount"],
            channel=obs["telemetry"]["channel"],
            telemetry=obs["telemetry"]
        )
        results_pass_1.append(diag)

    assert client_1.call_count == 20
    assert cache_path.exists()

    # Pass 2: New client instance reading from the populated cache
    client_2 = LLMDiagnosisClient(cache_file_path=cache_path)
    results_pass_2 = []
    for cid in case_ids:
        obs = world.get_agent_observation(cid)
        diag = client_2.diagnose(
            case_id=cid,
            failure_code=obs["transaction"]["failure_code"],
            amount=obs["transaction"]["amount"],
            channel=obs["telemetry"]["channel"],
            telemetry=obs["telemetry"]
        )
        results_pass_2.append(diag)

    # 0 new calls were made to the LLM generator
    assert client_2.call_count == 0

    # Exactly identical results
    for d1, d2 in zip(results_pass_1, results_pass_2):
        assert d1.case_id == d2.case_id
        assert d1.root_cause == d2.root_cause
        assert d1.confidence == d2.confidence
        assert d1.evidence == d2.evidence


def test_llm_client_isolation():
    """REGRESSION / ISOLATION TEST (Issue B): Proves LLM client modularity and decoupling.

    Verifies that:
    (a) The client parses and validates a mocked LLM response into a DiagnosisOutput correctly,
        even when the mocked response differs from the internal heuristic generator.
    (b) The append-only audit ledger records the LLM decision/diagnosis event with full metadata.
    (c) If the mocked response is malformed JSON or violates schema across all retries, the client
        catches the errors, retries, and falls back to deterministic rule-based diagnosis gracefully.

    Architectural Replay Note:
    In tests/test_four_arms.py::test_rules_vs_agent_decision_divergence_for_same_diagnosis, the test
    asserts `rule_diag.root_cause == llm_diag.root_cause` for its test cases. If a live model
    (e.g., claude-3-haiku or gpt-4o-mini) is plugged in, that test requires the model's output to
    match the rule-based root cause on those specific benchmark cases, or those cases must use
    a deterministic cache / fixture replay to maintain test reproducibility without network calls.
    """
    from core.entities import DiagnosisOutput
    from core.ledger import AppendOnlyLedger

    cache_dir = Path(tempfile.mkdtemp())
    cache_path_1 = cache_dir / "cache_mock.jsonl"
    client = LLMDiagnosisClient(cache_file_path=cache_path_1)

    # -------------------------------------------------------------------------
    # (a) Mock _generate_raw_diagnosis to return a valid JSON response different
    #     from what the deterministic generator would produce.
    #     For failure_code="BANK_DOWN_503", default generator produces ISSUER_TECHNICAL_DECLINE.
    #     We mock it to return AUTHENTICATION_ABANDONED.
    # -------------------------------------------------------------------------
    mock_payload = {
        "root_cause": "AUTHENTICATION_ABANDONED",
        "confidence": 0.88,
        "evidence": ["Custom LLM analysis: Customer abandoned 3DS authentication challenge window"]
    }
    client._generate_raw_diagnosis = lambda *args, **kwargs: json.dumps(mock_payload)

    diag = client.diagnose(
        case_id="case_iso_001",
        failure_code="BANK_DOWN_503",
        amount=2500.0,
        channel="UPI",
        telemetry={"http_status": 503}
    )

    # Verify (a): parsed and validated into DiagnosisOutput correctly
    assert isinstance(diag, DiagnosisOutput)
    assert diag.case_id == "case_iso_001"
    assert diag.root_cause == "AUTHENTICATION_ABANDONED"  # Mocked value, not ISSUER_TECHNICAL_DECLINE
    assert diag.confidence == 0.88
    assert diag.evidence == ["Custom LLM analysis: Customer abandoned 3DS authentication challenge window"]

    # -------------------------------------------------------------------------
    # (b) Verify that the audit ledger records the LLM decision with full metadata
    # -------------------------------------------------------------------------
    ledger = AppendOnlyLedger()
    event = ledger.append_event(
        case_id="case_iso_001",
        event_type="DIAGNOSIS_RECORDED",
        payload=diag.to_dict()
    )

    assert event.case_id == "case_iso_001"
    assert event.event_type == "DIAGNOSIS_RECORDED"
    assert event.payload["root_cause"] == "AUTHENTICATION_ABANDONED"
    assert event.payload["confidence"] == 0.88
    assert len(event.payload["evidence"]) == 1
    assert "timestamp" in event.payload
    assert ledger.verify_chain_integrity() is True

    # -------------------------------------------------------------------------
    # (c) Verify fallback: if mocked response is malformed or invalid across retries,
    #     client catches it, exhausts retries, and gracefully falls back to
    #     deterministic rule-based diagnosis.
    # -------------------------------------------------------------------------
    cache_path_2 = cache_dir / "cache_fallback.jsonl"
    fallback_client = LLMDiagnosisClient(cache_file_path=cache_path_2)

    call_counter = {"attempts": 0}

    def failing_mock(*args, **kwargs):
        call_counter["attempts"] += 1
        return "{ malformed_json: true, unclosed"

    fallback_client._generate_raw_diagnosis = failing_mock

    # For failure_code="INSUFFICIENT_BALANCE_51", rule-based classifier yields INSUFFICIENT_FUNDS
    fallback_diag = fallback_client.diagnose(
        case_id="case_iso_fallback",
        failure_code="INSUFFICIENT_BALANCE_51",
        amount=1200.0,
        channel="UPI",
        telemetry={"http_status": 402}
    )

    assert call_counter["attempts"] == 3  # Proves 3 retry attempts were made
    assert isinstance(fallback_diag, DiagnosisOutput)
    assert fallback_diag.root_cause == "INSUFFICIENT_FUNDS"  # Fallback to rule-based classification
    assert any("Fallback to rule-based diagnosis" in ev for ev in fallback_diag.evidence)

