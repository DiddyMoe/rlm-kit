#!/usr/bin/env python3
"""
Test script for RLM MCP Gateway

This script validates that the MCP gateway is working correctly by testing
all major tools and verifying compliance with the strict tool contract.
"""

import sys
from pathlib import Path

# Bootstrap: repo root on path so path_utils and scripts are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repo_root import find_repo_root  # noqa: E402

sys.path.insert(0, str(find_repo_root(Path(__file__).resolve().parent)))
from path_utils import REPO_ROOT  # noqa: E402
from scripts.rlm_mcp_gateway import RLMMCPGateway


def test_session_management(gateway: RLMMCPGateway):
    """Test session creation and management."""
    print("Testing session management...")

    # Create session
    result = gateway.session_create({"max_tool_calls": 50, "timeout_ms": 300000})
    assert result.get("session_id"), "Session creation failed"
    session_id = result["session_id"]
    print(f"  ✅ Session created: {session_id}")

    # Set roots
    repo_root = REPO_ROOT
    result = gateway.roots_set(session_id, [str(repo_root)])
    assert result.get("success"), f"Roots set failed: {result.get('error')}"
    print(f"  ✅ Roots set: {result.get('roots')}")

    # Close session
    result = gateway.session_close(session_id)
    assert result.get("success"), "Session close failed"
    print("  ✅ Session closed")

    return session_id


def test_filesystem_metadata(gateway: RLMMCPGateway, session_id: str):
    """Test filesystem metadata tools."""
    print("\nTesting filesystem metadata tools...")

    repo_root = REPO_ROOT

    # Set roots
    gateway.roots_set(session_id, [str(repo_root)])

    # List directory
    result = gateway.fs_list(session_id, str(repo_root / "rlm"), depth=1)
    assert result.get("success"), f"fs.list failed: {result.get('error')}"
    assert "items" in result, "Missing items in response"
    print(f"  ✅ fs.list: {len(result['items'])} items")

    # Create manifest
    result = gateway.fs_manifest(session_id, str(repo_root / "rlm" / "core"))
    assert result.get("success"), f"fs.manifest failed: {result.get('error')}"
    assert "files" in result, "Missing files in response"
    print(f"  ✅ fs.manifest: {len(result['files'])} files")

    # Verify no content in metadata
    for item in result.get("items", [])[:5]:
        assert "content" not in item, "Metadata should not contain content"
    print("  ✅ Metadata-only (no content dumps)")


def test_bounded_reading(gateway: RLMMCPGateway, session_id: str):
    """Test bounded span reading."""
    print("\nTesting bounded span reading...")

    repo_root = REPO_ROOT
    test_file = repo_root / "rlm" / "core" / "types.py"

    gateway.roots_set(session_id, [str(repo_root)])

    # Create file handle
    result = gateway.fs_handle_create(session_id, str(test_file))
    assert result.get("success"), f"Handle create failed: {result.get('error')}"
    file_handle = result["file_handle"]
    print(f"  ✅ File handle created: {file_handle}")

    # Read bounded span
    result = gateway.span_read(session_id, file_handle, start_line=1, end_line=50, max_bytes=8192)
    assert result.get("success"), f"span.read failed: {result.get('error')}"
    assert "content" in result, "Missing content in response"
    assert result.get("start_line") == 1, "Wrong start line"
    assert result.get("end_line") <= 50, "Wrong end line"

    content_bytes = len(result["content"].encode("utf-8"))
    assert content_bytes <= 8192, f"Content too large: {content_bytes} > 8192"
    print(
        f"  ✅ span.read: {result['end_line'] - result['start_line'] + 1} lines, {content_bytes} bytes"
    )

    # Verify provenance
    assert "provenance" in result, "Missing provenance"
    assert result["provenance"]["file_path"], "Missing file_path in provenance"
    print(f"  ✅ Provenance tracked: {result['provenance']['file_path']}")

    # Test bounds enforcement
    result = gateway.span_read(session_id, file_handle, start_line=1, end_line=500, max_bytes=8192)
    assert (
        not result.get("success") or (result.get("end_line") - result.get("start_line") + 1) <= 200
    ), "Span bounds not enforced"
    print("  ✅ Bounds enforced (max 200 lines)")


def test_search(gateway: RLMMCPGateway, session_id: str):
    """Test search tools."""
    print("\nTesting search tools...")

    repo_root = REPO_ROOT
    gateway.roots_set(session_id, [str(repo_root)])

    # Semantic search
    result = gateway.search_query(session_id, "class RLM", str(repo_root / "rlm"), k=5)
    assert result.get("success"), f"search.query failed: {result.get('error')}"
    assert "results" in result, "Missing results"

    # Verify references only (no content)
    for res in result["results"]:
        assert "content" not in res, "Search should return references only"
        assert "file_path" in res, "Missing file_path in result"
        assert "start_line" in res, "Missing start_line in result"
    print(f"  ✅ search.query: {len(result['results'])} references (no content)")

    # Regex search
    result = gateway.search_regex(session_id, "def.*completion", str(repo_root / "rlm"), k=5)
    assert result.get("success"), f"search.regex failed: {result.get('error')}"
    assert "results" in result, "Missing results"
    print(f"  ✅ search.regex: {len(result['results'])} references")


