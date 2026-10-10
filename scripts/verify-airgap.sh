#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="${SYSTEM_PYTHON_BIN:-python3}"
fi
API_URL="${API_URL:-http://127.0.0.1:8000}"
API_ONLY=0

usage() {
    cat <<'EOF'
Usage: ./scripts/verify-airgap.sh [options]

Check the stable local API contract and inspect established sockets for
non-loopback/non-private peers. The backend must already be running.

Options:
  --url URL       Backend origin (default: http://127.0.0.1:8000).
  --api-only      Skip the OS socket inspection (use only in restricted containers).
  -h, --help      Show this help.
EOF
}

die() {
    printf 'verify-airgap: %s\n' "$*" >&2
    exit 1
}

while (($#)); do
    case "$1" in
        --url)
            (($# >= 2)) || die "--url requires a value"
            API_URL="$2"
            shift
            ;;
        --api-only)
            API_ONLY=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1 (use --help for usage)"
            ;;
    esac
    shift
done

command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python is required"
"$PYTHON_BIN" - "$API_URL" "$API_ONLY" <<'PY'
from __future__ import annotations

import ipaddress
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


base_url = sys.argv[1].rstrip("/")
api_only = sys.argv[2] == "1"


def is_local_host(host: str) -> bool:
    host = host.strip("[]").split("%", 1)[0]
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if address.is_loopback or address.is_link_local:
        return True
    private_ranges = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("fc00::/7"),
    )
    return any(address in network for network in private_ranges)


parsed_url = urlparse(base_url)
if parsed_url.scheme != "http" or not parsed_url.hostname or not (
    parsed_url.hostname == "localhost" or is_local_host(parsed_url.hostname)
):
    raise SystemExit("FAIL: --url must be an HTTP origin on loopback or a private IP")


def fetch(path: str) -> dict[str, object]:
    request = urllib.request.Request(f"{base_url}{path}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError) as exc:
        raise SystemExit(f"backend API unavailable at {base_url}{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"unexpected JSON response from {path}")
    return payload


health = fetch("/api/health")
egress = fetch("/api/audit/egress")

if health.get("status") != "ok":
    raise SystemExit(f"health check failed: {health}")
if health.get("airgap") is not True or egress.get("airgap") is not True:
    raise SystemExit("FAIL: backend is not reporting AIRGAP=true")
external_allowed = egress.get("external_allowed")
if external_allowed != 0:
    raise SystemExit(f"FAIL: backend reports {external_allowed} allowed external calls")

print(f"PASS: API health is ok ({base_url}/api/health)")
print(f"PASS: AIRGAP=true; blocked attempts={egress.get('blocked', 0)}")
print(f"PASS: local endpoints={egress.get('local_endpoints', [])}")


def endpoint_host(endpoint: str) -> str | None:
    endpoint = endpoint.strip()
    if endpoint.startswith("[") and "]" in endpoint:
        return endpoint[1 : endpoint.index("]")]
    if endpoint.count(":") == 1:
        return endpoint.rsplit(":", 1)[0]
    if endpoint.count(":") > 1:
        return endpoint
    return None


def established_from_ss() -> list[str] | None:
    if shutil.which("ss") is None:
        return None
    result = subprocess.run(
        ["ss", "-H", "-tun"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return None
    peers: list[str] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 6 or fields[1].lower() not in {"estab", "established"}:
            continue
        peer = fields[5]
        host = endpoint_host(peer)
        if host is not None and not is_local_host(host):
            peers.append(peer)
    return peers


def decode_proc_endpoint(value: str, ipv6: bool) -> str | None:
    address, _port = value.split(":", 1)
    try:
        raw = bytes.fromhex(address)
        if ipv6:
            raw = b"".join(raw[index : index + 4][::-1] for index in range(0, 16, 4))
            return str(ipaddress.IPv6Address(raw))
        return str(ipaddress.IPv4Address(raw[::-1]))
    except (ValueError, ipaddress.AddressValueError):
        return None


def established_from_proc() -> list[str] | None:
    proc = Path("/proc/net")
    if not proc.is_dir():
        return None
    peers: list[str] = []
    for filename, ipv6 in (("tcp", False), ("tcp6", True), ("udp", False), ("udp6", True)):
        path = proc / filename
        if not path.exists():
            continue
        lines = path.read_text(encoding="ascii", errors="replace").splitlines()[1:]
        for line in lines:
            fields = line.split()
            if len(fields) < 4 or fields[3] != "01":
                continue
            peer = decode_proc_endpoint(fields[2], ipv6)
            if peer and not is_local_host(peer) and peer not in {"0.0.0.0", "::"}:
                peers.append(peer)
    return peers


if not api_only:
    peers = established_from_ss()
    if peers is None:
        peers = established_from_proc()
    if peers is None:
        raise SystemExit("FAIL: unable to inspect established sockets; use --api-only only in a restricted container")
    if peers:
        raise SystemExit(f"FAIL: external established socket peers: {sorted(set(peers))}")
    print("PASS: no established external socket connections")
PY
