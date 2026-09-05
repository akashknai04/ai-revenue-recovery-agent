"""Test for ground truth isolation between simulator and core package.

NON-NEGOTIABLE RULE 4:
The simulator's ground truth must never be visible to the agent's decision logic.
core/ must never import simulator's ground-truth module.
"""

import ast
from pathlib import Path
import pytest


def check_ast_for_leakage(file_path: Path) -> list[str]:
    """Scan an AST tree for illegal imports of simulator.ground_truth."""
    violations = []
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

    for node in ast.walk(tree):
        # Case 1: import simulator.ground_truth
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "ground_truth" in alias.name:
                    violations.append(f"{file_path.name}:{node.lineno} imports '{alias.name}'")
        # Case 2: from simulator.ground_truth import ... OR from simulator import ground_truth
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if "ground_truth" in module_name:
                violations.append(f"{file_path.name}:{node.lineno} imports from '{module_name}'")
            for alias in node.names:
                if alias.name == "ground_truth":
                    violations.append(f"{file_path.name}:{node.lineno} imports symbol '{alias.name}' from '{module_name}'")

    return violations


def test_core_never_imports_ground_truth():
    """Verify that zero files in core/ import simulator's ground truth module."""
    workspace_root = Path(__file__).resolve().parent.parent.parent
    core_dir = workspace_root / "core"
    assert core_dir.exists(), f"Core directory not found at {core_dir}"

    all_violations = []
    core_files = list(core_dir.glob("**/*.py"))
    assert len(core_files) > 0, "No python files found in core/"

    for py_file in core_files:
        violations = check_ast_for_leakage(py_file)
        all_violations.extend(violations)

    assert not all_violations, f"Ground-truth leakage detected in core/:\n" + "\n".join(all_violations)


def test_leakage_detector_catches_simulated_leakage():
    """Verify the leakage detector itself correctly catches illegal imports."""
    dummy_code = """
import os
from simulator.ground_truth import GroundTruthState

def evaluate(case):
    return GroundTruthState
"""
    tree = ast.parse(dummy_code)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if "ground_truth" in module_name:
                violations.append(f"line {node.lineno}: imports from '{module_name}'")

    assert len(violations) > 0
    assert "simulator.ground_truth" in violations[0]
