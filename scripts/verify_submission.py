"""
AI Revenue Recovery Agent — Submission & Benchmark Verification Suite
Executes all automated checks required for the Razorpay AI Buildathon Track 03 submission.
"""

import sys
import subprocess
from pathlib import Path

def run_step(step_name: str, command: list[str], cwd: Path) -> bool:
    print(f"\n================================================================================")
    print(f">> RUNNING STEP: {step_name}")
    print(f"Command: {' '.join(command)}")
    print(f"================================================================================")
    result = subprocess.run(command, cwd=str(cwd), capture_output=False)
    if result.returncode == 0:
        print(f"[PASS] {step_name} succeeded.")
        return True
    else:
        print(f"[FAIL] {step_name} exited with code {result.returncode}.")
        return False

def main():
    root_dir = Path(__file__).resolve().parent.parent
    python_exe = sys.executable

    print("\n" + "#" * 80)
    print("#  AI REVENUE RECOVERY AGENT — SUBMISSION READINESS VERIFICATION")
    print("#  Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery")
    print("#" * 80)

    steps = [
        ("Full Test Suite (68 Tests)", [python_exe, "-m", "pytest", "-v"]),
        ("14-Stage End-to-End Pipeline Trace", [python_exe, "-m", "pytest", "tests/test_end_to_end_pipeline.py", "-v", "-s"]),
        ("Four-Arm Evaluation Benchmark (Batch B, Seed 2002)", [python_exe, "-m", "evaluation.runner", "--config", "config/experiment_configs/default_config.json", "--seed", "2002"]),
        ("Batch Report Generation & Ledger Traceability", [python_exe, "report/generate_report.py"]),
    ]

    all_passed = True
    for name, cmd in steps:
        if not run_step(name, cmd, root_dir):
            all_passed = False
            break

    print("\n" + "=" * 80)
    if all_passed:
        print(">> ALL VERIFICATION STEPS PASSED SUCCESSFULLY (100% GREEN)")
        print(">> The project is fully compliant, reproducible, and ready for submission!")
        print(">> Refer to SUBMISSION_KIT.md for pre-filled submission form fields.")
    else:
        print(">> VERIFICATION FAILED. Please review the output above.")
    print("=" * 80 + "\n")

    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
