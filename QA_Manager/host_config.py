"""
Hostname and ALLOWED_HOSTS resolution for packaged QAID Manager deployments.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


def get_exe_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(os.path.dirname(sys.executable))
    return Path(__file__).resolve().parent.parent


def read_hostname() -> str:
    """Read configured hostname from file or environment."""
    exe_dir = get_exe_dir()
    candidates = (
        exe_dir / 'hostname.txt',
        exe_dir / 'config' / 'hostname.txt',
    )
    for hostname_file in candidates:
        if not hostname_file.exists():
            continue
        try:
            hostname = hostname_file.read_text(encoding='utf-8').strip()
            if hostname:
                return hostname
        except OSError:
            continue
    return os.environ.get('QAID_HOSTNAME', '127.0.0.1').strip() or '127.0.0.1'


def _local_network_hosts() -> list[str]:
    """Collect local IPs and computer name for LAN browser access."""
    hosts: set[str] = set()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        hosts.add(sock.getsockname()[0])
        sock.close()
    except OSError:
        pass

    try:
        computer_name = socket.gethostname()
        if computer_name:
            hosts.add(computer_name.lower())
            hosts.add(computer_name)
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            hosts.add(info[4][0])
    except OSError:
        pass

    hosts.discard('')
    hosts.discard('0.0.0.0')
    return sorted(hosts)


def build_allowed_hosts(hostname: str | None = None) -> list[str]:
    """Build ALLOWED_HOSTS for production deployments."""
    hostname = (hostname or read_hostname()).strip()
    extra = [
        host.strip()
        for host in os.environ.get('QAID_ALLOWED_HOSTS', '').split(',')
        if host.strip()
    ]
    allowed = {hostname, '127.0.0.1', 'localhost', *extra}

    # Packaged app listens on 0.0.0.0; allow common local/LAN host headers.
    if getattr(sys, 'frozen', False):
        allowed.update(_local_network_hosts())
        # Pre-1.3 packaged builds (e.g. 1.2.1) used ALLOWED_HOSTS=['*'].
        # Keep that behaviour for desktop/LAN installs unless strict mode is requested.
        strict = os.environ.get('QAID_STRICT_HOSTS', '').strip().lower() in {
            '1', 'true', 'yes', 'on',
        }
        if not strict:
            allowed.add('*')

    return sorted(allowed)


def ensure_root_hostname_file() -> Path | None:
    """
    Ensure hostname.txt exists next to the executable.
    Copies from config/hostname.txt when only that file exists (post-update layout).
    """
    exe_dir = get_exe_dir()
    root_file = exe_dir / 'hostname.txt'
    config_file = exe_dir / 'config' / 'hostname.txt'

    if root_file.exists():
        return root_file

    if config_file.exists():
        try:
            content = config_file.read_text(encoding='utf-8').strip()
            if content:
                root_file.write_text(content + '\n', encoding='utf-8')
                return root_file
        except OSError:
            pass

    return None