def test_provenance(gateway: RLMMCPGateway, session_id: str):
    """Test provenance tracking."""
    print("\nTesting provenance tracking...")

    repo_root = REPO_ROOT
    gateway.roots_set(session_id, [str(repo_root)])

    # Perform some operations
    test_file = repo_root / "rlm" / "core" / "rlm.py"
    handle_result = gateway.fs_handle_create(session_id, str(test_file))
    if handle_result.get("success"):
        gateway.span_read(session_id, handle_result["file_handle"], 1, 50)

    # Get provenance report
    result = gateway.provenance_report(session_id)
    assert result.get("success"), f"provenance.report failed: {result.get('error')}"
    assert "provenance_graph" in result, "Missing provenance_graph"

    provenance = result["provenance_graph"]
    assert "spans" in provenance, "Missing spans in provenance"
    assert "tool_calls" in provenance, "Missing tool_calls in provenance"
    print(
        f"  ✅ Provenance tracked: {len(provenance.get('spans', []))} spans, {provenance.get('tool_calls', 0)} tool calls"
    )


def test_budget_enforcement(gateway: RLMMCPGateway):
    """Test budget enforcement."""
    print("\nTesting budget enforcement...")

    # Create session with small budget
    result = gateway.session_create(
        {"max_tool_calls": 2, "max_output_bytes": 1000, "timeout_ms": 1000}
    )
    session_id = result["session_id"]

    repo_root = REPO_ROOT
    gateway.roots_set(session_id, [str(repo_root)])

    # Exceed tool call budget
    gateway.fs_list(session_id, str(repo_root))
    gateway.fs_list(session_id, str(repo_root))
    result = gateway.fs_list(session_id, str(repo_root))
    assert not result.get("success"), "Budget should be exceeded"
    assert (
        "budget" in result.get("error", "").lower() or "exceeded" in result.get("error", "").lower()
    ), "Should return budget error"
    print(f"  ✅ Budget enforcement: {result.get('error')}")


def test_security(gateway: RLMMCPGateway, session_id: str):
    """Test security features."""
    print("\nTesting security features...")

    repo_root = REPO_ROOT
    gateway.roots_set(session_id, [str(repo_root)])

    # Test path traversal prevention
    result = gateway.fs_list(session_id, "/etc/passwd")
    assert not result.get("success"), "Path traversal should be blocked"
    print("  ✅ Path traversal blocked")

    # Test restricted paths
    result = gateway.fs_list(session_id, str(repo_root / ".git"))
    # Should either fail or filter out .git
    if result.get("success"):
        items = result.get("items", [])
        git_items = [i for i in items if ".git" in str(i)]
        assert len(git_items) == 0, ".git should be filtered"
    print("  ✅ Restricted paths filtered")


def run_smoke(gateway: RLMMCPGateway) -> int:
    """Smoke test: session.create → roots.set → fs.list → handle.create → span.read."""
    print("Smoke test: session → roots → list → handle → span.read")
    repo_root = REPO_ROOT
    result = gateway.session_create()
    assert result.get("session_id"), "Session creation failed"
    session_id = result["session_id"]
    result = gateway.roots_set(session_id, [str(repo_root)])
    assert result.get("success"), f"roots.set failed: {result.get('error')}"
    result = gateway.fs_list(session_id, str(repo_root / "rlm"), depth=1)
    assert result.get("success"), f"fs.list failed: {result.get('error')}"
    test_file = repo_root / "rlm" / "core" / "types.py"
    result = gateway.fs_handle_create(session_id, str(test_file))
    assert result.get("success"), f"handle.create failed: {result.get('error')}"
    file_handle = result["file_handle"]
    result = gateway.span_read(session_id, file_handle, start_line=1, end_line=50, max_bytes=8192)
    assert result.get("success"), f"span.read failed: {result.get('error')}"
    assert "content" in result, "Missing content"
    print("  ✅ Smoke passed: session → roots → list → handle → span.read")
    return 0


def main():
    """Run all tests or smoke only."""
    import argparse

    parser = argparse.ArgumentParser(description="RLM MCP Gateway test suite")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run only smoke: session → roots → list → handle → span.read",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("RLM MCP Gateway Test Suite" + (" (smoke)" if args.smoke else ""))
    print("=" * 60)

    repo_root = REPO_ROOT
    gateway = RLMMCPGateway(str(repo_root))

    try:
        if args.smoke:
            return run_smoke(gateway)

        # Run tests
        session_id = test_session_management(gateway)

        # Recreate session for other tests
        result = gateway.session_create()
        session_id = result["session_id"]
        repo_root = REPO_ROOT
        gateway.roots_set(session_id, [str(repo_root)])

        test_filesystem_metadata(gateway, session_id)
        test_bounded_reading(gateway, session_id)
        test_search(gateway, session_id)
        test_provenance(gateway, session_id)
        test_budget_enforcement(gateway)
        test_security(gateway, session_id)

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
