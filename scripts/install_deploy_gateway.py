#!/usr/bin/env python3
"""
Install and Deploy Remote RLM MCP Gateway

This script automates the deployment of the RLM MCP Gateway to a remote host
for production use with remote isolation.

Usage:
    python scripts/install_deploy_gateway.py --host remote-host --repo-path /repo/rlm-kit --api-key KEY
    python scripts/install_deploy_gateway.py --mode docker --host remote-host --repo-path /repo/rlm-kit
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Bootstrap: repo root on path so path_utils is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _repo_root import find_repo_root  # noqa: E402

sys.path.insert(0, str(find_repo_root(Path(__file__).resolve().parent)))
from path_utils import REPO_ROOT  # noqa: E402


def check_requirements() -> tuple[bool, list[str]]:
    """Check if required tools are available."""
    missing = []

    # Check Python
    try:
        result = subprocess.run(["python3", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            missing.append("python3")
    except FileNotFoundError:
        missing.append("python3")

    # Check Docker (if docker mode)
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            missing.append("docker (optional, for Docker mode)")
    except FileNotFoundError:
        pass  # Docker is optional

    return len(missing) == 0, missing


def generate_api_key() -> str:
    """Generate a secure API key."""
    import secrets

    return secrets.token_urlsafe(32)


def create_systemd_service(
    gateway_path: Path,
    repo_path: Path,
    api_key: str,
    host: str = "0.0.0.0",
    port: int = 8080,
    user: str = "rlm",
) -> str:
    """Create systemd service file for the gateway."""
    service_content = f"""[Unit]
Description=RLM MCP Gateway Server
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={gateway_path}
Environment="RLM_GATEWAY_API_KEY={api_key}"
Environment="PYTHONPATH={gateway_path.parent}"
ExecStart=/usr/bin/python3 {gateway_path}/scripts/rlm_mcp_gateway.py \\
    --mode http \\
    --host {host} \\
    --port {port} \\
    --repo-path {repo_path} \\
    --api-key {api_key}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    return service_content


def deploy_docker(
    repo_path: Path,
    api_key: str,
    host: str = "0.0.0.0",
    port: int = 8080,
    image_name: str = "rlm-gateway",
) -> bool:
    """Deploy gateway using Docker."""
    print("🐳 Deploying RLM Gateway with Docker...")

    # Check if Dockerfile exists
    dockerfile = REPO_ROOT / "Dockerfile.gateway"
    if not dockerfile.exists():
        print(f"❌ ERROR: Dockerfile not found: {dockerfile}")
        return False

    # Build Docker image
    print(f"  Building Docker image: {image_name}")
    build_cmd = ["docker", "build", "-f", str(dockerfile), "-t", image_name, "."]

    result = subprocess.run(build_cmd, cwd=dockerfile.parent)
    if result.returncode != 0:
        print("❌ ERROR: Docker build failed")
        return False

    # Stop existing container if running
    subprocess.run(["docker", "stop", image_name], capture_output=True)
    subprocess.run(["docker", "rm", image_name], capture_output=True)

    # Run container
    print(f"  Starting container on port {port}...")
    run_cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        image_name,
        "-p",
        f"{port}:{port}",
        "-v",
        f"{repo_path}:/repo/rlm-kit:ro",
        "-e",
        f"RLM_GATEWAY_API_KEY={api_key}",
        "--restart",
        "always",
        image_name,
        "python",
        "scripts/rlm_mcp_gateway.py",
        "--mode",
        "http",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--repo-path",
        "/repo/rlm-kit",
        "--api-key",
        api_key,
    ]

    result = subprocess.run(run_cmd)
    if result.returncode != 0:
        print("❌ ERROR: Docker run failed")
        return False

    print(f"✅ Gateway deployed in Docker container: {image_name}")
    return True


def deploy_systemd(
    gateway_path: Path, repo_path: Path, api_key: str, host: str = "0.0.0.0", port: int = 8080
) -> bool:
    """Deploy gateway as systemd service."""
    print("🔧 Deploying RLM Gateway as systemd service...")

    # Check if running as root
    if os.geteuid() != 0:
        print("⚠️  WARNING: Systemd deployment requires root privileges")
        print("   Run with: sudo python scripts/install_deploy_gateway.py ...")
        return False

    # Create service file
    service_content = create_systemd_service(gateway_path, repo_path, api_key, host, port)

    service_file = Path("/etc/systemd/system/rlm-gateway.service")
    print(f"  Creating service file: {service_file}")

    try:
        service_file.write_text(service_content)
        print("  ✅ Service file created")
    except PermissionError:
        print("❌ ERROR: Permission denied. Run with sudo.")
        return False

    # Reload systemd
    print("  Reloading systemd...")
    subprocess.run(["systemctl", "daemon-reload"])

    # Enable service
    print("  Enabling service...")
    subprocess.run(["systemctl", "enable", "rlm-gateway"])

    # Start service
    print("  Starting service...")
    result = subprocess.run(["systemctl", "start", "rlm-gateway"])
    if result.returncode != 0:
        print("❌ ERROR: Failed to start service")
        return False

    # Check status
    time.sleep(2)
    result = subprocess.run(
        ["systemctl", "is-active", "rlm-gateway"], capture_output=True, text=True
    )
    if result.stdout.strip() != "active":
        print("❌ ERROR: Service is not active")
        print("   Check logs: journalctl -u rlm-gateway -n 50")
        return False

    print("✅ Gateway deployed as systemd service")
    return True


