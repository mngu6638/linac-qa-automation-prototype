import os


def _is_server_mode():
    return os.environ.get('QAID_SERVER_MODE', '').lower() in ('1', 'true', 'yes')


def runtime_mode(request):
    server_mode = _is_server_mode()
    return {
        'qaid_server_mode': server_mode,
        'qaid_shutdown_on_browser_close': not server_mode,
    }
