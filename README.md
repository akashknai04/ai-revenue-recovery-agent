
**Headline numbers (Batch B, seed 2002, 100 cases):**

| Arm | Gross Recovery | Incremental Recovery | Lift | Duplicate Charges | Status |
|---|---:|---:|---:|---:|---|
| CONTROL | ₹428,676.08 | ₹0.00 | +0.00% | 0 | PASSED |
| NAIVE | ₹260,040.21 | −₹168,635.87 | −10.47% | **9** | **FAILED** |
| RULES | ₹770,418.91 | ₹341,742.83 | +21.22% | 0 | PASSED |
| **AGENT** | **₹995,546.12** | **₹566,870.04** | **+35.20%** | **0** | **PASSED** |

The overall run status is honestly reported as **FAILED**, because the NAIVE arm breached the duplicate-charge safety invariant — per Rule 7, this is surfaced, not hidden. It's included deliberately, as evidence the safety system correctly detects and reports unsafe behavior instead of only ever showing a clean result.

Every number above is reconstructable from the append-only, SHA-256 hash-chained ledger (761 events for this run) with no other data source required.

---

## 6. Build & Review History

For the complete project lifecycle — the phase-by-phase build log (Phases 1–12), all rounds of post-build verification and correction, and the final verified-state summary — see [`PROGRESS.md`](./PROGRESS.md).

---

## Getting Started

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the full test suite
python -m pytest -v

# 3. Run the four-arm evaluation benchmark
python -m evaluation.runner --config config/experiment_configs/default_config.json --seed 2002

# 4. Trace a single case through the full pipeline
python -m pytest tests/test_end_to_end_pipeline.py -v -s
```

No external API keys or network access are required to run any part of this project.

For a guided walkthrough of five key capabilities (recoverable failure, ambiguous debit protection, promise-to-pay lifecycle, rules-vs-agent divergence, and the full batch benchmark), see [`DEMO_RUNBOOK.md`](./DEMO_RUNBOOK.md).
