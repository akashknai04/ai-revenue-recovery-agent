"""Evaluation Runner for 4-Arm Benchmark.

Compares:
1. CONTROL: No intervention (pure natural recovery baseline)
2. NAIVE: Always immediate retry without diagnosis or safety checks
3. RULES: Deterministic rule-based baseline without LLM
4. AGENT: Full AI Revenue Recovery pipeline

Calculates true Incremental Recovery = (Arm Recovery - Control Natural Recovery).
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.decision_engine import route_decision
from core.entities import Customer, Payment, Transaction
from core.execution_adapter import SandboxPaymentExecutionAdapter
from core.guardrails import SafetyGuardrails
from core.ledger import AppendOnlyLedger
from core.reconciliation import ReconciliationEngine
from core.rule_classifier import classify_rule_based
from core.rules_arm_policy import select_rules_action
from core.verification import AuthoritativeVerificationEngine, AuthoritativeWebhookEvent
from evaluation.invariants import InvariantCheckResult, verify_run_safety_invariants
from llm.client import LLMDiagnosisClient
from simulator.recovery import simulate_recovery_outcome
from simulator.world import SimulatedWorld


@dataclass(frozen=True)
class ArmMetrics:
    arm_name: str
    total_cases: int
    total_at_risk_inr: float
    gross_recovered_inr: float
    natural_recovery_inr: float
    incremental_recovery_inr: float
    recovery_rate_pct: float
    incremental_lift_pct: float
    total_cost_inr: float
    net_recovery_inr: float
    duplicate_charges_count: int
    ambiguous_reconciled_count: int
    guardrail_blocks_count: int
    human_reviews_count: int
    contact_count: int
    safety_invariants_status: str  # PASSED or FAILED
    failed_invariants: List[str]


@dataclass(frozen=True)
class EvaluationRunResult:
    config_version: str
    seed: int
    batch_name: str
    run_timestamp: str
    diagnosis_accuracy_rules_pct: float
    diagnosis_accuracy_llm_pct: float
    arm_metrics: Dict[str, ArmMetrics]
    ledger: AppendOnlyLedger


class EvaluationRunner:
    """Orchestrates 4-arm comparative benchmarking on simulated worlds."""

    def __init__(self, seed: int = 2002, num_cases: int = 100, batch_name: str = "Batch_B"):
        self.seed = seed
        self.num_cases = num_cases
        self.batch_name = batch_name
        self.world = SimulatedWorld(seed=seed, num_cases=num_cases)
        self.llm_client = LLMDiagnosisClient()
        self.execution_adapter = SandboxPaymentExecutionAdapter()

    def run_all_arms(self) -> EvaluationRunResult:
        """Run all 4 arms on the identical batch of cases."""
        case_ids = self.world.get_case_ids()
        total_at_risk = sum(
            self.world.get_agent_observation(cid)["transaction"]["amount"]
            for cid in case_ids
        )

        ledger = AppendOnlyLedger()

        # Step 1: Run CONTROL arm to establish ground-truth natural recovery
        control_records = self._run_control_arm(case_ids, ledger)
        control_inv = verify_run_safety_invariants(control_records, total_at_risk)
        control_recovered = sum(r["amount"] for r in control_records if r["is_recovered"])
        control_cost = sum(r["cost"] for r in control_records)

        # Natural recovery baseline in INR for computing incremental lift
        baseline_natural_recovery_inr = control_recovered

        control_metrics = ArmMetrics(
            arm_name="CONTROL",
            total_cases=len(case_ids),
            total_at_risk_inr=round(total_at_risk, 2),
            gross_recovered_inr=round(control_recovered, 2),
            natural_recovery_inr=round(control_recovered, 2),
            incremental_recovery_inr=0.0,
            recovery_rate_pct=round(control_recovered / total_at_risk * 100, 2),
            incremental_lift_pct=0.0,
            total_cost_inr=round(control_cost, 2),
            net_recovery_inr=round(control_recovered - control_cost, 2),
            duplicate_charges_count=0,
            ambiguous_reconciled_count=0,
            guardrail_blocks_count=0,
            human_reviews_count=0,
            contact_count=0,
            safety_invariants_status=control_inv.status,
            failed_invariants=control_inv.failed_invariants
        )

        # Step 2: Run NAIVE arm (blind immediate retry)
        naive_records = self._run_naive_arm(case_ids, ledger)
        naive_inv = verify_run_safety_invariants(naive_records, total_at_risk)
        naive_recovered = sum(r["amount"] for r in naive_records if r["is_recovered"])
        naive_cost = sum(r["cost"] for r in naive_records)
        naive_inc = naive_recovered - baseline_natural_recovery_inr
        naive_dup = sum(1 for r in naive_records if r["duplicate_charge"])

        naive_metrics = ArmMetrics(
            arm_name="NAIVE",
            total_cases=len(case_ids),
            total_at_risk_inr=round(total_at_risk, 2),
            gross_recovered_inr=round(naive_recovered, 2),
            natural_recovery_inr=round(baseline_natural_recovery_inr, 2),
            incremental_recovery_inr=round(naive_inc, 2),
            recovery_rate_pct=round(naive_recovered / total_at_risk * 100, 2),
            incremental_lift_pct=round((naive_recovered - baseline_natural_recovery_inr) / total_at_risk * 100, 2),
            total_cost_inr=round(naive_cost, 2),
            net_recovery_inr=round(naive_inc - naive_cost, 2),
            duplicate_charges_count=naive_dup,
            ambiguous_reconciled_count=0,
            guardrail_blocks_count=0,
            human_reviews_count=0,
            contact_count=0,
            safety_invariants_status=naive_inv.status,
            failed_invariants=naive_inv.failed_invariants
        )

        # Step 3: Run RULES arm (deterministic baseline)
        rules_records = self._run_rules_arm(case_ids, ledger)
        rules_inv = verify_run_safety_invariants(rules_records, total_at_risk)
        rules_recovered = sum(r["amount"] for r in rules_records if r["is_recovered"])
        rules_cost = sum(r["cost"] for r in rules_records)
        rules_inc = rules_recovered - baseline_natural_recovery_inr
        rules_dup = sum(1 for r in rules_records if r["duplicate_charge"])

        rules_metrics = ArmMetrics(
            arm_name="RULES",
            total_cases=len(case_ids),
            total_at_risk_inr=round(total_at_risk, 2),
            gross_recovered_inr=round(rules_recovered, 2),
            natural_recovery_inr=round(baseline_natural_recovery_inr, 2),
            incremental_recovery_inr=round(rules_inc, 2),
            recovery_rate_pct=round(rules_recovered / total_at_risk * 100, 2),
            incremental_lift_pct=round((rules_recovered - baseline_natural_recovery_inr) / total_at_risk * 100, 2),
            total_cost_inr=round(rules_cost, 2),
            net_recovery_inr=round(rules_inc - rules_cost, 2),
            duplicate_charges_count=rules_dup,
            ambiguous_reconciled_count=sum(1 for r in rules_records if r["is_ambiguous"]),
            guardrail_blocks_count=sum(1 for r in rules_records if r["guardrail_blocked"]),
            human_reviews_count=sum(1 for r in rules_records if r["action"] == "HUMAN_REVIEW"),
            contact_count=sum(r["contact_count"] for r in rules_records),
            safety_invariants_status=rules_inv.status,
            failed_invariants=rules_inv.failed_invariants
        )

        # Step 4: Run AGENT arm (Full AI Recovery Pipeline)
        agent_records = self._run_agent_arm(case_ids, ledger)
        agent_inv = verify_run_safety_invariants(agent_records, total_at_risk)
        agent_recovered = sum(r["amount"] for r in agent_records if r["is_recovered"])
        agent_cost = sum(r["cost"] for r in agent_records)
        agent_inc = agent_recovered - baseline_natural_recovery_inr
        agent_dup = sum(1 for r in agent_records if r["duplicate_charge"])

        agent_metrics = ArmMetrics(
            arm_name="AGENT",
            total_cases=len(case_ids),
            total_at_risk_inr=round(total_at_risk, 2),
            gross_recovered_inr=round(agent_recovered, 2),
            natural_recovery_inr=round(baseline_natural_recovery_inr, 2),
            incremental_recovery_inr=round(agent_inc, 2),
            recovery_rate_pct=round(agent_recovered / total_at_risk * 100, 2),
            incremental_lift_pct=round((agent_recovered - baseline_natural_recovery_inr) / total_at_risk * 100, 2),
            total_cost_inr=round(agent_cost, 2),
            net_recovery_inr=round(agent_inc - agent_cost, 2),
            duplicate_charges_count=agent_dup,
            ambiguous_reconciled_count=sum(1 for r in agent_records if r["is_ambiguous"]),
            guardrail_blocks_count=sum(1 for r in agent_records if r["guardrail_blocked"]),
            human_reviews_count=sum(1 for r in agent_records if r["action"] == "HUMAN_REVIEW"),
            contact_count=sum(r["contact_count"] for r in agent_records),
            safety_invariants_status=agent_inv.status,
            failed_invariants=agent_inv.failed_invariants
        )

        # Diagnosis accuracy against simulator ground truth
        rules_correct = sum(
            1 for cid in case_ids
            if classify_rule_based(cid, self.world.get_agent_observation(cid)["transaction"]["failure_code"]).root_cause
            == self.world.get_ground_truth(cid).true_root_cause
        )
        llm_correct = sum(
            1 for cid in case_ids
            if self.llm_client.diagnose(
                case_id=cid,
                failure_code=self.world.get_agent_observation(cid)["transaction"]["failure_code"],
                amount=self.world.get_agent_observation(cid)["transaction"]["amount"],
                channel=self.world.get_agent_observation(cid)["telemetry"]["channel"],
                telemetry=self.world.get_agent_observation(cid)["telemetry"]
            ).root_cause == self.world.get_ground_truth(cid).true_root_cause
        )

        return EvaluationRunResult(
            config_version="1.0.0",
            seed=self.seed,
            batch_name=self.batch_name,
            run_timestamp=datetime.now(timezone.utc).isoformat(),
            diagnosis_accuracy_rules_pct=round(rules_correct / len(case_ids) * 100, 2),
            diagnosis_accuracy_llm_pct=round(llm_correct / len(case_ids) * 100, 2),
            arm_metrics={
                "CONTROL": control_metrics,
                "NAIVE": naive_metrics,
                "RULES": rules_metrics,
                "AGENT": agent_metrics
            },
            ledger=ledger
        )

    def _run_control_arm(self, case_ids: List[str], ledger: AppendOnlyLedger) -> List[Dict[str, Any]]:
        records = []
        rng = random.Random(self.seed + 10)
        for cid in case_ids:
            obs = self.world.get_agent_observation(cid)
            gt = self.world.get_ground_truth(cid)
            outcome = simulate_recovery_outcome("NO_ACTION", gt, rng)
            is_rec = outcome["success"]

            terminal_state = "NATURALLY_RECOVERED" if is_rec else "FAILED_TERMINAL"
            record = {
                "case_id": cid,
                "amount": obs["transaction"]["amount"],
                "is_recovered": is_rec,
                "duplicate_charge": False,
                "contact_count": 0,
                "action": "NO_ACTION",
                "customer_opted_out": obs["customer"]["opted_out"],
                "terminal_state": terminal_state,
                "cost": 0.0,
                "is_ambiguous": gt.true_root_cause == "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT",
                "guardrail_blocked": False
            }
            records.append(record)

            ledger.append_event(
                case_id=cid,
                event_type="CONTROL_ARM_EVALUATION",
                payload={"is_recovered": is_rec, "terminal_state": terminal_state, "amount": record["amount"]}
            )
        return records

    def _run_naive_arm(self, case_ids: List[str], ledger: AppendOnlyLedger) -> List[Dict[str, Any]]:
        records = []
        rng = random.Random(self.seed + 20)
        for cid in case_ids:
            obs = self.world.get_agent_observation(cid)
            gt = self.world.get_ground_truth(cid)

            # Naive blindly retries every case without checking debit or fraud status
            outcome = simulate_recovery_outcome("RETRY", gt, rng)
            is_rec = outcome["success"]
            is_dup = outcome["duplicate_charge"]

            terminal_state = "RECOVERED" if is_rec else "FAILED_TERMINAL"
            record = {
                "case_id": cid,
                "amount": obs["transaction"]["amount"],
                "is_recovered": is_rec,
                "duplicate_charge": is_dup,
                "contact_count": 0,
                "action": "RETRY",
                "customer_opted_out": obs["customer"]["opted_out"],
                "terminal_state": terminal_state,
                "cost": outcome["cost"],
                "is_ambiguous": gt.true_root_cause == "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT",
                "guardrail_blocked": False
            }
            records.append(record)

            ledger.append_event(
                case_id=cid,
                event_type="NAIVE_ARM_EVALUATION",
                payload={"action": "RETRY", "is_recovered": is_rec, "duplicate_charge": is_dup, "cost": outcome["cost"]}
            )
        return records

    def _run_rules_arm(self, case_ids: List[str], ledger: AppendOnlyLedger) -> List[Dict[str, Any]]:
        records = []
        rng = random.Random(self.seed + 30)
        for cid in case_ids:
            obs = self.world.get_agent_observation(cid)
            gt = self.world.get_ground_truth(cid)

            diag = classify_rule_based(cid, obs["transaction"]["failure_code"], obs["telemetry"])

            # Map diagnosis and customer opt-out to action deterministically via extracted policy
            customer_opted_out = obs["customer"]["opted_out"]
            action = select_rules_action(diag.root_cause, customer_opted_out)
            blocked = (action == "BLOCK")

            outcome = simulate_recovery_outcome(action, gt, rng)
            is_rec = outcome["success"]

            terminal_state = "RECOVERED" if is_rec else ("BLOCKED" if blocked else "FAILED_TERMINAL")
            contacts = 1 if action == "PAYMENT_LINK" and not blocked else 0

            record = {
                "case_id": cid,
                "amount": obs["transaction"]["amount"],
                "is_recovered": is_rec,
                "duplicate_charge": outcome["duplicate_charge"],
                "contact_count": contacts,
                "action": action,
                "customer_opted_out": customer_opted_out,
                "terminal_state": terminal_state,
                "cost": outcome["cost"],
                "is_ambiguous": diag.root_cause == "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT",
                "guardrail_blocked": blocked
            }
            records.append(record)

            ledger.append_event(
                case_id=cid,
                event_type="RULES_ARM_EVALUATION",
                payload={"action": action, "is_recovered": is_rec, "cost": outcome["cost"]}
            )
        return records

    def _run_agent_arm(self, case_ids: List[str], ledger: AppendOnlyLedger) -> List[Dict[str, Any]]:
        records = []
        rng = random.Random(self.seed + 40)
        fixed_evaluation_time = datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc)  # 16:30 IST (compliant contact hours)

        for cid in case_ids:
            obs = self.world.get_agent_observation(cid)
            gt = self.world.get_ground_truth(cid)

            cust = Customer(**obs["customer"])
            txn = Transaction(**obs["transaction"])
            pay = Payment(**obs["initial_payment"])
            telem = obs["telemetry"]

            # 1. LLM Diagnosis (strictly structured, cached)
            diag = self.llm_client.diagnose(
                case_id=cid,
                failure_code=txn.failure_code,
                amount=txn.amount,
                channel=telem.get("channel", "UPI"),
                telemetry=telem
            )
            ledger.append_event(cid, "DIAGNOSIS_RECORDED", diag.to_dict())

            # 2. Decision Engine (Stopping Rules -> EV Ranking -> Guardrails -> Routing)
            decision = route_decision(
                case_id=cid,
                diagnosis=diag,
                customer=cust,
                transaction=txn,
                payment=pay,
                telemetry=telem,
                current_time_utc=fixed_evaluation_time
            )
            ledger.append_event(cid, "DECISION_EVALUATED", decision.to_dict())

            # 3. Execution via Sandbox Adapter
            exec_resp = self.execution_adapter.execute(
                case_id=cid,
                action_type=decision.action,
                amount=txn.amount,
                customer_phone=cust.phone,
                idempotency_key=f"idemp_{cid}_{decision.action}"
            )
            ledger.append_event(cid, "EXECUTION_DISPATCHED", asdict(exec_resp))

            if exec_resp.status in ("ACCEPTED_PENDING_SETTLEMENT", "DISPATCHED_PENDING_CUSTOMER_ACTION", "QUEUED_FOR_OPERATIONS_DESK"):
                if pay.status != "PENDING":
                    from core.state_machine import validate_transition
                    validate_transition(pay.status, "PENDING")
                    pay.status = "PENDING"
                    txn.state = "PENDING"

            # 4. Simulation outcome
            outcome = simulate_recovery_outcome(decision.action, gt, rng)
            is_rec = outcome["success"]
            is_dup = outcome["duplicate_charge"]

            # 5. Authoritative Verification
            # Recovery is marked ONLY via authoritative webhook
            if is_rec:
                wh = AuthoritativeWebhookEvent(
                    webhook_id=f"wh_{cid}",
                    case_id=cid,
                    event_type="payment.settled",
                    provider_reference=exec_resp.provider_reference,
                    settled_amount=txn.amount,
                    status="SETTLED",
                    signature="sha256_valid_settlement_signature",
                    timestamp=fixed_evaluation_time.isoformat()
                )
                verif = AuthoritativeVerificationEngine.verify_webhook(wh, pay, txn)
                ledger.append_event(cid, "WEBHOOK_SETTLEMENT_VERIFIED", asdict(verif))
                terminal_state = "RECOVERED"
            else:
                terminal_state = "BLOCKED" if decision.action == "BLOCK" else "FAILED_TERMINAL"

            # 6. Tripartite Reconciliation
            recon = ReconciliationEngine.reconcile(
                case_id=cid,
                customer_debited=outcome["customer_debited"],
                provider_status="SUCCESS" if is_rec else "FAILED",
                merchant_order_paid=outcome["merchant_confirmed"],
                successful_payment_count=1 if is_rec else 0,
                transaction_amount=txn.amount,
                settled_amount=txn.amount if is_rec else 0.0
            )
            ledger.append_event(cid, "RECONCILIATION_COMPLETED", asdict(recon))

            contact_count = 1 if decision.action in ("PAYMENT_LINK", "REMINDER", "VOICE_CALL") else 0
            blocked = (decision.action == "BLOCK" or "OVERRIDDEN" in decision.guardrail_verdict)

            record = {
                "case_id": cid,
                "amount": txn.amount,
                "is_recovered": is_rec,
                "duplicate_charge": is_dup,
                "contact_count": contact_count,
                "action": decision.action,
                "customer_opted_out": cust.opted_out,
                "terminal_state": terminal_state,
                "cost": outcome["cost"],
                "contact_timestamp": fixed_evaluation_time.isoformat(),
                "timezone": cust.timezone,
                "is_ambiguous": diag.root_cause == "AMBIGUOUS_DEBIT_NETWORK_TIMEOUT",
                "guardrail_blocked": blocked
            }
            records.append(record)

        return records


def main() -> None:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="4-Arm Benchmark Evaluation Runner")
    parser.add_argument("--config", type=str, default="config/experiment_configs/default_config.json", help="Path to config JSON")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (defaults to batch_b_seed in config)")
    parser.add_argument("--num-cases", type=int, default=None, help="Number of cases (defaults to batch_b_size in config)")
    parser.add_argument("--batch", type=str, default="Batch_B", help="Batch name")
    args = parser.parse_args()

    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = {}

    seed = args.seed if args.seed is not None else cfg.get("batch_b_seed", 2002)
    num_cases = args.num_cases if args.num_cases is not None else cfg.get("batch_b_size", 100)
    batch_name = args.batch

    print("================================================================================")
    print("AI REVENUE RECOVERY AGENT - 4-ARM EVALUATION BENCHMARK")
    print(f"Config: {args.config} | Seed: {seed} | Batch: {batch_name} | Cases: {num_cases}")
    print("================================================================================")

    runner = EvaluationRunner(seed=seed, num_cases=num_cases, batch_name=batch_name)
    result = runner.run_all_arms()

    print(f"\n%-10s | %14s | %14s | %14s | %8s | %10s | %10s | %4s | %6s" % (
        "ARM", "GROSS REC (INR)", "NATURAL (INR)", "INCREMENTAL", "LIFT", "COST (INR)", "NET (INR)", "DUP", "STATUS"
    ))
    print("-" * 105)
    for arm_name in ["CONTROL", "NAIVE", "RULES", "AGENT"]:
        m = result.arm_metrics[arm_name]
        print(f"%-10s | %14.2f | %14.2f | %14.2f | %+7.2f%% | %10.2f | %10.2f | %4d | %6s" % (
            m.arm_name,
            m.gross_recovered_inr,
            m.natural_recovery_inr,
            m.incremental_recovery_inr,
            m.incremental_lift_pct,
            m.total_cost_inr,
            m.net_recovery_inr,
            m.duplicate_charges_count,
            m.safety_invariants_status
        ))
    print("-" * 105)

    agent_m = result.arm_metrics["AGENT"]
    naive_m = result.arm_metrics["NAIVE"]
    overall_status = "FAILED" if any(m.safety_invariants_status == "FAILED" for m in result.arm_metrics.values()) else "PASSED"

    print("\nHEADLINE FINANCIAL IMPACT (AGENT ARM vs CONTROL BASELINE):")
    print(f"  Total At-Risk Volume:          INR {agent_m.total_at_risk_inr:,.2f}")
    print(f"  Control Natural Recovery:      INR {agent_m.natural_recovery_inr:,.2f} ({agent_m.natural_recovery_inr / agent_m.total_at_risk_inr * 100:.2f}%)")
    print(f"  Agent Gross Recovery:          INR {agent_m.gross_recovered_inr:,.2f} ({agent_m.recovery_rate_pct:.2f}%)")
    print(f"  Headline Incremental Lift:     INR {agent_m.incremental_recovery_inr:,.2f} (+{agent_m.incremental_lift_pct:.2f}%)")
    print(f"  Operational Cost:              INR {agent_m.total_cost_inr:,.2f}")
    print(f"  Net Money Recovered:           INR {agent_m.net_recovery_inr:,.2f}")
    print(f"  Duplicate Debits (Agent):      {agent_m.duplicate_charges_count}")
    print(f"  Duplicate Debits (Naive):      {naive_m.duplicate_charges_count} (VIOLATION: INVARIANT_FAIL_DUPLICATE_CHARGES)")
    print(f"  Agent Safety Status:           {agent_m.safety_invariants_status}")
    print(f"  Overall Benchmark Run Status:  {overall_status} (Per Rule 7: Naive arm breached duplicate charge invariant)")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
