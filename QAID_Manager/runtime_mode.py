import os


def is_server_mode():
    """True when running the LAN server executable (not the desktop app)."""
    return os.environ.get('QAID_SERVER_MODE', '').lower() in ('1', 'true', 'yes')
