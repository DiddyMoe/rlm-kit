#!/usr/bin/env python3
"""
Install and Create Thin Workspace

This script creates a thin workspace for IDE integration with remote isolation.
The thin workspace contains only configuration files and documentation, not source code.

Usage:
    python scripts/install_thin_workspace.py --output-dir ~/rlm-kit-thin --gateway-url https://gateway-host:8080
"""

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path

# Bootstrap: repo root on path so path_utils is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repo_root import find_repo_root  # noqa: E402

sys.path.insert(0, str(find_repo_root(Path(__file__).resolve().parent)))
from path_utils import REPO_ROOT  # noqa: E402

THIN_WORKSPACE_FILES = [
    # Configuration files
    ".cursor/mcp.json",
    ".cursorrules",
    ".vscode/settings.json",
    ".vscode/launch.json",
    ".vscode/tasks.json",
    # Documentation (detailed docs are in docs/content/)
    "README.md",
    # Environment
    ".env.example",
    ".gitignore",
    # Build config (for reference)
    "pyproject.toml",
    "Makefile",
]

THIN_WORKSPACE_DIRS = [
    "docs/",  # Documentation only
]


def create_remote_mcp_config(output_dir: Path, gateway_url: str, api_key: str = None) -> Path:
    """Create remote MCP configuration for Cursor."""
    mcp_dir = output_dir / ".cursor"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    mcp_config = {
        "mcpServers": {
            "rlm-gateway": {
                "command": "curl",
                "args": [
                    "-X",
                    "POST",
                    f"{gateway_url}/mcp",
                    "-H",
                    "Authorization: Bearer ${RLM_GATEWAY_API_KEY}",
                    "-H",
                    "Content-Type: application/json",
                    "--data-binary",
                    "@-",
                ],
                "env": {"RLM_GATEWAY_API_KEY": "${env:RLM_GATEWAY_API_KEY}"},
                "description": "RLM MCP Gateway - Remote isolation mode (HTTP)",
            }
        },
        "_instructions": {
            "remote_isolation": "This workspace uses remote isolation. The repository is NOT in this workspace. All access must go through MCP tools.",
            "mcp_tools": "All repository access MUST go through MCP tools: rlm.session.create, rlm.fs.list, rlm.span.read, etc. NEVER read files directly.",
            "gateway_url": gateway_url,
        },
    }

    mcp_file = mcp_dir / "mcp.json"
    with open(mcp_file, "w") as f:
        json.dump(mcp_config, f, indent=2)

    print("  ✅ Created: .cursor/mcp.json")
    return mcp_file


def create_remote_vscode_config(output_dir: Path, gateway_url: str, api_key: str = None) -> Path:
    """Create remote VS Code configuration with Copilot instructions."""
    vscode_dir = output_dir / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)

    vscode_config = {
        "mcp.servers": {
            "rlm-gateway": {
                "command": "curl",
                "args": [
                    "-X",
                    "POST",
                    f"{gateway_url}/mcp",
                    "-H",
                    "Authorization: Bearer ${RLM_GATEWAY_API_KEY}",
                    "-H",
                    "Content-Type: application/json",
                    "--data-binary",
                    "@-",
                ],
                "env": {"RLM_GATEWAY_API_KEY": "${env:RLM_GATEWAY_API_KEY}"},
                "description": "RLM MCP Gateway - Remote isolation mode (HTTP)",
            }
        },
        "github.copilot.advanced": {
            "agent": {
                "instructions": [
                    "🚨 CRITICAL: You cannot read the repository directly. Use MCP tools only.",
                    "",
                    "MANDATORY RLM-ONLY ACCESS:",
                    "- All repository access MUST go through rlm.* MCP tools",
                    "- NEVER attempt to read files directly from the filesystem",
                    "- The repository is NOT in this workspace",
                    "",
                    "REQUIRED TOOL SEQUENCE:",
                    "1. Use rlm.session.create to start a session",
                    "2. Use rlm.roots.set to configure allowed roots",
                    "3. Use rlm.fs.list for directory browsing (metadata only)",
                    "4. Use rlm.fs.handle.create to create file handles",
                    "5. Use rlm.span.read for bounded file reading (max 200 lines/8KB)",
                    "6. Use rlm.search.query for semantic search (references only)",
                    "7. Use rlm.complete for RLM reasoning with budgets",
                    "",
                    "BOUNDED OPERATIONS:",
                    "- Max span size: 200 lines or 8192 bytes",
                    "- Max search results: 10",
                    "- Max tool calls per session: 100",
                    "- Always respect bounded operations",
                    "",
                    "PROVENANCE:",
                    "- All operations are provenance-tracked",
                    "- Use rlm.provenance.report to get audit trail",
                    "",
                    "FORBIDDEN:",
                    "- ❌ Direct file reading (open(), read_file(), etc.)",
                    "- ❌ Reading entire files",
                    "- ❌ Path traversal outside allowed roots",
                    "- ❌ Network/process execution from sandbox",
                ]
            }
        },
    }

    settings_file = vscode_dir / "settings.json"
    with open(settings_file, "w") as f:
        json.dump(vscode_config, f, indent=2)

    print("  ✅ Created: .vscode/settings.json")
    return settings_file


