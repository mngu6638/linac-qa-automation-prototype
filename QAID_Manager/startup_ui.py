"""User-visible fatal errors when the packaged app cannot start (console is hidden)."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path


PORT_BIND_FAILURE_MESSAGE = (
    'QAID Manager could not start.\n\n'
    'The selected port is blocked or already in use.\n\n'
    'Please edit config\\port.txt and try another port, for example 8765.\n\n'
    'Technical details were saved to data\\error.log.'
)


def _error_log_path() -> Path | None:
    try:
        from django.conf import settings
        return Path(settings.LOGGING['handlers']['file']['filename'])
    except Exception:
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent / 'data' / 'error.log'
        return None


def log_startup_error(exc: Exception, heading: str = 'Startup error') -> None:
    log_path = _error_log_path()
    if log_path is None:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f'\n\n=== {heading} ===\n')
            f.write(f'{type(exc).__name__}: {exc}\n')
            traceback.print_exc(file=f)
    except OSError:
        pass


def show_fatal_error(message: str, title: str = 'QAID Manager') -> None:
    if not getattr(sys, 'frozen', False):
        print(f'{title}: {message}', file=sys.stderr)
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        pass


def show_port_bind_failure() -> None:
    show_fatal_error(PORT_BIND_FAILURE_MESSAGE)
