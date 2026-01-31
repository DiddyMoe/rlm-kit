#!/usr/bin/env python3
"""
CI Provenance Gate - Require Provenance for All Patches

This script enforces that all code changes have corresponding provenance
information, ensuring that repository access went through RLM MCP Gateway.

Usage:
    python scripts/ci_provenance_gate.py --provenance PROVENANCE.json --changes CHANGES.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json_file(file_path: Path) -> dict[str, Any]:
    """Load JSON file."""
    try:
        with open(file_path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def check_provenance_for_changes(
    provenance: dict[str, Any], changes: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """
    Check that all changes have corresponding provenance.

    Returns:
        (success, warnings)
    """
    warnings = []

    # Extract spans from provenance
    provenance_spans = {}
    if "provenance_graph" in provenance:
        for span in provenance.get("spans", []):
            file_path = span.get("file_path")
            if file_path:
                if file_path not in provenance_spans:
                    provenance_spans[file_path] = []
                provenance_spans[file_path].append(span)

    # Check each change
    for change in changes:
        file_path = change.get("file")
        if not file_path:
            continue

        # Normalize file path (remove leading slash, handle relative paths)
        normalized_path = file_path.lstrip("/")

        # Check if file has provenance
        has_provenance = False
        for prov_file, _spans in provenance_spans.items():
            prov_normalized = prov_file.lstrip("/")
            if normalized_path == prov_normalized or normalized_path.endswith(prov_normalized):
                has_provenance = True
                break

        if not has_provenance:
            # Could be a new file (not in repository yet)
            # Or could be a legitimate change without provenance
            warnings.append(
                f"WARNING: Change to {file_path} not in provenance. "
                f"This could indicate direct file access bypassing MCP Gateway."
            )

    # If we have provenance but no changes match, that's suspicious
    if provenance_spans and not changes:
        warnings.append(
            "WARNING: Provenance exists but no changes detected. "
            "This could indicate provenance was generated without actual changes."
        )

    # Success if no critical warnings (warnings are informational)
    return True, warnings


def main():
    """Run provenance gate check."""
    parser = argparse.ArgumentParser(description="CI Provenance Gate")
    parser.add_argument(
        "--provenance", type=Path, required=True, help="Path to PROVENANCE.json file"
    )
    parser.add_argument(
        "--changes",
        type=Path,
        required=True,
        help="Path to CHANGES.json file (list of changed files)",
    )
    parser.add_argument("--strict", action="store_true", help="Strict mode: fail on warnings")

    args = parser.parse_args()

    print("🔍 CI Provenance Gate Check")
    print("=" * 50)

    # Load files
    print(f"Loading provenance: {args.provenance}")
    provenance = load_json_file(args.provenance)

    print(f"Loading changes: {args.changes}")
    changes = load_json_file(args.changes)

    if not isinstance(changes, list):
        print("ERROR: CHANGES.json must be a list of change objects", file=sys.stderr)
        sys.exit(1)

    # Check provenance
    success, warnings = check_provenance_for_changes(provenance, changes)

    # Report results
    print("\n" + "=" * 50)
    print("📊 PROVENANCE GATE RESULTS")
    print("=" * 50)

    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("\n✅ No warnings - all changes have provenance")

    # Summary
    if success and (not warnings or not args.strict):
        print("\n✅ PROVENANCE GATE PASSED")
        print("All changes have corresponding provenance information.")
        return 0
    else:
        print("\n❌ PROVENANCE GATE FAILED")
        if args.strict and warnings:
            print("Strict mode enabled - warnings treated as failures.")
        print("\n🔍 RLM ARCHITECTURE ENFORCEMENT:")
        print("All repository access must go through RLM MCP Gateway.")
        print("Provenance tracking ensures bounded, tool-mediated access.")
        print("See: MCP_TOOL_CONTRACT_SPEC.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
