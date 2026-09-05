import sys
from pathlib import Path

# Add project root to sys.path
workspace_root = Path(__file__).resolve().parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from evaluation.runner import EvaluationRunner
from report.generator import save_reports


def main():
    print("Running 4-Arm Evaluation on Batch B (Seed: 2002, 100 cases)...")
    runner = EvaluationRunner(seed=2002, num_cases=100, batch_name="Batch_B")
    result = runner.run_all_arms()

    report_dir = Path(__file__).resolve().parent
    paths = save_reports(result, report_dir)

    print(f"Reports successfully generated:")
    print(f"  Markdown: {paths['markdown']}")
    print(f"  HTML:     {paths['html']}")
    print(f"\nHeadline Incremental Recovery: INR {result.arm_metrics['AGENT'].incremental_recovery_inr:,.2f}")
    print(f"Safety Invariant Status:        {result.arm_metrics['AGENT'].safety_invariants_status}")


if __name__ == "__main__":
    main()