def create_canary_token_file(output_dir: Path) -> str:
    """Create a canary token file for bypass detection."""
    canary_token = f"RLM_CANARY_{uuid.uuid4().hex}"

    canary_file = output_dir / ".rlm_canary_token.txt"
    canary_file.write_text(f"""# RLM Canary Token (DO NOT MODIFY)

This file contains a canary token for bypass detection.
If this token appears in AI agent responses without proper provenance,
it indicates a potential bypass of the RLM MCP Gateway.

Token: {canary_token}

This file should NOT be read directly by AI agents.
All repository access must go through MCP tools.
""")

    print("  ✅ Created: .rlm_canary_token.txt (bypass detection)")
    return canary_token


def create_env_file(output_dir: Path, api_key: str) -> Path:
    """Create .env file with API key."""
    env_file = output_dir / ".env"
    env_content = f"""# RLM Gateway Configuration
# This file contains sensitive information - do not commit to version control

RLM_GATEWAY_API_KEY={api_key}
"""
    env_file.write_text(env_content)
    env_file.chmod(0o600)  # Read/write for owner only
    print("  ✅ Created: .env (API key configured)")
    return env_file


def create_thin_workspace(
    output_dir: Path, source_dir: Path, gateway_url: str, api_key: str = None, ide: str = "both"
) -> bool:
    """Create a thin workspace with only config files and docs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📁 Creating thin workspace in: {output_dir}")
    print(f"   Source directory: {source_dir}")
    print(f"   Gateway URL: {gateway_url}")
    print(f"   IDE: {ide}\n")

    # Copy files (excluding MCP configs - we'll create remote versions)
    copied_files = 0
    skip_files = {".cursor/mcp.json", ".vscode/settings.json"}

    for file_path in THIN_WORKSPACE_FILES:
        if file_path in skip_files:
            continue
        source_file = source_dir / file_path
        if source_file.exists():
            dest_file = output_dir / file_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, dest_file)
            copied_files += 1
            print(f"  ✅ Copied: {file_path}")
        else:
            print(f"  ⚠️  Skipped (not found): {file_path}")

    # Copy directories
    for dir_path in THIN_WORKSPACE_DIRS:
        source_dir_path = source_dir / dir_path
        if source_dir_path.exists():
            dest_dir_path = output_dir / dir_path
            shutil.copytree(source_dir_path, dest_dir_path, dirs_exist_ok=True)
            print(f"  ✅ Copied directory: {dir_path}")

    # Create remote MCP configurations
    if ide in ("cursor", "both"):
        create_remote_mcp_config(output_dir, gateway_url, api_key)
        copied_files += 1

    if ide in ("vscode", "both"):
        create_remote_vscode_config(output_dir, gateway_url, api_key)
        copied_files += 1

    # Create canary token for bypass detection
    canary_token = create_canary_token_file(output_dir)

    # Create .env file if API key provided
    if api_key:
        create_env_file(output_dir, api_key)

    # Create README for thin workspace
    thin_readme = output_dir / "THIN_WORKSPACE_README.md"
    thin_readme.write_text(f"""# RLM Kit - Thin Workspace

