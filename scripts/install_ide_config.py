#!/usr/bin/env python3
"""
Auto-Configure IDE for RLM MCP Gateway

This script automatically configures VS Code and Cursor to use the RLM MCP Gateway
with proper settings and instructions.

Usage:
    # One-click local setup (stdio gateway in workspace)
    python scripts/install_ide_config.py --all
    # Or: make ide-setup

    # Remote gateway
    python scripts/install_ide_config.py --gateway-url https://gateway-host:8080 --api-key KEY

    # Thin workspace + remote
    python scripts/install_ide_config.py --all --thin --output-dir ~/rlm-kit-thin
"""

import argparse
import json
import os
import platform
import sys
from pathlib import Path

# Bootstrap: repo root on path so path_utils is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repo_root import find_repo_root  # noqa: E402

sys.path.insert(0, str(find_repo_root(Path(__file__).resolve().parent)))
from path_utils import REPO_ROOT, SCRIPT_DIR  # noqa: E402

_IDE_CONFIG_PATHS = {
    "cursor": {
        "Darwin": lambda: Path.home() / "Library" / "Application Support" / "Cursor" / "User",
        "Windows": lambda: Path(os.getenv("APPDATA", "")) / "Cursor" / "User",
        "Linux": lambda: Path.home() / ".config" / "Cursor" / "User",
    },
    "vscode": {
        "Darwin": lambda: Path.home() / "Library" / "Application Support" / "Code" / "User",
        "Windows": lambda: Path(os.getenv("APPDATA", "")) / "Code" / "User",
        "Linux": lambda: Path.home() / ".config" / "Code" / "User",
    },
}


def _find_ide_config_dir(ide: str) -> Path | None:
    """Find IDE config directory (cursor or vscode). Returns None if not present."""
    system = platform.system()
    if system not in _IDE_CONFIG_PATHS[ide]:
        system = "Linux"
    config_dir = _IDE_CONFIG_PATHS[ide][system]()
    return config_dir if config_dir.exists() else None


def find_cursor_config_dir() -> Path | None:
    """Find Cursor configuration directory."""
    return _find_ide_config_dir("cursor")


def find_vscode_config_dir() -> Path | None:
    """Find VS Code configuration directory."""
    return _find_ide_config_dir("vscode")


def configure_cursor(gateway_url: str, api_key: str, config_dir: Path) -> bool:
    """Configure Cursor IDE."""
    print("🔧 Configuring Cursor...")

    # Create MCP config directory
    mcp_dir = config_dir / "globalStorage" / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    # Create MCP servers config
    servers_file = mcp_dir / "servers.json"

    # Load existing config or create new
    if servers_file.exists():
        try:
            with open(servers_file) as f:
                servers_config = json.load(f)
        except json.JSONDecodeError:
            servers_config = {}
    else:
        servers_config = {}

    # Add RLM gateway
    servers_config["rlm-gateway"] = {
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
        "env": {"RLM_GATEWAY_API_KEY": api_key},
        "description": "RLM MCP Gateway - Remote isolation mode",
    }

    # Save config
    with open(servers_file, "w") as f:
        json.dump(servers_config, f, indent=2)

    print(f"  ✅ Configured: {servers_file}")

    # Update settings.json
    settings_file = config_dir / "settings.json"

    if settings_file.exists():
        with open(settings_file) as f:
            settings = json.load(f)
    else:
        settings = {}

    # Add RLM-specific settings
    if "rlm" not in settings:
        settings["rlm"] = {}

    settings["rlm"]["gateway_url"] = gateway_url
    settings["rlm"]["enabled"] = True
    settings["rlm"]["remote_isolation"] = True

    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)

    print(f"  ✅ Updated: {settings_file}")

    return True


def configure_vscode(gateway_url: str, api_key: str, config_dir: Path) -> bool:
    """Configure VS Code."""
    print("🔧 Configuring VS Code...")

    settings_file = config_dir / "settings.json"

    # Load existing settings
    if settings_file.exists():
        with open(settings_file) as f:
            settings = json.load(f)
    else:
        settings = {}

    # Add MCP server configuration
    if "mcp.servers" not in settings:
        settings["mcp.servers"] = {}

    settings["mcp.servers"]["rlm-gateway"] = {
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
        "env": {"RLM_GATEWAY_API_KEY": api_key},
        "description": "RLM MCP Gateway - Remote isolation mode",
    }

    # Add Copilot agent instructions
    if "github.copilot.advanced" not in settings:
        settings["github.copilot.advanced"] = {}

    if "agent" not in settings["github.copilot.advanced"]:
        settings["github.copilot.advanced"]["agent"] = {}

    settings["github.copilot.advanced"]["agent"]["instructions"] = [
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
        "",
        "FORBIDDEN:",
        "- ❌ Direct file reading (open(), read_file(), etc.)",
        "- ❌ Reading entire files",
        "- ❌ Path traversal outside allowed roots",
    ]

    # Add RLM-specific settings
    if "rlm" not in settings:
        settings["rlm"] = {}

    settings["rlm"]["gateway_url"] = gateway_url
    settings["rlm"]["enabled"] = True
    settings["rlm"]["remote_isolation"] = True

    # Save settings
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)

    print(f"  ✅ Configured: {settings_file}")

    return True


