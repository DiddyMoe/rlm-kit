#!/usr/bin/env python3
"""
CI Integration Script for RLM Architecture Enforcement

Runs comprehensive checks to ensure RLM-only architecture is maintained:
1. Static scanning for direct model calls
2. Linting and formatting
3. Type checking
4. Unit and integration tests
5. Import validation

Exits with non-zero code if any checks fail, blocking CI/CD merges.
"""

import os
import subprocess
import sys
from pathlib import Path

# Bootstrap: repo root on path so path_utils is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repo_root import find_repo_root  # noqa: E402

sys.path.insert(0, str(find_repo_root(Path(__file__).resolve().parent)))
from path_utils import REPO_ROOT  # noqa: E402


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"🔍 Running: {description}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        if result.returncode == 0:
            print(f"✅ {description} PASSED")
            return True
        else:
            print(f"❌ {description} FAILED")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
    except Exception as e:
        print(f"❌ {description} ERROR: {e}")
        return False


def main():
    """Run all RLM architecture checks."""
    print("🚀 RLM Architecture CI Enforcement")
    print("=" * 50)

    checks_passed = 0
    total_checks = 0

    # Ensure we're in the project root
    os.chdir(REPO_ROOT)

    # 1. Static RLM scanning
    total_checks += 1
    if run_command(
        [
            sys.executable,
            "-m",
            "rlm.core.static_scanner",
            ".",
            "--exclude",
            "__pycache__",
            "--exclude",
            "*.pyc",
            "--exclude",
            ".git",
            "--exclude",
            "node_modules",
            "--exclude",
            "build",
            "--exclude",
            "dist",
            "--ci",
        ],
        "RLM Static Scanner",
    ):
        checks_passed += 1

    # 2. Import validation
    total_checks += 1
    if run_command(
        [sys.executable, "-c", "import rlm; print('RLM imports successful')"],
        "RLM Import Validation",
    ):
        checks_passed += 1

    # 3. Linting
    total_checks += 1
    if run_command(["uv", "run", "ruff", "check", "."], "Code Linting (ruff)"):
        checks_passed += 1

    # 4. Formatting check
    total_checks += 1
    if run_command(["uv", "run", "ruff", "format", "--check", "."], "Code Formatting (ruff)"):
        checks_passed += 1

    # 5. Type checking
    total_checks += 1
    if run_command(["uv", "run", "ty", "check", "."], "Type Checking (ty)"):
        checks_passed += 1

    # 6. Unit tests
    total_checks += 1
    if run_command(["uv", "run", "pytest", "--tb=short"], "Unit Tests"):
        checks_passed += 1

    # 7. Provenance gate (if PROVENANCE.json exists)
    provenance_file = REPO_ROOT / "PROVENANCE.json"
    changes_file = REPO_ROOT / "CHANGES.json"
    if provenance_file.exists() and changes_file.exists():
        total_checks += 1
        if run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "ci_provenance_gate.py"),
                "--provenance",
                str(provenance_file),
                "--changes",
                str(changes_file),
            ],
            "Provenance Gate Check",
        ):
            checks_passed += 1
    else:
        print("⚠️  Skipping provenance gate (PROVENANCE.json or CHANGES.json not found)")

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 CHECK SUMMARY: {checks_passed}/{total_checks} PASSED")

    if checks_passed == total_checks:
        print("🎉 ALL CHECKS PASSED - RLM ARCHITECTURE ENFORCED")
        return 0
    else:
        print("💥 CHECKS FAILED - BLOCKING MERGE")
        print("\n🔍 RLM ARCHITECTURE VIOLATION DETECTED")
        print("All code changes must maintain RLM-only model usage.")
        print("Direct LLM calls are forbidden - use RLM interface only.")
        print("See: https://arxiv.org/abs/2512.24601")
        return 1


if __name__ == "__main__":
    sys.exit(main())