This is a **thin workspace** for IDE integration with remote isolation.

## What's Different?

This workspace contains **only configuration files and documentation**.
The actual source code (`rlm/`, `scripts/`, `examples/`, `tests/`) is **NOT** in this workspace.

## Why?

For **remote isolation** - the IDE cannot read the repository directly.
All repository access must go through the **RLM MCP Gateway** running in an isolated environment.

## Setup

1. **Set Environment Variable:**
   ```bash
   export RLM_GATEWAY_API_KEY=your-secret-api-key
   ```
   Or use the `.env` file (already configured if created by install script).

2. **Update Gateway URL (if needed):**
   - Edit `.cursor/mcp.json` (Cursor) or `.vscode/settings.json` (VS Code)
   - Update the gateway URL if different from default

3. **Open This Workspace:**
   - Open this directory in VS Code or Cursor
   - The IDE will connect to the remote MCP gateway

4. **Use MCP Tools:**
   - All repository access via `rlm.*` MCP tools
   - Start with `rlm.session.create`
   - Then `rlm.roots.set` to configure allowed paths
   - Use `rlm.fs.list`, `rlm.span.read`, etc. for repository access

## Remote Gateway Setup

The remote gateway should be running with:
```bash
python scripts/rlm_mcp_gateway.py --mode http --host 0.0.0.0 --port 8080 --repo-path /repo/rlm-kit --api-key YOUR_API_KEY
```

Or use the deployment script:
```bash
python scripts/install_deploy_gateway.py --mode docker --repo-path /repo/rlm-kit
```

## Bypass Detection

This workspace includes a canary token (`.rlm_canary_token.txt`) for bypass detection.
If this token appears in AI agent responses without proper provenance, it indicates
a potential bypass of the RLM MCP Gateway.

**Canary Token:** `{canary_token}`

## Documentation

See `docs/content/guides/ide-setup.md` for complete setup instructions.
See `docs/content/guides/remote-isolation.md` for remote isolation details.
""")
    print("  ✅ Created: THIN_WORKSPACE_README.md")

    print(f"\n✅ Thin workspace created: {copied_files} files copied")
    print("\n📋 Next steps:")
    print("  1. Set RLM_GATEWAY_API_KEY environment variable (or use .env file)")
    if api_key:
        print(f"     API key: {api_key[:8]}...")
    print(f"  2. Open {output_dir} in your IDE")
    print("  3. Verify MCP connection in IDE chat")
    print("  4. Test with: 'List the repository structure'")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Create thin workspace for remote isolation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create thin workspace with gateway URL
  python scripts/install_thin_workspace.py \\
    --output-dir ~/rlm-kit-thin \\
    --gateway-url https://gateway-host:8080 \\
    --api-key YOUR_API_KEY

  # Create for specific IDE only
  python scripts/install_thin_workspace.py \\
    --output-dir ~/rlm-kit-thin \\
    --gateway-url https://gateway-host:8080 \\
    --ide cursor
        """,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./rlm-kit-thin"),
        help="Output directory for thin workspace (default: ./rlm-kit-thin)",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=REPO_ROOT,
        help="Source directory (default: repository root)",
    )
    parser.add_argument(
        "--gateway-url",
        type=str,
        required=True,
        help="Remote gateway URL (e.g., https://gateway-host:8080)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for gateway (will create .env file if provided)",
    )
    parser.add_argument(
        "--ide",
        choices=["cursor", "vscode", "both"],
        default="both",
        help="IDE to configure (default: both)",
    )

    args = parser.parse_args()

    if not args.source_dir.exists():
        print(f"❌ ERROR: Source directory does not exist: {args.source_dir}", file=sys.stderr)
        sys.exit(1)

    success = create_thin_workspace(
        args.output_dir, args.source_dir, args.gateway_url, args.api_key, args.ide
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