def deploy_direct(
    gateway_path: Path, repo_path: Path, api_key: str, host: str = "0.0.0.0", port: int = 8080
) -> bool:
    """Deploy gateway directly (for testing)."""
    print("🚀 Deploying RLM Gateway directly...")

    gateway_script = gateway_path / "scripts" / "rlm_mcp_gateway.py"
    if not gateway_script.exists():
        print(f"❌ ERROR: Gateway script not found: {gateway_script}")
        return False

    # Set environment
    env = os.environ.copy()
    env["RLM_GATEWAY_API_KEY"] = api_key
    env["PYTHONPATH"] = str(gateway_path)

    # Run gateway
    print(f"  Starting gateway on {host}:{port}...")
    print(f"  Repository: {repo_path}")
    print(f"  API Key: {api_key[:8]}...")
    print("\n  Gateway running. Press Ctrl+C to stop.\n")

    cmd = [
        sys.executable,
        str(gateway_script),
        "--mode",
        "http",
        "--host",
        host,
        "--port",
        str(port),
        "--repo-path",
        str(repo_path),
        "--api-key",
        api_key,
    ]

    try:
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\n✅ Gateway stopped")
        return True

    return False


def verify_deployment(host: str, port: int, api_key: str) -> bool:
    """Verify gateway is running and accessible."""
    try:
        import requests
    except ImportError:
        print("⚠️  WARNING: requests library not available. Skipping verification.")
        print("   Install with: pip install requests")
        return True  # Don't fail if requests not available

    url = f"http://{host}:{port}/health"

    print(f"\n🔍 Verifying deployment at {url}...")

    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                print("✅ Gateway is running and healthy")
                return True
            else:
                print(f"❌ Gateway returned unexpected status: {data}")
                return False
        else:
            print(f"❌ Gateway returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Could not connect to gateway: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Install and deploy RLM MCP Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Docker deployment
  python scripts/install_deploy_gateway.py --mode docker --repo-path /repo/rlm-kit

  # Systemd deployment (requires sudo)
  sudo python scripts/install_deploy_gateway.py --mode systemd --repo-path /opt/rlm-kit

  # Direct deployment (testing)
  python scripts/install_deploy_gateway.py --mode direct --repo-path /path/to/repo
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["docker", "systemd", "direct"],
        default="docker",
        help="Deployment mode (default: docker)",
    )
    parser.add_argument(
        "--repo-path", type=Path, required=True, help="Path to repository root on remote host"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for authentication (generated if not provided)",
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to (default: 8080)")
    parser.add_argument(
        "--gateway-path",
        type=Path,
        default=None,
        help="Path to gateway code (default: script parent directory)",
    )
    parser.add_argument("--skip-verify", action="store_true", help="Skip deployment verification")

    args = parser.parse_args()

    # Check requirements
    print("🔍 Checking requirements...")
    has_requirements, missing = check_requirements()
    if not has_requirements:
        print(f"❌ ERROR: Missing requirements: {', '.join(missing)}")
        sys.exit(1)
    print("✅ All requirements met")

    # Determine gateway path
    if args.gateway_path:
        gateway_path = args.gateway_path.resolve()
    else:
        gateway_path = REPO_ROOT.resolve()

    # Generate API key if not provided
    if not args.api_key:
        args.api_key = generate_api_key()
        print(f"\n🔑 Generated API key: {args.api_key}")
        print("   ⚠️  Save this key securely! You'll need it for IDE configuration.")
    else:
        print(f"\n🔑 Using provided API key: {args.api_key[:8]}...")

    # Verify repo path exists
    if not args.repo_path.exists():
        print(f"❌ ERROR: Repository path does not exist: {args.repo_path}")
        sys.exit(1)

    # Deploy based on mode
    success = False
    if args.mode == "docker":
        success = deploy_docker(args.repo_path, args.api_key, args.host, args.port)
    elif args.mode == "systemd":
        success = deploy_systemd(gateway_path, args.repo_path, args.api_key, args.host, args.port)
    elif args.mode == "direct":
        success = deploy_direct(gateway_path, args.repo_path, args.api_key, args.host, args.port)

    if not success:
        sys.exit(1)

    # Verify deployment
    if not args.skip_verify and args.mode != "direct":
        verify_deployment(args.host, args.port, args.api_key)

    # Print summary
    print("\n" + "=" * 60)
    print("✅ DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"Gateway URL: http://{args.host}:{args.port}")
    print(f"API Key: {args.api_key}")
    print(f"Repository: {args.repo_path}")
    print("\nNext steps:")
    print("  1. Save the API key securely")
    print("  2. Configure firewall to allow access to port", args.port)
    print("  3. Run: python scripts/install_thin_workspace.py")
    print("  4. Run: python scripts/install_ide_config.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
