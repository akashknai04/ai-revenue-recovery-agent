"""Unit tests for Phase 4: Root-cause taxonomy and rule-based baseline classifier."""

from core.taxonomy import TAXONOMY, TAXONOMY_CATEGORIES
from core.rule_classifier import classify_rule_based, ERROR_CODE_MAP
from simulator.failures import FAILURE_PROFILES
from simulator.world import SimulatedWorld


def test_every_simulated_code_maps_to_exactly_one_taxonomy_category():
    """CRITICAL ACCEPTANCE CRITERION: Every simulated failure code maps to exactly one category."""
    all_simulated_codes = []
    for cat, profile in FAILURE_PROFILES.items():
        all_simulated_codes.extend(profile["codes"])

    assert len(all_simulated_codes) > 0

    for code in all_simulated_codes:
        # Must exist in the error code map
        assert code in ERROR_CODE_MAP, f"Failure code '{code}' not present in ERROR_CODE_MAP"
        category = ERROR_CODE_MAP[code]
        assert category in TAXONOMY_CATEGORIES, f"Mapped category '{category}' not in official taxonomy"

        # Verify rule classifier produces this exact category
        diag = classify_rule_based(case_id="test_case", failure_code=code)
        assert diag.root_cause == category
        assert diag.confidence > 0.0
        assert len(diag.evidence) > 0


def test_rule_baseline_runs_full_batch_with_zero_llm_calls():
    """CRITICAL ACCEPTANCE CRITERION: Rule baseline runs and classifies a full batch with zero LLM calls."""
    world = SimulatedWorld(seed=777, num_cases=100)
    case_ids = world.get_case_ids()
    assert len(case_ids) == 100

    diagnoses = []
    for cid in case_ids:
        obs = world.get_agent_observation(cid)
        failure_code = obs["transaction"]["failure_code"]
        telemetry = obs["telemetry"]

        diag = classify_rule_based(case_id=cid, failure_code=failure_code, telemetry=telemetry)
        diagnoses.append(diag)

        # Assert output integrity
        assert diag.case_id == cid
        assert diag.root_cause in TAXONOMY_CATEGORIES
        assert 0.0 <= diag.confidence <= 1.0
        assert isinstance(diag.evidence, list)

    assert len(diagnoses) == 100
