"""Export real evaluation benchmark data to JSON for dashboard visualization.

Reads the authoritative EvaluationRunResult from evaluation.runner and writes
a clean, self-contained dashboard_data.json for the read-only viewer dashboard.

Strictly non-negotiable: all figures are dynamically derived from the real run,
never hand-typed or synthesized.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# Add project root to sys.path
workspace_root = Path(__file__).resolve().parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from evaluation.runner import EvaluationRunner


def export_dashboard_data(output_path: Path | None = None) -> dict:
    """Run benchmark evaluation and export dashboard data JSON."""
    runner = EvaluationRunner(seed=2002, num_cases=100, batch_name="Batch_B")
    result = runner.run_all_arms()

    agent_m = result.arm_metrics["AGENT"]
    ctrl_m = result.arm_metrics["CONTROL"]
    naive_m = result.arm_metrics["NAIVE"]
    rules_m = result.arm_metrics["RULES"]

    # Build arms matrix
    arms = []
    for name in ["CONTROL", "NAIVE", "RULES", "AGENT"]:
        m = result.arm_metrics[name]
        arms.append({
            "name": m.arm_name,
            "gross_recovery": round(m.gross_recovered_inr, 2),
            "incremental": round(m.incremental_recovery_inr, 2),
            "lift_pct": round(m.incremental_lift_pct, 2),
            "cost": round(m.total_cost_inr, 2),
            "net": round(m.net_recovery_inr, 2),
            "duplicate_charges": m.duplicate_charges_count,
            "status": m.safety_invariants_status,
        })

    # Action mix from DECISION_EVALUATED ledger events
    action_counts = Counter(
        e.payload.get("action") or e.payload.get("action_type")
        for e in result.ledger.get_all_events()
        if e.event_type == "DECISION_EVALUATED"
    )
    action_mix = [
        {"action": act, "count": count}
        for act, count in action_counts.most_common()
    ]

    # Recent ledger events (last 10 events)
    recent_events = []
    all_events = result.ledger.get_all_events()
    for evt in all_events[-10:]:
        summary_items = []
        for k, v in list(evt.payload.items())[:3]:
            summary_items.append(f"{k}: {v}")
        summary_str = ", ".join(summary_items)
        if len(summary_str) > 90:
            summary_str = summary_str[:87] + "..."

        recent_events.append({
            "event_id": evt.event_id,
            "case_id": evt.case_id,
            "event_type": evt.event_type,
            "timestamp": evt.timestamp,
            "payload_summary": summary_str,
        })

    dashboard_data = {
        "engine_label": "Deterministic Sandbox Engine",
        "total_at_risk": round(agent_m.total_at_risk_inr, 2),
        "total_recovered_gross": round(agent_m.gross_recovered_inr, 2),
        "total_incremental_recovery": round(agent_m.incremental_recovery_inr, 2),
        "total_incremental_lift_pct": round(agent_m.incremental_lift_pct, 2),
        "net_recovery": round(agent_m.net_recovery_inr, 2),
        "arms": arms,
        "action_mix": action_mix,
        "recent_ledger_events": recent_events,
        "decision_engine_stats": {
            "diagnosis_accuracy_rules_pct": round(result.diagnosis_accuracy_rules_pct, 1),
            "human_reviews_count": agent_m.human_reviews_count,
            "guardrail_blocks_count": agent_m.guardrail_blocks_count,
            "ambiguous_reconciled_count": agent_m.ambiguous_reconciled_count,
        },
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, indent=2)
        print(f"Successfully exported dashboard data to: {output_path}")

    return dashboard_data


if __name__ == "__main__":
    report_dir = Path(__file__).resolve().parent
    target_file = report_dir / "dashboard_data.json"
    export_dashboard_data(target_file)
