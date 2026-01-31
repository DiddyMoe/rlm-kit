#!/usr/bin/env python3
"""
Setup Verification Script

Verifies that the RLM MCP Gateway is properly configured and ready to use.
"""

import json
import sys
from pathlib import Path

# Bootstrap: repo root on path so path_utils and rlm are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repo_root import find_repo_root  # noqa: E402

sys.path.insert(0, str(find_repo_root(Path(__file__).resolve().parent)))
from path_utils import REPO_ROOT, SCRIPT_DIR  # noqa: E402


def check_mcp_config():
    """Check MCP configuration file. Returns (passed, config_type) where config_type is 'stdio' or 'remote'."""
    print("Checking MCP configuration...")

    config_path = REPO_ROOT / ".cursor" / "mcp.json"

    if not config_path.exists():
        print(f"  ⚠️  MCP config not found: {config_path}")
        print("     Create .cursor/mcp.json with rlm-gateway configuration")
        return False, None

    try:
        with open(config_path) as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})

        if "rlm-gateway" not in servers:
            print("  ⚠️  MCP config found but 'rlm-gateway' not configured")
            print(f"     Available servers: {list(servers.keys())}")
            return False, None

        server_config = servers["rlm-gateway"]
        command = server_config.get("command", "")
        args = server_config.get("args", [])

        # Local stdio: uv run python scripts/rlm_mcp_gateway.py
        if "rlm_mcp_gateway.py" in str(args):
            print("  ✅ MCP config found: rlm-gateway configured (local stdio)")
            print(f"     Command: {command} {' '.join(str(a) for a in args)}")
            return True, "stdio"

        # Remote: curl POST to gateway URL
        if command == "curl" and any("/mcp" in str(a) for a in args):
            print("  ✅ MCP config found: rlm-gateway configured (remote HTTP)")
            print(f"     Command: {command} ... (remote gateway)")
            return True, "remote"

        print("  ⚠️  MCP config found but rlm-gateway not recognized")
        print(f"     command={command!r}, args={args}")
        return False, None

    except json.JSONDecodeError as e:
        print(f"  ❌ MCP config invalid JSON: {e}")
        return False, None
    except Exception as e:
        print(f"  ❌ Error reading MCP config: {e}")
        return False, None


def check_gateway_file(config_type: str | None):
    """Check gateway file exists (only for local stdio config; skip for remote)."""
    print("\nChecking gateway file...")

    if config_type == "remote":
        print("  ✅ Skipped (remote gateway; gateway runs on remote host)")
        return True

    gateway_path = SCRIPT_DIR / "rlm_mcp_gateway.py"

    if not gateway_path.exists():
        print(f"  ❌ Gateway file not found: {gateway_path}")
        return False

    # Check file size (should be non-trivial)
    size = gateway_path.stat().st_size
    if size < 1000:  # Entry point + imports should be non-trivial
        print(f"  ⚠️  Gateway file seems too small: {size} bytes")
        return False

    print(f"  ✅ Gateway file found: {gateway_path} ({size} bytes)")
    return True


def check_dependencies():
    """Check required dependencies."""
    print("\nChecking dependencies...")

    try:
        import importlib.util

        if importlib.util.find_spec("mcp") is None:
            raise ImportError("mcp not found")
        print("  ✅ MCP SDK installed")
    except ImportError:
        print("  ❌ MCP SDK not installed")
        print("     Install with: uv sync --extra gateway  (or: make install-gateway)")
        return False

    try:
        root_str = str(REPO_ROOT)
        if not sys.path or sys.path[0] != root_str:
            sys.path.insert(0, root_str)
        import rlm.core.types  # noqa: F401

        print("  ✅ RLM package available")
    except ImportError as e:
        print(f"  ❌ RLM package not available: {e}")
        print("     Install with: uv pip install -e .")
        return False

    return True


def check_test_suite():
    """Check test suite exists."""
    print("\nChecking test suite...")

    test_path = SCRIPT_DIR / "test_mcp_gateway.py"

    if not test_path.exists():
        print(f"  ⚠️  Test suite not found: {test_path}")
        return False

    print(f"  ✅ Test suite found: {test_path}")
    return True


def check_env_vars():
    """Check optional env vars for gateway/complete."""
    print("\nChecking environment variables (optional)...")
    import os

    openai = bool(os.getenv("OPENAI_API_KEY"))
    anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    gateway_key = bool(os.getenv("RLM_GATEWAY_API_KEY"))
    if openai or anthropic:
        print("  ✅ At least one LM API key set (OPENAI_API_KEY or ANTHROPIC_API_KEY)")
    else:
        print("  ⚠️  No OPENAI_API_KEY or ANTHROPIC_API_KEY (needed for rlm.complete)")
    if gateway_key:
        print("  ✅ RLM_GATEWAY_API_KEY set (for remote gateway)")
    else:
        print("  ℹ️  RLM_GATEWAY_API_KEY not set (only needed for remote gateway)")
    return True  # Don't fail verification; env is optional for local stdio


def print_next_steps():
    """Print next steps."""
    print("\n" + "=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print("1. Restart your IDE completely")
    print("2. Open AI chat (Copilot/Cursor)")
    print("3. Ask: 'What RLM tools are available?'")
    print("4. You should see tools like:")
    print("   - rlm.session.create")
    print("   - rlm.fs.list")
    print("   - rlm.span.read")
    print("   - etc.")
    print("\n5. Run smoke test (session → roots → list → handle → span.read):")
    print("   uv run python scripts/test_mcp_gateway.py --smoke")
    print("   Full test suite:")
    print("   uv run python scripts/test_mcp_gateway.py")
    print("\nFor help:")
    print("  - Quick Start: docs/content/getting-started/quick-start.md")
    print("  - Full Guide: docs/content/guides/ide-setup.md")
    print("=" * 60)


def main():
    """Run all checks."""
    print("=" * 60)
    print("RLM MCP Gateway Setup Verification")
    print("=" * 60)
    print()

    results = []
    # MCP config check returns (passed, config_type) for gateway file check
    try:
        mcp_passed, config_type = check_mcp_config()
        results.append(("MCP Configuration", mcp_passed))
    except Exception as e:
        print(f"  ❌ Error in MCP Configuration: {e}")
        results.append(("MCP Configuration", False))
        config_type = None

    try:
        results.append(("Gateway File", check_gateway_file(config_type)))
    except Exception as e:
        print(f"  ❌ Error in Gateway File: {e}")
        results.append(("Gateway File", False))

    for name, check_func in [
        ("Dependencies", check_dependencies),
        ("Test Suite", check_test_suite),
        ("Env vars (optional)", check_env_vars),
    ]:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ Error in {name}: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Verification Summary:")
    print("=" * 60)

    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
        if not result:
            all_passed = False

    print()

    if all_passed:
        print("✅ All checks passed! Setup looks good.")
        print_next_steps()
        return 0
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        print("\nSee docs/content/guides/ide-setup.md for detailed setup instructions.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