def set_environment_variable(api_key: str) -> bool:
    """Set RLM_GATEWAY_API_KEY environment variable."""
    print("🔧 Setting environment variable...")

    shell = os.getenv("SHELL", "/bin/bash")
    shell_rc = None

    if "bash" in shell:
        shell_rc = Path.home() / ".bashrc"
    elif "zsh" in shell:
        shell_rc = Path.home() / ".zshrc"
    elif "fish" in shell:
        shell_rc = Path.home() / ".config" / "fish" / "config.fish"

    if shell_rc and shell_rc.exists():
        # Check if already set
        content = shell_rc.read_text()
        if "RLM_GATEWAY_API_KEY" in content:
            print(f"  ⚠️  RLM_GATEWAY_API_KEY already set in {shell_rc}")
            return True

        # Add to shell config
        export_line = f'\nexport RLM_GATEWAY_API_KEY="{api_key}"\n'
        shell_rc.write_text(content + export_line)
        print(f"  ✅ Added to {shell_rc}")
        print(f"  ⚠️  Run: source {shell_rc} or restart terminal")
        return True
    else:
        print("  ⚠️  Could not find shell config file")
        print(f"  💡 Manually set: export RLM_GATEWAY_API_KEY={api_key}")
        return False


def _read_json_or_empty(path: Path) -> dict:
    """Read JSON from path; return {} if missing or invalid. O(1) file read."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def write_workspace_local_config(target_dir: Path, thin: bool = False) -> int:
    """Write .cursor/mcp.json and .vscode/settings.json in target_dir (local stdio or thin)."""
    target_dir = target_dir.resolve()
    if target_dir.exists() and not target_dir.is_dir():
        raise NotADirectoryError(f"Target exists and is not a directory: {target_dir}")
    if not thin:
        gateway_script = SCRIPT_DIR / "rlm_mcp_gateway.py"
        if not gateway_script.is_file():
            raise FileNotFoundError(
                f"Gateway script not found: {gateway_script}. Run from repo root."
            )
    target_dir.mkdir(parents=True, exist_ok=True)

    # Build MCP server config once (O(1))
    if thin:
        mcp_content = {
            "mcpServers": {
                "rlm-gateway": {
                    "command": "curl",
                    "args": [
                        "-X",
                        "POST",
                        "https://your-gateway-host:8080/mcp",
                        "-H",
                        "Authorization: Bearer ${RLM_GATEWAY_API_KEY}",
                        "-H",
                        "Content-Type: application/json",
                        "--data-binary",
                        "@-",
                    ],
                    "env": {"RLM_GATEWAY_API_KEY": "${env:RLM_GATEWAY_API_KEY}"},
                }
            }
        }
    else:
        gateway_script = (SCRIPT_DIR / "rlm_mcp_gateway.py").relative_to(REPO_ROOT).as_posix()
        mcp_content = {
            "mcpServers": {
                "rlm-gateway": {
                    "command": "uv",
                    "args": ["run", "python", gateway_script],
                    "cwd": "${workspaceFolder}",
                    "env": {"PYTHONPATH": "${workspaceFolder}"},
                }
            }
        }

    # Cursor: .cursor/mcp.json
    cursor_dir = target_dir / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    mcp_path = cursor_dir / "mcp.json"
    mcp_path.write_text(json.dumps(mcp_content, indent=2))
    print(f"  ✅ Wrote {mcp_path}")

    # VS Code: .vscode/settings.json (merge with existing; O(1) dict ops)
    vscode_dir = target_dir / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    settings_path = vscode_dir / "settings.json"
    existing = _read_json_or_empty(settings_path)
    if "mcp.servers" not in existing:
        existing["mcp.servers"] = {}
    existing["mcp.servers"]["rlm-gateway"] = mcp_content["mcpServers"]["rlm-gateway"]
    settings_path.write_text(json.dumps(existing, indent=2))
    print(f"  ✅ Wrote {settings_path}")

    return 2


def main():
    parser = argparse.ArgumentParser(
        description="Auto-configure IDE for RLM MCP Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # One-click local setup (creates .cursor/mcp.json and .vscode/settings.json in workspace)
  python scripts/install_ide_config.py --all

  # Thin workspace then configure for remote
  python scripts/install_ide_config.py --all --thin --output-dir ~/rlm-kit-thin

  # Remote gateway (global IDE config)
  python scripts/install_ide_config.py --gateway-url https://gateway-host:8080 --api-key KEY

  # Configure only Cursor
  python scripts/install_ide_config.py --gateway-url https://gateway-host:8080 --api-key KEY --ide cursor
        """,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="One-click: write workspace .cursor/mcp.json and .vscode/settings.json (local stdio gateway)",
    )
    parser.add_argument(
        "--thin",
        action="store_true",
        help="With --all: create thin workspace and configure for remote (set RLM_GATEWAY_URL and RLM_GATEWAY_API_KEY)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="With --thin: output directory for thin workspace (default: current dir)",
    )
    parser.add_argument(
        "--gateway-url",
        type=str,
        default=None,
        help="Remote gateway URL (e.g., https://gateway-host:8080)",
    )
    parser.add_argument(
        "--api-key", type=str, default=None, help="API key for gateway authentication"
    )
    parser.add_argument(
        "--ide",
        choices=["cursor", "vscode", "both"],
        default="both",
        help="IDE to configure (default: both)",
    )
    parser.add_argument(
        "--set-env", action="store_true", help="Set RLM_GATEWAY_API_KEY environment variable"
    )
    args = parser.parse_args()

    if args.all:
        _run_all_local_setup(args)
        return

    if not args.gateway_url or not args.api_key:
        parser.print_help()
        print("\nFor one-click local setup use: python scripts/install_ide_config.py --all")
        sys.exit(1)

    _run_remote_setup(args)


