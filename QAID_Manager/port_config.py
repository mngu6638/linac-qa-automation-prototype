"""
Listen-port resolution for packaged QAID Manager.

Port 8000 is commonly blocked on Windows (Hyper-V reserved ranges, WinError 10013).
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

# Avoid 8000 — frequently forbidden on Windows 10/11.
DEFAULT_PORT_CANDIDATES = (17890, 17891, 17892, 8765, 18080, 8088)


def get_exe_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(os.path.dirname(sys.executable))
    return Path(__file__).resolve().parent.parent


def is_general_build() -> bool:
    """Public research edition always uses the general (non-site-specific) build profile."""
    return True


def legacy_listen_port() -> int:
    """Legacy fallback listen port when no candidate ports are available."""
    return int(os.environ.get('QAID_PORT', '8000'))


def _read_port_file(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding='utf-8').strip()
        if raw.isdigit():
            port = int(raw)
            if 1024 <= port <= 65535:
                return port
    except OSError:
        pass
    return None


def get_configured_port() -> int | None:
    """Explicit port from environment or config/port.txt (no availability check)."""
    env_port = os.environ.get('QAID_PORT', '').strip()
    if env_port.isdigit():
        port = int(env_port)
        if 1024 <= port <= 65535:
            return port

    exe_dir = get_exe_dir()
    for candidate in (
        exe_dir / 'config' / 'port.txt',
        exe_dir / 'port.txt',
    ):
        port = _read_port_file(candidate)
        if port is not None:
            return port
    return None


def can_bind_port(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def resolve_listen_port(host: str, candidates: tuple[int, ...] | None = None) -> int:
    """
    Return the first port that can bind on host.
    Honors QAID_PORT / port.txt first, then tries fallback candidates.
    """
    configured = get_configured_port()
    ordered: list[int] = []
    if configured is not None:
        ordered.append(configured)
    for port in candidates or DEFAULT_PORT_CANDIDATES:
        if port not in ordered:
            ordered.append(port)

    for port in ordered:
        if can_bind_port(host, port):
            return port

    raise OSError(
        f'No available port on {host}. Tried: {", ".join(str(p) for p in ordered)}. '
        'Set QAID_PORT or create config\\port.txt with a free port number.'
    )
