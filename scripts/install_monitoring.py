#!/usr/bin/env python3
"""
Real-Time Lightweight Monitoring for Bypass Attempts

This script monitors for potential bypass attempts of the RLM MCP Gateway.
It watches for canary token appearances, direct file access patterns, and
provenance violations.

Usage:
    python scripts/install_monitoring.py --gateway-url https://gateway-host:8080 --api-key KEY
    python scripts/install_monitoring.py --mode file --watch-dir ~/rlm-kit-thin
"""

import argparse
import asyncio
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests library required. Install with: pip install requests")
    sys.exit(1)


@dataclass
class BypassAlert:
    """Represents a bypass attempt alert."""

    timestamp: float
    alert_type: str
    severity: str  # "low", "medium", "high", "critical"
    message: str
    details: dict
    canary_token: str | None = None
    file_path: str | None = None
    provenance: dict | None = None


class BypassMonitor:
    """Lightweight monitor for bypass attempts."""

    def __init__(
        self,
        gateway_url: str,
        api_key: str,
        canary_token: str | None = None,
        watch_dir: Path | None = None,
    ):
        self.gateway_url = gateway_url
        self.api_key = api_key
        self.canary_token = canary_token
        self.watch_dir = watch_dir
        self.alerts: list[BypassAlert] = []
        self.alert_counts = defaultdict(int)
        self.session_stats = defaultdict(int)

    def load_canary_token(self, workspace_dir: Path) -> str | None:
        """Load canary token from thin workspace."""
        canary_file = workspace_dir / ".rlm_canary_token.txt"
        if canary_file.exists():
            content = canary_file.read_text()
            # Extract token from file
            match = re.search(r"Token:\s*([A-Z0-9_]+)", content)
            if match:
                return match.group(1)
        return None

    def check_gateway_health(self) -> bool:
        """Check if gateway is healthy."""
        try:
            response = requests.get(f"{self.gateway_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            self.record_alert(
                "gateway_unreachable",
                "high",
                f"Gateway is unreachable: {e}",
                {"gateway_url": self.gateway_url},
            )
            return False

    def check_provenance(self, session_id: str) -> dict | None:
        """Get provenance report for a session."""
        try:
            response = requests.post(
                f"{self.gateway_url}/mcp",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "rlm.provenance.report",
                        "arguments": {"session_id": session_id},
                    },
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    content = json.loads(data["result"]["content"][0]["text"])
                    if content.get("success"):
                        return content.get("provenance_graph")

            return None
        except Exception:
            return None

    def detect_canary_token(self, text: str) -> bool:
        """Detect if canary token appears in text."""
        if not self.canary_token:
            return False

        return self.canary_token in text

    def detect_direct_file_access(self, text: str) -> bool:
        """Detect patterns indicating direct file access."""
        patterns = [
            r"open\(['\"][^'\"]+['\"]\)",
            r"read_file\(['\"][^'\"]+['\"]\)",
            r"Path\(['\"][^'\"]+['\"]\)\.read_text\(\)",
            r"with open\(['\"][^'\"]+['\"]\)",
            r"\.read\(\)",
            r"os\.path\.join\([^)]+\)",
        ]

        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def record_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: dict,
        canary_token: str | None = None,
        file_path: str | None = None,
        provenance: dict | None = None,
    ):
        """Record a bypass alert."""
        alert = BypassAlert(
            timestamp=time.time(),
            alert_type=alert_type,
            severity=severity,
            message=message,
            details=details,
            canary_token=canary_token,
            file_path=file_path,
            provenance=provenance,
        )

        self.alerts.append(alert)
        self.alert_counts[alert_type] += 1

        # Print alert
        timestamp_str = datetime.fromtimestamp(alert.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        severity_emoji = {"low": "ℹ️", "medium": "⚠️", "high": "🔴", "critical": "🚨"}

        emoji = severity_emoji.get(severity, "⚠️")
        print(f"\n{emoji} [{timestamp_str}] {severity.upper()}: {message}")
        if details:
            print(f"   Details: {json.dumps(details, indent=2)}")

    async def monitor_gateway_sessions(self, interval: int = 30):
        """Monitor gateway sessions for suspicious activity."""
        print("🔍 Monitoring gateway sessions...")

        while True:
            try:
                # Check gateway health
                if not self.check_gateway_health():
                    await asyncio.sleep(interval)
                    continue

                # In a real implementation, we would:
                # 1. Query gateway for active sessions
                # 2. Check provenance for each session
                # 3. Detect anomalies (too many tool calls, large outputs, etc.)

                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.record_alert(
                    "monitoring_error", "medium", f"Monitoring error: {e}", {"error": str(e)}
                )
                await asyncio.sleep(interval)

    def monitor_file_changes(self, watch_dir: Path, interval: int = 5):
        """Monitor file changes in workspace for canary token access."""
        if not watch_dir or not watch_dir.exists():
            return

        print(f"🔍 Monitoring file changes in: {watch_dir}")

        canary_file = watch_dir / ".rlm_canary_token.txt"
        if not canary_file.exists():
            print(f"⚠️  Canary token file not found: {canary_file}")
            return

        last_modified = canary_file.stat().st_mtime

        while True:
            try:
                current_modified = canary_file.stat().st_mtime
                if current_modified > last_modified:
                    self.record_alert(
                        "canary_file_accessed",
                        "critical",
                        "Canary token file was accessed!",
                        {
                            "file": str(canary_file),
                            "last_modified": last_modified,
                            "current_modified": current_modified,
                        },
                        canary_token=self.canary_token,
                        file_path=str(canary_file),
                    )
                    last_modified = current_modified

                time.sleep(interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️  Monitoring error: {e}")
                time.sleep(interval)

    def analyze_text_for_bypass(self, text: str, context: dict = None) -> list[BypassAlert]:
        """Analyze text for bypass indicators."""
        alerts = []

        # Check for canary token
        if self.detect_canary_token(text):
            alerts.append(
                BypassAlert(
                    timestamp=time.time(),
                    alert_type="canary_token_detected",
                    severity="critical",
                    message="Canary token detected in text without proper provenance!",
                    details={"text_preview": text[:200]},
                    canary_token=self.canary_token,
                )
            )

        # Check for direct file access patterns
        if self.detect_direct_file_access(text):
            alerts.append(
                BypassAlert(
                    timestamp=time.time(),
                    alert_type="direct_file_access_pattern",
                    severity="high",
                    message="Direct file access pattern detected!",
                    details={"text_preview": text[:200], "context": context},
                )
            )

        return alerts

    def generate_report(self) -> dict:
        """Generate monitoring report."""
        return {
            "timestamp": time.time(),
            "total_alerts": len(self.alerts),
            "alert_counts": dict(self.alert_counts),
            "session_stats": dict(self.session_stats),
            "recent_alerts": [
                asdict(alert)
                for alert in self.alerts[-10:]  # Last 10 alerts
            ],
            "severity_breakdown": {
                severity: sum(1 for a in self.alerts if a.severity == severity)
                for severity in ["low", "medium", "high", "critical"]
            },
        }

    def save_report(self, output_file: Path):
        """Save monitoring report to file."""
        report = self.generate_report()
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"✅ Report saved to: {output_file}")


async def main_async(args):
    """Main async function."""
    monitor = BypassMonitor(
        gateway_url=args.gateway_url,
        api_key=args.api_key,
        canary_token=args.canary_token,
        watch_dir=args.watch_dir,
    )

    # Load canary token if workspace directory provided
    if args.watch_dir:
        canary_token = monitor.load_canary_token(args.watch_dir)
        if canary_token:
            monitor.canary_token = canary_token
            print(f"🔑 Loaded canary token: {canary_token[:16]}...")

    print("🚨 RLM Bypass Monitor Started")
    print("=" * 60)
    print(f"Gateway: {args.gateway_url}")
    print(f"Watch Directory: {args.watch_dir or 'None'}")
    print(f"Canary Token: {'Loaded' if monitor.canary_token else 'Not loaded'}")
    print("=" * 60)
    print("\nMonitoring... (Press Ctrl+C to stop)\n")

    # Start monitoring tasks
    tasks = []

    if args.mode in ("gateway", "both"):
        tasks.append(asyncio.create_task(monitor.monitor_gateway_sessions(interval=args.interval)))

    if args.mode in ("file", "both") and args.watch_dir:
        # Run file monitoring in executor (blocking)
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(monitor.monitor_file_changes, args.watch_dir, args.interval)

    # Wait for tasks
    try:
        if tasks:
            await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped")

    # Generate final report
    if args.output:
        monitor.save_report(args.output)
    else:
        report = monitor.generate_report()
        print("\n" + "=" * 60)
        print("📊 MONITORING REPORT")
        print("=" * 60)
        print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Real-time lightweight monitoring for bypass attempts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor gateway sessions
  python scripts/install_monitoring.py \\
    --gateway-url https://gateway-host:8080 \\
    --api-key KEY \\
    --mode gateway

  # Monitor file changes in workspace
  python scripts/install_monitoring.py \\
    --watch-dir ~/rlm-kit-thin \\
    --mode file

  # Monitor both
  python scripts/install_monitoring.py \\
    --gateway-url https://gateway-host:8080 \\
    --api-key KEY \\
    --watch-dir ~/rlm-kit-thin \\
    --mode both
        """,
    )

    parser.add_argument(
        "--gateway-url",
        type=str,
        default=None,
        help="Remote gateway URL (required for gateway mode)",
    )
    parser.add_argument(
        "--api-key", type=str, default=None, help="API key for gateway (required for gateway mode)"
    )
    parser.add_argument(
        "--watch-dir",
        type=Path,
        default=None,
        help="Directory to watch for file changes (thin workspace)",
    )
    parser.add_argument(
        "--canary-token",
        type=str,
        default=None,
        help="Canary token to detect (auto-loaded from workspace if not provided)",
    )
    parser.add_argument(
        "--mode",
        choices=["gateway", "file", "both"],
        default="both",
        help="Monitoring mode (default: both)",
    )
    parser.add_argument(
        "--interval", type=int, default=30, help="Monitoring interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Output file for monitoring report"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.mode in ("gateway", "both"):
        if not args.gateway_url:
            print("❌ ERROR: --gateway-url required for gateway mode", file=sys.stderr)
            sys.exit(1)
        if not args.api_key:
            print("❌ ERROR: --api-key required for gateway mode", file=sys.stderr)
            sys.exit(1)

    if args.mode in ("file", "both"):
        if not args.watch_dir:
            print("❌ ERROR: --watch-dir required for file mode", file=sys.stderr)
            sys.exit(1)

    # Run async main
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