def _run_all_local_setup(args) -> None:
    """One-click: write workspace .cursor/mcp.json and .vscode/settings.json (local stdio or thin)."""
    import subprocess

    print("🚀 One-click IDE setup (workspace-local MCP config)")
    print("=" * 60)
    out_dir = Path(args.output_dir).resolve() if args.output_dir else REPO_ROOT
    thin = args.thin

    if thin:
        thin_dir = out_dir / "rlm-kit-thin" if out_dir == REPO_ROOT else out_dir
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "setup_thin_workspace.py"),
                    "--output-dir",
                    str(thin_dir),
                ],
                check=True,
                cwd=str(REPO_ROOT),
            )
        except subprocess.CalledProcessError as e:
            print(f"  ⚠️  Thin workspace failed: {e}")
            print("  Run: python scripts/setup_thin_workspace.py --output-dir <dir>")
            print("=" * 60)
            sys.exit(1)
        write_workspace_local_config(thin_dir, thin=True)
    else:
        try:
            write_workspace_local_config(out_dir, thin=False)
        except (NotADirectoryError, FileNotFoundError) as e:
            print(f"  ❌ {e}")
            print("=" * 60)
            sys.exit(1)

    print("\n📋 Next: Restart IDE; ask in chat: 'What RLM tools are available?'")
    print("=" * 60)


def _run_remote_setup(args) -> None:
    """Configure global IDE config for remote gateway (gateway_url + api_key)."""
    print("🚀 Auto-Configuring IDE for RLM MCP Gateway (remote)")
    print("=" * 60)
    success_count = 0
    if args.ide in ("cursor", "both"):
        cursor_config = find_cursor_config_dir()
        if not cursor_config:
            print("⚠️  Cursor not found (config directory not detected)")
        elif configure_cursor(args.gateway_url, args.api_key, cursor_config):
            success_count += 1
    if args.ide in ("vscode", "both"):
        vscode_config = find_vscode_config_dir()
        if not vscode_config:
            print("⚠️  VS Code not found (config directory not detected)")
        elif configure_vscode(args.gateway_url, args.api_key, vscode_config):
            success_count += 1
    if args.set_env:
        set_environment_variable(args.api_key)
    print("\n" + "=" * 60)
    if success_count > 0:
        print(f"✅ Configuration complete ({success_count} IDE(s) configured)")
        print(
            "\n📋 Next steps: Restart IDE(s); verify MCP in chat; test: 'List the repository structure'"
        )
        if args.set_env:
            print("  Restart terminal or: source ~/.bashrc (or ~/.zshrc)")
    else:
        print("⚠️  No IDEs configured. Use --all for workspace-local setup.")
    print("=" * 60)


if __name__ == "__main__":
    main()
