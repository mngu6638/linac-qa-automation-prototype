from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login

from .session_hooks import RUNTIME_SESSION_KEY


class RuntimeBoundSessionMiddleware:
    """
    Bind authenticated sessions to the current packaged-app runtime.

    Browser-close detection is not reliable across browsers or restore modes.
    This middleware provides a durable server-side guarantee: when the app is
    launched again, old authenticated sessions are invalidated and users must
    log in again.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        runtime_id = getattr(settings, "QAID_RUNTIME_SESSION_ID", "").strip()
        if runtime_id and getattr(request, "user", None) and request.user.is_authenticated:
            bound_runtime = request.session.get(RUNTIME_SESSION_KEY, "")
            if bound_runtime != runtime_id:
                logout(request)
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        return self.get_response(request)
